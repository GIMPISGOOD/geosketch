"""定角工具：指定角度，生成一个精确度数的角（顶点 + 两边点 + 角度标注）。"""
import math

from PySide6.QtCore import QPointF, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDoubleSpinBox, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QWidget)

from core.registry import register_tool
from geo.points import FreePoint
from plugins.angle_tool import AngleMeasure
from tools.base import Tool, point_or_snap
from ui import theme


class AnglePanel(QWidget):
    """角度输入浮层。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("anglePanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)
        layout.addWidget(QLabel("角度 (°)", self))
        self._spin = QDoubleSpinBox(self)
        self._spin.setRange(1.0, 359.0)
        self._spin.setSingleStep(5.0)
        self._spin.setDecimals(1)
        self._spin.setValue(60.0)
        layout.addWidget(self._spin)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22); shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def value(self):
        return self._spin.value()


@register_tool(name="定角", order=27, icon="fixedangle", panel="menu",
               hint="先点顶点、再点第一边上的点，上方设定角度，移动光标选侧，点一下生成精确角度")
class FixedAngleTool(Tool):
    def __init__(self):
        self.pts = []
        self._panel = None

    def activated(self, canvas):
        self.pts = []
        self._panel = AnglePanel(canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show(); self._panel.raise_()

    def deactivated(self, canvas):
        self.pts = []
        if self._panel is not None:
            self._panel.hide(); self._panel.deleteLater()
            self._panel = None

    def _target_b(self, view):
        """按指定角度与光标所在侧，计算第二边端点 B 的世界坐标。"""
        V, A = self.pts[0], self.pts[1]
        a_va = math.atan2(A.y - V.y, A.x - V.x)
        a_vc = math.atan2(view.cursor_wpt[1] - V.y, view.cursor_wpt[0] - V.x)
        sign = 1.0 if math.sin(a_vc - a_va) >= 0 else -1.0   # 光标决定取哪一侧
        target = a_va + sign * math.radians(self._panel.value())
        dist = math.hypot(A.x - V.x, A.y - V.y)
        return (V.x + dist * math.cos(target), V.y + dist * math.sin(target))

    def press(self, canvas, wpt, hit):
        if len(self.pts) < 2:
            self.pts.append(point_or_snap(canvas, wpt, hit))
        else:
            b = self._target_b(canvas)
            V, A = self.pts[0], self.pts[1]
            B = FreePoint(*b)
            canvas.doc.add(B)
            canvas.doc.add(AngleMeasure(V, A, B))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

    def draw_overlay(self, p, view):
        if not self.pts:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        V = self.pts[0]
        if len(self.pts) == 1:
            p.drawLine(view.to_screen(V.x, V.y),
                       view.to_screen(*view.cursor_wpt))
        else:
            A = self.pts[1]
            p.drawLine(view.to_screen(V.x, V.y), view.to_screen(A.x, A.y))
            b = self._target_b(view)
            p.drawLine(view.to_screen(V.x, V.y), view.to_screen(*b))
            p.drawText(view.to_screen(*b) + QPointF(8, -8),
                       f"{self._panel.value():g}°")