"""图表对象：饼状图（图例+变量占比）/ 柱状图，数据支持 {表达式}。"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QFormLayout, QDoubleSpinBox

from core.registry import register_geo, register_renderer
from core.variables import eval_expr, render_template
from media.base import MediaObject, draw_media_decorations
from ui import theme

CHART_COLORS = ["#1971c2", "#e8590c", "#2f9e44", "#f08c00", "#9c36b5", "#0c8599"]


def _eval_value(v):
    """求值：数值直接返回；{表达式} 或纯表达式字符串求值。"""
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("{") and s.endswith("}") and len(s) > 2:
            s = s[1:-1].strip()
        val = eval_expr(s)
        if val is not None:
            return float(val)
    return 0.0


@register_geo("PieChartObject")
class PieChartObject(MediaObject):
    def __init__(self, x, y, data=None, labels=None, colors=None,
                 width=6.0, height=5.0):
        super().__init__(x, y, width, height)
        self.data = data if data is not None else [30.0, 45.0, 25.0]
        n = len(self.data)
        self.labels = labels or [f"项{i+1}" for i in range(n)]
        self.colors = colors or [CHART_COLORS[i % len(CHART_COLORS)] for i in range(n)]

    def get_values(self):
        return [_eval_value(v) for v in self.data]

    def dump(self):
        d = super().dump()
        d.update({"data": self.data, "labels": self.labels, "colors": self.colors})
        return d

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"], params.get("data"),
                   params.get("labels"), params.get("colors"),
                   params.get("width", 6.0), params.get("height", 5.0))

    def edit(self, canvas):
        from media.pie_wizard import PieChartWizard
        wiz = PieChartWizard(canvas, self.data, self.labels, self.colors)
        if wiz.exec():
            data, labels, colors = wiz.get_data()
            self.data, self.labels, self.colors = data, labels, colors


@register_renderer(PieChartObject)
def draw_pie(p, obj, view):
    rect = obj.screen_rect(view)
    values = obj.get_values()
    total = sum(abs(v) for v in values) or 1.0
    n = len(values)
    if n == 0:
        return

    # 饼图区（左 58%），图例区（右 42%）
    pie_zone = QRectF(rect.x(), rect.y(), rect.width() * 0.58, rect.height())
    side = min(pie_zone.width(), pie_zone.height()) * 0.9
    pie_sq = QRectF(pie_zone.center().x() - side / 2,
                    pie_zone.center().y() - side / 2, side, side)

    start = 0.0
    for i in range(n):
        span = abs(values[i]) / total * 360.0
        color = obj.colors[i] if i < len(obj.colors) else CHART_COLORS[i % len(CHART_COLORS)]
        p.setBrush(theme.brush(QColor(color)))
        p.setPen(theme.pen(theme.BG_TOP, 1))
        p.drawPie(pie_sq.toRect(), int(start * 16), int(span * 16))
        start += span

    # 图例
    legend_x = rect.x() + rect.width() * 0.62
    legend_top = rect.y() + rect.height() * 0.12
    line_h = rect.height() * 0.76 / max(n, 1)
    box = line_h * 0.55
    font_h = max(int(line_h * 0.5), 9)
    for i in range(n):
        color = obj.colors[i] if i < len(obj.colors) else CHART_COLORS[i % len(CHART_COLORS)]
        y = legend_top + i * line_h
        p.setBrush(theme.brush(QColor(color)))
        p.setPen(theme.pen(theme.LABEL, 1))
        p.drawRect(QRectF(legend_x, y + (line_h - box) / 2, box, box))
        label = render_template(obj.labels[i]) if i < len(obj.labels) else f"项{i+1}"
        pct = abs(values[i]) / total * 100
        txt = f"{label}: {values[i]:.1f} ({pct:.0f}%)"
        p.setPen(theme.pen(theme.INK, 1))
        f = p.font(); f.setPixelSize(font_h); p.setFont(f)
        p.drawText(QRectF(legend_x + box * 1.4, y, rect.width() * 0.36, line_h),
                   Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, txt)

    draw_media_decorations(p, obj, view)


@register_geo("BarChartObject")
class BarChartObject(MediaObject):
    def __init__(self, x, y, data=None, labels=None, colors=None,
                 width=6.0, height=4.0):
        super().__init__(x, y, width, height)
        self.data = data if data is not None else [40.0, 70.0, 25.0, 55.0]
        n = len(self.data)
        self.labels = labels or [f"项{i+1}" for i in range(n)]
        self.colors = colors or [CHART_COLORS[i % len(CHART_COLORS)] for i in range(n)]

    def get_values(self):
        return [_eval_value(v) for v in self.data]

    def dump(self):
        d = super().dump()
        d.update({"data": self.data, "labels": self.labels, "colors": self.colors})
        return d

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"], params.get("data"),
                   params.get("labels"), params.get("colors"),
                   params.get("width", 6.0), params.get("height", 4.0))

    def edit(self, canvas):
        from media.pie_wizard import PieChartWizard     # 复用同一向导
        wiz = PieChartWizard(canvas, self.data, self.labels, self.colors)
        if wiz.exec():
            data, labels, colors = wiz.get_data()
            self.data, self.labels, self.colors = data, labels, colors


@register_renderer(BarChartObject)
def draw_bar(p, obj, view):
    rect = obj.screen_rect(view)
    values = obj.get_values()
    n = len(values)
    if n == 0:
        return
    max_val = max(abs(v) for v in values) or 1.0
    plot = QRectF(rect.x(), rect.y(), rect.width(), rect.height() * 0.82)
    slot = plot.width() / n
    bar_w = slot * 0.5
    for i in range(n):
        h = abs(values[i]) / max_val * plot.height() * 0.95
        x = plot.x() + i * slot + (slot - bar_w) / 2
        color = obj.colors[i] if i < len(obj.colors) else CHART_COLORS[i % len(CHART_COLORS)]
        p.setBrush(theme.brush(QColor(color)))
        p.setPen(theme.pen(theme.BG_TOP, 1))
        p.drawRect(QRectF(x, plot.bottom() - h, bar_w, h))
        # 底部标签
        label = render_template(obj.labels[i]) if i < len(obj.labels) else f"项{i+1}"
        p.setPen(theme.pen(theme.INK, 1))
        fh = max(int(rect.height() * 0.06), 8)
        f = p.font(); f.setPixelSize(fh); p.setFont(f)
        p.drawText(QRectF(plot.x() + i * slot, plot.bottom() + 2, slot, rect.height() * 0.15),
                   Qt.AlignmentFlag.AlignCenter, label)
    draw_media_decorations(p, obj, view)