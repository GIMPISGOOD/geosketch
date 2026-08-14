"""构造工具插件：过三点圆、中垂线、三角形内心、三角形重心。

新增几何对象：
  ThreePointCircle  过三点的圆（外接圆）
  PerpBisector      线段的垂直平分线
  Incenter          三角形内心（内切圆圆心）
  Centroid          三角形重心（中线交点）

新增工具（注册到「工具」菜单 panel="menu"）：
  过三点圆、中垂线、内心、重心
"""
import math
from PySide6.QtCore import QPointF, Qt
from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from geo.points import AbstractPoint
from tools.base import Tool, point_or_snap
from ui import theme
from ui.math import draw_math


# ═══════════════════════════════════════════════════════════
#  1. 过三点圆（外接圆）
# ═══════════════════════════════════════════════════════════

@register_geo("ThreePointCircle")
class ThreePointCircle(GeoObject):
    """过三点的圆：由三个不共线的点唯一确定。"""
    closed = True

    def __init__(self, p1, p2, p3):
        super().__init__(parents=(p1, p2, p3))
        self.p1, self.p2, self.p3 = p1, p2, p3
        self.cx = self.cy = self.r = 0.0
        self.recompute()

    def recompute(self):
        x1, y1 = self.p1.x, self.p1.y
        x2, y2 = self.p2.x, self.p2.y
        x3, y3 = self.p3.x, self.p3.y
        D = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
        if abs(D) < 1e-12:
            self.exists = False
            return
        self.exists = True
        s1 = x1 * x1 + y1 * y1
        s2 = x2 * x2 + y2 * y2
        s3 = x3 * x3 + y3 * y3
        self.cx = (s1 * (y2 - y3) + s2 * (y3 - y1) + s3 * (y1 - y2)) / D
        self.cy = (s1 * (x3 - x2) + s2 * (x1 - x3) + s3 * (x2 - x1)) / D
        self.r = math.hypot(x1 - self.cx, y1 - self.cy)

    def point_at(self, t):
        ang = 2 * math.pi * t
        return (self.cx + self.r * math.cos(ang),
                self.cy + self.r * math.sin(ang))

    def project(self, x, y):
        return (math.atan2(y - self.cy, x - self.cx) / (2 * math.pi)) % 1.0

    def distance_to(self, x, y):
        return abs(math.hypot(x - self.cx, y - self.cy) - self.r)

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


@register_renderer(ThreePointCircle)
def draw_three_point_circle(p, obj, view):
    if not obj.exists:
        return
    c = view.to_screen(obj.cx, obj.cy)
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.CIRCLE, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, obj.r * view.scale, obj.r * view.scale)
    # 圆心十字标记
    p.setPen(theme.pen(theme.CIRCLE, 1.2))
    p.drawLine(QPointF(c.x() - 4, c.y()), QPointF(c.x() + 4, c.y()))
    p.drawLine(QPointF(c.x(), c.y() - 4), QPointF(c.x(), c.y() + 4))


# ═══════════════════════════════════════════════════════════
#  2. 中垂线（垂直平分线）
# ═══════════════════════════════════════════════════════════

@register_geo("PerpBisector")
class PerpBisector(GeoObject):
    """线段 AB 的垂直平分线：过中点，垂直于 AB，无限延伸。"""

    def __init__(self, a, b):
        super().__init__(parents=(a, b))
        self.a, self.b = a, b
        self.mx = self.my = 0.0
        self.dx = self.dy = 1.0
        self.recompute()

    def recompute(self):
        self.mx = (self.a.x + self.b.x) / 2
        self.my = (self.a.y + self.b.y) / 2
        abx = self.b.x - self.a.x
        aby = self.b.y - self.a.y
        self.dx, self.dy = -aby, abx

    def point_at(self, t):
        return (self.mx + self.dx * t, self.my + self.dy * t)

    def project(self, x, y):
        denom = self.dx * self.dx + self.dy * self.dy
        return 0.0 if denom < 1e-12 else \
            ((x - self.mx) * self.dx + (y - self.my) * self.dy) / denom

    def distance_to(self, x, y):
        L = math.hypot(self.dx, self.dy)
        if L < 1e-12:
            return 1e18
        return abs(self.dx * (self.my - y) - self.dy * (self.mx - x)) / L

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1])


@register_renderer(PerpBisector)
def draw_perp_bisector(p, obj, view):
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.LINE, 2.0))
    w, h = view.width(), view.height()
    ts = [obj.project(*view.to_world(QPointF(cx, cy)))
          for cx, cy in ((0, 0), (w, 0), (0, h), (w, h))]
    p0, p1 = obj.point_at(min(ts)), obj.point_at(max(ts))
    p.drawLine(view.to_screen(*p0), view.to_screen(*p1))
    # 中点 × 标记
    mid = view.to_screen(obj.mx, obj.my)
    p.setPen(theme.pen(theme.MEASURE, 1.5))
    p.drawLine(QPointF(mid.x() - 3, mid.y() - 3),
               QPointF(mid.x() + 3, mid.y() + 3))
    p.drawLine(QPointF(mid.x() - 3, mid.y() + 3),
               QPointF(mid.x() + 3, mid.y() - 3))


# ═══════════════════════════════════════════════════════════
#  3. 三角形内心
# ═══════════════════════════════════════════════════════════

