"""表达式工具：用变量的代数式创建线段 / 角度（从「变量与函数」菜单启动，不进工具栏）。"""
import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget, QHBoxLayout, QLabel, QLineEdit,
                               QGraphicsDropShadowEffect)

from core.variables import eval_expr
from geo.constraints import ExprSegment, ExprAngle
from geo.points import FreePoint
from geo.segments import Segment
from plugins.angle_tool import AngleMeasure
from tools.base import Tool, point_or_snap
from ui import theme


class ExprPanel(QWidget):
    """表达式输入浮层：实时显示求值结果。"""
    def __init__(self, label="长度 =", parent=None):
        super().__init__(parent)
        self.setObjectName("exprPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        layout.addWidget(QLabel(label))
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("如 2*边长+1、sqrt(a)、90")
        self.edit.setMinimumWidth(190)
        self.edit.textChanged.connect(self._update_val)
        layout.addWidget(self.edit)
        self.val_lbl = QLabel("")
        self.val_lbl.setFont(theme.LABEL_FONT)
        layout.addWidget(self.val_lbl)
        self._update_val()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20); shadow.setOffset(0, 4)
        shadow.setColor(QColor(0, 0, 0, 50))
        self.setGraphicsEffect(shadow)

    def _update_val(self):
        expr = self.edit.text().strip()
        if not expr:
            self.val_lbl.setText(""); return
        v = eval_expr(expr)
        if v is None:
            self.val_lbl.setText("无效表达式")
            self.val_lbl.setStyleSheet(f"color:{theme.SELECTED.name()};")
        else:
            self.val_lbl.setText(f"= {v:.3f}")
            self.val_lbl.setStyleSheet(f"color:{theme.ACCENT.name()};")

    def value(self):
        return eval_expr(self.edit.text().strip())

    def expr(self):
        return self.edit.text().strip()


class ExprSegmentTool(Tool):
    """表达式线段：长度 = 变量代数式，随变量实时伸缩。"""
    def __init__(self):
        self.start = None
        self._panel = None

    def activated(self, canvas):
        self.start = None
        self._panel = ExprPanel("长度 =", canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show(); self._panel.raise_()

    def deactivated(self, canvas):
        self.start = None
        if self._panel is not None:
            self._panel.hide(); self._panel.deleteLater(); self._panel = None

    def press(self, canvas, wpt, hit):
        L = self._panel.value() if self._panel else None
        if L is None or L <= 1e-9:
            return
        if self.start is None:
            self.start = point_or_snap(canvas, wpt, hit)
        else:
            dx, dy = wpt[0] - self.start.x, wpt[1] - self.start.y
            d = math.hypot(dx, dy)
            if d < 1e-9:
                return
            end = FreePoint(self.start.x + dx / d * L, self.start.y + dy / d * L)
            canvas.doc.add(end)
            seg = canvas.doc.add(Segment(self.start, end))
            canvas.doc.add(ExprSegment(seg, self._panel.expr()))
            self.start = None

    def cancel(self, canvas):
        self.start = None
        canvas.update()

    def draw_overlay(self, p, view):
        if self.start is None:
            return
        L = self._panel.value() if self._panel else None
        if L is None or L <= 1e-9:
            return
        dx, dy = view.cursor_wpt[0] - self.start.x, view.cursor_wpt[1] - self.start.y
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return
        end_w = (self.start.x + dx / d * L, self.start.y + dy / d * L)
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.drawLine(view.to_screen(self.start.x, self.start.y), view.to_screen(*end_w))
        mid = view.to_screen((self.start.x + end_w[0]) / 2, (self.start.y + end_w[1]) / 2)
        p.drawText(mid + QPointF(8, -8), f"{L:g}")


class ExprAngleTool(Tool):
    """表达式角：角度数 = 变量代数式，随变量实时变化。"""
    def __init__(self):
        self.pts = []
        self._panel = None

    def activated(self, canvas):
        self.pts = []
        self._panel = ExprPanel("角度(°) =", canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show(); self._panel.raise_()

    def deactivated(self, canvas):
        self.pts = []
        if self._panel is not None:
            self._panel.hide(); self._panel.deleteLater(); self._panel = None

    def _target_b(self, view):
        V, A = self.pts[0], self.pts[1]
        deg = self._panel.value()
        a_va = math.atan2(A.y - V.y, A.x - V.x)
        a_vc = math.atan2(view.cursor_wpt[1] - V.y, view.cursor_wpt[0] - V.x)
        sign = 1.0 if math.sin(a_vc - a_va) >= 0 else -1.0
        target = a_va + sign * math.radians(deg)
        dist = math.hypot(A.x - V.x, A.y - V.y)
        return (V.x + dist * math.cos(target), V.y + dist * math.sin(target))

    def press(self, canvas, wpt, hit):
        if self._panel is None or self._panel.value() is None:
            return
        if len(self.pts) < 2:
            self.pts.append(point_or_snap(canvas, wpt, hit))
        else:
            V, A = self.pts[0], self.pts[1]
            B = FreePoint(*self._target_b(canvas))
            canvas.doc.add(B)
            ang = canvas.doc.add(AngleMeasure(V, A, B))
            canvas.doc.add(ExprAngle(ang, self._panel.expr()))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

    def draw_overlay(self, p, view):
        if not self.pts:
            return
        deg = self._panel.value() if self._panel else None
        if deg is None:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        V = self.pts[0]
        if len(self.pts) == 1:
            p.drawLine(view.to_screen(V.x, V.y), view.to_screen(*view.cursor_wpt))
        else:
            A = self.pts[1]
            p.drawLine(view.to_screen(V.x, V.y), view.to_screen(A.x, A.y))
            b = self._target_b(view)
            p.drawLine(view.to_screen(V.x, V.y), view.to_screen(*b))
            p.drawText(view.to_screen(*b) + QPointF(8, -8), f"{deg:g}°")