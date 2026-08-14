"""墨迹注释工具：钢笔/荧光笔/铅笔/橡皮擦（真正擦除）。"""
import math
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
                               QSlider, QLabel, QColorDialog, QGraphicsDropShadowEffect)
from core.registry import register_tool
from geo.ink import InkStroke
from tools.base import Tool
from ui import theme

MODES = [("pen", "钢笔"), ("highlighter", "荧光笔"),
         ("pencil", "铅笔"), ("eraser", "橡皮擦")]
PRESET_COLORS = ["#222222", "#e03131", "#1971c2", "#2f9e44",
                 "#f08c00", "#9c36b5", "#ffd43b"]


class InkSettingsPanel(QWidget):
    """墨迹设置浮层。"""
    def __init__(self, tool, parent=None):
        super().__init__(parent)
        self.setObjectName("inkPanel")
        self.tool = tool
        v = QVBoxLayout(self)
        v.setContentsMargins(10, 8, 10, 8)
        v.setSpacing(6)

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

        crow = QHBoxLayout()
        crow.addWidget(QLabel("颜色"))
        self._color_btns = {}
        for c in PRESET_COLORS:
            b = QPushButton()
            b.setFixedSize(20, 20)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"background:{c};border-radius:10px;"
                            f"border:2px solid transparent;")
            b.clicked.connect(lambda _=False, cc=c: self._set_color(cc))
            crow.addWidget(b)
            self._color_btns[c] = b
        self._custom = QPushButton("…")
        self._custom.setFixedSize(20, 20)
        self._custom.clicked.connect(self._pick_color)
        crow.addWidget(self._custom)
        crow.addStretch(1)
        v.addLayout(crow)
        self._highlight_color(PRESET_COLORS[0])

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

        undo_btn = QPushButton("↩ 撤销笔画")
        undo_btn.clicked.connect(self.tool.undo_stroke)
        v.addWidget(undo_btn)

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
            sel = "2px solid " + theme.ACCENT.name() if cc == c \
                else "2px solid transparent"
            b.setStyleSheet(f"background:{cc};border-radius:10px;border:{sel};")

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.tool._color), self, "选择墨迹颜色")
        if c.isValid():
            self._set_color(c.name())

    def _set_opacity(self, v):
        self.tool._opacity = v / 100
        self._op_lbl.setText(f"{v}%")


@register_tool(name="墨迹", shortcut="I", order=11, icon="ink", panel="rail",
               hint="自由手绘：钢笔/荧光笔/铅笔/橡皮擦（真正擦除）")
class InkTool(Tool):
    def __init__(self):
        self._points = []
        self._drawing = False
        self._mode = "pen"
        self._color = "#222222"
        self._opacity = 1.0
        self._panel = None
        self._strokes = []
        self._canvas = None

    def activated(self, canvas):
        self._canvas = canvas
        self._drawing = False
        self._points = []
        self._strokes = []
        self._panel = InkSettingsPanel(self, canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show(); self._panel.raise_()

    def deactivated(self, canvas):
        self._drawing = False
        self._points = []
        self._canvas = None
        if self._panel is not None:
            self._panel.hide(); self._panel.deleteLater()
        self._panel = None

    # ───────── 按压 ─────────
    def press(self, canvas, wpt, hit):
        if self._mode == "eraser":
            canvas.doc.begin_action()
        self._drawing = True
        self._points = [wpt]

    # ───────── 移动 ─────────
    def move(self, canvas, wpt, hit):
        if not self._drawing:
            return
        if self._mode == "eraser":
            self._erase_at(canvas, wpt)
        else:
            if (self._points and
                math.hypot(wpt[0] - self._points[-1][0],
                           wpt[1] - self._points[-1][1]) > 2.0 / canvas.scale):
                self._points.append(wpt)
        canvas.update()

    # ───────── 释放 ─────────
    def release(self, canvas, wpt, hit):
        if self._mode == "eraser":
            canvas.doc.end_action()
        elif self._drawing and len(self._points) > 1:
            width = {"pen": 2.5, "highlighter": 3.0, "pencil": 1.8}[self._mode]
            stroke = InkStroke(self._points, self._color, width,
                               self._opacity, self._mode)
            canvas.doc.add(stroke)
            self._strokes.append(stroke)
        self._drawing = False
        self._points = []
        canvas.update()

    # ───────── 真正擦除 ─────────
    def _erase_at(self, canvas, wpt):
        """在 wpt 处擦除笔画：把被擦到的笔画分割成多段。"""
        radius = 0.35  # 世界坐标擦除半径
        doc = canvas.doc
        to_remove = []
        to_add = []
        for obj in list(doc.objects):
            if not isinstance(obj, InkStroke) or not obj.exists:
                continue
            segments = self._split_stroke(obj.points, wpt, radius)
            # 判断是否真的被分割
            if len(segments) == 1 and len(segments[0]) == len(obj.points):
                continue
            to_remove.append(obj)
            for seg in segments:
                if len(seg) >= 2:
                    to_add.append(InkStroke(seg, obj.color, obj.width,
                                            obj.opacity, obj.mode))
        for obj in to_remove:
            doc._remove(obj)
        for obj in to_add:
            doc._add(obj)
        if to_remove or to_add:
            doc._mutation_count += 1

    @staticmethod
    def _split_stroke(points, center, radius):
        """把笔画点列表分割成不在擦除圆内的连续段。"""
        segments = []
        current = []
        cx, cy = center
        for pt in points:
            if math.hypot(pt[0] - cx, pt[1] - cy) < radius:
                if len(current) >= 2:
                    segments.append(current)
                current = []
            else:
                current.append(pt)
        if len(current) >= 2:
            segments.append(current)
        return segments

    # ───────── 撤销笔画 ─────────
    def undo_stroke(self):
        if self._strokes and self._canvas is not None:
            stroke = self._strokes.pop()
            if stroke in self._canvas.doc.objects:
                self._canvas.doc.remove(stroke)

    def cancel(self, canvas):
        self._drawing = False
        self._points = []
        canvas.update()

    # ───────── 覆盖层 ─────────
    def draw_overlay(self, p, view):
        if self._drawing and len(self._points) > 1:
            if self._mode == "eraser":
                # 橡皮擦：画一个半透明圆表示擦除范围
                sp = view.to_screen(*self._points[-1])
                p.setPen(theme.dashed_pen(theme.SUBINK, 1.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(sp, 0.35 * view.scale, 0.35 * view.scale)
                return
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
            path = QPainterPath()
            path.moveTo(view.to_screen(*self._points[0]))
            for pt in self._points[1:]:
                path.lineTo(view.to_screen(*pt))
            p.drawPath(path)