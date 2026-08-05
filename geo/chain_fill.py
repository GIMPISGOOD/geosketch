"""链式填充：由"点+曲线"有序链围成的闭合区域。

新增：
- 弧段条件：auto / short / long / ccw / cw
- 填充规则：evenodd / winding
- 点击闭合曲线时可根据点击位置选择期望弧段
"""

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QBrush, QLinearGradient, QPainterPath

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme


# ───────────── 几何工具 ─────────────

def _point_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    t = 0.0 if denom == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
    return math.hypot(x1 + t * dx - px, y1 + t * dy - py)


def _point_in_polygon(x, y, pts):
    inside, n = False, len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def polygon_edge(poly, x, y):
    """返回离点 (x,y) 最近的多边形边索引。"""
    best_k, best_d = 0, float("inf")

    for k in range(poly.n):
        a = poly.verts[k]
        b = poly.verts[(k + 1) % poly.n]
        d = _point_seg_dist(x, y, a[0], a[1], b[0], b[1])
        if d < best_d:
            best_k, best_d = k, d

    return best_k


def hatch_lines(p, rect, color, opacity, gap=8, angle=45):
    """在矩形内画一组指定角度/间距的斜线（配合裁剪使用）。"""
    a = math.radians(angle)
    dx, dy = math.cos(a), math.sin(a)
    px, py = -math.sin(a), math.cos(a)

    diag = math.hypot(rect.width(), rect.height()) * 1.5
    cx, cy = rect.center().x(), rect.center().y()
    n = int(diag / gap) + 2

    c = QColor(color)
    c.setAlphaF(opacity)
    p.setPen(theme.pen(c, 1.2))

    for i in range(-n, n + 1):
        ox, oy = cx + px * i * gap, cy + py * i * gap
        p.drawLine(
            QPointF(ox - dx * diag, oy - dy * diag),
            QPointF(ox + dx * diag, oy + dy * diag)
        )


# ───────────── 弧段条件 ─────────────

ARC_MODES = ("auto", "short", "long", "ccw", "cw")


def _closed_span(t0: float, t1: float, mode: str = "auto") -> float:
    """
    计算闭合曲线从 t0 到 t1 的参数跨度。

    mode:
        auto   自动，默认短弧
        short  短弧
        long   长弧
        ccw    逆时针方向，即参数增加方向
        cw     顺时针方向，即参数减少方向
    """
    eps = 1e-9
    delta = (t1 - t0) % 1.0

    # 逆时针：参数增加方向
    if mode == "ccw":
        return delta if delta > eps else 1.0

    # 顺时针：参数减少方向
    if mode == "cw":
        return delta - 1.0 if delta > eps else -1.0

    # 长弧
    if mode == "long":
        if delta <= eps or delta >= 1.0 - eps:
            return 1.0
        if delta < 0.5:
            return delta - 1.0
        return delta

    # auto / short：短弧
    if delta <= eps or delta >= 1.0 - eps:
        return 0.0

    if delta > 0.5:
        return delta - 1.0

    return delta


def choose_closed_arc(curve, from_pt, to_pt, prefer):
    """
    根据用户点击位置 prefer，在闭合曲线的两段候选弧中选择一段。

    返回:
        "ccw" 或 "cw"
    """
    if not getattr(curve, "closed", False):
        return "auto"

    t0 = curve.project(from_pt.x, from_pt.y)
    t1 = curve.project(to_pt.x, to_pt.y)

    eps = 1e-9
    delta = (t1 - t0) % 1.0

    # 逆时针候选
    span_ccw = delta if delta > eps else 1.0
    mid_ccw = curve.point_at(t0 + span_ccw * 0.5)
    d_ccw = math.hypot(mid_ccw[0] - prefer[0], mid_ccw[1] - prefer[1])

    # 顺时针候选
    span_cw = delta - 1.0 if delta > eps else -1.0
    mid_cw = curve.point_at(t0 + span_cw * 0.5)
    d_cw = math.hypot(mid_cw[0] - prefer[0], mid_cw[1] - prefer[1])

    return "ccw" if d_ccw <= d_cw else "cw"


# ───────────── 曲线引用 & 段 ─────────────

class CurveRef:
    """曲线引用：整条曲线对象，或多边形的第 edge 条边。"""

    def __init__(self, obj, edge=None):
        self.obj = obj
        self.edge = edge

    def point_at(self, t):
        if self.edge is None:
            return self.obj.point_at(t)

        poly = self.obj
        a = poly.verts[self.edge]
        b = poly.verts[(self.edge + 1) % poly.n]

        return (
            a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t
        )

    def project(self, x, y):
        if self.edge is None:
            return self.obj.project(x, y)

        poly = self.obj
        a = poly.verts[self.edge]
        b = poly.verts[(self.edge + 1) % poly.n]

        dx, dy = b[0] - a[0], b[1] - a[1]
        denom = dx * dx + dy * dy

        if denom == 0:
            return 0.0

        return max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / denom))

    @property
    def closed(self):
        if self.edge is None:
            if hasattr(self.obj, "closed"):
                return bool(self.obj.closed)

            # 兼容未显式设置 closed 的对象
            return type(self.obj).__name__ in (
                "Circle",
                "ExprCircle",
                "Ellipse",
            )

        return False


class Span:
    """边界的一段：from_pt → to_pt，可选沿某条曲线。"""

    def __init__(self, from_pt, to_pt, curve=None, arc="auto"):
        self.from_pt = from_pt
        self.to_pt = to_pt
        self.curve = curve
        self.arc = arc if arc in ARC_MODES else "auto"


