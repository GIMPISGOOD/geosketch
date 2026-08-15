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

# ───────────────────────── 万能兜底引擎 (Fallback) ─────────────────────────
def _get_line_params(obj):
    """提取线对象的起点、方向向量和参数范围。"""
    tn = type(obj).__name__
    if tn == "Segment":
        return (obj.a.x, obj.a.y), (obj.b.x - obj.a.x, obj.b.y - obj.a.y), 0.0, 1.0
    elif tn == "Ray":
        return (obj.origin.x, obj.origin.y), (obj.through.x - obj.origin.x, obj.through.y - obj.origin.y), 0.0, float('inf')
    elif tn in ("Line", "DirectedLine", "PerpLine", "ParallelLine", "AngleBisector", "AngleDivLine", "PerpBisector"):
        if hasattr(obj, 'a') and hasattr(obj, 'b'):
            return (obj.a.x, obj.a.y), (obj.b.x - obj.a.x, obj.b.y - obj.a.y), float('-inf'), float('inf')
        elif hasattr(obj, 'point') and hasattr(obj, 'dx') and hasattr(obj, 'dy'):
            return (obj.point.x, obj.point.y), (obj.dx, obj.dy), float('-inf'), float('inf')
    return None

def _get_circle_params(obj):
    """提取圆对象的圆心和半径。"""
    tn = type(obj).__name__
    if tn in ("Circle", "ExprCircle", "ThreePointCircle"):
        if hasattr(obj, 'center') and hasattr(obj, 'r'):
            return (obj.center.x, obj.center.y), obj.r
        elif hasattr(obj, 'cx') and hasattr(obj, 'cy') and hasattr(obj, 'r'): 
            return (obj.cx, obj.cy), obj.r
    return None

def _fallback_solve(a, b):
    """通用线-线、线-圆求交（Fallback）。"""
    la = _get_line_params(a)
    lb = _get_line_params(b)
    ca = _get_circle_params(a)
    cb = _get_circle_params(b)
    
    # 1. 线 - 线
    if la and lb:
        p1, d1, tmin1, tmax1 = la
        p2, d2, tmin2, tmax2 = lb
        cross = d1[0]*d2[1] - d1[1]*d2[0]
        if abs(cross) < 1e-12: return []
        dx = p2[0] - p1[0]
        dy = p2[1] - p1[1]
        t1 = (dx*d2[1] - dy*d2[0]) / cross
        t2 = (dx*d1[1] - dy*d1[0]) / cross
        if tmin1 - 1e-9 <= t1 <= tmax1 + 1e-9 and tmin2 - 1e-9 <= t2 <= tmax2 + 1e-9:
            return [(p1[0] + t1*d1[0], p1[1] + t1*d1[1])]
        return []
        
    # 2. 线 - 圆
    if la and cb:
        p, d, tmin, tmax = la
        c, r = cb
        fx, fy = p[0] - c[0], p[1] - c[1]
        a_q = d[0]*d[0] + d[1]*d[1]
        if a_q < 1e-12: return []
        b_q = 2 * (fx*d[0] + fy*d[1])
        c_q = fx*fx + fy*fy - r*r
        disc = b_q*b_q - 4*a_q*c_q
        if disc < 0: return []
        sq = math.sqrt(max(0, disc))
        pts = []
        for t in ((-b_q - sq)/(2*a_q), (-b_q + sq)/(2*a_q)):
            if tmin - 1e-9 <= t <= tmax + 1e-9:
                pts.append((p[0] + t*d[0], p[1] + t*d[1]))
        # 相切去重
        if len(pts) == 2 and math.hypot(pts[0][0]-pts[1][0], pts[0][1]-pts[1][1]) < 1e-9:
            pts = pts[:1]
        return pts
        
    # 3. 圆 - 线
    if ca and lb:
        return _fallback_solve(b, a)
        
    return []

# ───────────────────────── 核心 API ─────────────────────────
def solve(a, b):
    """求两图形的全部交点 [(x, y), ...]。自动匹配类型（含对称与继承）。"""
    for (ta, tb), fn in INTERSECT_SOLVERS.items():
        if isinstance(a, ta) and isinstance(b, tb):
            return fn(a, b)
        if isinstance(a, tb) and isinstance(b, ta):
            return fn(b, a)
    # ★ 新增：Fallback 通用求交
    return _fallback_solve(a, b)

def has_solver(a, b) -> bool:
    for (ta, tb) in INTERSECT_SOLVERS:
        if (isinstance(a, ta) and isinstance(b, tb)) or \
           (isinstance(a, tb) and isinstance(b, ta)):
            return True
    # ★ 新增：检查 Fallback 是否支持
    if _get_line_params(a) and (_get_line_params(b) or _get_circle_params(b)):
        return True
    if _get_circle_params(a) and _get_line_params(b):
        return True
    return False

