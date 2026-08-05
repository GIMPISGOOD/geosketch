"""变换对象：TransformDriver / TransformPoint / IterPoint / InvertedCircle 等。"""

import math

from PySide6.QtCore import Qt

from core.registry import register_geo, register_renderer
from core.variables import evaluate, get_store

from geo.base import GeoObject
from geo.points import AbstractPoint
from ui import theme

from transforms.base import (
    eval_num,
    identity,
    translation,
    rotation_matrix,
    scale_matrix,
    reflect_matrix,
    solve_affine,
    apply_matrix,
)


# ============================================================
# 变换驱动器
# ============================================================

@register_geo("TransformDriver")
class TransformDriver(GeoObject):
    """变换驱动器：保存变换类型、参数点、参数表达式，并实时计算变换。"""

    expr_driver = True

    def __init__(self, kind, points=(), segments=(), circles=(), exprs=None):
        self.kind = kind
        self._points = list(points)
        self._segments = list(segments)
        self._circles = list(circles)
        self.exprs = dict(exprs or {})

        objs = self._points + self._segments + self._circles

        unique = []
        idx = {}
        for o in objs:
            if id(o) not in idx:
                idx[id(o)] = len(unique)
                unique.append(o)

        super().__init__(parents=tuple(unique))

        self.point_idxs = [idx[id(o)] for o in self._points]
        self.segment_idxs = [idx[id(o)] for o in self._segments]
        self.circle_idxs = [idx[id(o)] for o in self._circles]

        self.ready = False
        self.similarity = False
        self.matrix = identity()
        self.inv_center = (0.0, 0.0)
        self.inv_r2 = 1.0

        self.recompute()

    # ---------------- 重算 ----------------

    def recompute(self):
        self.ready = False
        self.similarity = False
        self.matrix = identity()
        self.inv_center = (0.0, 0.0)
        self.inv_r2 = 1.0

        pts = self._points
        segs = self._segments
        circs = self._circles
        ex = self.exprs
        kind = self.kind

        # ---------- 平移 ----------
        if kind == "translate":
            mode = ex.get("mode", "expr")

            if mode == "expr":
                dx = eval_num(ex.get("dx", "0"))
                dy = eval_num(ex.get("dy", "0"))
                self.matrix = translation(dx, dy)
                self.ready = True
                self.similarity = True

            elif mode == "points":
                if len(pts) >= 2 and pts[0].exists and pts[1].exists:
                    dx = pts[1].x - pts[0].x
                    dy = pts[1].y - pts[0].y
                    self.matrix = translation(dx, dy)
                    self.ready = True
                    self.similarity = True

            elif mode == "segment":
                if segs:
                    seg = segs[0]
                    p1 = p2 = None

                    if hasattr(seg, "a") and hasattr(seg, "b"):
                        p1, p2 = seg.a, seg.b
                    elif hasattr(seg, "origin") and hasattr(seg, "through"):
                        p1, p2 = seg.origin, seg.through

                    if p1 is not None and p2 is not None and p1.exists and p2.exists:
                        dx = p2.x - p1.x
                        dy = p2.y - p1.y
                        self.matrix = translation(dx, dy)
                        self.ready = True
                        self.similarity = True

        # ---------- 旋转 ----------
        elif kind == "rotate":
            angle = eval_num(ex.get("angle", "0"))
            cx = cy = 0.0

            if pts:
                p = pts[0]
                if p.exists:
                    cx, cy = p.x, p.y

            self.matrix = rotation_matrix(cx, cy, angle)
            self.ready = True
            self.similarity = True

        # ---------- 缩放 ----------
        elif kind == "scale":
            mode = ex.get("mode", "expr")
            s = 1.0
            ok = False

            if mode == "ratio":
                if len(segs) >= 2 and hasattr(segs[0], "length") and hasattr(segs[1], "length"):
                    l1 = segs[0].length()
                    l2 = segs[1].length()
                    if abs(l2) > 1e-12:
                        s = l1 / l2
                        ok = True
            else:
                s = eval_num(ex.get("factor", "1"), 1.0)
                ok = True

            if ok:
                cx = cy = 0.0
                if pts:
                    p = pts[0]
                    if p.exists:
                        cx, cy = p.x, p.y

                self.matrix = scale_matrix(cx, cy, s)
                self.ready = True
                self.similarity = True

        # ---------- 轴对称反射 ----------
        elif kind == "reflect":
            if len(pts) >= 2 and pts[0].exists and pts[1].exists:
                m = reflect_matrix(pts[0].x, pts[0].y, pts[1].x, pts[1].y)
                if m is not None:
                    self.matrix = m
                    self.ready = True
                    self.similarity = True

        # ---------- 中心对称 ----------
        elif kind == "symmetry":
            cx = cy = 0.0
            if pts:
                p = pts[0]
                if p.exists:
                    cx, cy = p.x, p.y

            self.matrix = (
                -1.0, 0.0, 2.0 * cx,
                0.0, -1.0, 2.0 * cy
            )
            self.ready = True
            self.similarity = True

        # ---------- 自定义仿射：矩阵表达式 ----------
        elif kind == "affine":
            a = eval_num(ex.get("a", "1"))
            b = eval_num(ex.get("b", "0"))
            c = eval_num(ex.get("c", "0"))
            d = eval_num(ex.get("d", "0"))
            e = eval_num(ex.get("e", "1"))
            f = eval_num(ex.get("f", "0"))

            self.matrix = (a, b, c, d, e, f)
            self.ready = True
            self.similarity = False

        # ---------- 自定义仿射：三对应点 ----------
        elif kind == "affine_pts":
            if len(pts) >= 6 and all(p.exists for p in pts[:6]):
                src = [(pts[i].x, pts[i].y) for i in range(3)]
                dst = [(pts[i].x, pts[i].y) for i in range(3, 6)]
                m = solve_affine(src, dst)

                if m is not None:
                    self.matrix = m
                    self.ready = True
                    self.similarity = False

        # ---------- 圆反演 ----------
        elif kind == "invert":
            center = None
            radius = None

            if circs:
                cobj = circs[0]
                if getattr(cobj, "exists", True) and hasattr(cobj, "center") and hasattr(cobj, "r"):
                    center = (cobj.center.x, cobj.center.y)
                    radius = cobj.r

            elif pts:
                p = pts[0]
                if p.exists:
                    center = (p.x, p.y)
                    radius = eval_num(ex.get("radius", "1"), 1.0)

            if center is not None and radius is not None and radius > 1e-12:
                self.inv_center = center
                self.inv_r2 = radius * radius
                self.ready = True
                self.similarity = False

    # ---------------- 应用 ----------------

    def apply_point(self, x, y):
        if not self.ready:
            return None

        if self.kind == "invert":
            cx, cy = self.inv_center
            dx = x - cx
            dy = y - cy
            d2 = dx * dx + dy * dy

            if d2 < 1e-12:
                return None

            k = self.inv_r2 / d2
            return (cx + dx * k, cy + dy * k)

        return apply_matrix(self.matrix, x, y)

    def moved_points(self):
        # 变量变化后触发依赖它的变换点重算
        return [self]

    def distance_to(self, x, y):
        return None

    # ---------------- 序列化 ----------------

    def dump(self):
        return {
            "kind": self.kind,
            "exprs": self.exprs,
            "point_idxs": self.point_idxs,
            "segment_idxs": self.segment_idxs,
            "circle_idxs": self.circle_idxs,
        }

    @classmethod
    def build(cls, parents, params):
        pts = [parents[i] for i in params.get("point_idxs", [])]
        segs = [parents[i] for i in params.get("segment_idxs", [])]
        circs = [parents[i] for i in params.get("circle_idxs", [])]

        return cls(
            params.get("kind", "translate"),
            points=pts,
            segments=segs,
            circles=circs,
            exprs=params.get("exprs", {})
        )


