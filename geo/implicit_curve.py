"""隐函数曲线：F(x,y)=0 的等值线。"""
import math
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QPainterPath
from core.registry import register_geo, register_renderer
from core.variables import get_store
from geo.base import GeoObject
from ui import theme

PALETTE = ["#e8590c", "#1971c2", "#2f9e44", "#9c36b5",
           "#0c8599", "#e64980", "#f08c00", "#5f3dc4"]
_color_index = [0]


def next_color():
    c = PALETTE[_color_index[0] % len(PALETTE)]
    _color_index[0] += 1
    return c


def parse_equation(expr):
    """'x^2+y^2=1' → '(x^2+y^2)-(1)'；无等号则原样返回。"""
    expr = expr.strip()
    if "=" in expr:
        parts = expr.split("=", 1)
        return f"({parts[0].strip()})-({parts[1].strip()})"
    return expr


@register_geo("ImplicitCurve")
class ImplicitCurve(GeoObject):
    def __init__(self, expr="x^2+y^2=1", domain=None,
                 color=None, resolution=100, label_text=None):
        super().__init__(parents=())
        self.expr = expr
        self._resolved_expr = parse_equation(expr)
        self.domain = domain
        self.color = color or next_color()
        self.resolution = max(30, min(250, resolution))
        self.label_text = label_text
        self._cached_segments = []
        self._cache_version = -1
        self._cache_domain = (None, None, None, None)
        self._cache_dirty = True

    def invalidate_cache(self):
        self._cache_dirty = True

    def _cache_valid(self, var_version, domain):
        return (not self._cache_dirty
                and self._cache_version == var_version
                and self._cache_domain == domain
                and len(self._cached_segments) > 0)

    def update_cache(self, segments, var_version, domain):
        self._cached_segments = segments
        self._cache_version = var_version
        self._cache_domain = domain
        self._cache_dirty = False

    def get_domain(self, view):
        if self.domain:
            return self.domain
        x0, _ = view.to_world(QPointF(0, 0))
        x1, _ = view.to_world(QPointF(view.width(), 0))
        _, y0 = view.to_world(QPointF(0, view.height()))
        _, y1 = view.to_world(QPointF(0, 0))
        return (min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1))

    def get_cached_or_request(self, view):
        domain = self.get_domain(view)
        store = get_store()
        var_version = store.version
        if self._cache_valid(var_version, domain):
            return self._cached_segments, True
        from geo.implicit_sampler import get_implicit_sampler
        get_implicit_sampler().submit(
            curve_id=self.id,
            expr=self._resolved_expr,
            domain=domain,
            n=self.resolution,
            var_snapshot=store.as_dict()
        )
        return self._cached_segments, False

    def distance_to(self, x, y):
        if not self._cached_segments:
            return None
        best = float("inf")
        for x1, y1, x2, y2 in self._cached_segments:
            dx, dy = x2 - x1, y2 - y1
            denom = dx * dx + dy * dy
            if denom < 1e-12:
                d = math.hypot(x - x1, y - y1)
            else:
                t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / denom))
                d = math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))
            if d < best:
                best = d
        return best

    def default_label(self):
        return self.expr

    def dump(self):
        return {"expr": self.expr,
                "domain": list(self.domain) if self.domain else None,
                "color": self.color,
                "resolution": self.resolution,
                "label_text": self.label_text}

    @classmethod
    def build(cls, parents, params):
        return cls(params.get("expr", "x^2+y^2=1"),
                   tuple(params["domain"]) if params.get("domain") else None,
                   params.get("color"),
                   params.get("resolution", 100),
                   params.get("label_text"))


@register_renderer(ImplicitCurve)
def draw_implicit(p, obj, view):
    if not obj.exists:
        return
    color = theme.SELECTED if obj.selected else obj.color
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(Qt.BrushStyle.NoBrush)

    cached, fresh = obj.get_cached_or_request(view)
    if not cached:
        return

    path = QPainterPath()
    for x1, y1, x2, y2 in cached:
        sp1 = view.to_screen(x1, y1)
        sp2 = view.to_screen(x2, y2)
        path.moveTo(sp1)
        path.lineTo(sp2)
    if path.elementCount() > 0:
        p.drawPath(path)