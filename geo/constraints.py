"""表达式约束：把线段长度 / 角度度数锁定为变量的代数式。
变量变化时由 Document.refresh_variables 驱动重算。"""
import math

from core.registry import register_geo
from core.variables import eval_expr
from geo.base import GeoObject


@register_geo("ExprSegment")
class ExprSegment(GeoObject):
    """表达式线段：长度恒等于 eval(expr)；拖动端点只改方向，长度不变。"""
    def __init__(self, segment, expr):
        super().__init__(parents=(segment,))
        self.segment = segment
        self.expr = expr

    def recompute(self):
        L = eval_expr(self.expr)
        if L is None or L <= 1e-9:
            return
        a, b = self.segment.a, self.segment.b
        dx, dy = b.x - a.x, b.y - a.y
        d = math.hypot(dx, dy)
        if d < 1e-9:
            return
        k = L / d
        b.x = a.x + dx * k
        b.y = a.y + dy * k

    def moved_points(self):
        return [self.segment.b]

    def dump(self):
        return {"expr": self.expr}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], params["expr"])


@register_geo("ExprAngle")
class ExprAngle(GeoObject):
    """表达式角：角度数恒等于 eval(expr)；拖动 p2 只改臂长，角度不变。
    angle 为鸭子类型：任何带 vertex/p1/p2 的角对象（AngleMeasure）。"""
    def __init__(self, angle, expr):
        super().__init__(parents=(angle,))
        self.angle = angle
        self.expr = expr
        v, p1, p2 = angle.vertex, angle.p1, angle.p2
        a1 = math.atan2(p1.y - v.y, p1.x - v.x)
        a2 = math.atan2(p2.y - v.y, p2.x - v.x)
        span = (a2 - a1 + 3 * math.pi) % (2 * math.pi) - math.pi
        self.sign = 1.0 if span >= 0 else -1.0

    def recompute(self):
        target = eval_expr(self.expr)
        if target is None:
            return
        v, p1, p2 = self.angle.vertex, self.angle.p1, self.angle.p2
        base = math.atan2(p1.y - v.y, p1.x - v.x)
        new_a2 = base + self.sign * math.radians(target)
        dist = math.hypot(p2.x - v.x, p2.y - v.y)
        if dist < 1e-9:
            return
        p2.x = v.x + dist * math.cos(new_a2)
        p2.y = v.y + dist * math.sin(new_a2)
        self.angle.degrees = target % 360        # 同步角度显示

    def moved_points(self):
        return [self.angle.p2]

    def dump(self):
        return {"expr": self.expr, "sign": self.sign}

    @classmethod
    def build(cls, parents, params):
        obj = cls(parents[0], params["expr"])
        obj.sign = params.get("sign", obj.sign)
        return obj