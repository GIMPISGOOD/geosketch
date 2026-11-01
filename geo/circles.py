import math

from PySide6.QtCore import Qt
from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme


@register_geo("Circle")
class Circle(GeoObject):
    """圆：圆心 + 圆周上一点。"""

    closed = True

    def __init__(self, center, through):
        super().__init__(parents=[center, through])
        self.center, self.through = center, through
        self.r = 0.0
        self.recompute()

    def _live_radius(self):
        """实时半径：避免 recompute 滞后导致 point_at/project 使用旧半径。"""
        return math.hypot(
            self.through.x - self.center.x,
            self.through.y - self.center.y,
        )

    def recompute(self):
        self.r = self._live_radius()

    def point_at(self, t):
        ang = 2 * math.pi * t
        r = self._live_radius()
        return (
            self.center.x + r * math.cos(ang),
            self.center.y + r * math.sin(ang),
        )

    def project(self, x, y):
        return (
            math.atan2(y - self.center.y, x - self.center.x)
            / (2 * math.pi)
        ) % 1.0

    def distance_to(self, x, y):
        return abs(
            math.hypot(x - self.center.x, y - self.center.y)
            - self._live_radius()
        )

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_renderer(Circle)
def draw_circle(p, obj, view):
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.CIRCLE, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)

    c = view.to_screen(obj.center.x, obj.center.y)
    p.drawEllipse(c, obj.r * view.scale, obj.r * view.scale)