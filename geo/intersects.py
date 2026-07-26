"""通用交点框架：任意两个几何图形的交点。

核心设计：
  - INTERSECT_SOLVERS 求解器注册表：按图形类型对注册求交函数。
    新图形（如多边形）在自己的文件里注册求解器即可，本文件无需改动。
  - IntersectPoint：通用交点对象，AbstractPoint 子类 →
    磁吸、拾取、渲染、级联删除自动继承；无解时 exists=False 自动隐身，
    图形移动后重新出现（"活"的交点）。
"""
import math

from PySide6.QtCore import QPointF, Qt

from core.registry import register_geo, register_renderer
from geo.circles import Circle
from geo.points import AbstractPoint
from geo.segments import Segment
from ui import theme

# ───────────────────────── 求解器注册表 ─────────────────────────
INTERSECT_SOLVERS: dict = {}


def register_solver(shape_a, shape_b):
    """注册一对图形类型的求交函数 fn(a, b) -> [(x, y), ...]。"""
    def deco(fn):
        INTERSECT_SOLVERS[(shape_a, shape_b)] = fn
        return fn
    return deco


def solve(a, b):
    """求两图形的全部交点 [(x, y), ...]。自动匹配类型（含对称与继承）。"""
    for (ta, tb), fn in INTERSECT_SOLVERS.items():
        if isinstance(a, ta) and isinstance(b, tb):
            return fn(a, b)
        if isinstance(a, tb) and isinstance(b, ta):
            return fn(b, a)
    return []


def has_solver(a, b) -> bool:
    for (ta, tb) in INTERSECT_SOLVERS:
        if (isinstance(a, ta) and isinstance(b, tb)) or \
           (isinstance(a, tb) and isinstance(b, ta)):
            return True
    return False


def max_intersections(a, b) -> int:
    """一对图形最多可能的交点数（用于预创建交点对象，无解时自动隐身）。"""
    na, nb = getattr(a, "n", 0), getattr(b, "n", 0)     # 多边形边数
    if na and nb:                                        # 多边形 × 多边形
        return 2 * min(na, nb)
    if na or nb:                                         # 多边形 × (圆|线段)
        n = na or nb
        other = b if na else a
        return 2 * n if isinstance(other, Circle) else 2
    if isinstance(a, Segment) and isinstance(b, Segment):
        return 1
    return 2                                             # 线段×圆 / 圆×圆


# ───────────────────────── 基础求交几何 ─────────────────────────
def _seg_seg(p1, p2, p3, p4):
    """线段 p1p2 与 p3p4 的交点（0 或 1 个）。"""
    d1x, d1y = p2[0] - p1[0], p2[1] - p1[1]
    d2x, d2y = p4[0] - p3[0], p4[1] - p3[1]
    cross = d1x * d2y - d1y * d2x
    if abs(cross) < 1e-12:
        return []                                        # 平行（含共线）
    ex, ey = p3[0] - p1[0], p3[1] - p1[1]
    t = (ex * d2y - ey * d2x) / cross
    u = (ex * d1y - ey * d1x) / cross
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return [(p1[0] + t * d1x, p1[1] + t * d1y)]
    return []


def _seg_circle(p1, p2, c, r):
    """线段 p1p2 与圆 (c, r) 的交点（0/1/2 个）。"""
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    fx, fy = p1[0] - c[0], p1[1] - c[1]
    a = dx * dx + dy * dy
    if a < 1e-12:
        return []
    b = 2 * (fx * dx + fy * dy)
    cc = fx * fx + fy * fy - r * r
    disc = b * b - 4 * a * cc
    if disc < 0:
        return []
    sq = math.sqrt(disc)
    pts = []
    for t in ((-b - sq) / (2 * a), (-b + sq) / (2 * a)):
        if -1e-9 <= t <= 1 + 1e-9:
            pts.append((p1[0] + t * dx, p1[1] + t * dy))
    if len(pts) == 2 and math.hypot(pts[0][0] - pts[1][0],
                                    pts[0][1] - pts[1][1]) < 1e-9:
        pts = pts[:1]                                    # 相切去重
    return pts


def _circle_circle(c1, r1, c2, r2):
    """两圆的交点（0/1/2 个）。"""
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    if d < 1e-12 or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = c1[0] + a * dx / d, c1[1] + a * dy / d
    px, py = h * dy / d, -h * dx / d
    if h < 1e-9:
        return [(mx, my)]                                # 相切
    return [(mx + px, my + py), (mx - px, my - py)]


# ───────────────────────── 内置求解器 ─────────────────────────
@register_solver(Segment, Segment)
def _solve_seg_seg(a, b):
    return _seg_seg((a.a.x, a.a.y), (a.b.x, a.b.y),
                    (b.a.x, b.a.y), (b.b.x, b.b.y))


@register_solver(Segment, Circle)
def _solve_seg_circle(seg, cir):
    return _seg_circle((seg.a.x, seg.a.y), (seg.b.x, seg.b.y),
                       (cir.center.x, cir.center.y), cir.r)


@register_solver(Circle, Circle)
def _solve_circle_circle(a, b):
    return _circle_circle((a.center.x, a.center.y), a.r,
                          (b.center.x, b.center.y), b.r)


# ───────────────────────── 通用交点对象 ─────────────────────────
@register_geo("IntersectPoint")
class IntersectPoint(AbstractPoint):
    """两图形交点中的一个（branch 指定取第几个解）。"""

    def __init__(self, a, b, branch=0):
        super().__init__(parents=(a, b))
        self.a, self.b = a, b
        self.branch = branch
        self.recompute()

    def recompute(self):
        pts = solve(self.a, self.b)
        if self.branch < len(pts):
            self.x, self.y = pts[self.branch]
            self.exists = True
        else:
            self.exists = False

    def dump(self):
        return {"branch": self.branch}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], params.get("branch", 0))


@register_renderer(IntersectPoint)
def draw_intersect(p, obj, view):
    """空心环 + 中心点（青蓝），与自由点区分；标注 X{id}。"""
    qpt = view.to_screen(obj.x, obj.y)
    color = theme.SELECTED if obj.selected else theme.INTERSECT
    r = 5.5 if obj.selected else 4.5
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(theme.brush(theme.BG_TOP))
    p.drawEllipse(qpt, r, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(qpt, 1.8, 1.8)
    p.setPen(theme.pen(theme.LABEL))
    p.setFont(theme.LABEL_FONT)
    p.drawText(qpt + QPointF(9, -8), f"X{obj.id}")