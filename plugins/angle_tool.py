"""角度插件：依次点边1、顶点、边2，测量夹角（度）。拖动任一点实时刷新。"""
import math
from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath
from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from tools.base import Tool, point_or_snap
from ui import theme
from geo.constraints import expr_driver
from ui.math import draw_math, measure_math

@register_geo("AngleMeasure")
class AngleMeasure(GeoObject):
    def __init__(self, vertex, p1, p2):
        super().__init__(parents=(vertex, p1, p2))
        self.vertex, self.p1, self.p2 = vertex, p1, p2
        self.a1 = self.a2 = 0.0
        self.degrees = 0.0
        self.anchor = (0.0, 0.0)
        self.recompute()

    def _span(self):
        s = self.a2 - self.a1
        while s > math.pi: s -= 2 * math.pi
        while s < -math.pi: s += 2 * math.pi
        return s

    def recompute(self):
        v = self.vertex
        self.a1 = math.atan2(self.p1.y - v.y, self.p1.x - v.x)
        self.a2 = math.atan2(self.p2.y - v.y, self.p2.x - v.x)
        span_deg = math.degrees(self.a2 - self.a1) % 360
        self.degrees = span_deg if span_deg <= 180 else 360 - span_deg
        arm = min(math.hypot(self.p1.x - v.x, self.p1.y - v.y),
                  math.hypot(self.p2.x - v.x, self.p2.y - v.y))
        mid = self.a1 + self._span() / 2
        d = max(arm * 0.4, 0.3)
        self.anchor = (v.x + d * math.cos(mid), v.y + d * math.sin(mid))

    def distance_to(self, x, y):
        return math.hypot(x - self.anchor[0], y - self.anchor[1])

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])

@register_renderer(AngleMeasure)
def draw_angle(p, obj, view):
    v = obj.vertex
    color = theme.SELECTED if obj.selected else theme.MEASURE
    a1 = math.atan2(obj.p1.y - v.y, obj.p1.x - v.x)
    a2 = math.atan2(obj.p2.y - v.y, obj.p2.x - v.x)
    span = (a2 - a1 + 3 * math.pi) % (2 * math.pi) - math.pi
    arm = 30.0 / view.scale
    p.setPen(theme.pen(color, 1.5))
    for a in (a1, a2):
        p.drawLine(view.to_screen(v.x, v.y),
                   view.to_screen(v.x + arm * math.cos(a), v.y + arm * math.sin(a)))
    r = 20.0 / view.scale
    path = QPainterPath()
    for i in range(33):
        a = a1 + span * i / 32
        sp = view.to_screen(v.x + r * math.cos(a), v.y + r * math.sin(a))
        path.moveTo(sp) if i == 0 else path.lineTo(sp)
    p.drawPath(path)
    mid = a1 + span / 2
    lr = 36.0 / view.scale
    lp = view.to_screen(v.x + lr * math.cos(mid), v.y + lr * math.sin(mid))
    drv = expr_driver(obj)
    label = f"{drv.expr} = {obj.degrees:.1f}°" if drv else f"{obj.degrees:.1f}°"
    w, _, _ = measure_math(label, 12)
    draw_math(p, lp.x() - w / 2, lp.y() + 4, label, 12,
              theme.SELECTED if obj.selected else theme.LABEL)

@register_tool(name="角度", shortcut="A", order=24, icon="angle", panel="menu",
               hint="★ 依次点击：边1上的点 → 顶点 → 边2上的点")
class AngleTool(Tool):
    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 3:
            # ★ 修复：第2个点是顶点 (p1 -> v -> p2)
            p1, v, p2 = self.pts
            canvas.doc.add(AngleMeasure(v, p1, p2))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

    def draw_overlay(self, p, view):
        if not self.pts:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        if len(self.pts) == 1:
            p.drawLine(view.to_screen(self.pts[0].x, self.pts[0].y),
                       view.to_screen(*view.cursor_wpt))
        elif len(self.pts) == 2:
            # ★ 预览：边1 -> 顶点 -> 光标
            p1, v = self.pts
            p.drawLine(view.to_screen(p1.x, p1.y), view.to_screen(v.x, v.y))
            p.drawLine(view.to_screen(v.x, v.y), view.to_screen(*view.cursor_wpt))