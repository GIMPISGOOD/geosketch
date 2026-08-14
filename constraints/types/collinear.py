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
        
    def dump(self):
        return {"p1": self.p1.id, "p2": self.p2.id, "p3": self.p3.id}
        
    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p1"]], point_map[params["p2"]], point_map[params["p3"]])