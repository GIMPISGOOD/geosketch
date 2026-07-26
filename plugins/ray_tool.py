# plugins/ray_tool.py
"""射线插件：从端点出发经过另一点的射线。"""
import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from tools.base import Tool, point_or_snap
from ui import theme


@register_geo("Ray")
class Ray(GeoObject):
    """射线：端点 + 方向点。t ∈ [0, +∞)。"""
    def __init__(self, origin, through):
        super().__init__(parents=(origin, through))
        self.origin, self.through = origin, through

    def point_at(self, t):
        t = max(0.0, t)
        return (self.origin.x + (self.through.x - self.origin.x) * t,
                self.origin.y + (self.through.y - self.origin.y) * t)

    def project(self, x, y):
        dx, dy = self.through.x - self.origin.x, self.through.y - self.origin.y
        denom = dx * dx + dy * dy
        t = 0.0 if denom == 0 else ((x - self.origin.x) * dx + (y - self.origin.y) * dy) / denom
        return max(0.0, t)

    def distance_to(self, x, y):
        px, py = self.point_at(self.project(x, y))
        return math.hypot(px - x, py - y)

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_renderer(Ray)
def draw_ray(p, obj, view):
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.RAY, 2.0))
    w, h = view.width(), view.height()
    t_max = max(obj.project(*view.to_world(QPointF(cx, cy)))
                for cx, cy in ((0, 0), (w, 0), (0, h), (w, h)))
    p0, p1 = obj.point_at(0.0), obj.point_at(max(t_max, 0.0))
    p.drawLine(view.to_screen(*p0), view.to_screen(*p1))


@register_tool(name="射线", shortcut="Y", order=23, icon="ray", panel="menu",
               hint="第一下为端点，第二下为方向点（自动磁吸）")
class RayTool(Tool):
    def __init__(self):
        self.first = None

    def activated(self, canvas):
        self.first = None

    def deactivated(self, canvas):
        self.first = None

    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if self.first is None:
            self.first = pt
        else:
            if pt is not self.first:
                canvas.doc.add(Ray(self.first, pt))
            self.first = None

    def cancel(self, canvas):
        self.first = None
        canvas.update()

    def draw_overlay(self, p, view):
        if self.first is None:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.drawLine(view.to_screen(self.first.x, self.first.y),
                   view.to_screen(*view.cursor_wpt))