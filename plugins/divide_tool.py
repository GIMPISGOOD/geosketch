"""N 等分插件：依次点两个点，把它们的连线段 N 等分（从动，始终保持等分）。"""
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QToolButton, QWidget)

from core.registry import register_tool
from geo.division import DivisionPoint
from tools.base import Tool, point_or_snap


class DividePicker(QWidget):
    """等分数选择器：2~12。"""
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
        for n in range(2, 13):
            btn = QToolButton(self)
            btn.setText(str(n))
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, n=n: self.n_changed.emit(n))
            group.addButton(btn)
            layout.addWidget(btn)
            if n == DivideTool.n:
                btn.setChecked(True)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22); shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)


@register_tool(name="N等分", shortcut="D", order=21, icon="divide", panel="menu",
               hint="依次点击两个点，将连线段 N 等分；上方选择等分数（2~12）")
class DivideTool(Tool):
    n = 4

    def __init__(self):
        self.first = None
        self._picker = None

    def activated(self, canvas):
        self.first = None
        self._picker = DividePicker(canvas)
        self._picker.n_changed.connect(self._set_n)
        self._picker.adjustSize()
        self._picker.move((canvas.width() - self._picker.width()) // 2, 14)
        self._picker.show(); self._picker.raise_()

    def _set_n(self, n):
        DivideTool.n = n

    def deactivated(self, canvas):
        self.first = None
        if self._picker is not None:
            self._picker.hide(); self._picker.deleteLater()
            self._picker = None

    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if self.first is None:
            self.first = pt
            canvas.doc.set_selection([pt])
        else:
            if pt is not self.first:
                for k in range(1, DivideTool.n):
                    canvas.doc.add(DivisionPoint(self.first, pt, k / DivideTool.n))
            self.first = None
            canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.first = None
        canvas.doc.set_selection([])
        canvas.update()