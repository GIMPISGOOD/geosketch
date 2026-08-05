"""函数曲线：支持 显函数 y=f(x) / 参数方程 x=f(t),y=g(t) / 极坐标 r=f(θ)。
表达式可含滑杆变量，变量变化时曲线每帧重采样、实时变形。
实现了 point_at/project/distance_to，故可在曲线上取吸附点、参与磁吸。"""
import math
from typing import Optional, Tuple

from PySide6.QtCore import QPointF
from PySide6.QtGui import QPainterPath

from core.registry import register_geo, register_renderer
from core.variables import evaluate, get_store
from geo.base import GeoObject
from ui import theme
from ui.math import draw_math

# 曲线调色板（自动轮流分配）
PALETTE = ["#1971c2", "#e8590c", "#2f9e44", "#9c36b5",
           "#0c8599", "#e64980", "#f08c00", "#5f3dc4"]
_color_index = [0]


def next_color():
    c = PALETTE[_color_index[0] % len(PALETTE)]
    _color_index[0] += 1
    return c


@register_geo("FunctionCurve")
class FunctionCurve(GeoObject):
    def __init__(self, kind="explicit", expr="x", expr2="",
                 domain=None, color=None, label_text=None):
        super().__init__(parents=())
        self.kind = kind
        self.expr = expr
        self.expr2 = expr2
        self.domain = domain
        self.color = color or next_color()
        self.label_text = label_text
        self._domain = domain

        # ★ 渲染缓存
        self._cached_points: list = []       # 采样点缓存
        self._cache_version: int = -1        # 缓存对应的变量版本号
        self._cache_domain: tuple = (None, None)     # 缓存对应的视窗域
        self._cache_dirty: bool = True       # 是否需要重新采样

    def _eval_at(self, u):
        """在参数 u 处求值。
        - explicit: 返回 y（float）
        - parametric: 返回 (x, y)（2-tuple）
        - polar: 返回 r（float）
        """
        vd = get_store().as_dict()
        if self.kind == "explicit":
            vd["x"] = u
            return evaluate(self.expr, vd)
        elif self.kind == "parametric":
            vd["t"] = u
            x = evaluate(self.expr, vd)
            y = evaluate(self.expr2, vd)
            return (x, y)
        elif self.kind == "polar":
            vd["t"] = u
            vd["θ"] = u
            return evaluate(self.expr, vd)
        return None

    def _eval_point(self, u) -> Optional[Tuple[float, float]]:
        """在参数 u 处求值，统一返回 (x, y) 世界坐标（或 None）。
        把 _eval_at 的三种返回格式归一化，供 sample/point_at/project 使用。"""
        val = self._eval_at(u)
        if val is None:
            return None
        if self.kind == "explicit":
            if isinstance(val, (int, float)) and math.isfinite(val):
                return (float(u), float(val))
            return None
        elif self.kind == "parametric":
            if isinstance(val, (tuple, list)) and len(val) == 2:
                x, y = val
                if all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)):
                    return (float(x), float(y))
            return None
        elif self.kind == "polar":
            if isinstance(val, (int, float)) and math.isfinite(val):
                r = float(val)
                return (r * math.cos(u), r * math.sin(u))
            return None
        return None

    def get_domain(self, view):
        if self.domain:
            return self.domain
        if self.kind == "explicit":
            x0, _ = view.to_world(QPointF(0, 0))
            x1, _ = view.to_world(QPointF(view.width(), 0))
            return (min(x0, x1), max(x0, x1))
        return (0.0, 2 * math.pi)
    
    def invalidate_cache(self):
        """表达式或变量变化时调用，标记缓存失效。"""
        self._cache_dirty = True

    def _cache_valid(self, var_version, domain):
        """检查缓存是否仍然有效。"""
        return (not self._cache_dirty
                and self._cache_version == var_version
                and self._cache_domain == domain
                and len(self._cached_points) > 0)

    def update_cache(self, points, var_version, domain):
        """子线程采样完成后更新缓存（由信号槽调用）。"""
        self._cached_points = points
        self._cache_version = var_version
        self._cache_domain = domain
        self._cache_dirty = False

    def get_cached_or_request(self, view):
        """获取缓存点列表；若失效则提交异步采样任务。

        返回 (points, is_fresh)：
        - is_fresh=True  → 缓存有效，直接使用
        - is_fresh=False → 缓存失效，已提交采样，当前返回旧缓存或空列表
        """
        domain = self.get_domain(view)
        store = get_store()
        var_version = store.version

        if self._cache_valid(var_version, domain):
            return self._cached_points, True

        # 缓存失效 → 提交异步采样
        n = min(max(int(view.width()), 400), 4000)
        from geo.function_sampler import get_sampler
        get_sampler().submit(
            curve_id=self.id,
            kind=self.kind,
            expr=self.expr,
            expr2=self.expr2,
            domain=domain,
            n=n,
            var_snapshot=store.as_dict()
        )

        # 返回旧缓存（可能为空），主线程先用旧数据绘制
        return self._cached_points, False
    
    def sample(self, view, n=900) -> list[Optional[Tuple[float, float]]]:
        a, b = self.get_domain(view)
        self._domain = (a, b)
        # ★ 必须改用 _eval_point
        raw: list[Optional[Tuple[float, float]]] = [
            self._eval_point(a + (b - a) * i / n) for i in range(n + 1)
        ]
        breaks = set()
        if self.kind == "explicit":
            yvals = sorted(p[1] for p in raw if p is not None)
            if yvals:
                y_med = yvals[len(yvals) // 2]
                devs = sorted(abs(y - y_med) for y in yvals)
                y_scale = max(devs[len(devs) // 2], 1e-9)
            else:
                y_scale = 1.0
            for i in range(1, len(raw)):
                p0, p1 = raw[i - 1], raw[i]
                if p0 is None or p1 is None or p0[1] * p1[1] >= 0:
                    continue
                prev = raw[i - 2] if i - 2 >= 0 else None
                next_p = raw[i + 1] if i + 1 < len(raw) else None
                left_ok = (prev is None) or (abs(p0[1]) >= abs(prev[1]))
                right_ok = (next_p is None) or (abs(p1[1]) >= abs(next_p[1]))
                if left_ok and right_ok and (abs(p0[1]) + abs(p1[1])) > y_scale * 4:
                    breaks.add(i)
        else:
            x0, y0 = view.to_world(QPointF(0, 0))
            x1, y1 = view.to_world(QPointF(view.width(), view.height()))
            diag = math.hypot(x1 - x0, y1 - y0)
            for i in range(1, len(raw)):
                p0, p1 = raw[i - 1], raw[i]
                if p0 is None or p1 is None:
                    continue
                if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > diag * 2:
                    breaks.add(i)
        pts: list[Optional[Tuple[float, float]]] = []
        for i, p in enumerate(raw):
            if i in breaks:
                pts.append(None)
            pts.append(p)
        return pts

    def _param_domain(self):
        if self.domain:
            return self.domain
        if self.kind == "explicit":
            return (-50.0, 50.0)
        return (0.0, 4 * math.pi)

    def point_at(self, t) -> Tuple[float, float]:
        a, b = self._param_domain()
        u = a + (b - a) * max(0.0, min(1.0, t))
        p = self._eval_point(u)          # ★ 必须改用 _eval_point
        return p if p else (0.0, 0.0)

    def project(self, x, y) -> float:
        a, b = self._param_domain()
        n = 500
        best_t, best_d = 0.0, float("inf")
        for i in range(n + 1):
            p = self._eval_point(a + (b - a) * i / n)   # ★ 必须改用 _eval_point
            if p is None:
                continue
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < best_d:
                best_d, best_t = d, i / n
        lo, hi = max(0.0, best_t - 1 / n), min(1.0, best_t + 1 / n)
        for i in range(50):
            tt = lo + (hi - lo) * i / 49
            p = self._eval_point(a + (b - a) * tt)      # ★ 必须改用 _eval_point
            if p is None:
                continue
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < best_d:
                best_d, best_t = d, tt
        return best_t

    def distance_to(self, x, y):
        p = self.point_at(self.project(x, y))
        return math.hypot(p[0] - x, p[1] - y)

    def default_label(self):
        if self.label_text:
            return self.label_text
        if self.kind == "explicit":
            return f"y = {self.expr}"
        if self.kind == "parametric":
            return f"({self.expr}, {self.expr2})"
        if self.kind == "polar":
            return f"r = {self.expr}"
        return self.expr

    def dump(self):
        return {"kind": self.kind, "expr": self.expr, "expr2": self.expr2,
                "domain": list(self.domain) if self.domain else None,
                "color": self.color, "label_text": self.label_text}

    @classmethod
    def build(cls, parents, params):
        return cls(params.get("kind", "explicit"), params.get("expr", "x"),
                   params.get("expr2", ""),
                   tuple(params["domain"]) if params.get("domain") else None,
                   params.get("color"), params.get("label_text"))


# ============================================================
# 渲染器（性能优化版）
# ============================================================

@register_renderer(FunctionCurve)
def draw_function(p, obj, view):
    if not obj.exists:
        return
    color = theme.SELECTED if obj.selected else getattr(obj, "color", theme.CIRCLE)
    p.setPen(theme.pen(color, 2))

    # ★ 尝试使用缓存
    cached, fresh = obj.get_cached_or_request(view)

    if fresh and cached:
        # 缓存有效：直接绘制缓存点（极快）
        _draw_cached(p, obj, view, cached)
    else:
        # 缓存无效：同步采样作为 fallback（首次加载/极端情况）
        if obj.kind == "explicit":
            _draw_explicit(p, obj, view)
        elif obj.kind == "parametric":
            _draw_parametric(p, obj, view)
        elif obj.kind == "polar":
            _draw_polar(p, obj, view)



def _draw_explicit(p, obj, view):
    """显函数：变量字典只获取一次 + QPainterPath + 合理采样密度。"""
    x0, _ = view.to_world(QPointF(0, 0))
    x1, _ = view.to_world(QPointF(view.width(), 0))
    if x0 > x1:
        x0, x1 = x1, x0

    _, yt = view.to_world(QPointF(0, 0))
    _, yb = view.to_world(QPointF(0, view.height()))
    y_range = abs(yt - yb) or 1.0

    # ★ 优化 1：采样点数 = 屏幕像素宽度（不再 ×3，上限 4000）
    n = min(max(int(view.width()), 400), 4000)

    # ★ 优化 2：变量字典只获取一次
    vd = get_store().as_dict()

    path = QPainterPath()
    has_path = False
    prev_y = None

    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        vd["x"] = x

        try:
            y = evaluate(obj.expr, vd)
        except Exception:
            y = None

        if y is None or not isinstance(y, (int, float)) or not math.isfinite(y):
            has_path = False
            prev_y = None
            continue

        # 渐近线检测
        if prev_y is not None and abs(y - prev_y) > y_range * 1.5:
            has_path = False

        sp = view.to_screen(x, y)
        if not has_path:
            path.moveTo(sp)
            has_path = True
        else:
            path.lineTo(sp)

        prev_y = y

    # ★ 优化 3：一次性绘制整个路径
    if has_path or path.elementCount() > 0:
        p.drawPath(path)


def _draw_parametric(p, obj, view):
    """参数方程：变量字典只获取一次 + QPainterPath。"""
    a, b = obj.domain or (0, 2 * math.pi)
    n = 800  # ★ 参数曲线 800 点足够平滑

    vd = get_store().as_dict()
    vd["t"] = 0.0

    path = QPainterPath()
    has_path = False

    for i in range(n + 1):
        t = a + (b - a) * i / n
        vd["t"] = t

        try:
            x = evaluate(obj.expr, vd)
            y = evaluate(obj.expr2, vd)
        except Exception:
            x = y = None

        if (x is None or y is None
                or not isinstance(x, (int, float)) or not math.isfinite(x)
                or not isinstance(y, (int, float)) or not math.isfinite(y)):
            has_path = False
            continue

        sp = view.to_screen(x, y)
        if not has_path:
            path.moveTo(sp)
            has_path = True
        else:
            path.lineTo(sp)

    if has_path or path.elementCount() > 0:
        p.drawPath(path)


def _draw_polar(p, obj, view):
    """极坐标：变量字典只获取一次 + QPainterPath。"""
    a, b = obj.domain or (0, 2 * math.pi)
    n = 800

    vd = get_store().as_dict()
    vd["t"] = 0.0
    vd["θ"] = 0.0

    path = QPainterPath()
    has_path = False

    for i in range(n + 1):
        t = a + (b - a) * i / n
        vd["t"] = t
        vd["θ"] = t

        try:
            r = evaluate(obj.expr, vd)
        except Exception:
            r = None

        if r is None or not isinstance(r, (int, float)) or not math.isfinite(r):
            has_path = False
            continue

        sp = view.to_screen(r * math.cos(t), r * math.sin(t))
        if not has_path:
            path.moveTo(sp)
            has_path = True
        else:
            path.lineTo(sp)

    if has_path or path.elementCount() > 0:
        p.drawPath(path)

def _draw_cached(p, obj, view, points):
    """从缓存点列表绘制（主线程零计算）。"""
    path = QPainterPath()
    has_path = False

    for pt in points:
        if pt is None:
            has_path = False
            continue

        sp = view.to_screen(pt[0], pt[1])
        if not has_path:
            path.moveTo(sp)
            has_path = True
        else:
            path.lineTo(sp)

    if path.elementCount() > 0:
        p.drawPath(path)