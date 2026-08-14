"""约束创建工具集。"""
from PySide6.QtWidgets import QInputDialog
from core.registry import register_tool
from tools.base import Tool, point_or_snap
from ..types.distance import DistanceConstraint
from ..types.fixed import FixedConstraint
from ..types.horizontal import HorizontalConstraint
from ..types.vertical import VerticalConstraint
from ..types.angle import AngleConstraint
from ..types.parallel import ParallelConstraint
from ..types.perpendicular import PerpendicularConstraint
from ..types.collinear import CollinearConstraint

def _extract_points(hit):
    """智能提取几何对象的定义点（支持点、线段、直线、射线）。"""
    if hit is None: return []
    if hasattr(hit, "x") and hasattr(hit, "y") and not hasattr(hit, "a"):
        return [hit]
    if hasattr(hit, "a") and hasattr(hit, "b"):
        return [hit.a, hit.b]
    if hasattr(hit, "center") and hasattr(hit, "through"):
        return [hit.center, hit.through]
    return []

# ───────── 距离 ─────────
@register_tool(name="距离约束", order=501, panel="constraint", icon="distance", hint="点击两点，输入距离表达式")
class DistanceConstraintTool(Tool):
    def __init__(self): self.pts = []
    def activated(self, canvas): self.pts = []
    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if not pt: return
        self.pts.append(pt)
        if len(self.pts) == 2:
            expr, ok = QInputDialog.getText(canvas, "距离约束", "距离表达式（如 5, a*2）：", text="5")
            if ok and expr.strip():
                canvas.doc.add_constraint(DistanceConstraint(self.pts[0], self.pts[1], expr.strip()))
            self.pts = []

# ───────── 固定 ─────────
@register_tool(name="固定约束", order=502, panel="constraint", icon="point", hint="点击一个点，将其固定在当前位置")
class FixedConstraintTool(Tool):
    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if pt: canvas.doc.add_constraint(FixedConstraint(pt, pt.x, pt.y))

# ───────── 水平 ─────────
@register_tool(name="水平约束", order=503, panel="constraint", icon="constraint_horizontal", hint="点击两点，使它们 Y 坐标相同")
class HorizontalConstraintTool(Tool):
    def __init__(self): self.pts = []
    def activated(self, canvas): self.pts = []
    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if not pt: return
        self.pts.append(pt)
        if len(self.pts) == 2:
            canvas.doc.add_constraint(HorizontalConstraint(self.pts[0], self.pts[1]))
            self.pts = []

# ───────── 竖直 ─────────
@register_tool(name="竖直约束", order=504, panel="constraint", icon="constraint_vertical", hint="点击两点，使它们 X 坐标相同")
class VerticalConstraintTool(Tool):
    def __init__(self): self.pts = []
    def activated(self, canvas): self.pts = []
    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if not pt: return
        self.pts.append(pt)
        if len(self.pts) == 2:
            canvas.doc.add_constraint(VerticalConstraint(self.pts[0], self.pts[1]))
            self.pts = []

# ───────── 角度 ─────────
@register_tool(name="角度约束", order=505, panel="constraint", icon="constraint_angle", hint="依次点击：边1上的点、顶点、边2上的点")
class AngleConstraintTool(Tool):
    def __init__(self): self.pts = []
    def activated(self, canvas): self.pts = []
    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if not pt: return
        self.pts.append(pt)
        if len(self.pts) == 3:
            expr, ok = QInputDialog.getText(canvas, "角度约束", "夹角表达式（度，如 90）：", text="90")
            if ok and expr.strip():
                p1, v, p2 = self.pts
                canvas.doc.add_constraint(AngleConstraint(p1, v, p2, expr.strip()))
            self.pts = []

# ───────── 平行 / 垂直 / 共线 (支持点击线段自动提取端点) ─────────
class LineConstraintTool(Tool):
    constraint_cls = None
    n_points = 4
    def __init__(self): self.pts = []
    def activated(self, canvas): self.pts = []
    def press(self, canvas, wpt, hit):
        extracted = _extract_points(hit)
        if extracted:
            self.pts.extend(extracted)
        else:
            pt = point_or_snap(canvas, wpt, hit)
            if pt: self.pts.append(pt)
            
        if len(self.pts) >= self.n_points:
            canvas.doc.add_constraint(self.constraint_cls(*self.pts[:self.n_points])) # pyright: ignore[reportOptionalCall]
            self.pts = []

@register_tool(name="平行约束", order=506, panel="constraint", icon="constraint_parallel", hint="点击两条线段/直线，使它们平行")
class ParallelTool(LineConstraintTool):
    constraint_cls = ParallelConstraint

@register_tool(name="垂直约束", order=507, panel="constraint", icon="constraint_perpendicular", hint="点击两条线段/直线，使它们垂直")
class PerpendicularTool(LineConstraintTool):
    constraint_cls = PerpendicularConstraint

@register_tool(name="共线约束", order=508, panel="constraint", icon="constraint_collinear", hint="点击三个点，使它们共线")
class CollinearTool(LineConstraintTool):
    constraint_cls = CollinearConstraint
    n_points = 3