def max_intersections(a, b) -> int:
    """一对图形最多可能的交点数（用于预创建交点对象，无解时自动隐身）。"""
    na = getattr(a, "n", 0)     # 多边形边数
    nb = getattr(b, "n", 0)     
    tn_a = type(a).__name__
    tn_b = type(b).__name__
    
    line_names = {"Segment", "Line", "Ray", "DirectedLine", "PerpLine", "ParallelLine", "AngleBisector", "AngleDivLine", "PerpBisector"}
    circle_names = {"Circle", "ExprCircle", "ThreePointCircle"}
    
    if tn_a in line_names and tn_b in line_names: return 1
    if (tn_a in line_names and tn_b in circle_names) or (tn_a in circle_names and tn_b in line_names): return 2
    if tn_a in circle_names and tn_b in circle_names: return 2
    
    if na and nb:                                        # 多边形 × 多边形
        return 2 * min(na, nb)
    if na or nb:                                         # 多边形 × (圆|线段)
        n = na or nb
        other = b if na else a
        if type(other).__name__ in circle_names: return 2 * n
        if type(other).__name__ in line_names: return n
        return 2 * n
    return 2                                             # 线段×圆 / 圆×圆

# ───────────────────────── 基础求交几何 (保留原有) ─────────────────────────
def _seg_seg(p1, p2, p3, p4):
    d1x, d1y = p2[0] - p1[0], p2[1] - p1[1]
    d2x, d2y = p4[0] - p3[0], p4[1] - p3[1]
    cross = d1x * d2y - d1y * d2x
    if abs(cross) < 1e-12: return []
    ex, ey = p3[0] - p1[0], p3[1] - p1[1]
    t = (ex * d2y - ey * d2x) / cross
    u = (ex * d1y - ey * d1x) / cross
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return [(p1[0] + t * d1x, p1[1] + t * d1y)]
    return []

def _seg_circle(p1, p2, c, r):
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    fx, fy = p1[0] - c[0], p1[1] - c[1]
    a = dx * dx + dy * dy
    if a < 1e-12: return []
    b = 2 * (fx * dx + fy * dy)
    cc = fx * fx + fy * fy - r * r
    disc = b * b - 4 * a * cc
    if disc < 0: return []
    sq = math.sqrt(disc)
    pts = []
    for t in ((-b - sq) / (2 * a), (-b + sq) / (2 * a)):
        if -1e-9 <= t <= 1 + 1e-9:
            pts.append((p1[0] + t * dx, p1[1] + t * dy))
    if len(pts) == 2 and math.hypot(pts[0][0] - pts[1][0], pts[0][1] - pts[1][1]) < 1e-9:
        pts = pts[:1]
    return pts

def _circle_circle(c1, r1, c2, r2):
    dx, dy = c2[0] - c1[0], c2[1] - c1[1]
    d = math.hypot(dx, dy)
    if d < 1e-12 or d > r1 + r2 + 1e-9 or d < abs(r1 - r2) - 1e-9:
        return []
    a = (r1 * r1 - r2 * r2 + d * d) / (2 * d)
    h = math.sqrt(max(r1 * r1 - a * a, 0.0))
    mx, my = c1[0] + a * dx / d, c1[1] + a * dy / d
    px, py = h * dy / d, -h * dx / d
    if h < 1e-9: return [(mx, my)]
    return [(mx + px, my + py), (mx - px, my - py)]

# ───────────────────────── 内置求解器 ─────────────────────────
@register_solver(Segment, Segment)
def _solve_seg_seg(a, b):
    return _seg_seg((a.a.x, a.a.y), (a.b.x, a.b.y), (b.a.x, b.a.y), (b.b.x, b.b.y))

@register_solver(Segment, Circle)
def _solve_seg_circle(seg, cir):
    return _seg_circle((seg.a.x, seg.a.y), (seg.b.x, seg.b.y), (cir.center.x, cir.center.y), cir.r)

@register_solver(Circle, Circle)
def _solve_circle_circle(a, b):
    return _circle_circle((a.center.x, a.center.y), a.r, (b.center.x, b.center.y), b.r)

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
    """空心环 + 中心点（青蓝），与自由点区分；标注名字或 X{id}。"""
    qpt = view.to_screen(obj.x, obj.y)
    color = theme.SELECTED if obj.selected else theme.INTERSECT
    r = 5.5 if obj.selected else 4.5
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(theme.brush(theme.BG_TOP))
    p.drawEllipse(qpt, r, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(qpt, 1.8, 1.8)
    
    # ★ 修复重命名 Bug：优先使用用户自定义名字，否则使用 X{id}
    label = getattr(obj, "name", "") or f"X{obj.id}"
    
    # 使用 draw_math 保持与其他点一致的字体风格
    from ui.math import draw_math
    draw_math(
        p,
        qpt.x() + 9,
        qpt.y() - 8,
        label,
        13,
        theme.SELECTED if obj.selected else theme.LABEL
    )