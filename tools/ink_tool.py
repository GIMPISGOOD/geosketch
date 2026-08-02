"""墨迹注释工具：钢笔/荧光笔/铅笔，可选颜色与透明度，显示在左侧工具栏。"""
from PySide6.QtCore import Qt
import math
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
                               QSlider, QLabel, QColorDialog, QGraphicsDropShadowEffect)

from core.registry import register_tool
from geo.ink import InkStroke
from tools.base import Tool
from ui import theme

MODES = [("pen", "钢笔"), ("highlighter", "荧光笔"), ("pencil", "铅笔")]
PRESET_COLORS = ["#222222", "#e03131", "#1971c2", "#2f9e44", "#f08c00", "#9c36b5", "#ffd43b"]


class InkSettingsPanel(QWidget):
    """墨迹设置浮层：笔型 / 颜色 / 透明度。"""
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.setObjectName("inkPanel")
        self.tool = tool
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

        # 笔型
        row = QHBoxLayout()
        self._mode_btns = {}
        for key, label in MODES:
            b = QPushButton(label)
            b.setCheckable(True)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(lambda _=False, k=key: self._set_mode(k))
            row.addWidget(b)
            self._mode_btns[key] = b
        self._mode_btns["pen"].setChecked(True)
        v.addLayout(row)

        # 颜色
        crow = QHBoxLayout()
        crow.addWidget(QLabel("颜色"))
        self._color_btns = {}
        for c in PRESET_COLORS:
            b = QPushButton()
            b.setFixedSize(20, 20)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"background:{c};border-radius:10px;border:2px solid transparent;")
            b.clicked.connect(lambda _=False, cc=c: self._set_color(cc))
            crow.addWidget(b)
            self._color_btns[c] = b
        self._custom = QPushButton("…")
        self._custom.setFixedSize(20, 20)
        self._custom.setCursor(Qt.CursorShape.PointingHandCursor)
        self._custom.clicked.connect(self._pick_color)
        crow.addWidget(self._custom)
        crow.addStretch(1)
        v.addLayout(crow)
        self._highlight_color(PRESET_COLORS[0])

        # 透明度
        orow = QHBoxLayout()
        orow.addWidget(QLabel("透明度"))
        self._opacity = QSlider(Qt.Orientation.Horizontal)
        self._opacity.setRange(10, 100)
        self._opacity.setValue(100)
        self._opacity.valueChanged.connect(self._set_opacity)
        orow.addWidget(self._opacity, 1)
        self._op_lbl = QLabel("100%")
        orow.addWidget(self._op_lbl)
        v.addLayout(orow)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20); shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)

    def _set_mode(self, key):
        self.tool._mode = key
        for k, b in self._mode_btns.items():
            b.setChecked(k == key)

    def _set_color(self, c):
        self.tool._color = c
        self._highlight_color(c)

    def _highlight_color(self, c):
        for cc, b in self._color_btns.items():
            sel = "2px solid " + theme.ACCENT.name() if cc == c else "2px solid transparent"
            b.setStyleSheet(f"background:{cc};border-radius:10px;border:{sel};")

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.tool._color), self, "选择墨迹颜色")
        if c.isValid():
            self._set_color(c.name())

    def _set_opacity(self, v):
        self.tool._opacity = v / 100
        self._op_lbl.setText(f"{v}%")


@register_tool(name="墨迹", shortcut="I", order=11, icon="ink", panel="rail",
               hint="自由手绘注释：钢笔/荧光笔/铅笔，可选颜色与透明度")
class InkTool(Tool):
    def __init__(self):
        self._points = []
        self._drawing = False
        self._mode = "pen"
        self._color = "#222222"
        self._opacity = 1.0
        self._panel = None

    def activated(self, canvas):
        self._drawing = False
        self._points = []
        self._panel = InkSettingsPanel(self, canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show(); self._panel.raise_()

    def deactivated(self, canvas):
        self._drawing = False
        self._points = []
        if self._panel is not None:
            self._panel.hide(); self._panel.deleteLater()
            self._panel = None

    def press(self, canvas, wpt, hit):
        self._drawing = True
        self._points = [wpt]

    def move(self, canvas, wpt, hit):
        if self._drawing:
            # 简单抽稀：与上一点太近就不加
            if self._points and math.hypot(wpt[0]-self._points[-1][0], wpt[1]-self._points[-1][1]) > 2.0/canvas.scale:
                self._points.append(wpt)
                canvas.update()

    def release(self, canvas, wpt, hit):
        if self._drawing and len(self._points) > 1:
            width = {"pen": 2.5, "highlighter": 3.0, "pencil": 1.8}[self._mode]
            canvas.doc.add(InkStroke(self._points, self._color, width, self._opacity, self._mode))
        self._drawing = False
        self._points = []
        canvas.update()

    def cancel(self, canvas):
        self._drawing = False
        self._points = []
        canvas.update()

    def draw_overlay(self, p, view):
        if self._drawing and len(self._points) > 1:
            c = QColor(self._color)
            c.setAlphaF(self._opacity)
            w = {"pen": 2.5, "highlighter": 3.0, "pencil": 1.8}[self._mode]
            if self._mode == "highlighter":
                w *= 3.5
            pen = theme.pen(c, w)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.setBrush(Qt.BrushStyle.NoBrush)
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.moveTo(view.to_screen(*self._points[0]))
            for pt in self._points[1:]:
                path.lineTo(view.to_screen(*pt))
            p.drawPath(path)