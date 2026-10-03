import math

from ..base import GeometricConstraint, register_constraint


@register_constraint("perpendicular")
class PerpendicularConstraint(GeometricConstraint):

    def __init__(self, a1, b1, a2, b2):
        super().__init__()
        self.a1, self.b1, self.a2, self.b2 = a1, b1, a2, b2

    def involved_points(self):
        return [self.a1, self.b1, self.a2, self.b2]

    def residual(self):
        ux, uy = self.b1.x - self.a1.x, self.b1.y - self.a1.y
        vx, vy = self.b2.x - self.a2.x, self.b2.y - self.a2.y
        len_u = math.hypot(ux, uy)
        len_v = math.hypot(vx, vy)
        if len_u < 1e-9 or len_v < 1e-9:
            self.status = "degenerate"
            return [0.0]
        dot = (ux * vx + uy * vy) / (len_u * len_v)
        return [dot]

    # ★ P1-6 新增：解析雅可比
    # 残差 R = û · v̂（归一化点积）
    # ∂R/∂u = (v̂ − R·û)/|u|
    # ∂R/∂v = (û − R·v̂)/|v|
    def _jacobian_analytic(self, vars_map):
        ux, uy = self.b1.x - self.a1.x, self.b1.y - self.a1.y
        vx, vy = self.b2.x - self.a2.x, self.b2.y - self.a2.y
        lu = math.hypot(ux, uy)
        lv = math.hypot(vx, vy)
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]
        if lu < 1e-9 or lv < 1e-9:
            return jac

        uhat_x, uhat_y = ux / lu, uy / lu
        vhat_x, vhat_y = vx / lv, vy / lv
        R = uhat_x * vhat_x + uhat_y * vhat_y

        # ∂R/∂u 分量
        du_x = (vhat_x - R * uhat_x) / lu
        du_y = (vhat_y - R * uhat_y) / lu
        # ∂R/∂v 分量
        dv_x = (uhat_x - R * vhat_x) / lv
        dv_y = (uhat_y - R * vhat_y) / lv

        # a1: u = b1−a1 → ∂u/∂a1 = −I
        ga1x, ga1y = -du_x, -du_y
        # b1: ∂u/∂b1 = +I
        gb1x, gb1y = du_x, du_y
        # a2: v = b2−a2 → ∂v/∂a2 = −I
        ga2x, ga2y = -dv_x, -dv_y
        # b2: ∂v/∂b2 = +I
        gb2x, gb2y = dv_x, dv_y

        for p, gx, gy in ((self.a1, ga1x, ga1y),
                          (self.b1, gb1x, gb1y),
                          (self.a2, ga2x, ga2y),
                          (self.b2, gb2x, gb2y)):
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2] = gx
                jac[0][idx * 2 + 1] = gy
        return jac

    def dump(self):
        return {"a1": self.a1.id, "b1": self.b1.id,
                "a2": self.a2.id, "b2": self.b2.id}

    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["a1"]], point_map[params["b1"]],
                   point_map[params["a2"]], point_map[params["b2"]])