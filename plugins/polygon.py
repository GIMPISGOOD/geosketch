"""正多边形插件：一个文件即一个完整功能。

包含：RegularPolygon 几何对象、渲染器、与线段/圆/多边形的交点求解器、
「工具」菜单里的插件工具（panel="menu"）、以及激活后弹出的 3~8 边数选择器。
"""
import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainterPath
from PySide6.QtWidgets import (QButtonGroup, QGraphicsDropShadowEffect,
                               QHBoxLayout, QLabel, QToolButton, QWidget)

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from geo.circles import Circle
from geo.intersects import register_solver, _seg_circle, _seg_seg
from geo.segments import Segment
from tools.base import Tool, point_or_snap
from geo.points import AbstractPoint
from ui import theme


# ───────────────────────── 几何对象 ─────────────────────────
@register_geo("RegularPolygon")
class RegularPolygon(GeoObject):
    """正 n 边形：由中心点 + 一个顶点完全确定。"""

    def __init__(self, center, vertex, n=3):
        super().__init__(parents=(center, vertex))
        self.center = center
        self.vertex = vertex
        self.n = n
        self.verts = []
        self.recompute()

    def recompute(self):
        cx, cy = self.center.x, self.center.y
        vx, vy = self.vertex.x, self.vertex.y
        self.r = math.hypot(vx - cx, vy - cy)
        self.angle0 = math.atan2(vy - cy, vx - cx)
        self.verts = []
        for k in range(self.n):
            ang = self.angle0 + 2 * math.pi * k / self.n
            self.verts.append((cx + self.r * math.cos(ang),
                               cy + self.r * math.sin(ang)))

    def edges(self):
        return [(self.verts[i], self.verts[(i + 1) % self.n])
                for i in range(self.n)]

    def distance_to(self, x, y):
        if not self.verts:
            return None
        return min(_point_seg_dist(x, y, *e[0], *e[1]) for e in self.edges())

    def dump(self):
        return {"n": self.n}

    def point_at(self, t):
        """t ∈ [0,1] 沿多边形周长参数化。"""
        n = len(self.verts)
        if n < 2:
            return self.verts[0] if self.verts else (0.0, 0.0)
        seg_t = (t % 1.0) * n
        i = int(seg_t) % n
        frac = seg_t - int(seg_t)
        a = self.verts[i]
        b = self.verts[(i + 1) % n]
        return (a[0] + (b[0] - a[0]) * frac, a[1] + (b[1] - a[1]) * frac)

    def project(self, x, y):
        """投影到多边形周长，返回参数 t ∈ [0,1]。"""
        n = len(self.verts)
        if n < 2:
            return 0.0
        best_t, best_d = 0.0, float("inf")
        for i in range(n):
            a = self.verts[i]
            b = self.verts[(i + 1) % n]
            dx, dy = b[0] - a[0], b[1] - a[1]
            denom = dx * dx + dy * dy
            if denom < 1e-12:
                continue
            f = max(0.0, min(1.0, ((x - a[0]) * dx + (y - a[1]) * dy) / denom))
            px, py = a[0] + f * dx, a[1] + f * dy
            d = (px - x) ** 2 + (py - y) ** 2
            if d < best_d:
                best_d, best_t = d, (i + f) / n
        return best_t

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], params.get("n", 3))


def _point_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    t = 0.0 if denom == 0 else max(0.0, min(1.0,
            ((px - x1) * dx + (py - y1) * dy) / denom))
    return math.hypot(x1 + t * dx - px, y1 + t * dy - py)


@register_renderer(RegularPolygon)
def draw_polygon(p, obj, view):
    if len(obj.verts) < 3:
        return
    path = QPainterPath()
    path.moveTo(view.to_screen(*obj.verts[0]))
    for v in obj.verts[1:]:
        path.lineTo(view.to_screen(*v))
    path.closeSubpath()
    color = theme.SELECTED if obj.selected else theme.POLYGON
    fill = QColor(color)
    fill.setAlpha(40)
    p.setBrush(theme.brush(fill))
    p.setPen(theme.pen(color, 2.0))
    p.drawPath(path)


# ───────────────────────── 交点求解器（多边形参与）─────────────────────────
@register_solver(RegularPolygon, Segment)
def _solve_poly_seg(poly, seg):
    pts = []
    for (x1, y1), (x2, y2) in poly.edges():
        pts += _seg_seg((x1, y1), (x2, y2),
                        (seg.a.x, seg.a.y), (seg.b.x, seg.b.y))
    return pts


