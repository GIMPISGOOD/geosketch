"""函数曲线：支持 显函数 y=f(x) / 参数方程 x=f(t),y=g(t) / 极坐标 r=f(θ)。
表达式可含滑杆变量，变量变化时曲线每帧重采样、实时变形。
实现了 point_at/project/distance_to，故可在曲线上取吸附点、参与磁吸。"""
import math
from typing import Optional, Tuple

from PySide6.QtCore import QPointF

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
        super().__init__(parents=())      # 不依赖几何对象，依赖变量（运行时求值）
        self.kind = kind                  # explicit / parametric / polar
        self.expr = expr                  # explicit: y=f(x); parametric: x(t); polar: r(θ)
        self.expr2 = expr2                # parametric: y(t)
        self.domain = domain              # None=自动(视窗); 或 (a, b)
        self.color = color or next_color()
        self.label_text = label_text
        self._domain = domain             # 采样时缓存的定义域（供 point_at/project 用）

    # ── 求值：代入参数 u 与全部滑杆变量 ──
    def _eval_at(self, u: float) -> Optional[tuple[float, float]]:
        """参数 u（定义域内）→ 世界坐标 (x,y)；无效返回 None。"""
        vd = get_store().as_dict()
        if self.kind == "explicit":
            vd["x"] = u
            y = evaluate(self.expr, vd)
            if y is None or not math.isfinite(y):
                return None
            return (u, y)
        if self.kind == "parametric":
            vd["t"] = u
            x = evaluate(self.expr, vd)
            y = evaluate(self.expr2, vd)
            if x is None or y is None or not (math.isfinite(x) and math.isfinite(y)):
                return None
            return (x, y)
        if self.kind == "polar":
            vd["t"] = u; vd["θ"] = u; vd["theta"] = u
            r = evaluate(self.expr, vd)
            if r is None or not math.isfinite(r):
                return None
            return (r * math.cos(u), r * math.sin(u))
        return None

    def get_domain(self, view):
        if self.domain:
            return self.domain
        if self.kind == "explicit":
            x0, _ = view.to_world(QPointF(0, 0))
            x1, _ = view.to_world(QPointF(view.width(), 0))
            return (min(x0, x1), max(x0, x1))
        return (0.0, 2 * math.pi)         # 参数/极坐标默认 [0, 2π]

    # ── 采样（含不连续自动断开）──
    def sample(self, view, n=900) -> list[Optional[tuple[float, float]]]:
        a, b = self.get_domain(view)
        self._domain = (a, b)
        raw: list[Optional[tuple[float, float]]] = [
            self._eval_at(a + (b - a) * i / n) for i in range(n + 1)
        ]

        breaks = set()                     # 需要断开的采样位置
        if self.kind == "explicit":
            # 与缩放无关的局部量级：|y - 中位数| 的中位数（MAD）
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
                    continue               # 无变号 → 不是竖直渐近线
                # 数值必须朝断点方向"发散"（区别于连续穿越：那是收敛到 0）
                prev = raw[i - 2] if i - 2 >= 0 else None
                next_p = raw[i + 1] if i + 1 < len(raw) else None
                left_ok = (prev is None) or (abs(p0[1]) >= abs(prev[1]))
                right_ok = (next_p is None) or (abs(p1[1]) >= abs(next_p[1]))
                if left_ok and right_ok and (abs(p0[1]) + abs(p1[1])) > y_scale * 4:
                    breaks.add(i)
        else:
            # 参数/极坐标：仍用视窗对角线阈值（它们没有竖直渐近线问题）
            x0, y0 = view.to_world(QPointF(0, 0))
            x1, y1 = view.to_world(QPointF(view.width(), view.height()))
            diag = math.hypot(x1 - x0, y1 - y0)
            for i in range(1, len(raw)):
                p0, p1 = raw[i - 1], raw[i]
                if p0 is None or p1 is None:
                    continue
                if math.hypot(p1[0] - p0[0], p1[1] - p0[1]) > diag * 2:
                    breaks.add(i)

        pts = []
        for i, p in enumerate(raw):
            if i in breaks:
                pts.append(None)
            pts.append(p)
        return pts
    # ── 参数化接口（取点 / 磁吸 / 未来的交点）──
    def _param_domain(self):
        """点参数化的稳定定义域（不随视窗变化，保证拖动平滑）。"""
        if self.domain:
            return self.domain
        if self.kind == "explicit":
            return (-50.0, 50.0)
        return (0.0, 4 * math.pi)

    def point_at(self, t):
        a, b = self._param_domain()
        u = a + (b - a) * max(0.0, min(1.0, t))
        p = self._eval_at(u)
        return p if p else (0.0, 0.0)

    def project(self, x, y):
        a, b = self._param_domain()
        n = 500
        best_t, best_d = 0.0, float("inf")
        for i in range(n + 1):
            p = self._eval_at(a + (b - a) * i / n)
            if p is None:
                continue
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < best_d:
                best_d, best_t = d, i / n
        lo, hi = max(0.0, best_t - 1 / n), min(1.0, best_t + 1 / n)
        for i in range(50):
            tt = lo + (hi - lo) * i / 49
            p = self._eval_at(a + (b - a) * tt)
            if p is None:
                continue
            d = (p[0] - x) ** 2 + (p[1] - y) ** 2
            if d < best_d:
                best_d, best_t = d, tt
        return best_t

    def distance_to(self, x, y):
        p = self.point_at(self.project(x, y))
        return math.hypot(p[0] - x, p[1] - y)

    # ── 标签 ──
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

    # ── 序列化 ──
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


