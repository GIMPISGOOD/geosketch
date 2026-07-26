"""比例插件：点两条线段，在左上角以文本显示长度比（最简分数形式）。"""
import math
from fractions import Fraction

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from geo.segments import Segment
from tools.base import Tool
from ui import theme


@register_geo("RatioMeasure")
class RatioMeasure(GeoObject):
    """两条线段的长度比，实时刷新；以左上角 HUD 文本呈现。"""
    def __init__(self, seg1, seg2):
        super().__init__(parents=(seg1, seg2))
        self.seg1, self.seg2 = seg1, seg2
        self.l1 = self.l2 = 0.0
        self.num, self.den = 1, 1
        self.recompute()

    def recompute(self):
        self.l1 = self.seg1.length()
        self.l2 = self.seg2.length()
        ratio = self.l1 / self.l2 if self.l2 > 1e-12 else float("inf")
        if math.isfinite(ratio):
            frac = Fraction(ratio).limit_denominator(100)   # 化简为最简分数
            self.num, self.den = frac.numerator, frac.denominator
        else:
            self.num, self.den = 1, 0

    def distance_to(self, x, y):
        return None          # HUD 渲染，不在世界坐标中拾取；删线段即级联删除

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_renderer(RatioMeasure)
def draw_ratio(p, obj, view):
    # 在所有比例对象中的序号 → 左上角垂直堆叠（x=84 避开宽 58 的左侧工具栏）
    idx = sum(1 for o in view.doc.objects
              if type(o) is RatioMeasure and o.id < obj.id)
    x, y = 84.0, 30.0 + idx * 24.0
    frac_str = f"{obj.num}/{obj.den}" if obj.den != 1 else f"{obj.num}"
    color = theme.SELECTED if obj.selected else theme.MEASURE
    p.setPen(theme.pen(color))
    p.setFont(theme.LABEL_FONT)
    p.drawText(QPointF(x, y), f"P1/P2 = {frac_str}")


@register_tool(name="比例", shortcut="R", order=25, icon="ratio", panel="menu",
               hint="依次点两条线段，在左上角显示它们的长度比（最简分数）")
class RatioTool(Tool):
    def __init__(self):
        self.first = None

    def activated(self, canvas):
        self.first = None

    def deactivated(self, canvas):
        self.first = None

    def press(self, canvas, wpt, hit):
        if not isinstance(hit, Segment):
            return
        if self.first is None:
            self.first = hit
            canvas.doc.set_selection([hit])
        else:
            if hit is not self.first:
                canvas.doc.add(RatioMeasure(self.first, hit))
            self.first = None
            canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.first = None
        canvas.doc.set_selection([])
        canvas.update()