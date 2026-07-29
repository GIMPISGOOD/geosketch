import math

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme

from geo.constraints import expr_driver
from ui.math import draw_math, measure_math


@register_geo("Segment")
class Segment(GeoObject):
    """线段：只依赖两个端点，自身不存任何坐标——端点动，它自然跟着动。"""

    def __init__(self, a, b):
        super().__init__(parents=[a, b])
        self.a, self.b = a, b

    def point_at(self, t):
        t = min(max(t, 0.0), 1.0)
        return (self.a.x + (self.b.x - self.a.x) * t,
                self.a.y + (self.b.y - self.a.y) * t)

    def project(self, x, y):
        """点在线段上的投影参数（截断到 [0,1]）"""
        dx, dy = self.b.x - self.a.x, self.b.y - self.a.y
        denom = dx * dx + dy * dy
        if denom == 0:
            return 0.0
        t = ((x - self.a.x) * dx + (y - self.a.y) * dy) / denom
        return min(max(t, 0.0), 1.0)

    def length(self):
        return math.hypot(self.b.x - self.a.x, self.b.y - self.a.y)

    def distance_to(self, x, y):
        px, py = self.point_at(self.project(x, y))
        return math.hypot(px - x, py - y)

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_renderer(Segment)
def draw_segment(p, obj, view):
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.SEGMENT,
                       3 if obj.selected else 2))
    sa = view.to_screen(obj.a.x, obj.a.y)
    sb = view.to_screen(obj.b.x, obj.b.y)
    p.drawLine(sa, sb)
    # 长度标签：中点沿屏幕垂线偏移 14px，水平居中
    mx, my = (sa.x() + sb.x()) / 2, (sa.y() + sb.y()) / 2
    sdx, sdy = sb.x() - sa.x(), sb.y() - sa.y()
    slen = math.hypot(sdx, sdy)
    if slen > 1e-6:
        px, py = -sdy / slen, sdx / slen
        lx, ly = mx + px * 14, my + py * 14
    else:
        lx, ly = mx + 10, my - 10
    drv = expr_driver(obj)
    label = f"{drv.expr} = {obj.length():.2f}" if drv else f"{obj.length():.2f}"
    w, _, _ = measure_math(label, 12)
    draw_math(p, lx - w / 2, ly, label, 12,
              theme.SELECTED if obj.selected else theme.LABEL)