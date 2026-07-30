import math
import os

from PySide6.QtCore import QPointF, QSize, Qt, Signal
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget, QToolButton
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath, QImage

from core.registry import find_renderer
from geo.points import SNAP_PX, AbstractPoint, nearest_point
from tools.select import SelectTool
from ui.variable_widgets import VariableSliderPanel
from ui import theme
from ui.icons import trash_icon
from ui.tool_rail import ToolRail
from ui.zoom_bar import ZoomBar
from ui.info_panel import InfoPanel
from ui.function_panel import FunctionPanel

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

        self.info_panel = InfoPanel(self, self)

        self.var_panel = VariableSliderPanel(self, self)

        self.function_panel = FunctionPanel(self, self)
        self.function_panel.refresh()

        self.refresh_theme()

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
            self.render_scene(p)                 # 几何场景（屏幕/导出共用）
            # —— 以下仅屏幕显示，不导出 ——
            self._draw_snap_indicator(p)
            if self.tool is not None:
                self.tool.draw_overlay(p, self)
        finally:
            p.end()
        self._place_trash()

    def render_scene(self, p: QPainter, bg_mode: str = "grid") -> None:
        """渲染几何场景（背景 + 可选网格/坐标轴 + 全部对象）。
        bg_mode: "grid"=网格+坐标轴, "axes"=仅坐标轴, "none"=都不画。"""
        self._draw_background(p)
        if bg_mode == "grid":
            self._draw_grid(p)
            self._draw_axes(p)
        elif bg_mode == "axes":
            self._draw_axes(p)
        for obj in self.doc.objects:
            if obj.visible and obj.exists:
                renderer = find_renderer(obj)
                if renderer is not None:
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
        self.var_panel.reposition()
        self.function_panel.reposition()

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
        self.update()

def content_bbox(doc):
    """所有可见几何对象的世界坐标包围盒 (x0,y0,x1,y1)；无对象返回 None。"""
    xs, ys = [], []
    for o in doc.objects:
        if not (o.visible and o.exists):
            continue
            
        # 1. 点类对象
        if isinstance(o, AbstractPoint):
            xs.append(o.x)
            ys.append(o.y)
            continue
            
        # 2. 文本对象（有 world_pos 方法）
        if hasattr(o, "world_pos"):
            try:
                wx, wy = o.world_pos()
                xs.append(wx); ys.append(wy)
                continue
            except Exception:
                pass
                
        # 3. 角度/比例等测量对象（有特定锚点属性）
        if hasattr(o, "anchor") and isinstance(getattr(o, "anchor", None), tuple):
            xs.append(o.anchor[0]); ys.append(o.anchor[1])
            continue
        if hasattr(o, "label_pos") and isinstance(getattr(o, "label_pos", None), tuple):
            xs.append(o.label_pos[0]); ys.append(o.label_pos[1])
            continue

        # 4. 参数化曲线（线段、圆、多边形、椭圆、贝塞尔等）
        # 使用 try-except 忽略不支持 point_at 的对象（基类默认会抛出 NotImplementedError）
        try:
            for i in range(37):
                px, py = o.point_at(i / 36)
                xs.append(px)
                ys.append(py)
        except NotImplementedError:
            pass
        except Exception:
            pass

    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)