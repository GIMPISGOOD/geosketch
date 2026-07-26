"""方向直线基类：过某点、沿某方向的无限长直线。
垂线/平行线/角平分线/n等分角线均继承它，只需在 recompute 中设置 self.dx/dy。"""
import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme


@register_geo("DirectedLine")
class DirectedLine(GeoObject):
    def __init__(self, parents, point):
        super().__init__(parents=parents)
        self.point = point
        self.dx, self.dy = 1.0, 0.0

    def point_at(self, t):                       # t ∈ ℝ
        return (self.point.x + self.dx * t, self.point.y + self.dy * t)

    def project(self, x, y):                     # 不截断 → 点可吸附其上
        denom = self.dx * self.dx + self.dy * self.dy
        return 0.0 if denom == 0 else \
            ((x - self.point.x) * self.dx + (y - self.point.y) * self.dy) / denom

    def distance_to(self, x, y):
        L = math.hypot(self.dx, self.dy)
        return 1e18 if L < 1e-12 else \
            abs(self.dx * (self.point.y - y) - self.dy * (self.point.x - x)) / L

    @classmethod
    def build(cls, parents, params):
        raise NotImplementedError                  # 子类各自实现


@register_renderer(DirectedLine)
def draw_directed_line(p, obj, view):
    """延伸到视口边界"""
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.LINE, 2.0))
    w, h = view.width(), view.height()
    ts = [obj.project(*view.to_world(QPointF(cx, cy)))
          for cx, cy in ((0, 0), (w, 0), (0, h), (w, h))]
    p0, p1 = obj.point_at(min(ts)), obj.point_at(max(ts))
    p.drawLine(view.to_screen(*p0), view.to_screen(*p1))