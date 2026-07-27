"""定长线段工具：指定长度，沿光标方向生成精确长度的线段。"""
import math

from PySide6.QtCore import QPointF, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDoubleSpinBox, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QWidget)

from core.registry import register_tool
from geo.points import FreePoint
from geo.segments import Segment
from tools.base import Tool, point_or_snap
from ui import theme


class LengthPanel(QWidget):
    """长度输入浮层。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("lengthPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        layout.addWidget(QLabel("长度", self))
        self._spin = QDoubleSpinBox(self)
        self._spin.setRange(0.1, 1000.0)
        self._spin.setSingleStep(0.5)
        self._spin.setDecimals(2)
        self._spin.setValue(3.0)
        layout.addWidget(self._spin)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22); shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def value(self):
        return self._spin.value()


@register_tool(name="定长线段", order=26, icon="length", panel="menu",
               hint="先点起点，上方设定长度，移动光标定方向，再点一下生成精确长度的线段")
class LengthSegTool(Tool):
    def __init__(self):
        self.start = None
        self._panel = None

    def activated(self, canvas):
        self.start = None
        self._panel = LengthPanel(canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show(); self._panel.raise_()

    def deactivated(self, canvas):
        self.start = None
        if self._panel is not None:
            self._panel.hide(); self._panel.deleteLater()
            self._panel = None

    def press(self, canvas, wpt, hit):
        if self.start is None:
            self.start = point_or_snap(canvas, wpt, hit)
        else:
            L = self._panel.value()
            dx, dy = wpt[0] - self.start.x, wpt[1] - self.start.y
            d = math.hypot(dx, dy)
            if d < 1e-9:
                return
            end = FreePoint(self.start.x + dx / d * L, self.start.y + dy / d * L)
            canvas.doc.add(end)
            canvas.doc.add(Segment(self.start, end))
            self.start = None

    def cancel(self, canvas):
        self.start = None
        canvas.update()

    def draw_overlay(self, p, view):
        if self.start is None:
            return
        L = self._panel.value()
        dx, dy = view.cursor_wpt[0] - self.start.x, view.cursor_wpt[1] - self.start.y
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return
        end_w = (self.start.x + dx / d * L, self.start.y + dy / d * L)
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.drawLine(view.to_screen(self.start.x, self.start.y),
                   view.to_screen(*end_w))
        mid = view.to_screen((self.start.x + end_w[0]) / 2,
                             (self.start.y + end_w[1]) / 2)
        p.drawText(mid + QPointF(8, -8), f"{L:g}")