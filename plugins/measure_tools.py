"""度量工具集：长度、距离、角度、比值、面积、周长、半径、直径、斜率、坐标。
统一用 Measure 对象显示度量值，随几何对象实时刷新。全部注册到「度量」菜单。"""
import math

from PySide6.QtGui import QPainterPath

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from tools.base import Tool, point_or_snap
from ui import theme
from ui.math import draw_math


# ───────── 度量计算辅助 ─────────
def _polygon_area(verts):
    n = len(verts)
    if n < 3:
        return 0.0
    s = sum(verts[i][0] * verts[(i + 1) % n][1] - verts[(i + 1) % n][0] * verts[i][1]
            for i in range(n))
    return abs(s) / 2


def _polygon_perimeter(verts):
    n = len(verts)
    if n < 2:
        return 0.0
    return sum(math.hypot(verts[(i + 1) % n][0] - verts[i][0],
                          verts[(i + 1) % n][1] - verts[i][1]) for i in range(n))


def _get_vertices(obj):
    tn = type(obj).__name__
    if tn == "RegularPolygon":
        return list(obj.verts)
    if tn == "FilledPolygon":
        return [(p.x, p.y) for p in obj.pts]
    return None


def _object_area(obj):
    tn = type(obj).__name__
    if tn == "Circle":
        return math.pi * obj.r ** 2
    if tn == "Ellipse":
        return math.pi * abs(obj.ux * obj.vy - obj.uy * obj.vx)
    verts = _get_vertices(obj)
    return _polygon_area(verts) if verts else 0.0


def _object_perimeter(obj):
    tn = type(obj).__name__
    if tn == "Circle":
        return 2 * math.pi * obj.r
    if tn == "Ellipse":
        a = math.hypot(obj.ux, obj.uy)
        b = math.hypot(obj.vx, obj.vy)
        if a + b <= 0:
            return 0.0
        h = (a - b) ** 2 / (a + b) ** 2          # Ramanujan 近似
        return math.pi * (a + b) * (1 + 3 * h / (10 + math.sqrt(4 - 3 * h)))
    verts = _get_vertices(obj)
    return _polygon_perimeter(verts) if verts else 0.0


def _is_region(obj):
    return obj is not None and type(obj).__name__ in (
        "RegularPolygon", "FilledPolygon", "Circle", "Ellipse")


MEASURE_SPEC = {
    "length":    {"label": "长度", "fmt": lambda v: f"{v:.2f}"},
    "distance":  {"label": "距离", "fmt": lambda v: f"{v:.2f}"},
    "angle":     {"label": "角度", "fmt": lambda v: f"{v:.1f}°"},
    "ratio":     {"label": "比值", "fmt": lambda v: f"{v:.3f}"},
    "area":      {"label": "面积", "fmt": lambda v: f"{v:.2f}"},
    "perimeter": {"label": "周长", "fmt": lambda v: f"{v:.2f}"},
    "radius":    {"label": "半径", "fmt": lambda v: f"{v:.2f}"},
    "diameter":  {"label": "直径", "fmt": lambda v: f"{v:.2f}"},
    "slope":     {"label": "斜率", "fmt": lambda v: "∞" if abs(v) > 1e6 else f"{v:.3f}"},
    "coord":     {"label": "坐标", "fmt": lambda v: v},
}


