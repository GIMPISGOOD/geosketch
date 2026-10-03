"""相切约束：圆-圆相切（外切/内切）、圆-线相切。"""
import math
from ..base import GeometricConstraint, register_constraint


@register_constraint("tangent_cc")
class TangentCC(GeometricConstraint):
    """圆与圆相切。
    参数：
        c1_center, c1_through: 圆1的圆心和圆周点
        c2_center, c2_through: 圆2的圆心和圆周点
        mode: "external"（外切）或 "internal"（内切）
    """

    def __init__(self, c1_center, c1_through, c2_center, c2_through,
                 mode="external"):
        super().__init__()
        self.c1_center = c1_center
        self.c1_through = c1_through
        self.c2_center = c2_center
        self.c2_through = c2_through
        self.mode = mode

    def involved_points(self):
        return [self.c1_center, self.c1_through,
                self.c2_center, self.c2_through]

    def residual(self):
        dx = self.c2_center.x - self.c1_center.x
        dy = self.c2_center.y - self.c1_center.y
        d = math.hypot(dx, dy)
        r1 = math.hypot(self.c1_through.x - self.c1_center.x,
                        self.c1_through.y - self.c1_center.y)
        r2 = math.hypot(self.c2_through.x - self.c2_center.x,
                        self.c2_through.y - self.c2_center.y)
        if d < 1e-9 or r1 < 1e-9 or r2 < 1e-9:
            self.status = "degenerate"
            return [0.0]
        self.status = "ok"
        if self.mode == "external":
            return [d - (r1 + r2)]
        return [d - abs(r1 - r2)]

    def _jacobian_analytic(self, vars_map):
        """解析雅可比：避免数值差分。"""
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]

        dx = self.c2_center.x - self.c1_center.x
        dy = self.c2_center.y - self.c1_center.y
        d = math.hypot(dx, dy)
        r1 = math.hypot(self.c1_through.x - self.c1_center.x,
                        self.c1_through.y - self.c1_center.y)
        r2 = math.hypot(self.c2_through.x - self.c2_center.x,
                        self.c2_through.y - self.c2_center.y)
        if d < 1e-9 or r1 < 1e-9 or r2 < 1e-9:
            return jac

        ux, uy = dx / d, dy / d
        u1x = (self.c1_through.x - self.c1_center.x) / r1
        u1y = (self.c1_through.y - self.c1_center.y) / r1
        u2x = (self.c2_through.x - self.c2_center.x) / r2
        u2y = (self.c2_through.y - self.c2_center.y) / r2

        if self.mode == "external":
            dc1x, dc1y = u1x - ux, u1y - uy
            dt1x, dt1y = -u1x, -u1y
            dc2x, dc2y = ux + u2x, uy + u2y
            dt2x, dt2y = -u2x, -u2y
        else:
            s = 1.0 if r1 >= r2 else -1.0
            dc1x, dc1y = s * u1x - ux, s * u1y - uy
            dt1x, dt1y = -s * u1x, -s * u1y
            dc2x, dc2y = ux - s * u2x, uy - s * u2y
            dt2x, dt2y = s * u2x, s * u2y

        for p, gx, gy in ((self.c1_center, dc1x, dc1y),
                          (self.c1_through, dt1x, dt1y),
                          (self.c2_center, dc2x, dc2y),
                          (self.c2_through, dt2x, dt2y)):
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2] = gx
                jac[0][idx * 2 + 1] = gy
        return jac

    def dump(self):
        return {"c1_center": self.c1_center.id,
                "c1_through": self.c1_through.id,
                "c2_center": self.c2_center.id,
                "c2_through": self.c2_through.id,
                "mode": self.mode}

    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["c1_center"]],
                   point_map[params["c1_through"]],
                   point_map[params["c2_center"]],
                   point_map[params["c2_through"]],
                   params.get("mode", "external"))


@register_constraint("tangent_cl")
class TangentCL(GeometricConstraint):
    """圆与直线/线段相切。
    参数：
        center, through: 圆的圆心和圆周点
        a, b: 直线/线段的两个端点
    """

    def __init__(self, center, through, a, b):
        super().__init__()
        self.center = center
        self.through = through
        self.a = a
        self.b = b

    def involved_points(self):
        return [self.center, self.through, self.a, self.b]

    def residual(self):
        dx = self.b.x - self.a.x
        dy = self.b.y - self.a.y
        L = math.hypot(dx, dy)
        if L < 1e-9:
            self.status = "degenerate"
            return [0.0]
        cross = dx * (self.center.y - self.a.y) - \
                dy * (self.center.x - self.a.x)
        dist = abs(cross) / L
        r = math.hypot(self.through.x - self.center.x,
                       self.through.y - self.center.y)
        self.status = "ok"
        return [dist - r]
    # ★ P1-6 新增：解析雅可比（TangentCL）
    # R = |cross|/L − r
    # cross = dx(center.y − a.y) − dy(center.x − a.x)
    # 与 TangentLineCircleConstraint 同构
    def _jacobian_analytic(self, vars_map):
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]

        ax, ay = self.a.x, self.a.y
        bx, by = self.b.x, self.b.y
        cx, cy = self.center.x, self.center.y
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-9:
            return jac

        cross = dx * (cy - ay) - dy * (cx - ax)
        s = 1.0 if cross >= 0 else -1.0
        dist = abs(cross) / L
        r = math.hypot(self.through.x - cx, self.through.y - cy)
        if r < 1e-9:
            return jac

        # ∂cross/∂q，按 residual() 中
        # cross = (bx-ax)*(cy-ay) - (by-ay)*(cx-ax) 解析求导
        dc_dax = by - cy
        dc_day = cx - bx
        dc_dbx = cy - ay
        dc_dby = ax - cx
        dc_dcx = -dy
        dc_dcy = dx

        dL_dax = -dx / L
        dL_day = -dy / L
        dL_dbx = dx / L
        dL_dby = dy / L

        def d_dist(q_cross, q_L):
            return s * q_cross / L - dist * q_L / L

        urx = (self.through.x - cx) / r
        ury = (self.through.y - cy) / r

        for p, ddist_x, ddist_y, dr_x, dr_y in (
            (self.a,      d_dist(dc_dax, dL_dax), d_dist(dc_day, dL_day), 0.0, 0.0),
            (self.b,      d_dist(dc_dbx, dL_dbx), d_dist(dc_dby, dL_dby), 0.0, 0.0),
            (self.center, d_dist(dc_dcx, 0.0),    d_dist(dc_dcy, 0.0),   -urx, -ury),
            (self.through, 0.0,                   0.0,                    urx,  ury),
        ):
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2] = ddist_x - dr_x
                jac[0][idx * 2 + 1] = ddist_y - dr_y
        return jac
    
    def dump(self):
        return {"center": self.center.id, "through": self.through.id,
                "a": self.a.id, "b": self.b.id}

    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["center"]],
                   point_map[params["through"]],
                   point_map[params["a"]],
                   point_map[params["b"]])