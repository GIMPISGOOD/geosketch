# plugins/line_tool.py
"""直线插件：过两点的无限长直线。点可吸附其上。"""
import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from tools.base import Tool, point_or_snap
from ui import theme


@register_geo("Line")
class Line(GeoObject):
    """无限长直线：由两点确定。实现 point_at/project → 点可吸附。"""
    def __init__(self, a, b):
        super().__init__(parents=(a, b))
        self.a, self.b = a, b

    def point_at(self, t):                       # t ∈ ℝ
        return (self.a.x + (self.b.x - self.a.x) * t,
                self.a.y + (self.b.y - self.a.y) * t)

    def project(self, x, y):                     # 不截断
        dx, dy = self.b.x - self.a.x, self.b.y - self.a.y
        denom = dx * dx + dy * dy
        return 0.0 if denom == 0 else ((x - self.a.x) * dx + (y - self.a.y) * dy) / denom

    def distance_to(self, x, y):
        dx, dy = self.b.x - self.a.x, self.b.y - self.a.y
        L = math.hypot(dx, dy)
        return 1e18 if L < 1e-12 else abs(dx * (self.a.y - y) - dy * (self.a.x - x)) / L

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_renderer(Line)
def draw_line(p, obj, view):
    """延伸到视口边界"""
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.LINE, 2.0))
    w, h = view.width(), view.height()
    ts = []
    for cx, cy in ((0, 0), (w, 0), (0, h), (w, h)):
        wx, wy = view.to_world(QPointF(cx, cy))
        ts.append(obj.project(wx, wy))
    p0, p1 = obj.point_at(min(ts)), obj.point_at(max(ts))
    p.drawLine(view.to_screen(*p0), view.to_screen(*p1))


@register_tool(name="直线", shortcut="L", order=22, icon="line", panel="menu",
               hint="点击两点确定一条无限长直线（端点自动磁吸）")
class LineTool(Tool):
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
                canvas.doc.add(Line(self.first, pt))
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