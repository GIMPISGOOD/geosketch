import math

from ..base import GeometricConstraint, register_constraint


@register_constraint("collinear")
class CollinearConstraint(GeometricConstraint):

    def __init__(self, p1, p2, p3):
        super().__init__()
        self.p1, self.p2, self.p3 = p1, p2, p3

    def involved_points(self):
        return [self.p1, self.p2, self.p3]

    def residual(self):
        ux, uy = self.p2.x - self.p1.x, self.p2.y - self.p1.y
        vx, vy = self.p3.x - self.p1.x, self.p3.y - self.p1.y
        len_u = math.hypot(ux, uy)
        len_v = math.hypot(vx, vy)
        if len_u < 1e-9 or len_v < 1e-9:
            self.status = "degenerate"
            return [0.0]
        cross = (ux * vy - uy * vx) / (len_u * len_v)
        return [cross]

    # ★ P1-6 新增：解析雅可比
    # 残差 R = û × v̂，u = p2−p1，v = p3−p1
    # ∂R/∂u = [(v̂y − R·ûx), (−v̂x − R·ûy)] / |u|
    # ∂R/∂v = [(−ûy − R·v̂x), (ûx − R·v̂y)] / |v|
    # p1 同时出现在 u 和 v 中（∂u/∂p1 = −I，∂v/∂p1 = −I）
    def _jacobian_analytic(self, vars_map):
        ux, uy = self.p2.x - self.p1.x, self.p2.y - self.p1.y
        vx, vy = self.p3.x - self.p1.x, self.p3.y - self.p1.y
        lu = math.hypot(ux, uy)
        lv = math.hypot(vx, vy)
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]
        if lu < 1e-9 or lv < 1e-9:
            return jac

        uhat_x, uhat_y = ux / lu, uy / lu
        vhat_x, vhat_y = vx / lv, vy / lv
        R = uhat_x * vhat_y - uhat_y * vhat_x

        # ∂R/∂u 分量
        du_x = (vhat_y - R * uhat_x) / lu
        du_y = (-vhat_x - R * uhat_y) / lu
        # ∂R/∂v 分量
        dv_x = (-uhat_y - R * vhat_x) / lv
        dv_y = (uhat_x - R * vhat_y) / lv

        # p1: ∂u/∂p1 = −I 且 ∂v/∂p1 = −I → 两项叠加
        gp1x = -du_x + (-dv_x)
        gp1y = -du_y + (-dv_y)
        # p2: ∂u/∂p2 = +I
        gp2x, gp2y = du_x, du_y
        # p3: ∂v/∂p3 = +I
        gp3x, gp3y = dv_x, dv_y

        for p, gx, gy in ((self.p1, gp1x, gp1y),
                          (self.p2, gp2x, gp2y),
                          (self.p3, gp3x, gp3y)):
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2] = gx
                jac[0][idx * 2 + 1] = gy
        return jac

    def dump(self):
        return {"p1": self.p1.id, "p2": self.p2.id, "p3": self.p3.id}

    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p1"]], point_map[params["p2"]],
                   point_map[params["p3"]])