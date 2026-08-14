from ..base import GeometricConstraint, register_constraint


@register_constraint("fixed")
class FixedConstraint(GeometricConstraint):
    def __init__(self, p, fx, fy):
        super().__init__()
        self.p = p
        self.fx, self.fy = fx, fy

    def involved_points(self):
        return [self.p]

    def residual(self):
        return [self.p.x - self.fx, self.p.y - self.fy]

    def _jacobian_analytic(self, vars_map):
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols, [0.0] * n_cols]
        if id(self.p) in vars_map:
            idx = vars_map[id(self.p)]
            jac[0][idx * 2] = 1.0
            jac[1][idx * 2 + 1] = 1.0
        return jac

    def dump(self):
        return {"p": self.p.id, "fx": self.fx, "fy": self.fy}

    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p"]], params["fx"], params["fy"])