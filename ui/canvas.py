import math
import os
import time
from typing import Any

from PySide6.QtCore import QPointF, QSize, Qt, Signal, QTimer, Slot, QEvent, QPoint
from PySide6.QtGui import QPainter, QImage, QColor, QTouchEvent
from PySide6.QtWidgets import QWidget, QToolButton, QGestureEvent, QScroller, QScrollerProperties
from PySide6.QtSvg import QSvgGenerator

from core.registry import find_renderer
from geo.points import SNAP_PX, AbstractPoint, nearest_point
from tools.select import SelectTool
from media.script_button import ScriptButtonObject
from ui import theme
from ui.icons import trash_icon
from ui.tool_rail import ToolRail
from ui.zoom_bar import ZoomBar
from ui.property_panel import PropertyPanel
from ui.physics_tool_bar import PhysicsToolBar
from ui.canvas_render import (
    draw_background_cached, draw_background, draw_grid, draw_axes,
    content_bbox, draw_publication, draw_publication_point, collect_screen_segments
)
from ui.canvas_menu import (
    show_context_menu, edit_function_object, doc_action, rename_objects,
    set_visible, duplicate_selected, reorder_objects, select_related,
    simple_edit_script_button, edit_text_object
)
from ui.canvas_snow import init_snow, tick_snow, draw_snow
try:
    from physics.optics.scene import sync_optics as _sync_optics_scene # type: ignore
except Exception:
    _sync_optics_scene = None
    
BASE_SCALE = 48.0