@register_geo("Incenter")
class Incenter(AbstractPoint):
    """三角形内心：三条角平分线的交点，内切圆圆心。
    坐标公式：I = (a·A + b·B + c·C) / (a + b + c)
    其中 a = |BC|, b = |AC|, c = |AB|"""

    def __init__(self, a, b, c):
        super().__init__(parents=(a, b, c))
        self.a, self.b, self.c = a, b, c
        self.recompute()

    def recompute(self):
        a_len = math.hypot(self.b.x - self.c.x, self.b.y - self.c.y)
        b_len = math.hypot(self.a.x - self.c.x, self.a.y - self.c.y)
        c_len = math.hypot(self.a.x - self.b.x, self.a.y - self.b.y)
        s = a_len + b_len + c_len
        if s < 1e-12:
            self.exists = False
            return
        self.exists = True
        self.x = (a_len * self.a.x + b_len * self.b.x + c_len * self.c.x) / s
        self.y = (a_len * self.a.y + b_len * self.b.y + c_len * self.c.y) / s

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


@register_renderer(Incenter)
def draw_incenter(p, obj, view):
    if not obj.exists:
        return
    qpt = view.to_screen(obj.x, obj.y)
    color = theme.SELECTED if obj.selected else theme.MEASURE
    r = 5.5 if obj.selected else 4.5
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(theme.brush(theme.BG_TOP))
    p.drawEllipse(qpt, r, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(qpt, 1.8, 1.8)
    draw_math(p, qpt.x() + 9, qpt.y() - 8, "I", 13,
              theme.SELECTED if obj.selected else theme.LABEL)


# ═══════════════════════════════════════════════════════════
#  4. 三角形重心
# ═══════════════════════════════════════════════════════════

@register_geo("Centroid")
class Centroid(AbstractPoint):
    """三角形重心：三条中线的交点。
    坐标公式：G = (A + B + C) / 3"""

    def __init__(self, a, b, c):
        super().__init__(parents=(a, b, c))
        self.a, self.b, self.c = a, b, c
        self.recompute()

    def recompute(self):
        self.x = (self.a.x + self.b.x + self.c.x) / 3.0
        self.y = (self.a.y + self.b.y + self.c.y) / 3.0

    def dump(self):
        return {}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


@register_renderer(Centroid)
def draw_centroid(p, obj, view):
    if not obj.exists:
        return
    qpt = view.to_screen(obj.x, obj.y)
    color = theme.SELECTED if obj.selected else theme.MEASURE
    r = 5.5 if obj.selected else 4.5
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(theme.brush(theme.BG_TOP))
    p.drawEllipse(qpt, r, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(qpt, 1.8, 1.8)
    draw_math(p, qpt.x() + 9, qpt.y() - 8, "G", 13,
              theme.SELECTED if obj.selected else theme.LABEL)


# ═══════════════════════════════════════════════════════════
#  工具
# ═══════════════════════════════════════════════════════════

@register_tool(name="过三点圆", order=40, icon="circle", panel="menu",
               hint="依次点击三个点，作过三点的圆（外接圆）")
class ThreePointCircleTool(Tool):
    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 3:
            canvas.doc.add(ThreePointCircle(*self.pts))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

    def draw_overlay(self, p, view):
        if not self.pts:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        for i in range(1, len(self.pts)):
            p.drawLine(view.to_screen(self.pts[i - 1].x, self.pts[i - 1].y),
                       view.to_screen(self.pts[i].x, self.pts[i].y))
        last = self.pts[-1]
        p.drawLine(view.to_screen(last.x, last.y),
                   view.to_screen(*view.cursor_wpt))


@register_tool(name="中垂线", order=41, icon="perp", panel="menu",
               hint="点击两个点或一条线段，作垂直平分线")
class PerpBisectorTool(Tool):
    def __init__(self):
        self.first = None

    def activated(self, canvas):
        self.first = None

    def deactivated(self, canvas):
        self.first = None

    def press(self, canvas, wpt, hit):
        if self.first is None and hit is not None \
                and hasattr(hit, 'a') and hasattr(hit, 'b') \
                and hasattr(hit.a, 'x') and hasattr(hit.b, 'x'):
            canvas.doc.add(PerpBisector(hit.a, hit.b))
            return
        pt = point_or_snap(canvas, wpt, hit)
        if self.first is None:
            self.first = pt
        else:
            if pt is not self.first:
                canvas.doc.add(PerpBisector(self.first, pt))
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


@register_tool(name="内心", order=42, icon="point", panel="menu",
               hint="依次点击三角形三个顶点，作内心（内切圆圆心）")
class IncenterTool(Tool):
    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 3:
            canvas.doc.add(Incenter(*self.pts))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

    def draw_overlay(self, p, view):
        if not self.pts:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        for i in range(1, len(self.pts)):
            p.drawLine(view.to_screen(self.pts[i - 1].x, self.pts[i - 1].y),
                       view.to_screen(self.pts[i].x, self.pts[i].y))
        last = self.pts[-1]
        p.drawLine(view.to_screen(last.x, last.y),
                   view.to_screen(*view.cursor_wpt))


@register_tool(name="重心", order=43, icon="point", panel="menu",
               hint="依次点击三角形三个顶点，作重心（中线交点）")
class CentroidTool(Tool):
    def __init__(self):
        self.pts = []

    def activated(self, canvas):
        self.pts = []

    def deactivated(self, canvas):
        self.pts = []

    def press(self, canvas, wpt, hit):
        self.pts.append(point_or_snap(canvas, wpt, hit))
        if len(self.pts) == 3:
            canvas.doc.add(Centroid(*self.pts))
            self.pts = []

    def cancel(self, canvas):
        self.pts = []
        canvas.update()

    def draw_overlay(self, p, view):
        if not self.pts:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        for i in range(1, len(self.pts)):
            p.drawLine(view.to_screen(self.pts[i - 1].x, self.pts[i - 1].y),
                       view.to_screen(self.pts[i].x, self.pts[i].y))
        last = self.pts[-1]
        p.drawLine(view.to_screen(last.x, last.y),
                   view.to_screen(*view.cursor_wpt))