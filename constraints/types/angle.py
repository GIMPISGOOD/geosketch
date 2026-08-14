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
        # 向量 u = p1 - vertex, v = p2 - vertex
        ux, uy = self.p1.x - self.vertex.x, self.p1.y - self.vertex.y
        vx, vy = self.p2.x - self.vertex.x, self.p2.y - self.vertex.y
        
        len_u = math.hypot(ux, uy)
        len_v = math.hypot(vx, vy)
        
        if len_u < 1e-9 or len_v < 1e-9:
            self.status = "degenerate"
            return [0.0]
            
        # ★ 核心：使用归一化点积避免 atan2 跳变
        cos_theta = (ux * vx + uy * vy) / (len_u * len_v)
        cos_theta = max(-1.0, min(1.0, cos_theta)) # 防止浮点误差越界
        
        target = self._target_rad()
        return [cos_theta - math.cos(target)]
        
    def dump(self):
        return {"p1": self.p1.id, "vertex": self.vertex.id, "p2": self.p2.id, "expr": self.expr}
        
    @classmethod
    def build(cls, point_map, params):
        return cls(point_map[params["p1"]], point_map[params["vertex"]], point_map[params["p2"]], params["expr"])