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
        
    def dump(self):
        return {"p": self.p.id, "fx": self.fx, "fy": self.fy}
        
    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p"]], params["fx"], params["fy"])