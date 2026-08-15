"""约束创建工具集（智能拾取版）。"""
from typing import Any, Optional
from PySide6.QtWidgets import QInputDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

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
    """★ 智能拾取引擎：自动从几何对象中提取定义点。"""
    if hit is None:
        return []
    if isinstance(hit, AbstractPoint):
        return [hit]
    if hasattr(hit, "a") and hasattr(hit, "b"):
        return [hit.a, hit.b]
    if hasattr(hit, "center") and hasattr(hit, "through"):
        return [hit.center, hit.through]
    if hasattr(hit, "verts") and hasattr(hit, "n"):
        verts = [c for c in getattr(hit, 'children', []) if type(c).__name__ == 'PolygonVertex']
        if verts:
            return verts
    return []


class BaseConstraintTool(Tool):
    """约束工具基类：统一处理智能拾取、状态机与实时预览高亮。"""
    
    # ★ 修复 Pylance 报错：使用 Any 避免基类 0 参数 __init__ 导致的误报
    constraint_cls: Optional[Any] = None
    n_points: int = 2
    needs_expr: bool = False
    expr_title: str = ""
    expr_label: str = ""
    expr_default: str = ""

    def __init__(self):
        self.pts = []
        self._hover = None

    def activated(self, canvas):
        self.pts = []
        self._hover = None

    def deactivated(self, canvas):
        self.pts = []
        self._hover = None

    def press(self, canvas, wpt, hit):
        # 1. 尝试智能提取（点线段自动拿两端点）
        extracted = _extract_points(hit)
        if extracted:
            for p in extracted:
                if p not in self.pts:  # 去重
                    self.pts.append(p)
        else:
            # 2. 降级为普通磁吸建点
            pt = point_or_snap(canvas, wpt, hit)
            if pt and pt not in self.pts:
                self.pts.append(pt)

        # 3. 检查是否凑齐所需点数
        if len(self.pts) >= self.n_points:
            self._finalize(canvas)

    def move(self, canvas, wpt, hit):
        """★ 实时预览：记录悬停对象"""
        self._hover = hit

    def _finalize(self, canvas):
        if self.constraint_cls is None:
            return

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
        self._hover = None
        canvas.update()

    # ═══════ ★ 实时预览高亮 ═══════
    def draw_overlay(self, p, view):
        # 延迟导入 theme，防止潜在的循环依赖
        try:
            from ui import theme
        except Exception:
            return

        # 1. 高亮已选择的点（蓝色圆环）
        if self.pts:
            p.setPen(theme.pen(theme.ACCENT, 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for pt in self.pts:
                if hasattr(pt, 'x') and hasattr(pt, 'y'):
                    sp = view.to_screen(pt.x, pt.y)
                    p.drawEllipse(sp, 8, 8)

        # 2. 高亮悬停对象（橙色半透明）
        if self._hover is not None:
            color = QColor(theme.PREVIEW)
            color.setAlphaF(0.25)

            # 圆 / 表达式圆
            if hasattr(self._hover, 'center') and hasattr(self._hover, 'r'):
                c = view.to_screen(self._hover.center.x, self._hover.center.y)
                p.setPen(theme.dashed_pen(theme.PREVIEW, 2.0))
                p.setBrush(theme.brush(color))
                p.drawEllipse(c, self._hover.r * view.scale,
                              self._hover.r * view.scale)
            # 线段 / 直线 / 射线
            elif hasattr(self._hover, 'a') and hasattr(self._hover, 'b') \
                    and hasattr(self._hover.a, 'x'):
                p.setPen(theme.pen(theme.PREVIEW, 3.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                sa = view.to_screen(self._hover.a.x, self._hover.a.y)
                sb = view.to_screen(self._hover.b.x, self._hover.b.y)
                p.drawLine(sa, sb)
            # 点
            elif hasattr(self._hover, 'x') and hasattr(self._hover, 'y'):
                sp = view.to_screen(self._hover.x, self._hover.y)
                p.setPen(theme.pen(theme.PREVIEW, 2.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(sp, 10, 10)

        # 3. 已选点之间画连线预览
        if len(self.pts) >= 2:
            p.setPen(theme.dashed_pen(theme.ACCENT, 1.5))
            p.setBrush(Qt.BrushStyle.NoBrush)
            for i in range(len(self.pts) - 1):
                a, b = self.pts[i], self.pts[i + 1]
                if hasattr(a, 'x') and hasattr(b, 'x'):
                    p.drawLine(view.to_screen(a.x, a.y),
                               view.to_screen(b.x, b.y))


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
        if not self.pts: return
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
    
from ..types.circle_constraints import (
    ConcentricConstraint, EqualRadiusConstraint,
    TangentCirclesConstraint, TangentLineCircleConstraint
)

class BaseObjectConstraintTool(Tool):
    """对象级约束工具基类：用于拾取圆、直线等完整对象。"""
    constraint_cls = None
    n_objects = 2
    valid_types = () 
    
    def __init__(self):
        self.objs = []
        self._hover = None
        
    def activated(self, canvas):
        self.objs = []
        self._hover = None
        
    def deactivated(self, canvas):
        self.objs = []
        self._hover = None
        
    def move(self, canvas, wpt, hit):
        self._hover = hit
        
    def press(self, canvas, wpt, hit):
        if hit is not None and type(hit).__name__ in self.valid_types:
            if hit not in self.objs:
                self.objs.append(hit)
        if len(self.objs) >= self.n_objects:
            self._finalize(canvas)
            
    def _finalize(self, canvas):
        if self.constraint_cls is None: return
        c = self.constraint_cls(*self.objs[:self.n_objects])
        canvas.doc.add_constraint(c)
        self.objs = []
        canvas.update()
        
    def cancel(self, canvas):
        self.objs = []
        self._hover = None
        canvas.update()
        
    # ═══════ 实时预览高亮 ═══════
    def draw_overlay(self, p, view):
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QColor
        from ui import theme
        
        # 1. 高亮悬停对象
        if self._hover is not None and type(self._hover).__name__ in self.valid_types:
            color = QColor(theme.PREVIEW)
            color.setAlphaF(0.25)
            if hasattr(self._hover, 'center') and hasattr(self._hover, 'r'):
                c = view.to_screen(self._hover.center.x, self._hover.center.y)
                p.setPen(theme.dashed_pen(theme.PREVIEW, 2.0))
                p.setBrush(theme.brush(color))
                p.drawEllipse(c, self._hover.r * view.scale, self._hover.r * view.scale)
            elif hasattr(self._hover, 'a') and hasattr(self._hover, 'b'):
                p.setPen(theme.pen(theme.PREVIEW, 3.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                sa = view.to_screen(self._hover.a.x, self._hover.a.y)
                sb = view.to_screen(self._hover.b.x, self._hover.b.y)
                p.drawLine(sa, sb)
                
        # 2. 高亮已选对象
        for obj in self.objs:
            if hasattr(obj, 'center') and hasattr(obj, 'r'):
                c = view.to_screen(obj.center.x, obj.center.y)
                p.setPen(theme.pen(theme.ACCENT, 2.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawEllipse(c, obj.r * view.scale, obj.r * view.scale)
            elif hasattr(obj, 'a') and hasattr(obj, 'b'):
                p.setPen(theme.pen(theme.ACCENT, 3.5))
                p.setBrush(Qt.BrushStyle.NoBrush)
                sa = view.to_screen(obj.a.x, obj.a.y)
                sb = view.to_screen(obj.b.x, obj.b.y)
                p.drawLine(sa, sb)


# ───────── 同心 ─────────
@register_tool(name="同心约束", order=510, panel="constraint", icon="circle",
               hint="★ 依次点击两个圆，使它们同心")
class ConcentricTool(BaseObjectConstraintTool):
    constraint_cls = ConcentricConstraint
    n_objects = 2
    valid_types = ("Circle", "ExprCircle", "ThreePointCircle")

# ───────── 等半径 ─────────
@register_tool(name="等半径约束", order=511, panel="constraint", icon="circle",
               hint="★ 依次点击两个圆，使它们半径相等")
class EqualRadiusTool(BaseObjectConstraintTool):
    constraint_cls = EqualRadiusConstraint
    n_objects = 2
    valid_types = ("Circle", "ExprCircle", "ThreePointCircle")

# ───────── 圆与圆相切 ─────────
@register_tool(name="圆相切约束", order=512, panel="constraint", icon="circle",
               hint="★ 依次点击两个圆，使它们外切")
class TangentCirclesTool(BaseObjectConstraintTool):
    constraint_cls = TangentCirclesConstraint
    n_objects = 2
    valid_types = ("Circle", "ExprCircle", "ThreePointCircle")

# ───────── 直线与圆相切 ─────────
@register_tool(name="线圆相切约束", order=513, panel="constraint", icon="circle",
               hint="★ 点击一条线段/直线和一个圆，使它们相切")
class TangentLineCircleTool(BaseObjectConstraintTool):
    constraint_cls = TangentLineCircleConstraint
    n_objects = 2
    valid_types = ("Circle", "ExprCircle", "ThreePointCircle", "Line", "Segment")
    
    def _finalize(self, canvas):
        o1, o2 = self.objs[0], self.objs[1]
        is_o1_circle = type(o1).__name__ in ("Circle", "ExprCircle", "ThreePointCircle")
        is_o2_circle = type(o2).__name__ in ("Circle", "ExprCircle", "ThreePointCircle")
        
        # 自动识别哪个是线，哪个是圆
        if is_o1_circle and not is_o2_circle:
            c = TangentLineCircleConstraint(o2, o1)
        elif is_o2_circle and not is_o1_circle:
            c = TangentLineCircleConstraint(o1, o2)
        else:
            self.objs = []
            return
            
        canvas.doc.add_constraint(c)
        self.objs = []
        canvas.update()