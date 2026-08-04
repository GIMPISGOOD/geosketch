"""信息面板：选中几何图形后浮动显示其属性（支持多边形等全部对象），拖动时实时刷新。"""
import math
from collections import Counter

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel

from ui import theme

_CN = {
    "FreePoint": "自由点", "PointOnObject": "吸附点", "IntersectPoint": "交点",
    "DivisionPoint": "等分点", "Midpoint": "中点", "PolygonVertex": "多边形顶点",
    "Segment": "线段", "Circle": "圆", "Line": "直线", "Ray": "射线",
    "PerpLine": "垂线", "ParallelLine": "平行线", "AngleBisector": "角平分线",
    "AngleDivLine": "等分角线", "RegularPolygon": "正多边形", "Ellipse": "椭圆",
    "CubicBezier": "贝塞尔曲线", "AngleMeasure": "角", "RatioMeasure": "比例",
    "TextObject": "文本",
}


def describe(obj):
    """返回 (标题, [(属性名, 值), ...])。按类名分发，兼容所有插件对象。"""
    n = type(obj).__name__
    title = _CN.get(n, n)
    rows = []

    if hasattr(obj, "x") and hasattr(obj, "y"):          # 点类
        rows.append(("坐标", f"({obj.x:.2f}, {obj.y:.2f})"))

    if n == "Segment":
        rows.append(("长度", f"{obj.length():.3f}"))
    elif n == "Circle":
        rows.append(("半径", f"{obj.r:.3f}"))
        rows.append(("圆心", f"({obj.center.x:.2f}, {obj.center.y:.2f})"))
        rows.append(("周长", f"{2 * math.pi * obj.r:.3f}"))
        rows.append(("面积", f"{math.pi * obj.r ** 2:.3f}"))
    elif n == "RegularPolygon":
        title = f"正{obj.n}边形"
        rows.append(("边数", f"{obj.n}"))
        if len(obj.verts) >= 2:
            side = math.hypot(obj.verts[0][0] - obj.verts[1][0],
                              obj.verts[0][1] - obj.verts[1][1])
            rows.append(("边长", f"{side:.3f}"))
            rows.append(("周长", f"{obj.n * side:.3f}"))
        if obj.r > 0:
            rows.append(("面积", f"{0.5 * obj.n * obj.r ** 2 * math.sin(2 * math.pi / obj.n):.3f}"))
        rows.append(("中心", f"({obj.center.x:.2f}, {obj.center.y:.2f})"))
    elif n == "Ellipse":
        a = math.hypot(obj.ux, obj.uy)
        b = math.hypot(obj.vx, obj.vy)
        rows.append(("半轴 a", f"{a:.3f}"))
        rows.append(("半轴 b", f"{b:.3f}"))
        rows.append(("面积", f"{math.pi * abs(obj.ux * obj.vy - obj.uy * obj.vx):.3f}"))
    elif n == "AngleMeasure":
        rows.append(("角度", f"{obj.degrees:.2f}°"))
    elif n == "RatioMeasure":
        rows.append(("长度₁", f"{obj.l1:.3f}"))
        rows.append(("长度₂", f"{obj.l2:.3f}"))
        if obj.den:
            rows.append(("比值", f"{obj.num / obj.den:.3f}"))
        else:
            rows.append(("比值", "∞"))
    elif n == "Ray":
        rows.append(("端点", f"({obj.origin.x:.2f}, {obj.origin.y:.2f})"))
    elif n == "TextObject":
        rows.append(("内容", obj.text))
    elif n == "CubicBezier":
        rows.append(("控制点", "4 个"))
    elif n == "PointOnObject":
        rows.append(("参数 t", f"{obj.t:.3f}"))
    elif n == "DivisionPoint":
        rows.append(("比例 t", f"{obj.t:.3f}"))
    elif hasattr(obj, "dx") and hasattr(obj, "dy"):      # 方向直线类
        rows.append(("方向", f"({obj.dx:.2f}, {obj.dy:.2f})"))
    return title, rows


class InfoPanel(QWidget):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setObjectName("infoPanel")
        self.canvas = canvas
        self.setFixedWidth(215)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(5)
        self._title = QLabel(self)
        self._body = QLabel(self)
        self._body.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._body)

        self._apply_style()
        canvas.doc.changed.connect(self.refresh)
        theme.bus.changed.connect(lambda _: (self._apply_style(), self.refresh()))
        self.hide()

    def _apply_style(self):
        self._title.setStyleSheet(
            f"color:{theme.INK.name()};font-weight:700;font-size:13px;")
        self._body.setStyleSheet(f"color:{theme.SUBINK.name()};font-size:11px;")
        self._body.setFont(theme.LABEL_FONT)

    def refresh(self):
        sel = [o for o in self.canvas.doc.objects if o.selected]
        if not sel:
            self.hide()
            return
        if len(sel) == 1:
            title, rows = describe(sel[0])
            self._title.setText(title)
            self._body.setText("\n".join(f"{k}  {v}" for k, v in rows))
        else:
            cnt = Counter(_CN.get(type(o).__name__, type(o).__name__) for o in sel)
            self._title.setText(f"已选 {len(sel)} 个对象")
            self._body.setText("\n".join(f"{k} × {v}" for k, v in cnt.items()))
        self.adjustSize()
        self.reposition()
        self.show()
        self.raise_()

    def reposition(self):
        self.move(self.canvas.width() - self.width() - 16, 14)