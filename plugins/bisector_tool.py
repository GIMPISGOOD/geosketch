# plugins/bisector_tool.py —— 角平分线
"""角平分线插件：过角的顶点作内角平分线。"""
import math

from core.registry import register_geo, register_tool
from geo.directed_line import DirectedLine
from tools.base import Tool, point_or_snap


@register_geo("AngleBisector")
class AngleBisector(DirectedLine):
    """角 (vertex,p1,p2) 的内角平分线（过顶点的直线）。"""
    def __init__(self, vertex, p1, p2):
        super().__init__((vertex, p1, p2), vertex)
        self.p1, self.p2 = p1, p2
        self.recompute()

    def recompute(self):
        v = self.point
        a1 = math.atan2(self.p1.y - v.y, self.p1.x - v.x)
        a2 = math.atan2(self.p2.y - v.y, self.p2.x - v.x)
        dx = math.cos(a1) + math.cos(a2)     # 两单位方向向量之和 = 内角平分线方向
        dy = math.sin(a1) + math.sin(a2)
        if abs(dx) < 1e-12 and abs(dy) < 1e-12:   # 平角（180°）：取垂线方向
            dx, dy = -math.sin(a1), math.cos(a1)
        self.dx, self.dy = dx, dy

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


@register_tool(name="角平分线", shortcut="K", order=32, icon="bisector", panel="menu",
               hint="先点顶点，再点角两侧的点，得到内角平分线")
class BisectorTool(Tool):
    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 3:
            v, p1, p2 = self.pts
            canvas.doc.add(AngleBisector(v, p1, p2))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()