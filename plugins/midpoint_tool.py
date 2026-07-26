"""中点插件：依次点两个点，得到它们连线段的中点（从动，拖动端点中点跟随）。"""
from core.registry import register_tool
from geo.division import DivisionPoint
from tools.base import Tool, point_or_snap


@register_tool(name="中点", shortcut="M", order=20, icon="midpoint", panel="menu",
               hint="依次点击两个点，得到它们之间线段的中点（拖动端点中点始终跟随）")
class MidpointTool(Tool):
    def __init__(self):
        self.first = None

    def activated(self, canvas):
        self.first = None

    def deactivated(self, canvas):
        self.first = None

    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if self.first is None:
            self.first = pt
            canvas.doc.set_selection([pt])
        else:
            if pt is not self.first:
                canvas.doc.add(DivisionPoint(self.first, pt, 0.5))
            self.first = None
            canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.first = None
        canvas.doc.set_selection([])
        canvas.update()