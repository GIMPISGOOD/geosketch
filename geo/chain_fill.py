"""链式填充：由"点+曲线"有序链围成的闭合区域。
边界可混合 点（顶点）与任意曲线（线段/圆/椭圆弧/贝塞尔/多边形边）；
支持 纯色/渐变/斜线/交叉线 四种填充样式，颜色与透明度用户自定义，无描边。
边界退化（面积趋近 0）时自动隐藏，恢复后自动出现。"""
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
        p.drawLine(QPointF(ox - dx * diag, oy - dy * diag),
                   QPointF(ox + dx * diag, oy + dy * diag))


# ───────────── 曲线引用 & 段 ─────────────
class CurveRef:
    """曲线引用：整条曲线对象，或多边形的第 edge 条边。
    统一提供 point_at / project / closed，使多边形边也能参与链式边界。"""
    def __init__(self, obj, edge=None):
        self.obj = obj
        self.edge = edge

    def point_at(self, t):
        if self.edge is None:
            return self.obj.point_at(t)
        poly = self.obj
        a = poly.verts[self.edge]
        b = poly.verts[(self.edge + 1) % poly.n]
        return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)

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
            return getattr(self.obj, "closed", False)
        return False


class Span:
    """边界的一段：from_pt → to_pt，可选沿某条曲线。"""
    def __init__(self, from_pt, to_pt, curve=None):
        self.from_pt = from_pt
        self.to_pt = to_pt
        self.curve = curve          # CurveRef 或 None（直线）


def sample_span(sp, n=32):
    """把一段采样成折线：[from_pt, ...曲线内部采样..., to_pt]。
    闭合曲线（圆/椭圆）自动取较短弧；端点若不在曲线上，由首尾直线自然衔接。"""
    result = [(sp.from_pt.x, sp.from_pt.y)]
    if sp.curve is not None:
        c = sp.curve
        t0 = c.project(sp.from_pt.x, sp.from_pt.y)
        t1 = c.project(sp.to_pt.x, sp.to_pt.y)
        if c.closed:
            span_t = (t1 - t0) % 1.0
            if span_t > 0.5:
                span_t -= 1.0       # 取较短弧
        else:
            span_t = t1 - t0
        for i in range(1, n):
            result.append(c.point_at(t0 + span_t * i / n))
    result.append((sp.to_pt.x, sp.to_pt.y))
    return result


# ───────────── 填充样式 ─────────────
class FillStyle:
    def __init__(self, color, opacity=0.6, kind="solid"):
        self.color = QColor(color)
        self.opacity = opacity
        self.kind = kind            # solid / gradient / hatch / crosshatch

    def dump(self):
        return {"color": self.color.name(), "opacity": self.opacity, "kind": self.kind}

    @classmethod
    def from_dump(cls, d):
        return cls(QColor(d["color"]), d.get("opacity", 0.6), d.get("kind", "solid"))


# ───────────── 链式填充对象 ─────────────
@register_geo("ChainFill")
class ChainFill(GeoObject):
    def __init__(self, spans, style):
        parents, seen = [], set()
        for sp in spans:
            for obj in (sp.from_pt, sp.to_pt):
                if id(obj) not in seen:
                    seen.add(id(obj)); parents.append(obj)
            if sp.curve is not None and id(sp.curve.obj) not in seen:
                seen.add(id(sp.curve.obj)); parents.append(sp.curve.obj)
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
        # 边界退化（面积≈0）时自动隐藏；恢复后自动出现
        self.exists = len(pts) >= 3 and abs(self._area()) > 1e-9

    def _area(self):
        pts, n = self.path_pts, len(self.path_pts)
        if n < 3:
            return 0.0
        return sum(pts[i][0] * pts[(i + 1) % n][1] -
                   pts[(i + 1) % n][0] * pts[i][1] for i in range(n)) / 2

    def distance_to(self, x, y):
        if not self.path_pts:
            return None
        if _point_in_polygon(x, y, self.path_pts):
            return 0.0
        best, n = float("inf"), len(self.path_pts)
        for i in range(n):
            best = min(best, _point_seg_dist(x, y, *self.path_pts[i],
                                             *self.path_pts[(i + 1) % n]))
        return best

    def dump(self):
        pidx = {id(pp): i for i, pp in enumerate(self.parents)}
        spans_data = []
        for sp in self.spans:
            curve = None
            if sp.curve is not None:
                curve = {"obj": pidx[id(sp.curve.obj)], "edge": sp.curve.edge}
            spans_data.append({"from": pidx[id(sp.from_pt)],
                               "to": pidx[id(sp.to_pt)], "curve": curve})
        return {"spans": spans_data, "style": self.style.dump()}

    @classmethod
    def build(cls, parents, params):
        spans = []
        for sd in params["spans"]:
            curve = None
            if sd.get("curve") is not None:
                curve = CurveRef(parents[sd["curve"]["obj"]], sd["curve"]["edge"])
            spans.append(Span(parents[sd["from"]], parents[sd["to"]], curve))
        return cls(spans, FillStyle.from_dump(params["style"]))


@register_renderer(ChainFill)
def draw_chain_fill(p, obj, view):
    if not obj.exists or len(obj.path_pts) < 3:
        return
    path = QPainterPath()
    path.moveTo(view.to_screen(*obj.path_pts[0]))
    for pt in obj.path_pts[1:]:
        path.lineTo(view.to_screen(*pt))
    path.closeSubpath()
    st = obj.style
    color = QColor(st.color)
    if st.kind == "gradient":
        bbox = path.boundingRect()
        g = QLinearGradient(bbox.topLeft(), bbox.bottomRight())
        c1 = QColor(color); c1.setAlphaF(st.opacity)
        c2 = QColor(color); c2.setAlphaF(st.opacity * 0.12)
        g.setColorAt(0, c1); g.setColorAt(1, c2)
        p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
        p.drawPath(path)
    elif st.kind in ("hatch", "crosshatch"):
        p.save()
        p.setClipPath(path)
        hatch_lines(p, path.boundingRect(), color, st.opacity, 8, 45)
        if st.kind == "crosshatch":
            hatch_lines(p, path.boundingRect(), color, st.opacity, 8, -45)
        p.restore()
    else:                                   # 纯色
        color.setAlphaF(st.opacity)
        p.setBrush(theme.brush(color))
        p.setPen(Qt.PenStyle.NoPen)         # 无描边
        p.drawPath(path)