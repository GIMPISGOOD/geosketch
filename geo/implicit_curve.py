"""隐函数曲线：F(x,y) = 0 的等值线绘制。

采样计算统一委托给 geo.implicit_sampler（唯一 Marching Squares 实现）。
首次构造同步计算；后续变量/域变化走子线程异步采样。
渲染路径（QPainterPath）按数据版本缓存，避免每帧重建。
"""

import math
from typing import List, Tuple, Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath

from core.registry import register_geo, register_renderer
from core.variables import evaluate, get_store
from geo.base import GeoObject
from ui import theme

PALETTE = [
    "#e8590c", "#1971c2", "#2f9e44", "#9c36b5",
    "#0c8599", "#e64980", "#f08c00", "#5f3dc4",
]
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


def validate_implicit_expr(expr: str) -> Optional[str]:
    """验证隐函数表达式合法性。返回错误消息或 None（合法）。"""
    if not expr.strip():
        return "表达式不能为空"
    resolved = parse_equation(expr)
    vd = {"x": 1.0, "y": 1.0}
    store_dict = get_store().as_dict()
    vd.update(store_dict)
    result = evaluate(resolved, vd)
    if result is None:
        return "表达式无法求值（请检查语法）"
    if isinstance(result, complex):
        return "表达式产生复数结果"
    return None


@register_geo("ImplicitCurve")
class ImplicitCurve(GeoObject):
    """隐函数曲线 F(x,y)=0。"""

    def __init__(self, expr="x^2+y^2=1", domain=None,
                 color=None, resolution=80, label_text=None):
        super().__init__(parents=())
        self.expr = expr
        self._resolved_expr = parse_equation(expr)
        self.domain = domain or (-5.0, 5.0, -5.0, 5.0)
        self.color = color or next_color()
        self.resolution = max(30, min(200, resolution))
        self.label_text = label_text

        self._segments: List[Tuple[float, float, float, float]] = []
        self._cache_version: int = -1
        self._cache_dirty: bool = True
        self._cache_domain: tuple = (None, None, None, None)

        # 渲染路径缓存
        self._path: Optional[QPainterPath] = None
        self._path_seg_count: int = -1

        # 首次同步计算
        self._sync_compute()

    # ── 域管理 ──────────────────────────────────────────

    def get_domain(self, view=None):
        if self.domain:
            return self.domain
        if view is None:
            return (-5.0, 5.0, -5.0, 5.0)
        x0, _ = view.to_world(QPointF(0, 0))
        x1, _ = view.to_world(QPointF(view.width(), 0))
        _, y0 = view.to_world(QPointF(0, view.height()))
        _, y1 = view.to_world(QPointF(0, 0))
        return (min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

    # ── 同步计算（构造/加载） ───────────────────────────

    def _sync_compute(self):
        from geo.implicit_sampler import march_squares_sync
        vd = get_store().as_dict()
        x0, x1, y0, y1 = self.domain
        self._segments = march_squares_sync(
            self._resolved_expr, vd, x0, x1, y0, y1, self.resolution
        )
        self._cache_version = get_store().version
        self._cache_dirty = False
        self._cache_domain = self.domain
        self._invalidate_path()
        self.exists = len(self._segments) > 0

    # ── 异步重算 ────────────────────────────────────────

    def recompute(self):
        store = get_store()
        if not self._cache_dirty and store.version == self._cache_version:
            return
        self._submit_async()

    def _submit_async(self):
        from geo.implicit_sampler import get_implicit_sampler
        sampler = get_implicit_sampler()
        vd = get_store().as_dict()
        sampler.submit(
            self.id, self._resolved_expr, self.domain,
            self.resolution, vd,
        )
        self._cache_version = get_store().version
        self._cache_dirty = False

    def ensure_fresh(self, view):
        if self._cache_dirty:
            self._submit_async()

    # ── 子线程回调 ──────────────────────────────────────

    def update_cache(self, segments, var_version, domain):
        self._segments = segments
        self._cache_version = var_version
        self._cache_domain = domain
        self._cache_dirty = False
        self._invalidate_path()
        self.exists = len(self._segments) > 0

    def invalidate_cache(self):
        self._cache_dirty = True

    # ── 渲染路径缓存 ────────────────────────────────────

    def _invalidate_path(self):
        self._path = None
        self._path_seg_count = -1

    def get_path(self, view) -> Optional[QPainterPath]:
        if (self._path is not None
                and self._path_seg_count == len(self._segments)):
            return self._path
        if not self._segments:
            return None
        path = QPainterPath()
        for x1, y1, x2, y2 in self._segments:
            sp1 = view.to_screen(x1, y1)
            sp2 = view.to_screen(x2, y2)
            path.moveTo(sp1)
            path.lineTo(sp2)
        self._path = path
        self._path_seg_count = len(self._segments)
        return path

    # ── 命中检测 ────────────────────────────────────────

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
            if d < best:
                best = d
                if best < 1e-9:
                    break
        return best

    # ── 序列化 ──────────────────────────────────────────

    def default_label(self):
        return self.expr

    def dump(self):
        return {
            "expr": self.expr,
            "domain": list(self.domain),
            "color": self.color,
            "resolution": self.resolution,
            "label_text": self.label_text,
        }

    @classmethod
    def build(cls, parents, params):
        return cls(
            params.get("expr", "x^2+y^2=1"),
            tuple(params["domain"]) if params.get("domain") else None,
            params.get("color"),
            params.get("resolution", 80),
            params.get("label_text"),
        )


# ──────────────────────────────────────────────────────────
#  渲染器
# ──────────────────────────────────────────────────────────

@register_renderer(ImplicitCurve)
def draw_implicit(p, obj, view):
    obj.ensure_fresh(view)
    if not obj.exists or not obj._segments:
        return
    color = theme.SELECTED if obj.selected else obj.color
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = obj.get_path(view)
    if path is not None and path.elementCount() > 0:
        p.drawPath(path)