def sample_span(sp, n=32):
    """把一段采样成折线。闭合曲线根据 arc 条件取弧段。"""
    result = [(sp.from_pt.x, sp.from_pt.y)]

    if sp.curve is not None:
        c = sp.curve

        t0 = c.project(sp.from_pt.x, sp.from_pt.y)
        t1 = c.project(sp.to_pt.x, sp.to_pt.y)

        if c.closed:
            span_t = _closed_span(t0, t1, getattr(sp, "arc", "auto"))
        else:
            span_t = t1 - t0

        for i in range(1, n):
            result.append(c.point_at(t0 + span_t * i / n))

    result.append((sp.to_pt.x, sp.to_pt.y))
    return result


# ───────────── 填充样式 ─────────────

class FillStyle:
    def __init__(self, color, opacity=0.6, kind="solid", fill_rule="evenodd"):
        self.color = QColor(color)
        self.opacity = opacity
        self.kind = kind
        self.fill_rule = fill_rule if fill_rule in ("evenodd", "winding") else "evenodd"

    def dump(self):
        return {
            "color": self.color.name(),
            "opacity": self.opacity,
            "kind": self.kind,
            "fill_rule": self.fill_rule,
        }

    @classmethod
    def from_dump(cls, d):
        return cls(
            QColor(d["color"]),
            d.get("opacity", 0.6),
            d.get("kind", "solid"),
            d.get("fill_rule", "evenodd"),
        )


# ───────────── 链式填充对象 ─────────────

@register_geo("ChainFill")
class ChainFill(GeoObject):
    def __init__(self, spans, style):
        parents, seen = [], set()

        for sp in spans:
            for obj in (sp.from_pt, sp.to_pt):
                if id(obj) not in seen:
                    seen.add(id(obj))
                    parents.append(obj)

            if sp.curve is not None and id(sp.curve.obj) not in seen:
                seen.add(id(sp.curve.obj))
                parents.append(sp.curve.obj)

        super().__init__(parents=tuple(parents))

        self.spans = spans
        self.style = style
        self.path_pts = []

        self.recompute()

    def recompute(self):
        pts = []

        for sp in self.spans:
            pts.extend(sample_span(sp)[:-1])

        self.path_pts = pts
        self.exists = len(pts) >= 3 and abs(self._area()) > 1e-9

    def _area(self):
        pts, n = self.path_pts, len(self.path_pts)

        if n < 3:
            return 0.0

        return sum(
            pts[i][0] * pts[(i + 1) % n][1] -
            pts[(i + 1) % n][0] * pts[i][1]
            for i in range(n)
        ) / 2

    def distance_to(self, x, y):
        if not self.path_pts:
            return None

        if _point_in_polygon(x, y, self.path_pts):
            return 0.0

        best, n = float("inf"), len(self.path_pts)

        for i in range(n):
            best = min(
                best,
                _point_seg_dist(
                    x, y,
                    *self.path_pts[i],
                    *self.path_pts[(i + 1) % n]
                )
            )

        return best

    def dump(self):
        pidx = {id(pp): i for i, pp in enumerate(self.parents)}
        spans_data = []

        for sp in self.spans:
            curve = None

            if sp.curve is not None:
                curve = {
                    "obj": pidx[id(sp.curve.obj)],
                    "edge": sp.curve.edge
                }

            spans_data.append({
                "from": pidx[id(sp.from_pt)],
                "to": pidx[id(sp.to_pt)],
                "curve": curve,
                "arc": getattr(sp, "arc", "auto"),
            })

        return {
            "spans": spans_data,
            "style": self.style.dump(),
        }

    @classmethod
    def build(cls, parents, params):
        spans = []

        for sd in params["spans"]:
            curve = None

            if sd.get("curve") is not None:
                curve = CurveRef(
                    parents[sd["curve"]["obj"]],
                    sd["curve"]["edge"]
                )

            spans.append(
                Span(
                    parents[sd["from"]],
                    parents[sd["to"]],
                    curve,
                    sd.get("arc", "auto"),
                )
            )

        return cls(spans, FillStyle.from_dump(params["style"]))


@register_renderer(ChainFill)
def draw_chain_fill(p, obj, view):
    if not obj.exists or len(obj.path_pts) < 3:
        return

    p.save()

    try:
        path = QPainterPath()
        path.moveTo(view.to_screen(*obj.path_pts[0]))

        for pt in obj.path_pts[1:]:
            path.lineTo(view.to_screen(*pt))

        path.closeSubpath()

        st = obj.style

        # ★ 填充规则
        path.setFillRule(
            Qt.FillRule.WindingFill
            if getattr(st, "fill_rule", "evenodd") == "winding"
            else Qt.FillRule.OddEvenFill
        )

        color = QColor(st.color)

        if st.kind == "gradient":
            bbox = path.boundingRect()
            g = QLinearGradient(bbox.topLeft(), bbox.bottomRight())

            c1 = QColor(color)
            c1.setAlphaF(st.opacity)

            c2 = QColor(color)
            c2.setAlphaF(st.opacity * 0.12)

            g.setColorAt(0, c1)
            g.setColorAt(1, c2)

            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

        elif st.kind in ("hatch", "crosshatch"):
            p.save()
            p.setClipPath(path)

            hatch_lines(p, path.boundingRect(), color, st.opacity, 8, 45)

            if st.kind == "crosshatch":
                hatch_lines(p, path.boundingRect(), color, st.opacity, 8, -45)

            p.restore()

        else:
            color.setAlphaF(st.opacity)
            p.setBrush(theme.brush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

    finally:
        p.restore()