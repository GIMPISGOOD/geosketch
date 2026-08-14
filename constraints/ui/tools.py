"""约束创建工具集（智能拾取版）。"""
from PySide6.QtWidgets import QInputDialog
from core.registry import register_tool
from tools.base import Tool, point_or_snap
from geo.points import AbstractPoint
from ..types.distance import DistanceConstraint
from ..types.fixed import FixedConstraint
from ..types.horizontal import HorizontalConstraint
from ..types.vertical import VerticalConstraint
from ..types.angle import AngleConstraint
from ..types.parallel import ParallelConstraint
from ..types.perpendicular import PerpendicularConstraint
from ..types.collinear import CollinearConstraint

def _extract_points(hit):
    """★ 智能拾取引擎：自动从几何对象中提取定义点。
    - 点 -> [点]
    - 线段/直线/射线 -> [端点a, 端点b]
    - 圆 -> [圆心, 圆周点]
    """
    if hit is None: 
        return []
    if isinstance(hit, AbstractPoint):
        return [hit]
    if hasattr(hit, "a") and hasattr(hit, "b"):
        return [hit.a, hit.b]
    if hasattr(hit, "center") and hasattr(hit, "through"):
        return [hit.center, hit.through]
    # 兼容正多边形的顶点
    if hasattr(hit, "verts") and hasattr(hit, "n"):
        verts = [c for c in getattr(hit, 'children', []) if type(c).__name__ == 'PolygonVertex']
        if verts: return verts
    return []

class BaseConstraintTool(Tool):
    """约束工具基类：统一处理智能拾取与状态机。"""
    constraint_cls = None
    n_points = 2
    needs_expr = False
    expr_title = ""
    expr_label = ""
    expr_default = ""

    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        # 1. 尝试智能提取（点线段自动拿两端点）
        extracted = _extract_points(hit)
        if extracted:
            for p in extracted:
                if p not in self.pts: # 去重
                    self.pts.append(p)
        else:
            # 2. 降级为普通磁吸建点
            pt = point_or_snap(canvas, wpt, hit)
            if pt and pt not in self.pts:
                self.pts.append(pt)
                
        # 3. 检查是否凑齐所需点数
        if len(self.pts) >= self.n_points:
            self._finalize(canvas)

    def _finalize(self, canvas):
        pts = self.pts[:self.n_points]
        if self.needs_expr:
            expr, ok = QInputDialog.getText(
                canvas, self.expr_title, self.expr_label, text=self.expr_default
            )
            if not (ok and expr.strip()):
                self.pts = []
                return
            c = self.constraint_cls(*pts, expr.strip())
        else:
            c = self.constraint_cls(*pts)
            
        canvas.doc.add_constraint(c)
        self.pts = []
        canvas.update()

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

# ───────── 距离 ─────────
@register_tool(name="距离约束", order=501, panel="constraint", icon="distance", 
               hint="★ 点击线段或两点，约束距离")
class DistanceConstraintTool(BaseConstraintTool):
    constraint_cls = DistanceConstraint
    n_points = 2
    needs_expr = True
    expr_title = "距离约束"
    expr_label = "距离表达式（如 5, a*2）："
    expr_default = "5"

# ───────── 固定 ─────────
@register_tool(name="固定约束", order=502, panel="constraint", icon="point", 
               hint="点击一个点或图形，将其固定")
class FixedConstraintTool(BaseConstraintTool):
    constraint_cls = FixedConstraint
    n_points = 1
    def _finalize(self, canvas):
        p = self.pts[0]
        c = FixedConstraint(p, p.x, p.y)
        canvas.doc.add_constraint(c)
        self.pts = []
        canvas.update()

# ───────── 水平 ─────────
@register_tool(name="水平约束", order=503, panel="constraint", icon="constraint_horizontal", 
               hint="★ 点击线段或两点，使 Y 坐标相同")
class HorizontalConstraintTool(BaseConstraintTool):
    constraint_cls = HorizontalConstraint
    n_points = 2

# ───────── 竖直 ─────────
@register_tool(name="竖直约束", order=504, panel="constraint", icon="constraint_vertical", 
               hint="★ 点击线段或两点，使 X 坐标相同")
class VerticalConstraintTool(BaseConstraintTool):
    constraint_cls = VerticalConstraint
    n_points = 2

# ───────── 角度 ─────────
@register_tool(name="角度约束", order=505, panel="constraint", icon="constraint_angle", 
               hint="依次点击：边1、顶点、边2")
class AngleConstraintTool(BaseConstraintTool):
    constraint_cls = AngleConstraint
    n_points = 3
    needs_expr = True
    expr_title = "角度约束"
    expr_label = "夹角表达式（度，如 90）："
    expr_default = "90"

# ───────── 平行 / 垂直 (需要 4 个点，即两条线段) ─────────
class LineConstraintTool(BaseConstraintTool):
    n_points = 4

@register_tool(name="平行约束", order=506, panel="constraint", icon="constraint_parallel", 
               hint="★ 依次点击两条线段，使它们平行")
class ParallelTool(LineConstraintTool):
    constraint_cls = ParallelConstraint

@register_tool(name="垂直约束", order=507, panel="constraint", icon="constraint_perpendicular", 
               hint="★ 依次点击两条线段，使它们垂直")
class PerpendicularTool(LineConstraintTool):
    constraint_cls = PerpendicularConstraint

# ───────── 共线 (需要 3 个点) ─────────
@register_tool(name="共线约束", order=508, panel="constraint", icon="constraint_collinear", 
               hint="点击三个点或线段，使它们共线")
class CollinearTool(BaseConstraintTool):
    constraint_cls = CollinearConstraint
    n_points = 3