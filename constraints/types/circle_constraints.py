"""圆相关约束：同心、等半径、相切（圆-圆、线-圆）。"""
import math
from ..base import GeometricConstraint, register_constraint

def _dist(p1, p2):
    return math.hypot(p1.x - p2.x, p1.y - p2.y)

# ═══════════════ 1. 同心约束 ═══════════════
@register_constraint("concentric")
class ConcentricConstraint(GeometricConstraint):
    """同心：两个圆共享同一个圆心。"""
    def __init__(self, c1, c2):
        super().__init__()
        self.c1, self.c2 = c1, c2
        
    def involved_points(self):
        return [self.c1.center, self.c2.center]

    def residual(self):
        return [
            self.c1.center.x - self.c2.center.x,
            self.c1.center.y - self.c2.center.y
        ]

    def dump(self):
        return {"c1": self.c1.id, "c2": self.c2.id}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["c1"]], obj_map[params["c2"]])


# ═══════════════ 2. 等半径约束 ═══════════════
@register_constraint("equal_radius")
class EqualRadiusConstraint(GeometricConstraint):
    """等半径：两个圆的半径相等。"""
    def __init__(self, c1, c2):
        super().__init__()
        self.c1, self.c2 = c1, c2
        
    def involved_points(self):
        return [self.c1.center, self.c1.through, self.c2.center, self.c2.through]

    def residual(self):
        r1 = _dist(self.c1.center, self.c1.through)
        r2 = _dist(self.c2.center, self.c2.through)
        return [r1 - r2]

    def dump(self):
        return {"c1": self.c1.id, "c2": self.c2.id}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["c1"]], obj_map[params["c2"]])


# ═══════════════ 3. 圆与圆相切 ═══════════════
@register_constraint("tangent_circles")
class TangentCirclesConstraint(GeometricConstraint):
    """两圆相切。
    mode="outer": 外切 (d = r1 + r2)
    mode="inner": 内切 (d + r2 = r1，假设 c1 包含 c2)
    """
    def __init__(self, c1, c2, mode="outer"):
        super().__init__()
        self.c1, self.c2 = c1, c2
        self.mode = mode
        
    def involved_points(self):
        return [self.c1.center, self.c1.through, self.c2.center, self.c2.through]

    def residual(self):
        d = _dist(self.c1.center, self.c2.center)
        r1 = _dist(self.c1.center, self.c1.through)
        r2 = _dist(self.c2.center, self.c2.through)
        
        if self.mode == "inner":
            # 内切：圆心距 + 小圆半径 = 大圆半径
            # 为避免绝对值导致的导数不连续，默认假设 c1 是大圆
            return [d + r2 - r1]
        else:
            # 外切：圆心距 = 半径之和
            return [d - (r1 + r2)]

    def dump(self):
        return {"c1": self.c1.id, "c2": self.c2.id, "mode": self.mode}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["c1"]], obj_map[params["c2"]], params.get("mode", "outer"))


# ═══════════════ 4. 直线与圆相切 ═══════════════
@register_constraint("tangent_line_circle")
class TangentLineCircleConstraint(GeometricConstraint):
    """直线/线段与圆相切：圆心到直线的距离等于半径。"""
    def __init__(self, line, circle):
        super().__init__()
        self.line, self.circle = line, circle
        
    def involved_points(self):
        return [self.line.a, self.line.b, self.circle.center, self.circle.through]

    def residual(self):
        ax, ay = self.line.a.x, self.line.a.y
        bx, by = self.line.b.x, self.line.b.y
        cx, cy = self.circle.center.x, self.circle.center.y
        
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        if L < 1e-9:
            return [0.0]
            
        # 点到直线距离公式
        dist = abs(dx * (ay - cy) - dy * (ax - cx)) / L
        r = _dist(self.circle.center, self.circle.through)
        
        return [dist - r]

    def dump(self):
        return {"line": self.line.id, "circle": self.circle.id}

    @classmethod
    def build(cls, obj_map, params):
        return cls(obj_map[params["line"]], obj_map[params["circle"]])