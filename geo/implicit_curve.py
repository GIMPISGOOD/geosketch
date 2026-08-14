"""隐函数曲线：F(x,y) = 0 的等值线绘制（Marching Squares 算法）。"""
import math
from typing import List, Tuple
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainterPath
from core.registry import register_geo, register_renderer
from core.variables import evaluate, get_store
from geo.base import GeoObject
from ui import theme

PALETTE = ["#e8590c", "#1971c2", "#2f9e44", "#9c36b5",
           "#0c8599", "#e64980", "#f08c00", "#5f3dc4"]
_color_index = [0]


def next_color():
    c = PALETTE[_color_index[0] % len(PALETTE)]
    _color_index[0] += 1
    return c


@register_geo("ImplicitCurve")
class ImplicitCurve(GeoObject):
    """隐函数曲线 F(x,y)=0。"""

    def __init__(self, expr="x^2 + y^2 - 1", domain=None,
                 color=None, resolution=80):
        super().__init__(parents=())
        self.expr = expr
        self.domain = domain or (-5.0, 5.0, -5.0, 5.0)  # x0, x1, y0, y1
        self.color = color or next_color()
        self.resolution = max(20, min(200, resolution))
        self._segments: List[Tuple[Tuple[float, float],
                                   Tuple[float, float]]] = []
        self._cache_version = -1
        self.recompute()

    def recompute(self):
        store = get_store()
        if store.version == self._cache_version and self._segments:
            return
        self._segments = self._marching_squares()
        self._cache_version = store.version
        self.exists = len(self._segments) > 0

    def invalidate_cache(self):
        self._cache_version = -1

    def _eval(self, x, y):
        vd = get_store().as_dict()
        vd["x"] = x
        vd["y"] = y
        return evaluate(self.expr, vd)

    # ───────── Marching Squares ─────────
    def _marching_squares(self):
        x0, x1, y0, y1 = self.domain
        n = self.resolution
        xs = [x0 + (x1 - x0) * i / n for i in range(n + 1)]
        ys = [y0 + (y1 - y0) * i / n for i in range(n + 1)]
        grid = [[self._eval(xs[j], ys[i]) for j in range(n + 1)]
                for i in range(n + 1)]
        segments = []
        for i in range(n):
            for j in range(n):
                segs = self._cell(
                    xs[j], ys[i], xs[j + 1], ys[i + 1],
                    grid[i][j], grid[i][j + 1],
                    grid[i + 1][j + 1], grid[i + 1][j]
                )
                segments.extend(segs)
        return segments

    @staticmethod
    def _cell(x0, y0, x1, y1, v00, v10, v11, v01):
        vals = [v00, v10, v11, v01]
        if any(v is None for v in vals):
            return []
        v00, v10, v11, v01 = vals

        case = 0
        if v00 > 0: case |= 1
        if v10 > 0: case |= 2
        if v11 > 0: case |= 4
        if v01 > 0: case |= 8
        if case == 0 or case == 15:
            return []

        def lerp(va, vb, pa, pb):
            if abs(vb - va) < 1e-12:
                return ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            t = max(0.0, min(1.0, -va / (vb - va)))
            return (pa[0] + t * (pb[0] - pa[0]),
                    pa[1] + t * (pb[1] - pa[1]))

        p00, p10, p11, p01 = (x0, y0), (x1, y0), (x1, y1), (x0, y1)
        bottom = lerp(v00, v10, p00, p10) if (v00 > 0) != (v10 > 0) else None
        right = lerp(v10, v11, p10, p11) if (v10 > 0) != (v11 > 0) else None
        top = lerp(v01, v11, p01, p11) if (v01 > 0) != (v11 > 0) else None
        left = lerp(v00, v01, p00, p01) if (v00 > 0) != (v01 > 0) else None

        pts = [p for p in (bottom, right, top, left) if p is not None]
        if len(pts) == 2:
            return [(pts[0], pts[1])]
        if len(pts) == 4:
            center = (v00 + v10 + v11 + v01) / 4
            if center > 0:
                return [(bottom, right), (top, left)]
            return [(bottom, left), (right, top)]
        return []

    # ───────── 拾取 ─────────
    def distance_to(self, x, y):
        if not self._segments:
            return None
        best = float('inf')
        for (ax, ay), (bx, by) in self._segments:
            dx, dy = bx - ax, by - ay
            denom = dx * dx + dy * dy
            if denom < 1e-12:
                d = math.hypot(x - ax, y - ay)
            else:
                t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / denom))
                d = math.hypot(x - (ax + t * dx), y - (ay + t * dy))
            best = min(best, d)
        return best

    # ───────── 序列化 ─────────
    def dump(self):
        return {"expr": self.expr, "domain": list(self.domain),
                "color": self.color, "resolution": self.resolution}

    @classmethod
    def build(cls, parents, params):
        return cls(params.get("expr", "x^2 + y^2 - 1"),
                   tuple(params.get("domain", (-5, 5, -5, 5))),
                   params.get("color"),
                   params.get("resolution", 80))


@register_renderer(ImplicitCurve)
def draw_implicit(p, obj, view):
    if not obj.exists or not obj._segments:
        return
    color = theme.SELECTED if obj.selected else obj.color
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    for (ax, ay), (bx, by) in obj._segments:
        sa = view.to_screen(ax, ay)
        sb = view.to_screen(bx, by)
        path.moveTo(sa)
        path.lineTo(sb)
    p.drawPath(path)