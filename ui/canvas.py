import math
import os
import random

from PySide6.QtCore import QPointF, QSize, Qt, Signal, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QToolButton
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath, QImage

from core.registry import find_renderer
from geo.points import SNAP_PX, AbstractPoint, nearest_point
from geo.function_curve import FunctionCurve
from core.variables import get_store
from tools.select import SelectTool
from ui import theme
from ui.icons import trash_icon
from ui.tool_rail import ToolRail
from ui.zoom_bar import ZoomBar
from ui.property_panel import PropertyPanel


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
        self.scale = BASE_SCALE
        self.origin = QPointF(0.0, 0.0)
        self._origin_ready = False
        self.tool = None
        self.cursor_wpt: tuple[float, float] = (0.0, 0.0)
        self.snap_target = None
        self._panning = False
        self._pan_anchor = QPointF()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 悬浮件：左侧工具栏 + 右下缩放控件
        self.rail = ToolRail(self)
        self.rail.tool_chosen.connect(self.set_tool)
        self.tool_activated.connect(self.rail.sync)
        self.zoom_bar = ZoomBar(self, self)

        # 悬浮删除按钮
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
        # ★ 性能优化：背景缓存 + 渲染列表缓存
        self._bg_cache = None
        self._bg_cache_key = None
        self._render_list = []
        self._render_list_version = -1
        
        # ================= 雪花彩蛋 =================
        self._snow_active = False
        self._snowflakes = []
        self._snow_timer = QTimer(self)
        self._snow_timer.setInterval(33)
        self._snow_timer.timeout.connect(self._tick_snow)

        self.refresh_theme()
        self.update_snow_state()

        from geo.function_sampler import get_sampler
        self._sampler = get_sampler()
        self._sampler.sampled.connect(self._on_function_sampled)

    def _on_function_sampled(self, curve_id, points):
        """子线程采样完成 → 更新对应曲线的缓存 → 触发重绘。"""
        from geo.function_curve import FunctionCurve
        store = get_store()
        for obj in self.doc.objects:
            if isinstance(obj, FunctionCurve) and obj.id == curve_id:
                domain = obj.get_domain(self)
                obj.update_cache(points, store.version, domain)
                self.update()
                break

    # ================= 坐标变换 =================
    def to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(self.origin.x() + x * self.scale,
                       self.origin.y() - y * self.scale)

    def to_world(self, pt: QPointF) -> tuple[float, float]:
        return ((pt.x() - self.origin.x()) / self.scale,
                (self.origin.y() - pt.y()) / self.scale)

    # ================= 工具 =================
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

    # ================= 缩放 =================
    def zoom_at(self, factor: float, anchor: QPointF | None = None) -> None:
        if anchor is None:
            anchor = QPointF(self.width() / 2, self.height() / 2)
        new_scale = min(max(self.scale * factor, 4.0), 4000.0)
        wx, wy = self.to_world(anchor)
        self.scale = new_scale
        self.origin = QPointF(anchor.x() - wx * self.scale,
                              anchor.y() + wy * self.scale)
        self._emit_zoom()
        self.update()

    def zoom_step(self, n: int) -> None:
        self.zoom_at(1.25 ** n)

    def reset_view(self) -> None:
        self.scale = BASE_SCALE
        self.origin = QPointF(self.width() / 2, self.height() / 2)
        self._emit_zoom()
        self.update()

    def _emit_zoom(self) -> None:
        self.zoom_changed.emit(self.scale / BASE_SCALE * 100.0)

    # ================= 绘制 =================
    def paintEvent(self, ev) -> None:
        p = QPainter(self)
        try:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            # 1. 几何场景（保存状态，防止某个对象污染画笔）
            p.save()
            try:
                self.render_scene(p)
            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                p.restore()

            # —— 以下仅屏幕显示，不导出 ——

            # 2. snow 彩蛋：标题为 snow 时飘雪花
            if getattr(self, "_snow_active", False):
                p.save()
                try:
                    self._draw_snow(p)
                except Exception:
                    pass
                finally:
                    p.restore()

            # 3. 磁吸指示器
            p.save()
            try:
                self._draw_snap_indicator(p)
            except Exception:
                pass
            finally:
                p.restore()

            # 4. ★ 工具覆盖层（画圆预览、框选框、红色参考线等）
            if self.tool is not None:
                p.save()
                try:
                    self.tool.draw_overlay(p, self)
                except Exception:
                    import traceback
                    traceback.print_exc()
                finally:
                    p.restore()

        finally:
            p.end()

        self._place_trash()
    # ================= 性能优化：背景缓存 =================

    def _draw_background_cached(self, p: QPainter) -> None:
        """背景 + 网格 + 坐标轴缓存渲染。视图/主题不变时直接 blit。"""
        key = (self.width(), self.height(),
               round(self.origin.x(), 2), round(self.origin.y(), 2),
               round(self.scale, 2), theme.active_name())
        if self._bg_cache is not None and self._bg_cache_key == key:
            p.drawPixmap(0, 0, self._bg_cache)
            return
        # 重建缓存
        from PySide6.QtGui import QPixmap
        self._bg_cache = QPixmap(self.width(), self.height())
        self._bg_cache.setDevicePixelRatio(self.devicePixelRatioF())
        self._bg_cache.fill(Qt.GlobalColor.transparent)
        bg_p = QPainter(self._bg_cache)
        bg_p.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._draw_background(bg_p)
        self._draw_grid(bg_p)
        self._draw_axes(bg_p)
        bg_p.end()
        self._bg_cache_key = key
        p.drawPixmap(0, 0, self._bg_cache)

    # ================= 性能优化：渲染列表缓存 =================

    def _get_render_list(self):
        """返回 [(obj, renderer), ...] 缓存列表。对象增删/显隐变化时重建。"""
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

    # ================= 性能优化：视口裁剪 =================

    def _in_viewport(self, obj) -> bool:
        """快速判断对象是否在视口内（粗略检测，宁多画不漏画）。"""
        margin = 60.0  # 像素边距
        w, h = self.width(), self.height()
        # 点类对象：直接坐标判断
        if hasattr(obj, 'x') and hasattr(obj, 'y') and not hasattr(obj, 'width'):
            sx = self.origin.x() + obj.x * self.scale
            sy = self.origin.y() - obj.y * self.scale
            return -margin <= sx <= w + margin and -margin <= sy <= h + margin
        # 媒体对象：矩形判断
        if hasattr(obj, 'width') and hasattr(obj, 'height') and hasattr(obj, 'x'):
            x0 = self.origin.x() + obj.x * self.scale
            y0 = self.origin.y() - obj.y * self.scale
            x1 = x0 + obj.width * self.scale
            y1 = y0 + obj.height * self.scale
            return not (x1 < -margin or x0 > w + margin or
                        y1 < -margin or y0 > h + margin)
        # 线段/圆/曲线等：第一版不裁剪，默认可见
        return True
    
    def render_scene(self, p: QPainter, bg_mode: str = "grid") -> None:
        """渲染几何场景（背景 + 可选网格/坐标轴 + 全部对象）。
        bg_mode: "grid"=网格+坐标轴, "axes"=仅坐标轴, "none"=都不画。"""

        # ★ 优化：背景/网格/坐标轴使用缓存
        if bg_mode == "grid":
            self._draw_background_cached(p)
        elif bg_mode == "axes":
            self._draw_background(p)
            self._draw_axes(p)
        else:
            self._draw_background(p)

        # ★ 优化：使用渲染列表缓存 + 视口裁剪
        for obj, renderer in self._get_render_list():
            if self._in_viewport(obj):
                renderer(p, obj, self)

        # ================= 图像导出 =================
        # ================= 图像导出 =================
    def _apply_fit(self, bbox) -> None:
        """把包围盒适配到画布尺寸并居中（四周留白 70px）。"""
        x0, y0, x1, y1 = bbox
        cw, ch = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
        margin = 70.0
        avail_w = max(self.width() - 2 * margin, 1.0)
        avail_h = max(self.height() - 2 * margin, 1.0)
        self.scale = min(avail_w / cw, avail_h / ch)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        self.origin = QPointF(self.width() / 2 - cx * self.scale,
                              self.height() / 2 + cy * self.scale)

    def render_to_image(self, fit=False, bg_mode="grid", scale=2.0):
        """渲染为 QImage（PNG 导出与向导预览共用）。fit=True 时先适配内容并居中。
        临时改写 scale/origin，结束后恢复，不影响当前视图。"""
        saved = (self.scale, self.origin)
        try:
            if fit:
                bbox = content_bbox(self.doc)
                if bbox:
                    self._apply_fit(bbox)
            img = QImage(int(self.width() * scale), int(self.height() * scale),
                         QImage.Format.Format_ARGB32)
            p = QPainter()
            p.begin(img)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            p.scale(scale, scale)
            self.render_scene(p, bg_mode)
            p.end()
            return img
        finally:
            self.scale, self.origin = saved

    def export_image(self, path, fit=False, bg_mode="grid", png_scale=2.0):
        """按扩展名导出：.svg → 矢量；其余 → PNG 位图。"""
        if os.path.splitext(path)[1].lower() == ".svg":
            self._export_svg(path, fit, bg_mode)
        else:
            self.render_to_image(fit, bg_mode, png_scale).save(path)

    def _export_svg(self, path, fit=False, bg_mode="grid"):
        from PySide6.QtCore import QRectF
        from PySide6.QtSvg import QSvgGenerator
        saved = (self.scale, self.origin)
        try:
            if fit:
                bbox = content_bbox(self.doc)
                if bbox:
                    self._apply_fit(bbox)
            gen = QSvgGenerator()
            gen.setFileName(path)
            gen.setSize(self.size())
            gen.setViewBox(QRectF(0, 0, self.width(), self.height()))
            gen.setTitle("GeoSketch 导出")
            p = QPainter()
            p.begin(gen)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.render_scene(p, bg_mode)
            p.end()
        finally:
            self.scale, self.origin = saved
    def _draw_background(self, p: QPainter) -> None:
        g = QLinearGradient(0.0, 0.0, 0.0, float(self.height()))
        g.setColorAt(0.0, theme.BG_TOP)
        g.setColorAt(1.0, theme.BG_BOTTOM)
        p.fillRect(self.rect(), g)

    def _draw_grid(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        step = self._nice_step(64.0 / self.scale)
        major = step * 5.0
        x0, y0 = self.to_world(QPointF(0.0, float(h)))
        x1, y1 = self.to_world(QPointF(float(w), 0.0))
        eps = step * 1e-6

        for s, color in ((step, theme.GRID_MINOR), (major, theme.GRID_MAJOR)):
            p.setPen(theme.pen(color, 1.0))
            gx = math.ceil(x0 / s) * s
            while gx <= x1:
                if abs(gx) > eps:
                    sx = self.to_screen(gx, 0.0).x()
                    p.drawLine(QPointF(sx, 0.0), QPointF(sx, float(h)))
                gx += s
            gy = math.ceil(y0 / s) * s
            while gy <= y1:
                if abs(gy) > eps:
                    sy = self.to_screen(0.0, gy).y()
                    p.drawLine(QPointF(0.0, sy), QPointF(float(w), sy))
                gy += s

        ox, oy = self.origin.x(), self.origin.y()
        p.setPen(theme.pen(theme.LABEL, 1.0))
        p.setFont(theme.LABEL_FONT)
        gx = math.ceil(x0 / major) * major
        while gx <= x1:
            if abs(gx) > eps:
                sx = self.to_screen(gx, 0.0).x()
                ly = float(min(max(oy + 16.0, 16.0), h - 6.0))
                p.drawText(QPointF(sx + 4.0, ly), f"{gx:g}")
            gx += major
        gy = math.ceil(y0 / major) * major
        while gy <= y1:
            if abs(gy) > eps:
                sy = self.to_screen(0.0, gy).y()
                lx = float(min(max(ox + 6.0, 6.0), w - 34.0))
                p.drawText(QPointF(lx, sy - 5.0), f"{gy:g}")
            gy += major

    def _draw_axes(self, p: QPainter) -> None:
        w, h = float(self.width()), float(self.height())
        ox, oy = self.origin.x(), self.origin.y()
        p.setPen(theme.pen(theme.AXIS, 1.6))
        p.setBrush(theme.brush(theme.AXIS))
        if 0.0 <= oy <= h:
            p.drawLine(QPointF(0.0, oy), QPointF(w, oy))
            p.drawPath(self._arrow(QPointF(w - 2.0, oy), 0.0))
        if 0.0 <= ox <= w:
            p.drawLine(QPointF(ox, 0.0), QPointF(ox, h))
            p.drawPath(self._arrow(QPointF(ox, 2.0), 90.0))

        p.setPen(theme.pen(theme.LABEL, 1.0))
        p.setFont(theme.AXIS_FONT)
        if 0.0 <= oy <= h:
            p.drawText(QPointF(w - 18.0, oy - 10.0), "x")
        if 0.0 <= ox <= w:
            p.drawText(QPointF(ox + 10.0, 20.0), "y")
        if 0.0 <= ox <= w and 0.0 <= oy <= h:
            p.drawText(QPointF(ox - 18.0, oy + 20.0), "O")

    @staticmethod
    def _arrow(tip: QPointF, angle_deg: float) -> QPainterPath:
        a = math.radians(angle_deg)
        size = 9.0
        bx = tip.x() - math.cos(a) * size
        by = tip.y() + math.sin(a) * size
        px, py = -math.sin(a) * size * 0.45, -math.cos(a) * size * 0.45
        path = QPainterPath()
        path.moveTo(tip)
        path.lineTo(bx + px, by + py)
        path.lineTo(bx - px, by - py)
        path.closeSubpath()
        return path

    @staticmethod
    def _nice_step(raw: float) -> float:
        e = 10.0 ** math.floor(math.log10(raw))
        return next(m * e for m in (1.0, 2.0, 5.0, 10.0) if m * e >= raw)

    def _draw_snap_indicator(self, p: QPainter) -> None:
        if self.snap_target is None:
            return
        qpt = self.to_screen(self.snap_target.x, self.snap_target.y)
        p.setPen(theme.pen(theme.ACCENT, 1.6))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(qpt, 9.0, 9.0)
        r, tick = SNAP_PX, 5.0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x0, y0 = qpt.x() + dx * r, qpt.y() + dy * r
            p.drawLine(QPointF(x0, y0), QPointF(x0 - dx * tick, y0 - dy * tick))

    # ================= 拾取 =================
    def pick(self, screen_pt: QPointF, tol_px: float = 9.0):
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

    # ================= 事件 =================
    def showEvent(self, ev) -> None:
        if not self._origin_ready:
            self.origin = QPointF(self.width() / 2.0, self.height() / 2.0)
            self._origin_ready = True

    def resizeEvent(self, ev) -> None:
        self.rail.move(14, 14)

        zb = self.zoom_bar
        zb.move(self.width() - zb.width() - 16,
                self.height() - zb.height() - 16)

        self.info_panel.reposition()
        self._bg_cache = None  
        # snow 彩蛋：如果当前没有雪花，但标题仍是 snow，则重新生成
        if self._snow_active and not self._snowflakes:
            self._init_snow()

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_anchor = ev.position() - self.origin
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if ev.button() == Qt.MouseButton.LeftButton and self.tool is not None:
            # 撤销包裹：按压前暂存快照，若本次按压产生几何变更则记入撤销栈。
            # → 所有"点击即创建"的工具自动获得"一次点击 = 一个撤销步"。
            self.doc._arm_undo()
            self.tool.press(self, self.to_world(ev.position()),
                            self.pick(ev.position()))
            self.doc._commit_undo_if_changed()

    def mouseDoubleClickEvent(self, ev):
        # ★ 双击脚本按钮打开脚本编辑器
        from media.script_button import ScriptButtonObject

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
            self.update()
            return
        hit = self.pick(ev.position())
        self.snap_target = nearest_point(self.doc, self.scale, self.cursor_wpt)
        if self.tool is not None:
            self.tool.move(self, self.cursor_wpt, hit)
        hover = getattr(hit, "draggable", False) or self.snap_target is not None
        self.setCursor(Qt.CursorShape.SizeAllCursor if hover
                       else Qt.CursorShape.ArrowCursor)
        self.update()
        
    def contextMenuEvent(self, ev):
        """增强右键菜单：对象编辑、层级、依赖、脚本按钮、文本、媒体对象等。"""
        from PySide6.QtWidgets import QMenu
        from PySide6.QtCore import QPointF
        from media.base import MediaObject
        from media.script_button import ScriptButtonObject

        # ★ 修复 1：QContextMenuEvent 没有 position()，必须使用 pos() 并转为 QPointF
        local_pos = QPointF(ev.pos())
        hit = self.pick(local_pos)
        selected = [o for o in self.doc.objects if o.selected]

        if hit is not None:
            if hit not in selected:
                self.doc.set_selection([hit])
                selected = [hit]

        menu = QMenu(self)

        # ---------- 命中对象的快捷操作 ----------
        if hit is not None:
            if isinstance(hit, ScriptButtonObject):
                menu.addAction("▶ 运行脚本", lambda: hit.run(self))
                menu.addAction("🧩 简单编辑脚本", lambda: self._simple_edit_script_button(hit))
                menu.addAction("✎ 高级编辑脚本", lambda: hit.edit(self))
                menu.addSeparator()

            if type(hit).__name__ == "TextObject":
                menu.addAction("✎ 编辑文本", lambda: self._edit_text_object(hit))
                menu.addSeparator()

            if isinstance(hit, MediaObject) and hasattr(hit, "edit") and callable(hit.edit):
                menu.addAction("✎ 编辑对象", lambda: hit.edit(self))
                menu.addSeparator()

        # ---------- 选中对象通用操作 ----------
        if selected:
            menu.addAction("重命名…", lambda: self._rename_objects(selected))

            visible_all = all(getattr(o, "visible", True) for o in selected)
            menu.addAction(
                "隐藏" if visible_all else "显示",
                lambda: self._set_visible(selected, not visible_all),
            )

            menu.addSeparator()

            menu.addAction("复制", self.doc.copy_selection)
            menu.addAction("剪切", self.doc.cut_selection)
            menu.addAction("复制一份", self._duplicate_selected)

            menu.addSeparator()

            menu.addAction("置顶", lambda: self._reorder_objects(selected, True))
            menu.addAction("置底", lambda: self._reorder_objects(selected, False))

            menu.addSeparator()

            menu.addAction("选择父对象", lambda: self._select_related(selected, "parents"))
            menu.addAction("选择子对象", lambda: self._select_related(selected, "children"))

            menu.addSeparator()

            menu.addAction("删除", self.doc.remove_selected)

        # ---------- 粘贴 ----------
        if getattr(self.doc, "_clipboard", None):
            if not menu.isEmpty():
                menu.addSeparator()
            menu.addAction("粘贴", lambda: self.doc.paste())

        if not menu.isEmpty():
            # ★ 修复 2：QContextMenuEvent 没有 globalPosition()，必须使用 globalPos()
            menu.exec(ev.globalPos())
        else:
            super().contextMenuEvent(ev)
            
    # ================= 右键菜单辅助 =================

    def _doc_action(self, fn):
        """在撤销组中执行一个文档动作。"""
        self.doc.begin_action()
        try:
            fn()
        finally:
            self.doc.end_action()
        self.doc.changed.emit()

    def _rename_objects(self, objs):
        if len(objs) != 1:
            return

        from PySide6.QtWidgets import QInputDialog

        obj = objs[0]
        old_name = getattr(obj, "name", "") or ""
        name, ok = QInputDialog.getText(
            self,
            "重命名对象",
            "对象名称：",
            text=old_name,
        )
        if ok and name.strip():
            self.doc.rename_object(obj, name.strip())

    def _set_visible(self, objs, visible):
        def doit():
            for o in objs:
                o.visible = bool(visible)

        self._doc_action(doit)

    def _duplicate_selected(self):
        self.doc.copy_selection()
        self.doc.paste()

    def _reorder_objects(self, objs, front):
        def doit():
            if front:
                for o in objs:
                    if o in self.doc.objects:
                        self.doc.objects.remove(o)
                        self.doc.objects.append(o)
            else:
                for o in reversed(objs):
                    if o in self.doc.objects:
                        self.doc.objects.remove(o)
                        self.doc.objects.insert(0, o)

        self._doc_action(doit)

    def _select_related(self, objs, mode):
        related = []
        for o in objs:
            if mode == "parents":
                related.extend(o.parents)
            else:
                related.extend(o.children)

        # 去重
        unique = []
        seen = set()
        for o in related:
            if id(o) not in seen:
                seen.add(id(o))
                unique.append(o)

        self.doc.set_selection(unique)

    def _simple_edit_script_button(self, obj):
        from media.script_button_wizard import ScriptButtonWizard

        dlg = ScriptButtonWizard(self, obj, parent=self)
        if dlg.exec():
            def doit():
                dlg.apply_to(obj)

            self._doc_action(doit)

    def _edit_text_object(self, obj):
        from PySide6.QtWidgets import (
            QColorDialog,
            QDialog,
            QDialogButtonBox,
            QFormLayout,
            QLineEdit,
            QPushButton,
            QSpinBox,
            QVBoxLayout,
        )
        from PySide6.QtGui import QColor

        dlg = QDialog(self)
        dlg.setWindowTitle("编辑文本")
        dlg.setMinimumWidth(360)

        layout = QVBoxLayout(dlg)
        form = QFormLayout()

        text_edit = QLineEdit(getattr(obj, "text", ""))
        size_spin = QSpinBox()
        size_spin.setRange(6, 200)
        size_spin.setValue(int(getattr(obj, "size", 16)))

        color_holder = [QColor(getattr(obj, "color", "#1f2937"))]
        color_btn = QPushButton()
        color_btn.setFixedHeight(22)

        def paint_color():
            color_btn.setStyleSheet(
                f"background:{color_holder[0].name()};"
                f"border:1px solid rgba(0,0,0,0.30);"
                f"border-radius:5px;"
            )

        def pick_color():
            c = QColorDialog.getColor(color_holder[0], self, "选择文本颜色")
            if c.isValid():
                color_holder[0] = c
                paint_color()

        color_btn.clicked.connect(pick_color)
        paint_color()

        form.addRow("文本内容", text_edit)
        form.addRow("字号", size_spin)
        form.addRow("颜色", color_btn)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        layout.addWidget(buttons)

        if dlg.exec():
            def doit():
                obj.text = text_edit.text()
                obj.size = int(size_spin.value())
                obj.color = color_holder[0].name()

            self._doc_action(doit)
                       
    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if ev.button() == Qt.MouseButton.LeftButton and self.tool is not None:
            self.tool.release(self, self.to_world(ev.position()),
                              self.pick(ev.position()))

    def wheelEvent(self, ev) -> None:
        k = 1.15 if ev.angleDelta().y() > 0 else 1.0 / 1.15
        self.zoom_at(k, ev.position())

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.doc.remove_selected()
        elif ev.key() == Qt.Key.Key_Escape and self.tool is not None:
            self.tool.cancel(self)
        else:
            super().keyPressEvent(ev)

    def _place_trash(self) -> None:
        sel = [o for o in self.doc.objects if o.selected]
        if (len(sel) == 1 and isinstance(sel[0], AbstractPoint)
                and isinstance(self.tool, SelectTool)):
            qpt = self.to_screen(sel[0].x, sel[0].y)
            self._trash.move(int(qpt.x()) + 12, int(qpt.y()) - 36)
            self._trash.show()
            self._trash.raise_()
        else:
            self._trash.hide()
    def refresh_theme(self) -> None:
        """换肤：刷新悬浮面板样式与全部图标配色，然后重绘。"""
        self.setStyleSheet(theme.canvas_qss())
        self._trash.setIcon(trash_icon())
        self.zoom_bar.refresh_icons()
        self.rail.refresh_icons()
        self._bg_cache = None   
        self.update()
    # ================= snow 彩蛋 =================

    def update_snow_state(self):
        """根据文档标题决定是否开启雪花。"""
        title = (self.doc.meta.get("title") or "").strip().lower()
        active = (title == "snow")

        if active and not self._snow_active:
            self._init_snow()
            self._snow_timer.start()
        elif not active and self._snow_active:
            self._snow_timer.stop()
            self._snowflakes.clear()

        self._snow_active = active
        self.update()

    def _init_snow(self):
        w = max(self.width(), 800)
        h = max(self.height(), 600)

        self._snowflakes = []
        for _ in range(140):
            self._snowflakes.append({
                "x": random.uniform(0.0, float(w)),
                "y": random.uniform(0.0, float(h)),
                "r": random.uniform(1.2, 3.4),
                "v": random.uniform(0.6, 1.9),
                "amp": random.uniform(0.2, 0.9),
                "phase": random.uniform(0.0, 2.0 * math.pi),
            })

    def _tick_snow(self):
        if not self._snow_active:
            return

        w = max(self.width(), 1)
        h = max(self.height(), 1)

        for f in self._snowflakes:
            f["y"] += f["v"]
            f["phase"] += 0.02
            f["x"] += math.sin(f["phase"]) * f["amp"]

            if f["y"] > h + 6.0:
                f["y"] = -6.0
                f["x"] = random.uniform(0.0, float(w))

        self.update()

    def _draw_snow(self, p: QPainter) -> None:
        p.save()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 190))

        for f in self._snowflakes:
            p.drawEllipse(QPointF(f["x"], f["y"]), f["r"], f["r"])

        p.restore()

