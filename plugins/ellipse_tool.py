"""椭圆插件：中心 + 两个轴端点确定一个椭圆。点可吸附到椭圆上。"""
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath

from core.registry import register_geo, register_renderer, register_tool
from geo.curves import ParamCurve
from tools.base import Tool, point_or_snap
from ui import theme


@register_geo("Ellipse")
class Ellipse(ParamCurve):
    """椭圆：P(t) = C + u·cos2πt + v·sin2πt，u/v 为两个半轴向量。"""
    closed = True

    def __init__(self, center, axis_a, axis_b):
        super().__init__(parents=(center, axis_a, axis_b))
        self.center, self.axis_a, self.axis_b = center, axis_a, axis_b
        self.ux = self.uy = self.vx = self.vy = 0.0
        self.recompute()

    def recompute(self):
        self.ux = self.axis_a.x - self.center.x
        self.uy = self.axis_a.y - self.center.y
        self.vx = self.axis_b.x - self.center.x
        self.vy = self.axis_b.y - self.center.y

    def point_at(self, t):
        ang = 2 * math.pi * t
        c, s = math.cos(ang), math.sin(ang)
        return (self.center.x + self.ux * c + self.vx * s,
                self.center.y + self.uy * c + self.vy * s)

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


@register_renderer(Ellipse)
def draw_ellipse(p, obj, view):
    path = QPainterPath()
    n = 72
    for i in range(n + 1):
        sp = view.to_screen(*obj.point_at(i / n))
        path.moveTo(sp) if i == 0 else path.lineTo(sp)
    path.closeSubpath()
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.ELLIPSE, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)


@register_tool(name="椭圆", shortcut="E", order=6, icon="ellipse", panel="rail",
               hint="依次点中心、第一个轴端点、第二个轴端点，绘制椭圆（均自动磁吸）")
class EllipseTool(Tool):
    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 3:
            c, a, b = self.pts
            canvas.doc.add(Ellipse(c, a, b))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

    def draw_overlay(self, p, view):
        if not self.pts:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        for i in range(1, len(self.pts)):
            p.drawLine(view.to_screen(self.pts[i-1].x, self.pts[i-1].y),
                       view.to_screen(self.pts[i].x, self.pts[i].y))
        last = self.pts[-1]
        p.drawLine(view.to_screen(last.x, last.y),
                   view.to_screen(*view.cursor_wpt))