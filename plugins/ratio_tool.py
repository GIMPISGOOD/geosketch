# plugins/ratio_tool.py
"""比例插件：点两条线段，计算长度比。"""
import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from geo.segments import Segment
from tools.base import Tool
from ui import theme


@register_geo("RatioMeasure")
class RatioMeasure(GeoObject):
    """两条线段的长度比 len1/len2，实时刷新。"""
    def __init__(self, seg1, seg2, label_pos):
        super().__init__(parents=(seg1, seg2))
        self.seg1, self.seg2 = seg1, seg2
        self.label_pos = tuple(label_pos)
        self.l1 = self.l2 = self.ratio = 0.0
        self.recompute()

    def recompute(self):
        self.l1 = self.seg1.length()
        self.l2 = self.seg2.length()
        self.ratio = self.l1 / self.l2 if self.l2 > 1e-12 else float("inf")

    def distance_to(self, x, y):
        return math.hypot(x - self.label_pos[0], y - self.label_pos[1])

    def dump(self):
        return {"pos": list(self.label_pos)}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], params.get("pos", (0, 0)))


@register_renderer(RatioMeasure)
def draw_ratio(p, obj, view):
    color = theme.SELECTED if obj.selected else theme.MEASURE
    p.setPen(theme.pen(color))
    p.setFont(theme.LABEL_FONT)
    txt = f"{obj.l1:.2f} / {obj.l2:.2f} = {obj.ratio:.2f}"
    p.drawText(view.to_screen(*obj.label_pos) + QPointF(6, -6), txt)


@register_tool(name="比例", shortcut="R", order=25, icon="ratio", panel="menu",
               hint="依次点两条线段，计算它们的长度比")
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
                canvas.doc.add(RatioMeasure(self.first, hit, wpt))
            self.first = None
            canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.first = None
        canvas.doc.set_selection([])
        canvas.update()