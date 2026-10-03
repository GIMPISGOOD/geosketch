import math

from core.variables import eval_expr
from ..base import GeometricConstraint, register_constraint


@register_constraint("angle")
class AngleConstraint(GeometricConstraint):

    def __init__(self, p1, vertex, p2, expr="90"):
        super().__init__()
        self.p1, self.vertex, self.p2 = p1, vertex, p2
        self.expr = str(expr)

    def involved_points(self):
        return [self.p1, self.vertex, self.p2]

    def _target_rad(self):
        deg = eval_expr(self.expr)
        if deg is None:
            self.status = "invalid_expr"
            return 0.0
        self.status = "ok"
        return math.radians(abs(deg))

    def residual(self):
        ux, uy = self.p1.x - self.vertex.x, self.p1.y - self.vertex.y
        vx, vy = self.p2.x - self.vertex.x, self.p2.y - self.vertex.y
        len_u = math.hypot(ux, uy)
        len_v = math.hypot(vx, vy)
        if len_u < 1e-9 or len_v < 1e-9:
            self.status = "degenerate"
            return [0.0]
        cos_theta = (ux * vx + uy * vy) / (len_u * len_v)
        cos_theta = max(-1.0, min(1.0, cos_theta))
        target = self._target_rad()
        return [cos_theta - math.cos(target)]

    # ★ P1-6 新增：解析雅可比
    # 残差 R = cos θ − cos(target)，cos θ = û·v̂
    # ∂cos θ/∂u = (v̂ − cos θ·û)/|u|
    # ∂cos θ/∂v = (û − cos θ·v̂)/|v|
    def _jacobian_analytic(self, vars_map):
        ux, uy = self.p1.x - self.vertex.x, self.p1.y - self.vertex.y
        vx, vy = self.p2.x - self.vertex.x, self.p2.y - self.vertex.y
        lu = math.hypot(ux, uy)
        lv = math.hypot(vx, vy)
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]
        if lu < 1e-9 or lv < 1e-9:
            return jac

        uhat_x, uhat_y = ux / lu, uy / lu
        vhat_x, vhat_y = vx / lv, vy / lv
        c = uhat_x * vhat_x + uhat_y * vhat_y

        # ∂R/∂p1 = ∂cos θ/∂u · I = (v̂ − c·û)/lu
        gp1x = (vhat_x - c * uhat_x) / lu
        gp1y = (vhat_y - c * uhat_y) / lu
        # ∂R/∂vertex = −∂cos θ/∂u − ∂cos θ/∂v
        gvtx = -(vhat_x - c * uhat_x) / lu - (uhat_x - c * vhat_x) / lv
        gvty = -(vhat_y - c * uhat_y) / lu - (uhat_y - c * vhat_y) / lv
        # ∂R/∂p2 = ∂cos θ/∂v · I = (û − c·v̂)/lv
        gp2x = (uhat_x - c * vhat_x) / lv
        gp2y = (uhat_y - c * vhat_y) / lv

        for p, gx, gy in ((self.p1, gp1x, gp1y),
                          (self.vertex, gvtx, gvty),
                          (self.p2, gp2x, gp2y)):
            if id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[0][idx * 2] = gx
                jac[0][idx * 2 + 1] = gy
        return jac

    def dump(self):
        return {"p1": self.p1.id, "vertex": self.vertex.id,
                "p2": self.p2.id, "expr": self.expr}

    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p1"]], point_map[params["vertex"]],
                   point_map[params["p2"]], params["expr"])