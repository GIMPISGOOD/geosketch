# plugins/angle_divide_tool.py —— n 等分角线
"""n 等分角线插件：把一个角 n 等分，得到 n-1 条分界线。"""
import math

from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QToolButton, QWidget)

from core.registry import register_geo, register_tool
from geo.directed_line import DirectedLine
from tools.base import Tool, point_or_snap


@register_geo("AngleDivLine")
class AngleDivLine(DirectedLine):
    """把角 (vertex,p1,p2) 分为 n 等份的第 k 条分界线。"""
    def __init__(self, vertex, p1, p2, k, n):
        super().__init__((vertex, p1, p2), vertex)
        self.p1, self.p2, self.k, self.n = p1, p2, k, n
        self.recompute()

    def recompute(self):
        v = self.point
        a1 = math.atan2(self.p1.y - v.y, self.p1.x - v.x)
        a2 = math.atan2(self.p2.y - v.y, self.p2.x - v.x)
        span = a2 - a1
        while span > math.pi: span -= 2 * math.pi
        while span < -math.pi: span += 2 * math.pi
        ang = a1 + span * self.k / self.n
        self.dx, self.dy = math.cos(ang), math.sin(ang)

    def dump(self):
        return {"k": self.k, "n": self.n}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2], params["k"], params["n"])


class AngleDivPicker(QWidget):
    """等分角数选择器：2~8。"""
    n_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("dividePicker")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)
        layout.addWidget(QLabel("等分", self))
        group = QButtonGroup(self)
        group.setExclusive(True)
        for n in range(2, 9):
            btn = QToolButton(self)
            btn.setText(str(n))
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, n=n: self.n_changed.emit(n))
            group.addButton(btn)
            layout.addWidget(btn)
            if n == AngleDivideTool.n:
                btn.setChecked(True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22); shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)


@register_tool(name="等分角", shortcut="N", order=33, icon="angle_divide", panel="menu",
               hint="先点顶点，再点角两侧的点，将角 n 等分；上方选择 n（2~8）")
class AngleDivideTool(Tool):
    n = 3

    def __init__(self):
        self.pts = []
        self._picker = None

    def activated(self, canvas):
        self.pts = []
        self._picker = AngleDivPicker(canvas)
        self._picker.n_changed.connect(self._set_n)
        self._picker.adjustSize()
        self._picker.move((canvas.width() - self._picker.width()) // 2, 14)
        self._picker.show(); self._picker.raise_()

    def _set_n(self, n):
        AngleDivideTool.n = n

    def deactivated(self, canvas):
        self.pts = []
        if self._picker is not None:
            self._picker.hide(); self._picker.deleteLater()
            self._picker = None

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 3:
            v, p1, p2 = self.pts
            for k in range(1, AngleDivideTool.n):
                canvas.doc.add(AngleDivLine(v, p1, p2, k, AngleDivideTool.n))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()