def content_bbox(doc):
    """所有可见对象的包围盒。
    函数曲线可能无限延伸，不参与普通包围盒计算，
    而是用其余对象的包围盒（加边距）裁剪函数采样点，避免导出被撑爆。
    """
    xs, ys = [], []
    funcs = []

    for o in doc.objects:
        if not (o.visible and o.exists):
            continue

        if isinstance(o, FunctionCurve):
            funcs.append(o)
            continue

        # 媒体对象：左上角世界坐标 + 宽高
        # 注意：MediaObject 修复后 y 向下增长，即底边是 o.y - o.height
        if getattr(o, "media", False):
            try:
                xs.append(o.x)
                xs.append(o.x + o.width)
                ys.append(o.y)
                ys.append(o.y - o.height)
                continue
            except Exception:
                pass

        if isinstance(o, AbstractPoint):
            xs.append(o.x)
            ys.append(o.y)
            continue

        if hasattr(o, "world_pos"):
            try:
                wx, wy = o.world_pos()
                xs.append(wx)
                ys.append(wy)
                continue
            except Exception:
                pass

        if isinstance(getattr(o, "anchor", None), tuple):
            xs.append(o.anchor[0])
            ys.append(o.anchor[1])
            continue

        if isinstance(getattr(o, "label_pos", None), tuple):
            xs.append(o.label_pos[0])
            ys.append(o.label_pos[1])
            continue

        try:
            for i in range(37):
                px, py = o.point_at(i / 36)
                xs.append(px)
                ys.append(py)
        except Exception:
            pass

    # 用非函数对象的包围盒（加边距）裁剪函数
    if funcs:
        if xs:
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            m = max(x_max - x_min, y_max - y_min) * 0.3 + 2.0
            cx0, cx1 = x_min - m, x_max + m
            cy0, cy1 = y_min - m, y_max + m
        else:
            cx0, cx1, cy0, cy1 = -10.0, 10.0, -10.0, 10.0

        for f in funcs:
            a, b = f._param_domain()

            if f.kind == "explicit":
                a = max(a, cx0)
                b = min(b, cx1)
                if a >= b:
                    a, b = cx0, cx1

                n = 199
                for i in range(n + 1):
                    u = a + (b - a) * i / n
                    p = f._eval_point(u)
                    if p is not None and cy0 <= p[1] <= cy1:
                        xs.append(p[0])
                        ys.append(p[1])
            else:
                n = 299
                for i in range(n + 1):
                    u = a + (b - a) * i / n
                    p = f._eval_point(u)
                    if p is not None and cx0 <= p[0] <= cx1 and cy0 <= p[1] <= cy1:
                        xs.append(p[0])
                        ys.append(p[1])

    if not xs:
        return None

    return min(xs), min(ys), max(xs), max(ys)