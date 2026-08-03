"""图表对象：饼状图 / 柱状图，数据可编辑。"""
from PySide6.QtCore import QRectF
from PySide6.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QFormLayout, QDoubleSpinBox

from core.registry import register_geo, register_renderer
from media.base import MediaObject
from ui import theme

CHART_COLORS = ["#1971c2", "#e8590c", "#2f9e44", "#f08c00", "#9c36b5", "#0c8599"]


def _edit_data_dialog(canvas, title, data):
    """通用的数据编辑对话框，返回新数据列表（或 None 表示取消）。"""
    dlg = QDialog(canvas)
    dlg.setWindowTitle(title)
    layout = QVBoxLayout(dlg)
    form = QFormLayout()
    spins = []
    for i, val in enumerate(data):
        sb = QDoubleSpinBox()
        sb.setRange(-1e6, 1e6)
        sb.setValue(val)
        form.addRow(f"数值 {i + 1}:", sb)
        spins.append(sb)
    layout.addLayout(form)
    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addWidget(btns)
    if dlg.exec():
        return [sb.value() for sb in spins]
    return None


@register_geo("PieChartObject")
class PieChartObject(MediaObject):
    def __init__(self, x, y, data=None, width=5.0, height=5.0):
        super().__init__(x, y, width, height)
        self.data = data if data is not None else [30.0, 45.0, 25.0]
        self.colors = CHART_COLORS

    def dump(self):
        d = super().dump()
        d["data"] = self.data
        return d

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"], params.get("data"),
                   params.get("width", 5.0), params.get("height", 5.0))

    def edit(self, canvas):
        new_data = _edit_data_dialog(canvas, "编辑饼图数据", self.data)
        if new_data is not None:
            self.data = new_data


@register_renderer(PieChartObject)
def draw_pie(p, obj, view):
    rect = obj.screen_rect(view)
    total = sum(abs(v) for v in obj.data) or 1.0
    start = 0.0
    for i, val in enumerate(obj.data):
        span = abs(val) / total * 360.0
        color = obj.colors[i % len(obj.colors)]
        p.setBrush(theme.brush(color))
        p.setPen(theme.pen(theme.BG_TOP, 1))
        p.drawPie(rect.toRect(), int(start * 16), int(span * 16))
        start += span
    if obj.selected:
        p.setPen(theme.pen(theme.SELECTED, 2))
        p.setBrush(theme.brush("transparent"))
        p.drawRect(rect)


@register_geo("BarChartObject")
class BarChartObject(MediaObject):
    def __init__(self, x, y, data=None, width=6.0, height=4.0):
        super().__init__(x, y, width, height)
        self.data = data if data is not None else [40.0, 70.0, 25.0, 55.0]
        self.colors = CHART_COLORS

    def dump(self):
        d = super().dump()
        d["data"] = self.data
        return d

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"], params.get("data"),
                   params.get("width", 6.0), params.get("height", 4.0))

    def edit(self, canvas):
        new_data = _edit_data_dialog(canvas, "编辑柱状图数据", self.data)
        if new_data is not None:
            self.data = new_data


@register_renderer(BarChartObject)
def draw_bar(p, obj, view):
    rect = obj.screen_rect(view)
    n = len(obj.data)
    if n == 0:
        return
    max_val = max(abs(v) for v in obj.data) or 1.0
    slot = rect.width() / n
    bar_w = slot * 0.5
    for i, val in enumerate(obj.data):
        h = abs(val) / max_val * rect.height() * 0.85
        x = rect.x() + i * slot + (slot - bar_w) / 2
        color = obj.colors[i % len(obj.colors)]
        p.setBrush(theme.brush(color))
        p.setPen(theme.pen(theme.BG_TOP, 1))
        p.drawRect(QRectF(x, rect.bottom() - h, bar_w, h))
    if obj.selected:
        p.setPen(theme.pen(theme.SELECTED, 2))
        p.setBrush(theme.brush("transparent"))
        p.drawRect(rect)