# ───────── 通用度量对象 ─────────
@register_geo("Measure")
class Measure(GeoObject):
    def __init__(self, kind, targets, label_pos=None):
        super().__init__(parents=tuple(targets))
        self.kind = kind
        self.targets = list(targets)
        self._fixed_lp = label_pos
        self.value = 0.0
        self.label_pos = (0.0, 0.0)
        self.recompute()

    def recompute(self):
        self.value = self._compute()
        self.label_pos = self._fixed_lp or self._auto_lp()

    def _compute(self):
        t = self.targets
        try:
            if self.kind == "length":
                return t[0].length()
            if self.kind == "distance":
                return math.hypot(t[0].x - t[1].x, t[0].y - t[1].y)
            if self.kind == "angle":
                v, p1, p2 = t[0], t[1], t[2]
                a1 = math.atan2(p1.y - v.y, p1.x - v.x)
                a2 = math.atan2(p2.y - v.y, p2.x - v.x)
                d = math.degrees(a2 - a1) % 360
                return d if d <= 180 else 360 - d
            if self.kind == "ratio":
                l1, l2 = t[0].length(), t[1].length()
                return l1 / l2 if l2 > 1e-9 else 0.0
            if self.kind == "area":
                return _object_area(t[0])
            if self.kind == "perimeter":
                return _object_perimeter(t[0])
            if self.kind == "radius":
                return t[0].r
            if self.kind == "diameter":
                return 2 * t[0].r
            if self.kind == "slope":
                s = t[0]
                dx, dy = s.b.x - s.a.x, s.b.y - s.a.y
                return dy / dx if abs(dx) > 1e-9 else float("inf")
            if self.kind == "coord":
                return f"({t[0].x:.2f}, {t[0].y:.2f})"
        except Exception:
            return 0.0
        return 0.0

    def _auto_lp(self):
        t = self.targets
        if self.kind == "length":
            s = t[0]
            mx, my = (s.a.x + s.b.x) / 2, (s.a.y + s.b.y) / 2
            dx, dy = s.b.x - s.a.x, s.b.y - s.a.y
            L = math.hypot(dx, dy) or 1.0
            return (mx - dy / L * 0.3, my + dx / L * 0.3)
        if self.kind == "distance":
            return ((t[0].x + t[1].x) / 2, (t[0].y + t[1].y) / 2)
        if self.kind == "angle":
            v, p1, p2 = t[0], t[1], t[2]
            a1 = math.atan2(p1.y - v.y, p1.x - v.x)
            a2 = math.atan2(p2.y - v.y, p2.x - v.x)
            mid = (a1 + a2) / 2
            return (v.x + 0.6 * math.cos(mid), v.y + 0.6 * math.sin(mid))
        if self.kind in ("area", "perimeter"):
            verts = _get_vertices(t[0])
            if verts:
                return (sum(v[0] for v in verts) / len(verts),
                        sum(v[1] for v in verts) / len(verts))
            if type(t[0]).__name__ in ("Circle", "Ellipse"):
                return (t[0].center.x, t[0].center.y)
        if self.kind in ("radius", "diameter"):
            c = t[0]
            return (c.center.x + c.r * 0.5, c.center.y)
        if self.kind == "slope":
            s = t[0]
            return ((s.a.x + s.b.x) / 2, (s.a.y + s.b.y) / 2)
        if self.kind == "coord":
            return (t[0].x, t[0].y)
        return (0.0, 0.0)

    def distance_to(self, x, y):
        return math.hypot(x - self.label_pos[0], y - self.label_pos[1])

    def dump(self):
        return {"kind": self.kind,
                "label_pos": list(self._fixed_lp) if self._fixed_lp else None}

    @classmethod
    def build(cls, parents, params):
        lp = params.get("label_pos")
        return cls(params["kind"], parents, tuple(lp) if lp else None)


@register_renderer(Measure)
def draw_measure(p, obj, view):
    if not obj.exists:
        return
    spec = MEASURE_SPEC.get(obj.kind)
    if not spec:
        return
    color = theme.SELECTED if obj.selected else theme.MEASURE
    # 角度：画两条短臂 + 弧
    if obj.kind == "angle":
        v, p1, p2 = obj.targets[0], obj.targets[1], obj.targets[2]
        a1 = math.atan2(p1.y - v.y, p1.x - v.x)
        a2 = math.atan2(p2.y - v.y, p2.x - v.x)
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
    # 文本标签
    text = f"{spec['label']} = {spec['fmt'](obj.value)}"
    sp = view.to_screen(*obj.label_pos)
    draw_math(p, sp.x() + 4, sp.y(), text, 13, color)


