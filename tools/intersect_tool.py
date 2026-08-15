"""交点工具：依次点两个几何图形 → 生成它们的全部交点。
支持：线段、直线、射线、圆、多边形等任意组合（自动 Fallback）。
"""
import math
from core.registry import register_tool
from geo.intersects import IntersectPoint, has_solver, max_intersections, solve
from geo.points import AbstractPoint
from tools.base import Tool

@register_tool(name="交点", shortcut="X", order=4, icon="intersect",
               hint="依次点两个图形（线段/圆/多边形/直线/射线等）求全部交点；自动去重；Esc 取消")
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
                max_i = max_intersections(self.first, hit)
                pts = solve(self.first, hit)
                
                for i in range(max_i):
                    # 1. 对象级去重：检查是否已经存在相同的 IntersectPoint 对象
                    exists = False
                    for obj in canvas.doc.objects:
                        if type(obj).__name__ == "IntersectPoint":
                            if (obj.a is self.first and obj.b is hit and obj.branch == i) or \
                               (obj.b is self.first and obj.a is hit and obj.branch == i):
                                exists = True
                                break
                    if exists:
                        continue
                        
                    # 2. 坐标级去重：检查该位置是否已经有其他点（避免在已有点上重复建点）
                    if i < len(pts):
                        px, py = pts[i]
                        too_close = False
                        tol = 1e-5 # 世界坐标容差
                        for obj in canvas.doc.objects:
                            if isinstance(obj, AbstractPoint) and obj.exists:
                                if math.hypot(obj.x - px, obj.y - py) < tol:
                                    too_close = True
                                    break
                        if too_close:
                            continue
                            
                    canvas.doc.add(IntersectPoint(self.first, hit, i))
                    
                self.first = None
                canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.first = None
        canvas.doc.set_selection([])
        canvas.update()

    def draw_overlay(self, p, view):
        return     # 保持高亮