@register_solver(RegularPolygon, Circle)
def _solve_poly_circle(poly, cir):
    pts = []
    for (x1, y1), (x2, y2) in poly.edges():
        pts += _seg_circle((x1, y1), (x2, y2),
                           (cir.center.x, cir.center.y), cir.r)
    return pts


@register_solver(RegularPolygon, RegularPolygon)
def _solve_poly_poly(p1, p2):
    pts = []
    for e1 in p1.edges():
        for e2 in p2.edges():
            pts += _seg_seg(e1[0], e1[1], e2[0], e2[1])
    return pts


# ───────────────────────── 边数选择器 ─────────────────────────
class SidesPicker(QWidget):
    """浮动边数选择器：3~8 边形，选中项高亮。"""
    sides_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidesPicker")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)

        layout.addWidget(QLabel("边数", self))
        group = QButtonGroup(self)
        group.setExclusive(True)
        for n in range(3, 9):
            btn = QToolButton(self)
            btn.setText(str(n))
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, n=n: self.sides_changed.emit(n))
            group.addButton(btn)
            layout.addWidget(btn)
            if n == PolygonTool.n:
                btn.setChecked(True)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(35, 60, 92, 40))
        self.setGraphicsEffect(shadow)


# ───────────────────────── 工具（「工具」菜单 · 插件区）─────────────────────────
@register_tool(name="多边形", shortcut="G", order=10, icon="polygon", panel="menu",
               hint="第一下定中心，第二下定顶点；上方选择边数（3~8）绘制正多边形；Esc 取消")
class PolygonTool(Tool):
    n = 3                                                # 类属性：跨实例记住边数

    def __init__(self):
        self.center = None
        self._picker = None

    def activated(self, canvas):
        self.center = None
        self._picker = SidesPicker(canvas)
        self._picker.sides_changed.connect(self._set_sides)
        self._picker.adjustSize()
        self._picker.move((canvas.width() - self._picker.width()) // 2, 14)
        self._picker.show()
        self._picker.raise_()

    def _set_sides(self, n):
        PolygonTool.n = n

    def deactivated(self, canvas):
        self.center = None
        if self._picker is not None:
            self._picker.hide()
            self._picker.deleteLater()
            self._picker = None

    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if self.center is None:
            self.center = pt
        else:
            if pt is not self.center:
                poly = canvas.doc.add(RegularPolygon(self.center, pt, PolygonTool.n))
                for k in range(PolygonTool.n):          # 每个顶点标记为特殊点
                    canvas.doc.add(PolygonVertex(poly, k))
            self.center = None

    def cancel(self, canvas):
        self.center = None
        canvas.update()

    def draw_overlay(self, p, view):
        if self.center is None:
            return
        cx, cy = self.center.x, self.center.y
        r = math.hypot(view.cursor_wpt[0] - cx, view.cursor_wpt[1] - cy)
        a0 = math.atan2(view.cursor_wpt[1] - cy, view.cursor_wpt[0] - cx)
        path = QPainterPath()
        pts = [view.to_screen(cx + r * math.cos(a0 + 2 * math.pi * k / PolygonTool.n),
                              cy + r * math.sin(a0 + 2 * math.pi * k / PolygonTool.n))
               for k in range(PolygonTool.n)]
        path.moveTo(pts[0])
        for q in pts[1:]:
            path.lineTo(q)
        path.closeSubpath()
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

# ───────────── 新增：多边形顶点（特殊点，从动于多边形，可磁吸）─────────────
@register_geo("PolygonVertex")
class PolygonVertex(AbstractPoint):
    """正多边形的第 k 个顶点：从动于多边形，不可拖动，可被磁吸。"""
    def __init__(self, poly, k):
        super().__init__(parents=(poly,))
        self.poly = poly
        self.k = k
        self.recompute()

    def recompute(self):
        self.x, self.y = self.poly.verts[self.k]

    def dump(self):
        return {"k": self.k}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], params["k"])


@register_renderer(PolygonVertex)
def draw_poly_vertex(p, obj, view):
    """空心环 + 中心点（与交点同风格，表示"派生点"）"""
    qpt = view.to_screen(obj.x, obj.y)
    color = theme.SELECTED if obj.selected else theme.POLYGON
    r = 4.5 if obj.selected else 3.5
    p.setPen(theme.pen(color, 1.8))
    p.setBrush(theme.brush(theme.BG_TOP))
    p.drawEllipse(qpt, r, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(qpt, 1.5, 1.5)