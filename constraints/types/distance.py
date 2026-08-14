import math
from core.variables import eval_expr
from ..base import GeometricConstraint, register_constraint


@register_constraint("distance")
class DistanceConstraint(GeometricConstraint):
    def __init__(self, p1, p2, expr="1"):
        super().__init__()
        self.p1, self.p2 = p1, p2
        self.expr = expr

    def involved_points(self):
        return [self.p1, self.p2]

    def residual(self):
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        d = math.hypot(dx, dy)
        target = eval_expr(self.expr)
        if target is None:
            self.status = "invalid_expr"
            return [0.0]
        self.status = "ok"
        return [d - target]

    def _jacobian_analytic(self, vars_map):
        dx = self.p2.x - self.p1.x
        dy = self.p2.y - self.p1.y
        d = math.hypot(dx, dy)
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols]
        if d < 1e-9:
            return jac
        ux, uy = dx / d, dy / d
        if id(self.p1) in vars_map:
            idx = vars_map[id(self.p1)]
            jac[0][idx * 2] = -ux
            jac[0][idx * 2 + 1] = -uy
        if id(self.p2) in vars_map:
            idx = vars_map[id(self.p2)]
            jac[0][idx * 2] = ux
            jac[0][idx * 2 + 1] = uy
        return jac

    def dump(self):
        return {"p1": self.p1.id, "p2": self.p2.id, "expr": self.expr}

    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p1"]], point_map[params["p2"]],
                   params["expr"])