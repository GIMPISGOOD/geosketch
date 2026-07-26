# plugins/midpoint_tool.py
"""中点插件：点线段得中点。中点是特殊点，可被磁吸。"""
from core.registry import register_geo, register_tool
from geo.points import AbstractPoint
from geo.segments import Segment
from tools.base import Tool


@register_geo("Midpoint")
class Midpoint(AbstractPoint):
    """线段中点：由线段唯一确定，不可拖动，可磁吸。"""
    def __init__(self, seg):
        super().__init__(parents=(seg,))
        self.seg = seg
        self.recompute()

    def recompute(self):
        a, b = self.seg.a, self.seg.b
        self.x, self.y = (a.x + b.x) / 2, (a.y + b.y) / 2

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0])


@register_tool(name="中点", shortcut="M", order=20, icon="midpoint", panel="menu",
               hint="点击一条线段得到它的中点（中点可被磁吸）")
class MidpointTool(Tool):
    def press(self, canvas, wpt, hit):
        if isinstance(hit, Segment):
            canvas.doc.add(Midpoint(hit))