# ───────── 度量工具基类 ─────────
class MeasureTool(Tool):
    kind = None
    n_targets = 1

    def __init__(self):
        self.targets = []

    def activated(self, canvas):
        self.targets = []

    def deactivated(self, canvas):
        self.targets = []

    def _get_target(self, canvas, wpt, hit):
        raise NotImplementedError

    def press(self, canvas, wpt, hit):
        tgt = self._get_target(canvas, wpt, hit)
        if tgt is None:
            return
        self.targets.append(tgt)
        if len(self.targets) >= self.n_targets:
            canvas.doc.add(Measure(self.kind, self.targets))
            self.targets = []
        canvas.update()

    def cancel(self, canvas):
        self.targets = []
        canvas.update()

    def draw_overlay(self, p, view):
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        for t in self.targets:
            if hasattr(t, "x"):
                p.drawEllipse(view.to_screen(t.x, t.y), 7, 7)


class LengthMeasureTool(MeasureTool):
    kind, n_targets = "length", 1
    def _get_target(self, canvas, wpt, hit):
        return hit if type(hit).__name__ == "Segment" else None


class DistanceMeasureTool(MeasureTool):
    kind, n_targets = "distance", 2
    def _get_target(self, canvas, wpt, hit):
        return point_or_snap(canvas, wpt, hit)


class AngleMeasureTool(MeasureTool):
    kind, n_targets = "angle", 3
    def _get_target(self, canvas, wpt, hit):
        return point_or_snap(canvas, wpt, hit)


class RatioMeasureTool(MeasureTool):
    kind, n_targets = "ratio", 2
    def _get_target(self, canvas, wpt, hit):
        return hit if type(hit).__name__ == "Segment" else None


class AreaMeasureTool(MeasureTool):
    kind, n_targets = "area", 1
    def _get_target(self, canvas, wpt, hit):
        return hit if _is_region(hit) else None


class PerimeterMeasureTool(MeasureTool):
    kind, n_targets = "perimeter", 1
    def _get_target(self, canvas, wpt, hit):
        return hit if _is_region(hit) else None


class RadiusMeasureTool(MeasureTool):
    kind, n_targets = "radius", 1
    def _get_target(self, canvas, wpt, hit):
        return hit if type(hit).__name__ == "Circle" else None


class DiameterMeasureTool(MeasureTool):
    kind, n_targets = "diameter", 1
    def _get_target(self, canvas, wpt, hit):
        return hit if type(hit).__name__ == "Circle" else None


class SlopeMeasureTool(MeasureTool):
    kind, n_targets = "slope", 1
    def _get_target(self, canvas, wpt, hit):
        return hit if type(hit).__name__ in ("Segment", "Line") else None


class CoordMeasureTool(MeasureTool):
    kind, n_targets = "coord", 1
    def _get_target(self, canvas, wpt, hit):
        return point_or_snap(canvas, wpt, hit)


# 全部注册到「度量」菜单（panel="measure"）
register_tool(name="长度", order=1, panel="measure", hint="点击线段度量长度")(LengthMeasureTool)
register_tool(name="距离", order=2, panel="measure", hint="点击两点度量距离")(DistanceMeasureTool)
register_tool(name="角度", order=3, panel="measure", hint="依次点顶点、两边上的点度量角度")(AngleMeasureTool)
register_tool(name="比值", order=4, panel="measure", hint="点击两条线段度量长度比值")(RatioMeasureTool)
register_tool(name="面积", order=5, panel="measure", hint="点击多边形/圆/椭圆度量面积")(AreaMeasureTool)
register_tool(name="周长", order=6, panel="measure", hint="点击多边形/圆/椭圆度量周长")(PerimeterMeasureTool)
register_tool(name="半径", order=7, panel="measure", hint="点击圆度量半径")(RadiusMeasureTool)
register_tool(name="直径", order=8, panel="measure", hint="点击圆度量直径")(DiameterMeasureTool)
register_tool(name="斜率", order=9, panel="measure", hint="点击线段/直线度量斜率")(SlopeMeasureTool)
register_tool(name="坐标", order=10, panel="measure", hint="点击点度量其坐标")(CoordMeasureTool)