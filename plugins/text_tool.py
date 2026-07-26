"""文本插件：可指定文字、颜色、字号、是否锚定到点。
不锚定时放在点击位置旁边；锚定时跟随该点移动。"""
import math

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox,
                               QGraphicsDropShadowEffect, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QVBoxLayout, QWidget)

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from geo.points import nearest_point
from tools.base import Tool
from ui import theme

TEXT_SIZES = [12, 14, 16, 20, 24, 32, 48]
SWATCHES = ["#1f2937", "#e03131", "#1971c2", "#2f9e44",
            "#f08c00", "#9c36b5", "#0c8599", "#ffffff"]


@register_geo("TextObject")
class TextObject(GeoObject):
    """文本标注：可选锚定到一个点（跟随移动），否则固定在世界坐标。"""
    def __init__(self, text, color, size, anchor=None, pos=(0.0, 0.0)):
        super().__init__(parents=(anchor,) if anchor else ())
        self.text = text
        self.color = color              # hex 字符串
        self.size = size                # 屏幕像素字号（不随缩放变化）
        self.anchor = anchor
        self.pos = tuple(pos)

    def world_pos(self):
        if self.anchor is not None:
            return (self.anchor.x, self.anchor.y)
        return self.pos

    def distance_to(self, x, y):
        wx, wy = self.world_pos()
        return math.hypot(x - wx, y - wy)

    def dump(self):
        return {"text": self.text, "color": self.color,
                "size": self.size, "pos": list(self.pos)}

    @classmethod
    def build(cls, parents, params):
        return cls(params["text"], params["color"], params["size"],
                   anchor=parents[0] if parents else None,
                   pos=tuple(params.get("pos", (0, 0))))


@register_renderer(TextObject)
def draw_text(p, obj, view):
    wx, wy = obj.world_pos()
    sp = view.to_screen(wx, wy) + QPointF(12, -12)     # 显示在锚点右上方
    font = QFont()
    font.setPixelSize(obj.size)
    p.setFont(font)
    color = QColor(obj.color)
    if obj.selected:
        color = QColor(theme.SELECTED)
    p.setPen(theme.pen(color))
    p.drawText(sp, obj.text)


class TextEditor(QWidget):
    """浮动文本编辑面板：输入文字、选颜色/字号、是否锚点。"""
    confirmed = Signal(str, str, int, bool)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("textEditor")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        self._edit = QLineEdit(self)
        self._edit.setPlaceholderText("输入文本…")
        self._edit.setFixedWidth(220)
        layout.addWidget(self._edit)

        # 颜色色块
        row = QHBoxLayout()
        row.addWidget(QLabel("颜色", self))
        self._swatches = []
        for c in SWATCHES:
            b = QPushButton(self)
            b.setFixedSize(20, 20)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"background:{c}; border-radius:10px; "
                            f"border:2px solid rgba(0,0,0,0.18);")
            b.clicked.connect(lambda _=False, c=c, btn=b: self._pick_color(c, btn))
            row.addWidget(b)
            self._swatches.append((c, b))
        layout.addLayout(row)
        self._color = SWATCHES[2]
        self._highlight(self._swatches[2][1])

        # 字号
        srow = QHBoxLayout()
        srow.addWidget(QLabel("字号", self))
        self._size = QComboBox(self)
        self._size.addItems([str(s) for s in TEXT_SIZES])
        self._size.setCurrentText("16")
        srow.addWidget(self._size)
        srow.addStretch(1)
        layout.addLayout(srow)

        self._anchor_cb = QCheckBox("锚定到点（跟随移动）", self)
        layout.addWidget(self._anchor_cb)

        brow = QHBoxLayout()
        ok = QPushButton("确定", self)
        cancel = QPushButton("取消", self)
        ok.clicked.connect(self._confirm)
        cancel.clicked.connect(self.cancelled.emit)
        brow.addStretch(1); brow.addWidget(ok); brow.addWidget(cancel)
        layout.addLayout(brow)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24); shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 70))
        self.setGraphicsEffect(shadow)

    def _pick_color(self, c, btn):
        self._color = c
        for _, b in self._swatches:
            b.setStyleSheet(b.styleSheet().split("border:2px")[0] +
                            "border:2px solid rgba(0,0,0,0.18);")
        self._highlight(btn)

    def _highlight(self, btn):
        base = btn.styleSheet().split("border:2px")[0]
        btn.setStyleSheet(base + f"border:2px solid {theme.ACCENT.name()};")

    def set_anchor_available(self, has_point):
        self._anchor_cb.setEnabled(has_point)
        self._anchor_cb.setChecked(has_point)

    def _confirm(self):
        text = self._edit.text().strip()
        if not text:
            return
        self.confirmed.emit(text, self._color,
                            int(self._size.currentText()),
                            self._anchor_cb.isChecked() and self._anchor_cb.isEnabled())
        self._edit.clear()


@register_tool(name="文本", shortcut="T", order=5, icon="text", panel="rail",
               hint="点击画布输入文本；靠近点时可锚定跟随，否则放在点击处旁边")
class TextTool(Tool):
    def __init__(self):
        self._editor = None
        self._pos = None
        self._anchor = None

    def activated(self, canvas):
        self._pos = None
        self._anchor = None
        self._editor = TextEditor(canvas)
        self._editor.confirmed.connect(lambda *a: self._commit(canvas, *a))
        if self._editor is not None:
            self._editor.cancelled.connect(lambda: self._editor.hide())
        self._editor.adjustSize()
        self._editor.move((canvas.width() - self._editor.width()) // 2, 14)
        self._editor.hide()

    def deactivated(self, canvas):
        if self._editor is not None:
            self._editor.hide(); self._editor.deleteLater()
            self._editor = None

    def press(self, canvas, wpt, hit):
        self._pos = wpt
        self._anchor = nearest_point(canvas.doc, canvas.scale, wpt)
        self._editor.set_anchor_available(self._anchor is not None)
        self._editor.show(); self._editor.raise_()

    def _commit(self, canvas, text, color, size, use_anchor):
        anchor = self._anchor if use_anchor else None
        canvas.doc.add(TextObject(text, color, size, anchor=anchor, pos=self._pos))
        self._editor.hide()
        self._pos = None
        self._anchor = None

    def cancel(self, canvas):
        if self._editor is not None:
            self._editor.hide()
        self._pos = None
        self._anchor = None