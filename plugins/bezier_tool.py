"""贝塞尔曲线插件：4 个控制点确定一条三次贝塞尔曲线。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath

from core.registry import register_geo, register_renderer, register_tool
from geo.curves import ParamCurve
from tools.base import Tool, point_or_snap
from ui import theme


@register_geo("CubicBezier")
class CubicBezier(ParamCurve):
    """三次贝塞尔曲线：B(t) = (1-t)³P0 + 3(1-t)²t·P1 + 3(1-t)t²·P2 + t³·P3。"""
    closed = False

    def __init__(self, p0, p1, p2, p3):
        super().__init__(parents=(p0, p1, p2, p3))
        self.p0, self.p1, self.p2, self.p3 = p0, p1, p2, p3

    def point_at(self, t):
        u = 1 - t
        a, b = u * u * u, 3 * u * u * t
        c, d = 3 * u * t * t, t * t * t
        return (a * self.p0.x + b * self.p1.x + c * self.p2.x + d * self.p3.x,
                a * self.p0.y + b * self.p1.y + c * self.p2.y + d * self.p3.y)

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2], parents[3])


@register_renderer(CubicBezier)
def draw_bezier(p, obj, view):
    color = theme.SELECTED if obj.selected else theme.BEZIER
    # 控制多边形（细虚线）
    p.setPen(theme.dashed_pen(color, 1.0))
    ctrl = (obj.p0, obj.p1, obj.p2, obj.p3)
    for i in range(3):
        p.drawLine(view.to_screen(ctrl[i].x, ctrl[i].y),
                   view.to_screen(ctrl[i+1].x, ctrl[i+1].y))
    # 曲线本体（实线，采样）
    path = QPainterPath()
    n = 60
    for i in range(n + 1):
        sp = view.to_screen(*obj.point_at(i / n))
        path.moveTo(sp) if i == 0 else path.lineTo(sp)
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)


@register_tool(name="贝塞尔", shortcut="Z", order=7, icon="bezier", panel="rail",
               hint="依次点 4 个控制点，绘制三次贝塞尔曲线（均自动磁吸）")
class BezierTool(Tool):
    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 4:
            canvas.doc.add(CubicBezier(*self.pts))
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