class Canvas(QWidget):
    cursor_info = Signal(str)
    tool_changed = Signal(str)
    tool_activated = Signal(object)
    zoom_changed = Signal(float)

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        doc.changed.connect(self.update)
        doc.cleared.connect(self._on_doc_cleared)

        # ── 从设置读取基础缩放（替代硬编码 BASE_SCALE）──
        self._base_scale = float(doc.settings.get("canvas.base_scale", BASE_SCALE))
        self.scale = self._base_scale

        self.origin = QPointF(0.0, 0.0)
        self._origin_ready = False
        self.tool = None
        self.cursor_wpt: tuple[float, float] = (0.0, 0.0)
        self.snap_target = None
        self._panning = False
        self._pan_anchor = QPointF()
        self._pan_velocity = QPointF(0.0, 0.0)
        self._pan_last_pos = QPointF()
        self._pan_last_time = 0.0
        self._inertia_timer = QTimer(self)
        self._inertia_timer.setInterval(16)
        self._inertia_timer.timeout.connect(self._tick_inertia)
        self._inertia_vx = 0.0
        self._inertia_vy = 0.0
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        # ── 触屏支持 ──────────────────────────────────
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        self.grabGesture(Qt.GestureType.PinchGesture)
        self.grabGesture(Qt.GestureType.PanGesture)
        self._touch_mode = False
        self._touch_points: dict = {}
        self._touch_start_pos = None
        self._touch_start_time = 0
        self._touch_moved = False
        self._pinch_active = False
        self._pan_active = False
        # 长按检测（替代右键菜单）
        self._long_press_timer = QTimer(self)
        self._long_press_timer.setSingleShot(True)
        self._long_press_timer.setInterval(
            int(doc.settings.get("interaction.long_press_ms", 500)))  # ← 改
        self._long_press_timer.timeout.connect(self._on_long_press)
        self._long_press_pos = None

        # 惯性滚动
        QScroller.grabGesture(self, QScroller.ScrollerGestureType.TouchGesture)
        scroller = QScroller.scroller(self)
        sp = scroller.scrollerProperties()
        sp.setScrollMetric(QScrollerProperties.ScrollMetric.DecelerationFactor, 0.05)
        sp.setScrollMetric(QScrollerProperties.ScrollMetric.MaximumVelocity, 1.5)
        sp.setScrollMetric(QScrollerProperties.ScrollMetric.MousePressEventDelay, 0.2)
        scroller.setScrollerProperties(sp)
        # ── 触屏支持结束 ──────────────────────────────
        self.rail = ToolRail(self)
        self.rail.tool_chosen.connect(self.set_tool)
        self.tool_activated.connect(self.rail.sync)
        self.physics_bar = PhysicsToolBar(self)
        self.physics_bar.tool_chosen.connect(self.set_tool)
        self.tool_activated.connect(self.physics_bar.sync)
        self.zoom_bar = ZoomBar(self, self)
        self._trash = QToolButton(self)
        self._trash.setObjectName("trashBtn")
        self._trash.setIcon(trash_icon())
        self._trash.setIconSize(QSize(15, 15))
        self._trash.setFixedSize(28, 28)
        self._trash.setToolTip("删除选中对象（级联删除依赖它的对象）")
        self._trash.setCursor(Qt.CursorShape.PointingHandCursor)
        self._trash.clicked.connect(self.doc.remove_selected)
        self._trash.hide()
        self.info_panel = PropertyPanel(self, self)
        self._bg_cache = None
        self._bg_cache_key = None
        self._render_list = []
        self._render_list_version = -1
        self._snow_active = False
        self._snowflakes = []
        self._snow_timer = QTimer(self)
        self._snow_timer.setInterval(33)
        self._snow_timer.timeout.connect(self._tick_snow)
        self.refresh_theme()
        self.update_snow_state()
        self.refresh_physics_bar()
        from geo.function_sampler import get_sampler
        self._sampler = get_sampler()
        self._sampler.sampled.connect(self._on_function_sampled)
        from geo.implicit_sampler import get_implicit_sampler
        self._implicit_sampler = get_implicit_sampler()
        self._implicit_sampler.sampled.connect(self._on_implicit_sampled)
        self._egg_data = None 

    def _on_implicit_sampled(self, curve_id, segments):
        from geo.implicit_curve import ImplicitCurve
        from core.variables import get_store
        store = get_store()
        for obj in self.doc.objects:
            if isinstance(obj, ImplicitCurve) and obj.id == curve_id:
                domain = obj.get_domain(self)
                obj.update_cache(segments, store.version, domain)
                self.update()
                break
            
    def _on_doc_cleared(self):
        """文档清空时，重置画布侧所有缓存与交互状态。"""
        # 强制渲染列表失效
        self._render_list.clear()
        self._render_list_version = -1

        # 清除磁吸目标（可能指向已销毁的旧对象）
        self.snap_target = None

        # 如果当前工具持有临时状态，取消之
        if self.tool is not None:
            try:
                self.tool.cancel(self)
            except Exception:
                pass

        # 停止动画轨迹绘制
        ctrl = getattr(self, "_anim_controller", None)
        if ctrl is not None:
            ctrl.stop()
            ctrl.clear_trails()
            ctrl.clip = None
            ctrl._bound_version = -1

        # 隐藏垃圾桶按钮
        self._trash.hide()

        # 重置背景缓存
        self._bg_cache = None

        self.update()
        
    def _on_function_sampled(self, curve_id, points):
        from geo.function_curve import FunctionCurve
        from core.variables import get_store
        store = get_store()
        for obj in self.doc.objects:
            if isinstance(obj, FunctionCurve) and obj.id == curve_id:
                domain = obj.get_domain(self)
                obj.update_cache(points, store.version, domain)
                self.update()
                break

    def to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(self.origin.x() + x * self.scale, self.origin.y() - y * self.scale)

    def to_world(self, pt: QPointF) -> tuple[float, float]:
        return ((pt.x() - self.origin.x()) / self.scale, (self.origin.y() - pt.y()) / self.scale)

    def set_tool(self, tool) -> None:
        if isinstance(tool, type):
            tool = tool()
        if self.tool is not None:
            self.tool.deactivated(self)
        self.tool = tool
        tool.activated(self)
        self.tool_changed.emit(tool.hint)
        self.tool_activated.emit(tool)
        self.update()

    def zoom_at(self, factor: float, anchor: QPointF | None = None) -> None:
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        new_scale = min(max(self.scale * factor, 4.0), 4000.0)
        wx, wy = self.to_world(anchor)
        self.scale = new_scale
        self.origin = QPointF(anchor.x() - wx * self.scale, anchor.y() + wy * self.scale)
        self._emit_zoom()
        self.update()

    def zoom_step(self, n: int) -> None:
        self.zoom_at(1.25 ** n)

    def reset_view(self) -> None:
        self._base_scale = float(
            self.doc.settings.get("canvas.base_scale", BASE_SCALE))
        self.scale = self._base_scale
        self.origin = QPointF(self.width() / 2, self.height() / 2)
        self._emit_zoom()
        self.update()

    def _emit_zoom(self) -> None:
        self.zoom_changed.emit(self.scale / self._base_scale * 100.0)
        
    def event(self, ev) -> bool:
        """分发手势事件（Pinch / Pan），其余走默认流程。"""
        if ev.type() == QEvent.Type.Gesture:
            return self._handle_gesture(ev)
        return super().event(ev)

    def _handle_gesture(self, ev: QGestureEvent) -> bool:
        pinch = ev.gesture(Qt.GestureType.PinchGesture)
        pan = ev.gesture(Qt.GestureType.PanGesture)

        if pinch is not None:
            self._handle_pinch(pinch)
            return True
        if pan is not None:
            self._handle_pan(pan)
            return True
        return False

    def _handle_pinch(self, pinch) -> None:
        """双指捏合 → 以两指中心为锚点缩放。"""
        state = pinch.state()
        if state == Qt.GestureState.GestureStarted:
            self._pinch_active = True
            self._long_press_timer.stop()
        elif state == Qt.GestureState.GestureUpdated and self._pinch_active:
            factor = pinch.scaleFactor()
            center = pinch.centerPoint().toPoint()
            anchor = QPointF(float(center.x()), float(center.y()))
            if abs(factor - 1.0) > 0.001:
                self.zoom_at(factor, anchor)
        elif state in (Qt.GestureState.GestureFinished,
                       Qt.GestureState.GestureCanceled):
            self._pinch_active = False

    def _handle_pan(self, pan) -> None:
        state = pan.state()
        if state == Qt.GestureState.GestureStarted:
            self._pan_active = True
            self._long_press_timer.stop()
            self._stop_inertia()
        elif state == Qt.GestureState.GestureUpdated and self._pan_active:
            delta = pan.delta()
            self.origin += QPointF(float(delta.x()), float(delta.y()))
            self._pan_velocity = QPointF(
                float(delta.x()) * 60.0, float(delta.y()) * 60.0)
            self.update()
        elif state in (Qt.GestureState.GestureFinished,
                       Qt.GestureState.GestureCanceled):
            self._pan_active = False
            self._start_inertia()
            
    def touchEvent(self, ev: QTouchEvent) -> None:
        """处理原始触摸事件：单指点击/拖动/长按。"""
        points = ev.points()
        touch_count = len(points)

        if ev.type() == QEvent.Type.TouchBegin:
            self._touch_mode = True
            self._touch_points = {p.id(): p.position() for p in points}

            if touch_count == 1:
                pos = points[0].position()
                self._touch_start_pos = pos
                self._touch_start_time = ev.timestamp()
                self._touch_moved = False
                self._long_press_pos = pos
                self._long_press_timer.start()
            ev.accept()

        elif ev.type() == QEvent.Type.TouchUpdate:
            self._touch_points = {p.id(): p.position() for p in points}

            if touch_count == 1 and self._touch_start_pos is not None:
                pos = points[0].position()
                dx = pos.x() - self._touch_start_pos.x()
                dy = pos.y() - self._touch_start_pos.y()
                dist = (dx * dx + dy * dy) ** 0.5

                # 超过 12px 视为移动，取消长按
                if dist > 12.0 and not self._touch_moved:
                    self._touch_moved = True
                    self._long_press_timer.stop()
                    # 模拟鼠标按下，启动工具交互
                    wpt = self.to_world(pos)
                    hit = self.pick(pos, tol_px=self._touch_tol())
                    self.doc._arm_undo()
                    if self.tool is not None:
                        self.tool.press(self, wpt, hit)
                elif self._touch_moved and self.tool is not None:
                    wpt = self.to_world(pos)
                    hit = self.pick(pos, tol_px=self._touch_tol())
                    self.tool.move(self, wpt, hit)
                    self.cursor_wpt = wpt
                    self.update()
            ev.accept()

        elif ev.type() in (QEvent.Type.TouchEnd, QEvent.Type.TouchCancel):
            self._long_press_timer.stop()

            if touch_count <= 1 and self._touch_start_pos is not None:
                if not self._touch_moved:
                    # 未移动 → 视为点击
                    pos = self._touch_start_pos
                    elapsed = ev.timestamp() - self._touch_start_time
                    if elapsed < 400:  # 短按 → 点击
                        wpt = self.to_world(pos)
                        hit = self.pick(pos, tol_px=self._touch_tol())
                        self.doc._arm_undo()
                        if self.tool is not None:
                            self.tool.press(self, wpt, hit)
                            self.tool.release(self, wpt, hit)
                        self.doc._commit_undo_if_changed()
                else:
                    # 已移动 → 释放拖拽
                    pos = points[0].position() if points else self._touch_start_pos
                    wpt = self.to_world(pos)
                    hit = self.pick(pos, tol_px=self._touch_tol())
                    if self.tool is not None:
                        self.tool.release(self, wpt, hit)
                    self.doc._commit_undo_if_changed()

            self._touch_start_pos = None
            self._touch_moved = False
            self._touch_points.clear()
            if touch_count <= 1:
                self._touch_mode = False
            ev.accept()
            
    def _touch_tol(self) -> float:
        """触屏模式下增大命中容差。"""
        if self._touch_mode:
            return float(self.doc.settings.get("interaction.touch_hit_tol", 26.0))
        return float(self.doc.settings.get("interaction.mouse_hit_tol", 9.0))

    def _on_long_press(self) -> None:
        """长按 500ms → 触发右键上下文菜单。"""
        if self._long_press_pos is None:
            return
        pos = self._long_press_pos
        self._long_press_pos = None
        # 构造一个等效的右键菜单事件位置
        from PySide6.QtGui import QContextMenuEvent
        ev_pos = pos.toPoint() if hasattr(pos, 'toPoint') else QPoint(int(pos.x()), int(pos.y()))
        # 直接调用画布右键菜单逻辑
        from PySide6.QtCore import QEvent as _QE
        from PySide6.QtGui import QContextMenuEvent as _CME
        ctx_ev = _CME(_CME.Reason.Mouse, ev_pos, self.mapToGlobal(ev_pos))
        self.contextMenuEvent(ctx_ev)
                               
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.save()
            try:
                self.render_scene(p)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                p.restore()

            if getattr(self, "_snow_active", False):
                p.save()
                try:
                    draw_snow(self, p)
                except Exception:
                    pass
                finally:
                    p.restore()

            p.save()
            try:
                self._draw_snap_indicator(p)
            except Exception:
                pass
            finally:
                p.restore()

            if self.tool is not None:
                p.save()
                try:
                    self.tool.draw_overlay(p, self)
                except Exception:
                    import traceback
                    traceback.print_exc()
                finally:
                    p.restore()

            # 约束参考线覆盖层
            if hasattr(self.doc, 'constraints') and self.doc.constraints:
                p.save()
                try:
                    p.setRenderHint(QPainter.RenderHint.Antialiasing)
                    pen = theme.dashed_pen(theme.MEASURE, 1.5)
                    p.setPen(pen)
                    p.setBrush(theme.brush(theme.MEASURE))
                    for c in self.doc.constraints:
                        if not getattr(c, 'enabled', True):
                            continue
                        pts = c.involved_points()
                        if not pts:
                            continue
                        screen_pts = []
                        for pt in pts:
                            if hasattr(pt, 'x') and hasattr(pt, 'y'):
                                screen_pts.append(self.to_screen(pt.x, pt.y))
                            elif hasattr(pt, 'a') and hasattr(pt, 'b'):
                                mx = (pt.a.x + pt.b.x) / 2
                                my = (pt.a.y + pt.b.y) / 2
                                screen_pts.append(self.to_screen(mx, my))
                        if len(screen_pts) >= 2:
                            if len(screen_pts) == 3 and c.type_name == "angle":
                                p.drawLine(screen_pts[0], screen_pts[1])
                                p.drawLine(screen_pts[1], screen_pts[2])
                            else:
                                for i in range(len(screen_pts) - 1):
                                    p.drawLine(screen_pts[i], screen_pts[i + 1])
                        r = 3.0
                        for sp in screen_pts:
                            p.drawEllipse(sp, r, r)
                except Exception:
                    pass
                finally:
                    p.restore()
        finally:
            p.end()
        self._place_trash()

    def _get_render_list(self):
        ver = self.doc._mutation_count
        if self._render_list_version != ver:
            self._render_list = []
            for obj in self.doc.objects:
                if obj.visible and obj.exists:
                    renderer = find_renderer(obj)
                    if renderer is not None:
                        self._render_list.append((obj, renderer))
            self._render_list_version = ver
        return self._render_list

    def _in_viewport(self, obj) -> bool:
        margin = 60.0
        w, h = self.width(), self.height()
        if hasattr(obj, 'x') and hasattr(obj, 'y') and not hasattr(obj, 'width'):
            sx = self.origin.x() + obj.x * self.scale
            sy = self.origin.y() - obj.y * self.scale
            return -margin <= sx <= w + margin and -margin <= sy <= h + margin
        if hasattr(obj, 'width') and hasattr(obj, 'height') and hasattr(obj, 'x'):
            x0 = self.origin.x() + obj.x * self.scale
            y0 = self.origin.y() - obj.y * self.scale
            x1 = x0 + obj.width * self.scale
            y1 = y0 + obj.height * self.scale
            return not (x1 < -margin or x0 > w + margin or y1 < -margin or y0 > h + margin)
        return True
    
    @Slot()
    def _process_egg_data(self):
        """主线程中处理下载好的图片数据（由 invokeMethod 调用）"""
        data = getattr(self, "_egg_data", None)
        if data is None:
            return
        from ui.canvas_render import _build_pixmap
        _build_pixmap(self, data)
        self._egg_data = None
        
    def render_scene(self, p: QPainter, bg_mode: str = "grid", publication: bool = False) -> None:
        self._sync_optics_scene()
        if publication:
            p.fillRect(self.rect(), QColor("#ffffff"))
        elif bg_mode == "grid":
            draw_background_cached(self, p)
        elif bg_mode == "axes":
            draw_background(self, p)
            draw_axes(self, p)
        else:
            draw_background(self, p)
            
        from ui.canvas_render import draw_egg_if_active
        draw_egg_if_active(p, self)
                
        render_list = self._get_render_list()
        if publication:
            for obj, renderer in render_list:
                if not isinstance(obj, AbstractPoint) and self._in_viewport(obj):
                    draw_publication(p, obj, self)
            screen_segments = collect_screen_segments(self)
            for obj, renderer in render_list:
                if isinstance(obj, AbstractPoint) and self._in_viewport(obj):
                    draw_publication_point(p, obj, self, screen_segments)
        else:
            for obj, renderer in render_list:
                if self._in_viewport(obj):
                    renderer(p, obj, self)


    def _apply_fit(self, bbox) -> None:
        x0, y0, x1, y1 = bbox
        cw, ch = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
        margin = 70.0
        avail_w = max(self.width() - 2 * margin, 1.0)
        avail_h = max(self.height() - 2 * margin, 1.0)
        self.scale = min(avail_w / cw, avail_h / ch)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.origin = QPointF(self.width() / 2 - cx * self.scale, self.height() / 2 + cy * self.scale)

    def render_to_image(self, fit=False, bg_mode="grid", scale=2.0, publication=False):
        saved = (self.scale, self.origin)
        try:
            if fit:
                bbox = content_bbox(self.doc)
                if bbox: self._apply_fit(bbox)
            img = QImage(int(self.width() * scale), int(self.height() * scale), QImage.Format.Format_ARGB32)
            p = QPainter()
            p.begin(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.scale(scale, scale)
            self.render_scene(p, bg_mode, publication=publication)
            p.end()
            return img
        finally:
            self.scale, self.origin = saved

    def export_image(self, path, fit=False, bg_mode="grid", png_scale=2.0, publication=False):
        if os.path.splitext(path)[1].lower() == ".svg":
            self._export_svg(path, fit, bg_mode, publication=publication)
        else:
            self.render_to_image(fit, bg_mode, png_scale, publication=publication).save(path)

    def _export_svg(self, path, fit=False, bg_mode="grid", publication=False):
        from PySide6.QtCore import QRectF
        saved = (self.scale, self.origin)
        try:
            if fit:
                bbox = content_bbox(self.doc)
                if bbox: self._apply_fit(bbox)
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(self.size())
            gen.setViewBox(QRectF(0, 0, self.width(), self.height()))
            gen.setTitle("GeoSketch 导出")
            p = QPainter()
            p.begin(gen)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.render_scene(p, bg_mode, publication=publication)
            p.end()
        finally:
            self.scale, self.origin = saved

    def _draw_snap_indicator(self, p: QPainter) -> None:
        if self.snap_target is None:
            return
        qpt = self.to_screen(self.snap_target.x, self.snap_target.y)
        p.setPen(theme.pen(theme.ACCENT, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(qpt, 9.0, 9.0)
        r = float(self.doc.settings.get("interaction.snap_radius_px", SNAP_PX))
        tick = 5.0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x0, y0 = qpt.x() + dx * r, qpt.y() + dy * r
            p.drawLine(QPointF(x0, y0), QPointF(x0 - dx * tick, y0 - dy * tick))

    def pick(self, screen_pt: QPointF, tol_px: float = None): # pyright: ignore[reportArgumentType]
        self._sync_optics_scene()
        if tol_px is None:
            tol_px = self._touch_tol()
        wx, wy = self.to_world(screen_pt)
        tol = tol_px / self.scale
        best, best_d = None, tol
        for obj in reversed(self.doc.objects):
            if not (obj.visible and obj.exists):
                continue
            d = obj.distance_to(wx, wy)
            if d is not None and d < best_d:
                best, best_d = obj, d
        return best

    def showEvent(self, ev) -> None:
        if not self._origin_ready:
            self.origin = QPointF(self.width() / 2.0, self.height() / 2.0)
            self._origin_ready = True

    def resizeEvent(self, ev) -> None:
        # ★ 触屏模式：增大边距，避免误触
        margin = 20 if self._touch_mode else 14
        self.rail.move(margin, margin)
        pb = self.physics_bar
        pb.move(margin, self.height() - pb.height() - margin)
        zb = self.zoom_bar
        zb.move(self.width() - zb.width() - margin,
                self.height() - zb.height() - margin)
        self.info_panel.reposition()
        self._bg_cache = None
        if self._snow_active and not self._snowflakes:
            init_snow(self)
            
    def _sync_optics_scene(self) -> None:
        """在渲染 / 拾取前同步光学场景。

        该同步不会增删对象，也不会发射 doc.changed，
        只更新光线内部追迹缓存。
        """
        if _sync_optics_scene is None:
            return
        try:
            _sync_optics_scene(self.doc)
        except Exception:
            import traceback
            traceback.print_exc()
            
    def mousePressEvent(self, ev) -> None:
        # 停止可能正在进行的惯性动画
        self._stop_inertia()

        if ev.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_anchor = ev.position() - self.origin
            self._pan_last_pos = ev.position()
            self._pan_last_time = time.perf_counter()
            self._pan_velocity = QPointF(0.0, 0.0)
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if ev.button() == Qt.MouseButton.LeftButton:
            hit = self.pick(ev.position())

            # 选择工具 + 空白区域 → 左键平移
            if isinstance(self.tool, SelectTool) and hit is None:
                self._panning = True
                self._pan_anchor = ev.position() - self.origin
                self._pan_last_pos = ev.position()
                self._pan_last_time = time.perf_counter()
                self._pan_velocity = QPointF(0.0, 0.0)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return

            # 正常工具交互
            if self.tool is not None:
                self.doc._arm_undo()
                self.tool.press(self, self.to_world(ev.position()), hit)
                self.doc._commit_undo_if_changed()

    def mouseDoubleClickEvent(self, ev):
        hit = self.pick(ev.position())
        if isinstance(hit, ScriptButtonObject):
            hit.edit(self)
            return
        super().mouseDoubleClickEvent(ev)

    def mouseMoveEvent(self, ev) -> None:
        self.cursor_wpt = self.to_world(ev.position())
        self.cursor_info.emit(
            f"( {self.cursor_wpt[0]:7.2f} , {self.cursor_wpt[1]:7.2f} )")
        if self._panning:
            self.origin = ev.position() - self._pan_anchor
            now = time.perf_counter()
            dt = now - self._pan_last_time
            if dt > 1e-4:
                dx = ev.position().x() - self._pan_last_pos.x()
                dy = ev.position().y() - self._pan_last_pos.y()
                inst_vx = dx / dt
                inst_vy = dy / dt
                alpha = 0.25
                self._pan_velocity.setX(
                    alpha * inst_vx + (1 - alpha) * self._pan_velocity.x())
                self._pan_velocity.setY(
                    alpha * inst_vy + (1 - alpha) * self._pan_velocity.y())
                self._pan_last_pos = ev.position()
                self._pan_last_time = now
            self.update()
            return
        hit = self.pick(ev.position())
        # ── 磁吸：从设置读取半径，传入 nearest_point ──
        snap_px = float(self.doc.settings.get("interaction.snap_radius_px", SNAP_PX))
        if self.doc.settings.get("interaction.snap_enabled", True):
            self.snap_target = nearest_point(
                self.doc, self.scale, self.cursor_wpt, snap_px=snap_px)
        else:
            self.snap_target = None
        if self.tool is not None:
            self.tool.move(self, self.cursor_wpt, hit)
        hover = getattr(hit, "draggable", False) or self.snap_target is not None
        self.setCursor(
            Qt.CursorShape.SizeAllCursor if hover
            else Qt.CursorShape.ArrowCursor)
        self.update()

    def contextMenuEvent(self, ev):
        if not show_context_menu(self, ev):
            super().contextMenuEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._start_inertia()
            return

        if ev.button() == Qt.MouseButton.LeftButton and self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self._start_inertia()
            return

        if ev.button() == Qt.MouseButton.LeftButton and self.tool is not None:
            self.tool.release(
                self, self.to_world(ev.position()), self.pick(ev.position()))
            
    # ──────────────────────────────────────────────────────
    #  惯性平移动画
    # ──────────────────────────────────────────────────────

    def _start_inertia(self) -> None:
        """释放后根据末速度启动惯性滑动。"""
        # ── 设置中关闭惯性则直接返回 ──
        if not self.doc.settings.get("effects.canvas_inertia", True):
            return
        vx = self._pan_velocity.x()
        vy = self._pan_velocity.y()
        speed = (vx * vx + vy * vy) ** 0.5
        if speed < 80.0:
            return
        max_speed = 1800.0
        if speed > max_speed:
            scale = max_speed / speed
            vx *= scale
            vy *= scale
        dt = 1.0 / 60.0
        self._inertia_vx = vx * dt
        self._inertia_vy = vy * dt
        self._inertia_timer.start()

    def _tick_inertia(self) -> None:
        """每帧衰减速度并平移画布。"""
        friction = float(self.doc.settings.get("effects.canvas_friction", 0.825))
        self._inertia_vx *= friction
        self._inertia_vy *= friction
        if (abs(self._inertia_vx) < 0.15
                and abs(self._inertia_vy) < 0.15):
            self._inertia_timer.stop()
            return
        self.origin += QPointF(self._inertia_vx, self._inertia_vy)
        self.update()

    def _stop_inertia(self) -> None:
        """立即停止惯性动画（新的交互开始时调用）。"""
        if self._inertia_timer.isActive():
            self._inertia_timer.stop()
        self._inertia_vx = 0.0
        self._inertia_vy = 0.0
        
    def wheelEvent(self, ev) -> None:
        self._stop_inertia()
        k = float(self.doc.settings.get("interaction.zoom_speed", 1.15))
        if ev.angleDelta().y() <= 0:
            k = 1.0 / k
        self.zoom_at(k, ev.position())
        
    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.doc.remove_selected()
        elif ev.key() == Qt.Key.Key_Escape:
            # ★ 触屏优化：Escape 同时取消轨迹拾取
            ctrl = getattr(self, "_anim_controller", None)
            if ctrl is not None and ctrl.is_trail_picking:
                ctrl.cancel_trail_picking()
                self.cursor_info.emit("已取消轨迹拾取")
                return
            if self.tool is not None:
                self.tool.cancel(self)
        else:
            super().keyPressEvent(ev)

    def _place_trash(self) -> None:
        sel = [o for o in self.doc.objects if o.selected]
        if (len(sel) == 1 and isinstance(sel[0], AbstractPoint)
                and isinstance(self.tool, SelectTool)):
            qpt = self.to_screen(sel[0].x, sel[0].y)
            # ★ 触屏模式：增大按钮尺寸和偏移
            if self._touch_mode:
                self._trash.setFixedSize(40, 40)
                self._trash.setIconSize(QSize(22, 22))
                offset_x, offset_y = 16, -50
            else:
                self._trash.setFixedSize(28, 28)
                self._trash.setIconSize(QSize(15, 15))
                offset_x, offset_y = 12, -36
            self._trash.move(int(qpt.x()) + offset_x, int(qpt.y()) + offset_y)
            self._trash.show()
            self._trash.raise_()
        else:
            self._trash.hide()

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.canvas_qss())
        self._trash.setIcon(trash_icon())
        self.zoom_bar.refresh_icons()
        self.rail.refresh_icons()
        self.physics_bar.refresh_icons()
        self._bg_cache = None
        self.update()
        
    def refresh_physics_bar(self) -> None:
        self.physics_bar.refresh_from_settings(self.doc.settings)
        
    def update_snow_state(self):
        title = (self.doc.meta.get("title") or "").strip().lower()
        active = (title == "snow")
        if active and not self._snow_active:
            init_snow(self)
            self._snow_timer.start()
        elif not active and self._snow_active:
            self._snow_timer.stop()
            self._snowflakes.clear()
        self._snow_active = active
        self.update()

    def _tick_snow(self):
        tick_snow(self)