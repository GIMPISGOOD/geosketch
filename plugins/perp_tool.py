# plugins/perp_tool.py —— 垂线
"""垂线插件：过一点作已知直线/线段的垂线。"""
from core.registry import register_geo, register_tool
from geo.directed_line import DirectedLine
from geo.segments import Segment
from plugins.line_tool import Line
from tools.base import Tool, point_or_snap


@register_geo("PerpLine")
class PerpLine(DirectedLine):
    """过 point 且垂直于 ref（直线/线段）的直线。"""
    def __init__(self, ref, point):
        super().__init__((ref, point), point)
        self.ref = ref
        self.recompute()

    def recompute(self):
        a, b = self.ref.a, self.ref.b
        self.dx, self.dy = -(b.y - a.y), (b.x - a.x)   # 垂直方向

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_tool(name="垂线", shortcut="H", order=30, icon="perp", panel="menu",
               hint="先点一条直线/线段，再点一个点，得到过该点的垂线")
class PerpTool(Tool):
    def __init__(self):
        self.ref = None

    def activated(self, canvas):
        self.ref = None

    def deactivated(self, canvas):
        self.ref = None

    def press(self, canvas, wpt, hit):
        if self.ref is None:
            if isinstance(hit, (Line, Segment)):
                self.ref = hit
                canvas.doc.set_selection([hit])
        else:
            pt = point_or_snap(canvas, wpt, hit)
            canvas.doc.add(PerpLine(self.ref, pt))
            self.ref = None
            canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.ref = None
        canvas.doc.set_selection([])
        canvas.update()