# ============================================================
# 变换点
# ============================================================

@register_geo("TransformPoint")
class TransformPoint(AbstractPoint):
    """由 TransformDriver 作用于 source 点得到的从动点。"""

    def __init__(self, driver, source):
        super().__init__(parents=(driver, source))
        self.driver = driver
        self.source = source
        self.recompute()

    def recompute(self):
        if not getattr(self.source, "exists", True):
            self.exists = False
            return

        if not self.driver.ready:
            self.exists = False
            return

        if not hasattr(self.source, "x") or not hasattr(self.source, "y"):
            self.exists = False
            return

        p = self.driver.apply_point(self.source.x, self.source.y)

        if p is None:
            self.exists = False
            return

        self.x, self.y = p
        self.exists = True

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


# ============================================================
# 圆的轴点：用于把圆经仿射变换映射成椭圆
# ============================================================

@register_geo("CircleAxisPoint")
class CircleAxisPoint(AbstractPoint):
    """圆上的辅助轴点：axis=0 → 圆心右侧 r；axis=1 → 圆心上方 r。"""

    def __init__(self, circle, axis=0):
        super().__init__(parents=(circle,))
        self.circle = circle
        self.axis = int(axis)
        self.recompute()

    def recompute(self):
        c = self.circle

        if not getattr(c, "exists", True):
            self.exists = False
            return

        if self.axis == 0:
            self.x = c.center.x + c.r
            self.y = c.center.y
        else:
            self.x = c.center.x
            self.y = c.center.y + c.r

        self.exists = True

    def dump(self):
        return {"axis": self.axis}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], params.get("axis", 0))


