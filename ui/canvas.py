import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QLinearGradient, QPainter, QPainterPath
from PySide6.QtWidgets import QWidget

from core.registry import find_renderer
from ui import theme
from ui.tool_rail import ToolRail
from ui.zoom_bar import ZoomBar
from geo.points import SNAP_PX, nearest_point

BASE_SCALE = 48.0          # 48 像素/单位 记为 100%


class Canvas(QWidget):
    cursor_info = Signal(str)        # 光标处世界坐标 → 状态栏
    tool_changed = Signal(str)       # 当前工具提示语 → 状态栏
    tool_activated = Signal(object)  # 当前工具实例 → 同步按钮/动作
    zoom_changed = Signal(float)     # 缩放百分比 → ZoomBar

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        doc.changed.connect(self.update)
        self.scale = BASE_SCALE
        self.origin = QPointF(0.0, 0.0)
        self._origin_ready = False
        self.tool = None
        self.snap_target = None 
        self.cursor_wpt: tuple[float, float] = (0.0, 0.0)
        self._panning = False
        self._pan_anchor = QPointF()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        # 悬浮件：左侧工具栏 + 右下缩放控件（都是画布的子控件）
        self.rail = ToolRail(self)
        self.rail.tool_chosen.connect(self.set_tool)
        self.tool_activated.connect(self.rail.sync)
        self.zoom_bar = ZoomBar(self, self)

    # ================= 坐标变换（类型严格区分）=================
    def to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(self.origin.x() + x * self.scale,
                       self.origin.y() - y * self.scale)   # y 轴翻转

    def to_world(self, pt: QPointF) -> tuple[float, float]:
        return ((pt.x() - self.origin.x()) / self.scale,
                (self.origin.y() - pt.y()) / self.scale)

    # ================= 工具 =================
    def set_tool(self, tool) -> None:
        # 兼容两种来源：ToolRail 发来的是工具类，快捷键动作发来的是实例
        if isinstance(tool, type):
            tool = tool()
        if self.tool is not None:
            self.tool.deactivated(self)
        self.tool = tool
        tool.activated(self)
        self.tool_changed.emit(tool.hint)
        self.tool_activated.emit(tool)
        self.update()

    # ================= 缩放：可在任意锚点 =================
    def zoom_at(self, factor: float, anchor: QPointF | None = None) -> None:
        """按锚点缩放；anchor=None 时用画布中心。滚轮传光标位置，按钮用中心。"""
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
            self._draw_background(p)
            self._draw_grid(p)
            self._draw_axes(p)
            for obj in self.doc.objects:
                if obj.visible and obj.exists:
                    renderer = find_renderer(obj)
                    if renderer is not None:
                        renderer(p, obj, self)
            self._draw_snap_indicator(p)
            if self.tool is not None:
                self.tool.draw_overlay(p, self)
        finally:
            p.end()  
            
    def _draw_snap_indicator(self, p: QPainter) -> None:
        """磁吸指示环：实线环锁定目标点，四向刻度标出吸附半径（= SNAP_PX 屏幕像素）"""
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

    def _draw_background(self, p: QPainter) -> None:
        g = QLinearGradient(0.0, 0.0, 0.0, float(self.height()))
        g.setColorAt(0.0, theme.BG_TOP)
        g.setColorAt(1.0, theme.BG_BOTTOM)
        p.fillRect(self.rect(), g)

    def _draw_grid(self, p: QPainter) -> None:
        w, h = self.width(), self.height()
        step = self._nice_step(64.0 / self.scale)      # 次网格 ≈64px 一档
        major = step * 5.0                             # 主网格：明确分界
        x0, y0 = self.to_world(QPointF(0.0, float(h)))
        x1, y1 = self.to_world(QPointF(float(w), 0.0))
        eps = step * 1e-6

        for s, color in ((step, theme.GRID_MINOR), (major, theme.GRID_MAJOR)):
            p.setPen(theme.pen(color, 1.0))
            gx = math.ceil(x0 / s) * s
            while gx <= x1:
                if abs(gx) > eps:                      # 坐标轴位置留空，单独画
                    sx = self.to_screen(gx, 0.0).x()
                    p.drawLine(QPointF(sx, 0.0), QPointF(sx, float(h)))
                gx += s
            gy = math.ceil(y0 / s) * s
            while gy <= y1:
                if abs(gy) > eps:
                    sy = self.to_screen(0.0, gy).y()
                    p.drawLine(QPointF(0.0, sy), QPointF(float(w), sy))
                gy += s

        # 主刻度数值（沿轴，轴移出视野时贴边）
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
        """坐标轴：加粗实线 + 箭头 + x/y/O 标注，与网格明确分界。"""
        w, h = float(self.width()), float(self.height())
        ox, oy = self.origin.x(), self.origin.y()
        p.setPen(theme.pen(theme.AXIS, 1.6))
        p.setBrush(theme.brush(theme.AXIS))
        if 0.0 <= oy <= h:                             # x 轴
            p.drawLine(QPointF(0.0, oy), QPointF(w, oy))
            p.drawPath(self._arrow(QPointF(w - 2.0, oy), 0.0))
        if 0.0 <= ox <= w:                             # y 轴
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
        """实心箭头。angle_deg 为指向（屏幕坐标：0=右，90=上）。"""
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
    def _nice_step(raw: float) -> float:               # 1-2-5 序列
        e = 10.0 ** math.floor(math.log10(raw))
        return next(m * e for m in (1.0, 2.0, 5.0, 10.0) if m * e >= raw)

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
        if not self._origin_ready:                     # 首次显示：原点居中
            self.origin = QPointF(self.width() / 2.0, self.height() / 2.0)
            self._origin_ready = True

    def resizeEvent(self, ev) -> None:                 # 悬浮件贴边定位
        self.rail.move(14, 14)
        zb = self.zoom_bar
        zb.move(self.width() - zb.width() - 16,
                self.height() - zb.height() - 16)

    def mousePressEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:         # 中键平移
            self._panning = True
            self._pan_anchor = ev.position() - self.origin
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return
        if ev.button() == Qt.MouseButton.LeftButton and self.tool is not None:
            self.tool.press(self, self.to_world(ev.position()),
                            self.pick(ev.position()))

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
        self.update()                                  # 刷新橡皮筋

    def mouseReleaseEvent(self, ev) -> None:
        if ev.button() == Qt.MouseButton.MiddleButton:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if ev.button() == Qt.MouseButton.LeftButton and self.tool is not None:
            self.tool.release(self, self.to_world(ev.position()),
                              self.pick(ev.position()))

    def wheelEvent(self, ev) -> None:                  # 滚轮：以光标为锚点
        k = 1.15 if ev.angleDelta().y() > 0 else 1.0 / 1.15
        self.zoom_at(k, ev.position())

    def keyPressEvent(self, ev) -> None:
        if ev.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.doc.remove_selected()
        elif ev.key() == Qt.Key.Key_Escape and self.tool is not None:
            self.tool.cancel(self)
        else:
            super().keyPressEvent(ev)