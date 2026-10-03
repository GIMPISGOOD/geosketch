"""圆相关约束：同心、等半径、相切（圆-圆、线-圆）。"""
import math

from ..base import GeometricConstraint, register_constraint


def _dist(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


# ═══════════════ 1. 同心约束 ═══════════════
@register_constraint("concentric")
class ConcentricConstraint(GeometricConstraint):
    """同心：两个圆共享同一个圆心。"""

    def __init__(self, c1, c2):
        super().__init__()
        self.c1, self.c2 = c1, c2

    def involved_points(self):
        return [self.c1.center, self.c2.center]

    def residual(self):
        return [
            self.c1.center.x - self.c2.center.x,
            self.c1.center.y - self.c2.center.y
        ]
    # ★ 解析雅可比（2 行残差 → 2 行雅可比）
    # R = [c1.x − c2.x,  c1.y − c2.y]
    def _jacobian_analytic(self, vars_map):
        n_cols = 2 * len(vars_map)
        # ★ 必须是 2 行，与 residual() 的 2 个分量对应
        jac = [[0.0] * n_cols,
               [0.0] * n_cols]
        if id(self.c1.center) in vars_map:
            idx = vars_map[id(self.c1.center)]
            jac[0][idx * 2]     =  1.0   # ∂R₁/∂c1.x
            jac[1][idx * 2 + 1] =  1.0   # ∂R₂/∂c1.y
        if id(self.c2.center) in vars_map:
            idx = vars_map[id(self.c2.center)]
            jac[0][idx * 2]     = -1.0   # ∂R₁/∂c2.x
            jac[1][idx * 2 + 1] = -1.0   # ∂R₂/∂c2.y
        return jac
    
    def dump(self):
        return {"c1": self.c1.id, "c2": self.c2.id}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["c1"]], obj_map[params["c2"]])


# ═══════════════ 2. 等半径约束 ═══════════════
@register_constraint("equal_radius")
class EqualRadiusConstraint(GeometricConstraint):
    """等半径：两个圆的半径相等。"""

    def __init__(self, c1, c2):
        super().__init__()
        self.c1, self.c2 = c1, c2

    def involved_points(self):
        return [self.c1.center, self.c1.through,
                self.c2.center, self.c2.through]

    def residual(self):
        r1 = _dist(self.c1.center, self.c1.through)
        r2 = _dist(self.c2.center, self.c2.through)
        return [r1 - r2]

    # ★ 解析雅可比（符号修正版）
    # R = r₁ − r₂
    # ∂r₁/∂c₁ = −u₁   ∂r₁/∂t₁ = +u₁
    # ∂(−r₂)/∂c₂ = +u₂   ∂(−r₂)/∂t₂ = −u₂
    def _jacobian_analytic(self, vars_map):
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]
        c1, t1 = self.c1.center, self.c1.through
        c2, t2 = self.c2.center, self.c2.through
        r1 = _dist(c1, t1)
        r2 = _dist(c2, t2)
        if r1 < 1e-9 or r2 < 1e-9:
            return jac

        u1x = (t1.x - c1.x) / r1
        u1y = (t1.y - c1.y) / r1
        u2x = (t2.x - c2.x) / r2
        u2y = (t2.y - c2.y) / r2

        # ★ 注意 c1 和 t1 的符号与 c2 和 t2 相反
        for p, gx, gy in ((c1, -u1x, -u1y),   # ∂R/∂c₁ = −u₁
                          (t1,  u1x,  u1y),   # ∂R/∂t₁ = +u₁
                          (c2,  u2x,  u2y),   # ∂R/∂c₂ = +u₂
                          (t2, -u2x, -u2y)):  # ∂R/∂t₂ = −u₂
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2]     = gx
                jac[0][idx * 2 + 1] = gy
        return jac

    def dump(self):
        return {"c1": self.c1.id, "c2": self.c2.id}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["c1"]], obj_map[params["c2"]])


