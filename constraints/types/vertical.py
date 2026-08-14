from ..base import GeometricConstraint, register_constraint

@register_constraint("vertical")
class VerticalConstraint(GeometricConstraint):
    def __init__(self, p1, p2):
        super().__init__()
        self.p1, self.p2 = p1, p2
        
    def involved_points(self):
        return [self.p1, self.p2]
        
    def residual(self):
        return [self.p2.x - self.p1.x]
        
    def dump(self):
        return {"p1": self.p1.id, "p2": self.p2.id}
        
    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p1"]], point_map[params["p2"]])