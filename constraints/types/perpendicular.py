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
        # 归一化点积 (cos theta)
        dot = (ux * vx + uy * vy) / (len_u * len_v)
        return [dot]
        
    def dump(self):
        return {"a1": self.a1.id, "b1": self.b1.id, "a2": self.a2.id, "b2": self.b2.id}
        
    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["a1"]], point_map[params["b1"]], 
                   point_map[params["a2"]], point_map[params["b2"]])