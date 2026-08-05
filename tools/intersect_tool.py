"""交点工具：依次点两个几何图形 → 生成它们的全部交点。
支持：线段×线段、线段×圆、圆×圆，以及涉及多边形的任意组合
（只要注册了求解器即可，无需改动本工具）。"""
from core.registry import register_tool
from geo.intersects import IntersectPoint, has_solver, max_intersections
from geo.points import AbstractPoint
from tools.base import Tool


@register_tool(name="交点", shortcut="X", order=4, icon="intersect",
               hint="依次点两个图形（线段/圆/多边形）求全部交点；交点可被磁吸；Esc 取消")
class IntersectTool(Tool):
    def __init__(self):
        self.first = None

    def activated(self, canvas):
        self.first = None

    def deactivated(self, canvas):
        self.first = None

    def press(self, canvas, wpt, hit):
        # 点不能作为被求交对象；其余曲线类图形均可
        if hit is None or isinstance(hit, AbstractPoint):
            return
        if self.first is None:
            self.first = hit
            canvas.doc.set_selection([hit])              # 高亮第一个图形
        else:
            if hit is not self.first and has_solver(self.first, hit):
                for i in range(max_intersections(self.first, hit)):
                    canvas.doc.add(IntersectPoint(self.first, hit, i))
            self.first = None
            canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.first = None
        canvas.doc.set_selection([])
        canvas.update()

    def draw_overlay(self, p, view):
        return     # 保持高亮