# plugins/angle_tool.py
"""角度插件：先点顶点再点两侧点，测量夹角（度）。"""
import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from tools.base import Tool, point_or_snap
from ui import theme


@register_geo("AngleMeasure")
class AngleMeasure(GeoObject):
    """角度测量：顶点 + 两侧点。拖动任一点实时更新读数。"""
    def __init__(self, vertex, p1, p2):
        super().__init__(parents=(vertex, p1, p2))
        self.vertex, self.p1, self.p2 = vertex, p1, p2
        self.degrees = 0.0
        self.a1 = self.a2 = 0.0
        self.label = (0.0, 0.0)
        self.recompute()

    def recompute(self):
        v = self.vertex
        self.a1 = math.atan2(self.p1.y - v.y, self.p1.x - v.x)
        self.a2 = math.atan2(self.p2.y - v.y, self.p2.x - v.x)
        span = math.degrees(self.a2 - self.a1) % 360
        self.degrees = span if span <= 180 else 360 - span
        # 标签放在角平分线方向
        mid = self.a1 + self._span() / 2
        self.label = (v.x + 40 * math.cos(mid) / 1, v.y + 40 * math.sin(mid) / 1)

    def _span(self):
        s = self.a2 - self.a1
        while s > math.pi: s -= 2 * math.pi
        while s < -math.pi: s += 2 * math.pi
        return s

    def distance_to(self, x, y):
        return math.hypot(x - self.label[0], y - self.label[1])

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


@register_renderer(AngleMeasure)
def draw_angle(p, obj, view):
    v = obj.vertex
    color = theme.SELECTED if obj.selected else theme.MEASURE
    # 两条短臂
    p.setPen(theme.pen(color, 1.5))
    for a in (obj.a1, obj.a2):
        p.drawLine(view.to_screen(v.x, v.y),
                   view.to_screen(v.x + 30 * math.cos(a) / view.scale * view.scale,
                                  v.y + 30 * math.sin(a) / view.scale * view.scale))
    # 圆弧（世界半径 = 22 屏幕像素）
    r = 22.0 / view.scale
    span = obj._span()
    path = QPainterPath()
    for i in range(33):
        a = obj.a1 + span * i / 32
        sp = view.to_screen(v.x + r * math.cos(a), v.y + r * math.sin(a))
        path.moveTo(sp) if i == 0 else path.lineTo(sp)
    p.drawPath(path)
    # 度数文本
    p.setPen(theme.pen(color))
    p.setFont(theme.LABEL_FONT)
    p.drawText(view.to_screen(*obj.label) + QPointF(-14, 4), f"{obj.degrees:.1f}°")


@register_tool(name="角度", shortcut="A", order=24, icon="angle", panel="menu",
               hint="先点顶点，再点两侧的点，测量夹角")
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
            v, p1, p2 = self.pts
            canvas.doc.add(AngleMeasure(v, p1, p2))
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
        if len(self.pts) < 3:
            last = self.pts[-1]
            p.drawLine(view.to_screen(last.x, last.y),
                       view.to_screen(*view.cursor_wpt))