# ============================================================
# 反演圆
# ============================================================

@register_geo("InvertedCircle")
class InvertedCircle(GeoObject):
    """圆在反演圆下的像。若原圆经过反演中心，则不存在（退化为直线）。"""

    def __init__(self, driver, source):
        super().__init__(parents=(driver, source))
        self.driver = driver
        self.source = source
        self.cx = 0.0
        self.cy = 0.0
        self.r = 0.0
        self.recompute()

    def recompute(self):
        drv = self.driver
        src = self.source

        if drv.kind != "invert" or not drv.ready:
            self.exists = False
            return

        if not getattr(src, "exists", True):
            self.exists = False
            return

        # 支持 Circle / InvertedCircle
        if hasattr(src, "center") and hasattr(src, "r"):
            sx = src.center.x
            sy = src.center.y
            sr = src.r
        elif hasattr(src, "cx") and hasattr(src, "cy") and hasattr(src, "r"):
            sx = src.cx
            sy = src.cy
            sr = src.r
        else:
            self.exists = False
            return

        ox, oy = drv.inv_center
        R2 = drv.inv_r2

        dx = sx - ox
        dy = sy - oy
        d2 = dx * dx + dy * dy
        denom = d2 - sr * sr

        if abs(denom) < 1e-9:
            self.exists = False
            return

        k = R2 / denom

        self.cx = ox + dx * k
        self.cy = oy + dy * k
        self.r = abs(R2 * sr / denom)
        self.exists = True

    def point_at(self, t):
        ang = 2.0 * math.pi * t
        return (self.cx + self.r * math.cos(ang),
                self.cy + self.r * math.sin(ang))

    def project(self, x, y):
        return (math.atan2(y - self.cy, x - self.cx) / (2.0 * math.pi)) % 1.0

    def distance_to(self, x, y):
        return abs(math.hypot(x - self.cx, y - self.cy) - self.r)

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_renderer(InvertedCircle)
def draw_inverted_circle(p, obj, view):
    if not obj.exists:
        return

    c = view.to_screen(obj.cx, obj.cy)

    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.CIRCLE, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, obj.r * view.scale, obj.r * view.scale)


# ============================================================
# 迭代点：用于数列点 / 分形迭代
# ============================================================

@register_geo("IterPoint")
class IterPoint(AbstractPoint):
    """迭代点：P_{n+1} = (fx(x,y,n), fy(x,y,n))。"""

    expr_driver = True

    def __init__(self, prev, n, expr_x, expr_y):
        super().__init__(parents=(prev,))
        self.prev = prev
        self.n = int(n)
        self.expr_x = expr_x
        self.expr_y = expr_y
        self.recompute()

    def recompute(self):
        if not getattr(self.prev, "exists", True):
            self.exists = False
            return

        vd = get_store().as_dict()
        vd["x"] = self.prev.x
        vd["y"] = self.prev.y
        vd["n"] = float(self.n)

        x = evaluate(self.expr_x, vd)
        y = evaluate(self.expr_y, vd)

        if x is None or y is None:
            self.exists = False
            return

        self.x = float(x)
        self.y = float(y)
        self.exists = True

    def moved_points(self):
        return [self]

    def dump(self):
        return {
            "n": self.n,
            "expr_x": self.expr_x,
            "expr_y": self.expr_y,
        }

    @classmethod
    def build(cls, parents, params):
        return cls(
            parents[0],
            params.get("n", 1),
            params.get("expr_x", "x"),
            params.get("expr_y", "y"),
        )