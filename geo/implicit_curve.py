"""隐函数曲线：F(x,y) = 0 的等值线绘制（Marching Squares）。
支持变量联动，表达式可含滑杆变量。
"""
import math
from typing import List, Tuple, Optional
from PySide6.QtCore import QPointF, Qt
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


def parse_equation(expr: str) -> str:
    """把 'x^2+y^2=1' 转为 '(x^2+y^2)-(1)'；无等号则原样返回。"""
    expr = expr.strip()
    if "=" in expr:
        parts = expr.split("=", 1)
        return f"({parts[0].strip()})-({parts[1].strip()})"
    return expr


@register_geo("ImplicitCurve")
class ImplicitCurve(GeoObject):
    """隐函数曲线 F(x,y)=0。"""

    def __init__(self, expr="x^2+y^2=1", domain=None,
                 color=None, resolution=80, label_text=None):
        super().__init__(parents=())
        self.expr = expr
        self._resolved_expr = parse_equation(expr)
        self.domain = domain or (-5.0, 5.0, -5.0, 5.0)  # x0, x1, y0, y1
        self.color = color or next_color()
        self.resolution = max(30, min(200, resolution))
        self.label_text = label_text
        self._segments: List[Tuple[float, float, float, float]] = []
        self._cache_version: int = -1
        self._cache_dirty: bool = True
        self.recompute()

    def invalidate_cache(self):
        self._cache_dirty = True

    def recompute(self):
        store = get_store()
        if not self._cache_dirty and store.version == self._cache_version:
            return
        self._segments = self._marching_squares()
        self._cache_version = store.version
        self._cache_dirty = False
        self.exists = len(self._segments) > 0

    def _eval(self, x, y):
        vd = get_store().as_dict()
        vd["x"] = x
        vd["y"] = y
        v = evaluate(self._resolved_expr, vd)
        # ★ 修复：复数结果视为无效（负数分数次幂、sqrt负数等）
        if isinstance(v, complex):
            return None
        return v

    def _marching_squares(self):
        x0, x1, y0, y1 = self.domain
        n = self.resolution
        dx = (x1 - x0) / n
        dy = (y1 - y0) / n

        # 采样网格
        grid = [[0.0] * (n + 1) for _ in range(n + 1)]
        for i in range(n + 1):
            yy = y0 + i * dy
            for j in range(n + 1):
                xx = x0 + j * dx
                v = self._eval(xx, yy)
                # ★ 修复：None / 复数 / 非有限值 均视为无效
                if v is None or isinstance(v, complex) or not math.isfinite(v):
                    grid[i][j] = 1e18
                else:
                    grid[i][j] = v

        segments = []
        for i in range(n):
            y_b = y0 + i * dy
            y_t = y_b + dy
            row0 = grid[i]
            row1 = grid[i + 1]
            for j in range(n):
                v00 = row0[j]
                v10 = row0[j + 1]
                v11 = row1[j + 1]
                v01 = row1[j]

                if v00 > 1e17 or v10 > 1e17 or v11 > 1e17 or v01 > 1e17:
                    continue

                case = 0
                if v00 > 0: case |= 1
                if v10 > 0: case |= 2
                if v11 > 0: case |= 4
                if v01 > 0: case |= 8

                if case == 0 or case == 15:
                    continue

                x_l = x0 + j * dx
                x_r = x_l + dx

                pts = []
                if (v00 > 0) != (v10 > 0):
                    d = v00 - v10
                    t = v00 / d if abs(d) > 1e-15 else 0.5
                    pts.append((x_l + t * dx, y_b))
                if (v10 > 0) != (v11 > 0):
                    d = v10 - v11
                    t = v10 / d if abs(d) > 1e-15 else 0.5
                    pts.append((x_r, y_b + t * dy))
                if (v01 > 0) != (v11 > 0):
                    d = v01 - v11
                    t = v01 / d if abs(d) > 1e-15 else 0.5
                    pts.append((x_l + t * dx, y_t))
                if (v00 > 0) != (v01 > 0):
                    d = v00 - v01
                    t = v00 / d if abs(d) > 1e-15 else 0.5
                    pts.append((x_l, y_b + t * dy))

                if len(pts) == 2:
                    segments.append((pts[0][0], pts[0][1],
                                     pts[1][0], pts[1][1]))
                elif len(pts) == 4:
                    center = (v00 + v10 + v11 + v01) * 0.25
                    if center > 0:
                        segments.append((pts[0][0], pts[0][1],
                                         pts[1][0], pts[1][1]))
                        segments.append((pts[2][0], pts[2][1],
                                         pts[3][0], pts[3][1]))
                    else:
                        segments.append((pts[0][0], pts[0][1],
                                         pts[3][0], pts[3][1]))
                        segments.append((pts[1][0], pts[1][1],
                                         pts[2][0], pts[2][1]))
        return segments

    def distance_to(self, x, y):
        if not self._segments:
            return None
        best = float("inf")
        for x1, y1, x2, y2 in self._segments:
            ddx, ddy = x2 - x1, y2 - y1
            denom = ddx * ddx + ddy * ddy
            if denom < 1e-12:
                d = math.hypot(x - x1, y - y1)
            else:
                t = max(0.0, min(1.0,
                                 ((x - x1) * ddx + (y - y1) * ddy) / denom))
                d = math.hypot(x - (x1 + t * ddx), y - (y1 + t * ddy))
            best = min(best, d)
        return best

    def default_label(self):
        return self.expr

    def dump(self):
        return {"expr": self.expr,
                "domain": list(self.domain),
                "color": self.color,
                "resolution": self.resolution,
                "label_text": self.label_text}

    @classmethod
    def build(cls, parents, params):
        return cls(params.get("expr", "x^2+y^2=1"),
                   tuple(params["domain"]) if params.get("domain") else None,
                   params.get("color"),
                   params.get("resolution", 80),
                   params.get("label_text"))


@register_renderer(ImplicitCurve)
def draw_implicit(p, obj, view):
    if not obj.exists or not obj._segments:
        return
    color = theme.SELECTED if obj.selected else obj.color
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    for x1, y1, x2, y2 in obj._segments:
        sp1 = view.to_screen(x1, y1)
        sp2 = view.to_screen(x2, y2)
        path.moveTo(sp1)
        path.lineTo(sp2)
    if path.elementCount() > 0:
        p.drawPath(path)