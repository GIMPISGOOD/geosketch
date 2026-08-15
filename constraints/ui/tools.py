"""约束创建工具集（智能拾取版）。"""
from typing import Type, Optional,Any
from PySide6.QtWidgets import QInputDialog
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from core.registry import register_tool
from tools.base import Tool, point_or_snap
from geo.points import AbstractPoint
from ui import theme

from ..base import GeometricConstraint
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
    # 兼容正多边形的顶点
    if hasattr(hit, "verts") and hasattr(hit, "n"):
        verts = [c for c in getattr(hit, 'children', []) if type(c).__name__ == 'PolygonVertex']
        if verts:
            return verts
    return []


class BaseConstraintTool(Tool):
    """约束工具基类：统一处理智能拾取、状态机与实时预览高亮。"""
    
    # ★ 修复 Pylance 报错 1 & 5：添加类型提示，明确告知检查器这是一个类，而非单纯的 None
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
        # ★ 修复 Pylance 报错 5 & 6：拦截 None 调用，消除“无法调用类型为 None 的对象”警告
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

# ───────── 下方具体的距离、固定、水平等约束工具类保持原样即可 ─────────