# ═══════════════ 3. 圆与圆相切 ═══════════════
@register_constraint("tangent_circles")
class TangentCirclesConstraint(GeometricConstraint):
    """两圆相切。"""

    def __init__(self, c1, c2, mode="outer"):
        super().__init__()
        self.c1, self.c2 = c1, c2
        self.mode = mode

    def involved_points(self):
        return [self.c1.center, self.c1.through,
                self.c2.center, self.c2.through]

    def residual(self):
        d = _dist(self.c1.center, self.c2.center)
        r1 = _dist(self.c1.center, self.c1.through)
        r2 = _dist(self.c2.center, self.c2.through)
        if self.mode == "inner":
            return [d + r2 - r1]
        else:
            return [d - (r1 + r2)]

    # ★ P1-6 新增：解析雅可比（与 TangentCC 同构）
    def _jacobian_analytic(self, vars_map):
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]

        c1, t1 = self.c1.center, self.c1.through
        c2, t2 = self.c2.center, self.c2.through
        dx = c2.x - c1.x
        dy = c2.y - c1.y
        d = math.hypot(dx, dy)
        r1 = _dist(c1, t1)
        r2 = _dist(c2, t2)
        if d < 1e-9 or r1 < 1e-9 or r2 < 1e-9:
            return jac

        ux, uy = dx / d, dy / d
        u1x = (t1.x - c1.x) / r1
        u1y = (t1.y - c1.y) / r1
        u2x = (t2.x - c2.x) / r2
        u2y = (t2.y - c2.y) / r2

        if self.mode != "inner":
            # 外切：R = d − r1 − r2
            dc1x, dc1y = u1x - ux, u1y - uy
            dt1x, dt1y = -u1x, -u1y
            dc2x, dc2y = ux + u2x, uy + u2y
            dt2x, dt2y = -u2x, -u2y
        else:
            # 内切：R = d + r2 − r1
            dc1x, dc1y = u1x - ux, u1y - uy
            dt1x, dt1y = -u1x, -u1y
            dc2x, dc2y = ux - u2x, uy - u2y
            dt2x, dt2y = u2x, u2y

        for p, gx, gy in ((c1, dc1x, dc1y),
                          (t1, dt1x, dt1y),
                          (c2, dc2x, dc2y),
                          (t2, dt2x, dt2y)):
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2] = gx
                jac[0][idx * 2 + 1] = gy
        return jac

    def dump(self):
        return {"c1": self.c1.id, "c2": self.c2.id, "mode": self.mode}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["c1"]], obj_map[params["c2"]],
                   params.get("mode", "outer"))


# ═══════════════ 4. 直线与圆相切 ═══════════════
@register_constraint("tangent_line_circle")
class TangentLineCircleConstraint(GeometricConstraint):
    """直线/线段与圆相切：圆心到直线的距离等于半径。"""

    def __init__(self, line, circle):
        super().__init__()
        self.line, self.circle = line, circle

    def involved_points(self):
        return [self.line.a, self.line.b,
                self.circle.center, self.circle.through]

    def residual(self):
        ax, ay = self.line.a.x, self.line.a.y
        bx, by = self.line.b.x, self.line.b.y
        cx, cy = self.circle.center.x, self.circle.center.y
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-9:
            return [0.0]
        dist = abs(dx * (ay - cy) - dy * (ax - cx)) / L
        r = _dist(self.circle.center, self.circle.through)
        return [dist - r]

    # ★ P1-6 新增：解析雅可比
    # R = |cross|/L − r，cross = dx(ay−cy) − dy(ax−cx)
    # 使用 sign(cross) 处理绝对值导数
    def _jacobian_analytic(self, vars_map):
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]

        a, b = self.line.a, self.line.b
        ctr, thr = self.circle.center, self.circle.through
        ax, ay, bx, by = a.x, a.y, b.x, b.y
        cx, cy = ctr.x, ctr.y
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-9:
            return jac

        cross = dx * (ay - cy) - dy * (ax - cx)
        s = 1.0 if cross >= 0 else -1.0
        dist = abs(cross) / L
        r = _dist(ctr, thr)
        if r < 1e-9:
            return jac

        # ── ∂cross/∂q ──
        dc_dax = cy - by
        dc_day = bx - cx
        dc_dbx = ay - cy
        dc_dby = cx - ax
        dc_dcx = dy
        dc_dcy = -dx

        # ── ∂L/∂q ──
        dL_dax = -dx / L
        dL_day = -dy / L
        dL_dbx = dx / L
        dL_dby = dy / L

        # ── ∂(|cross|/L)/∂q = s·∂cross/∂q / L − dist·∂L/∂q / L ──
        def d_dist(q_cross, q_L):
            return s * q_cross / L - dist * q_L / L

        # ── ∂r/∂q ──
        urx = (thr.x - cx) / r
        ury = (thr.y - cy) / r

        # ∂R/∂q = ∂dist/∂q − ∂r/∂q
        for p, ddist_x, ddist_y, dr_x, dr_y in (
            (a,   d_dist(dc_dax, dL_dax), d_dist(dc_day, dL_day), 0.0, 0.0),
            (b,   d_dist(dc_dbx, dL_dbx), d_dist(dc_dby, dL_dby), 0.0, 0.0),
            (ctr, d_dist(dc_dcx, 0.0),    d_dist(dc_dcy, 0.0),   -urx, -ury),
            (thr, 0.0,                    0.0,                    urx,  ury),
        ):
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2] = ddist_x - dr_x
                jac[0][idx * 2 + 1] = ddist_y - dr_y
        return jac

    def dump(self):
        return {"line": self.line.id, "circle": self.circle.id}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["line"]], obj_map[params["circle"]])