@register_renderer(FunctionCurve)
def draw_function(p, obj, view):
    if not obj.exists:
        return
    color = theme.SELECTED if obj.selected else getattr(obj, "color", theme.CIRCLE)
    p.setPen(theme.pen(color, 2))

    if obj.kind == "explicit":
        _draw_explicit(p, obj, view)
    elif obj.kind == "parametric":
        _draw_parametric(p, obj, view)
    elif obj.kind == "polar":
        _draw_polar(p, obj, view)


def _draw_explicit(p, obj, view):
    """显函数：只采样可见 x 范围，按像素密度采样，渐近线处断开。"""
    x0, _ = view.to_world(QPointF(0, 0))
    x1, _ = view.to_world(QPointF(view.width(), 0))
    if x0 > x1:
        x0, x1 = x1, x0
    _, yt = view.to_world(QPointF(0, 0))
    _, yb = view.to_world(QPointF(0, view.height()))
    y_range = abs(yt - yb) or 1.0

    n = min(max(int(view.width() * 3), 600), 12000)

    prev = None
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        y = obj._eval_at(x)
        # ★ 类型保护：只接受实数，tuple/None/复数全部跳过
        if not isinstance(y, (int, float)) or not math.isfinite(y):
            prev = None
            continue
        if prev is not None and abs(y - prev[1]) > y_range * 1.5:
            prev = None
        sp = view.to_screen(x, y)
        if prev is not None:
            p.drawLine(prev, sp)
        prev = (x, y)


def _draw_parametric(p, obj, view):
    a, b = obj.domain or (0, 2 * math.pi)
    n = 2000
    prev = None
    for i in range(n + 1):
        t = a + (b - a) * i / n
        pt = obj._eval_at(t)
        if not isinstance(pt, (tuple, list)) or len(pt) != 2:
            prev = None
            continue
        x, y = pt
        if not (isinstance(x, (int, float)) and isinstance(y, (int, float))
                and math.isfinite(x) and math.isfinite(y)):
            prev = None
            continue
        sp = view.to_screen(x, y)
        if prev is not None:
            p.drawLine(prev, sp)
        prev = sp


def _draw_polar(p, obj, view):
    a, b = obj.domain or (0, 2 * math.pi)
    n = 2000
    prev = None
    for i in range(n + 1):
        t = a + (b - a) * i / n
        r = obj._eval_at(t)
        if not isinstance(r, (int, float)) or not math.isfinite(r):
            prev = None
            continue
        sp = view.to_screen(r * math.cos(t), r * math.sin(t))
        if prev is not None:
            p.drawLine(prev, sp)
        prev = sp