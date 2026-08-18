import math
import os
from PySide6.QtCore import QPointF, QSize, Qt, Signal, QTimer
from PySide6.QtGui import QPainter, QImage, QColor
from PySide6.QtWidgets import QWidget, QToolButton
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
        self.rail = ToolRail(self)
        self.rail.tool_chosen.connect(self.set_tool)
        self.tool_activated.connect(self.rail.sync)
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
        from geo.function_sampler import get_sampler
        self._sampler = get_sampler()
        self._sampler.sampled.connect(self._on_function_sampled)
        from geo.implicit_sampler import get_implicit_sampler
        self._implicit_sampler = get_implicit_sampler()
        self._implicit_sampler.sampled.connect(self._on_implicit_sampled)

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
        self.scale = BASE_SCALE
        self.origin = QPointF(self.width() / 2, self.height() / 2)
        self._emit_zoom()
        self.update()

    def _emit_zoom(self) -> None:
        self.zoom_changed.emit(self.scale / BASE_SCALE * 100.0)

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

    def render_scene(self, p: QPainter, bg_mode: str = "grid", publication: bool = False) -> None:
        if publication:
            p.fillRect(self.rect(), QColor("#ffffff"))
        elif bg_mode == "grid":
            draw_background_cached(self, p)
        elif bg_mode == "axes":
            draw_background(self, p)
            draw_axes(self, p)
        else:
            draw_background(self, p)
        
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
        r, tick = SNAP_PX, 5.0
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            x0, y0 = qpt.x() + dx * r, qpt.y() + dy * r
            p.drawLine(QPointF(x0, y0), QPointF(x0 - dx * tick, y0 - dy * tick))

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

    def showEvent(self, ev) -> None:
        if not self._origin_ready:
            self.origin = QPointF(self.width() / 2.0, self.height() / 2.0)
            self._origin_ready = True

    def resizeEvent(self, ev) -> None:
        self.rail.move(14, 14)
        zb = self.zoom_bar
        zb.move(self.width() - zb.width() - 16, self.height() - zb.height() - 16)
        self.info_panel.reposition()
        self._bg_cache = None
        if self._snow_active and not self._snowflakes:
            init_snow(self)

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._pan_anchor = ev.position() - self.origin
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if ev.button() == Qt.MouseButton.LeftButton and self.tool is not None:
            self.doc._arm_undo()
            self.tool.press(self, self.to_world(ev.position()), self.pick(ev.position()))
            self.doc._commit_undo_if_changed()

    def mouseDoubleClickEvent(self, ev):
        hit = self.pick(ev.position())
        if isinstance(hit, ScriptButtonObject):
            hit.edit(self)
            return
        super().mouseDoubleClickEvent(ev)

    def mouseMoveEvent(self, ev) -> None:
        self.cursor_wpt = self.to_world(ev.position())
        self.cursor_info.emit(f"( {self.cursor_wpt[0]:7.2f} , {self.cursor_wpt[1]:7.2f} )")
        if self._panning:
            self.origin = ev.position() - self._pan_anchor
            self.update()
            return
        hit = self.pick(ev.position())
        self.snap_target = nearest_point(self.doc, self.scale, self.cursor_wpt)
        if self.tool is not None:
            self.tool.move(self, self.cursor_wpt, hit)
        hover = getattr(hit, "draggable", False) or self.snap_target is not None
        self.setCursor(Qt.CursorShape.SizeAllCursor if hover else Qt.CursorShape.ArrowCursor)
        self.update()

    def contextMenuEvent(self, ev):
        if not show_context_menu(self, ev):
            super().contextMenuEvent(ev)

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if ev.button() == Qt.MouseButton.LeftButton and self.tool is not None:
            self.tool.release(self, self.to_world(ev.position()), self.pick(ev.position()))

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
        if (len(sel) == 1 and isinstance(sel[0], AbstractPoint) and isinstance(self.tool, SelectTool)):
            qpt = self.to_screen(sel[0].x, sel[0].y)
            self._trash.move(int(qpt.x()) + 12, int(qpt.y()) - 36)
            self._trash.show()
            self._trash.raise_()
        else:
            self._trash.hide()

    def refresh_theme(self) -> None:
        self.setStyleSheet(theme.canvas_qss())
        self._trash.setIcon(trash_icon())
        self.zoom_bar.refresh_icons()
        self.rail.refresh_icons()
        self._bg_cache = None
        self.update()

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