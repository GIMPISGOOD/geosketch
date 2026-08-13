"""约束创建工具。"""
from PySide6.QtWidgets import QInputDialog
from core.registry import register_tool
from tools.base import Tool, point_or_snap
from ..types.distance import DistanceConstraint
from ..types.fixed import FixedConstraint

@register_tool(name="距离约束", order=501, panel="menu", icon="distance",
               hint="点击两点，输入距离表达式")
class DistanceConstraintTool(Tool):
    def __init__(self): self.pts = []
    def activated(self, canvas): self.pts = []
    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        self.pts.append(pt)
        if len(self.pts) == 2:
            expr, ok = QInputDialog.getText(canvas, "距离约束", "距离表达式：", text="5")
            if ok and expr.strip():
                c = DistanceConstraint(self.pts[0], self.pts[1], expr.strip())
                canvas.doc.add_constraint(c)
            self.pts = []

@register_tool(name="固定约束", order=502, panel="menu", icon="point",
               hint="点击一个点，将其固定在当前位置")
class FixedConstraintTool(Tool):
    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if pt:
            c = FixedConstraint(pt, pt.x, pt.y)
            canvas.doc.add_constraint(c)