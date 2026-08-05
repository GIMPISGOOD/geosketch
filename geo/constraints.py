"""表达式约束：把线段长度 / 角度度数 / 圆半径 / 点坐标锁定为变量的代数式。"""

import math

from PySide6.QtCore import Qt
from core.registry import register_geo, register_renderer
from ui import theme
from ui.math import draw_math
from core.variables import eval_expr
from geo.base import GeoObject
from geo.points import AbstractPoint


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
    """表达式角：角度数恒等于 eval(expr)；拖动 p2 只改臂长，角度不变。"""

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

        self.angle.degrees = target % 360

    def moved_points(self):
        return [self.angle.p2]

    def dump(self):
        return {"expr": self.expr, "sign": self.sign}

    @classmethod
    def build(cls, parents, params):
        obj = cls(parents[0], params["expr"])
        obj.sign = params.get("sign", obj.sign)
        return obj


def expr_driver(obj):
    """返回对象身上的表达式约束（ExprSegment / ExprAngle），没有则 None。"""
    for c in obj.children:
        if hasattr(c, "expr"):
            return c
    return None


@register_geo("ExprCircle")
class ExprCircle(GeoObject):
    """表达式圆：圆心 + 表达式半径，变量变化时半径实时更新。"""

    closed = True  # ★ 新增：表达式圆也是闭合曲线

    def __init__(self, center, expr):
        super().__init__(parents=(center,))
        self.center = center
        self.expr = expr
        self.r = 0.0
        self.recompute()

    def recompute(self):
        r = eval_expr(self.expr)
        self.r = abs(r) if r is not None else 0.0

    def point_at(self, t):
        ang = 2 * math.pi * t
        return (
            self.center.x + self.r * math.cos(ang),
            self.center.y + self.r * math.sin(ang)
        )

    def project(self, x, y):
        return (
            math.atan2(y - self.center.y, x - self.center.x)
            / (2 * math.pi)
        ) % 1.0

    def distance_to(self, x, y):
        return abs(math.hypot(x - self.center.x, y - self.center.y) - self.r)

    def moved_points(self):
        return [self]

    def dump(self):
        return {"expr": self.expr}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], params["expr"])


@register_geo("ExprPoint")
class ExprPoint(AbstractPoint):
    """表达式点：坐标由表达式决定，随变量变化，不可拖动。"""

    def __init__(self, expr_x, expr_y):
        super().__init__(parents=())
        self.expr_x = expr_x
        self.expr_y = expr_y
        self.recompute()

    def recompute(self):
        x = eval_expr(self.expr_x)
        y = eval_expr(self.expr_y)
        self.x = x if x is not None else 0.0
        self.y = y if y is not None else 0.0

    def moved_points(self):
        return [self]

    def dump(self):
        return {"expr_x": self.expr_x, "expr_y": self.expr_y}

    @classmethod
    def build(cls, parents, params):
        return cls(params["expr_x"], params["expr_y"])


@register_renderer(ExprCircle)
def draw_expr_circle(p, obj, view):
    c = view.to_screen(obj.center.x, obj.center.y)

    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.CIRCLE, 2))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, obj.r * view.scale, obj.r * view.scale)

    draw_math(
        p,
        c.x() + obj.r * view.scale * 0.7,
        c.y(),
        f"r={obj.expr}",
        12,
        theme.MEASURE
    )