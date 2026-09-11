"""几何光学对象。

本版扩展：
- LightSourcePoint：点光源
- PlaneMirror：平面镜，支持双面反射字段
- LightRay：多平面镜连续反射光线，支持无限延伸

所有对象仍继承现有 GeoObject 体系，
通过 parents/children 接入 Document 的增量重算、撤销重做和序列化。
"""
from __future__ import annotations

import math
import weakref

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from geo.points import FreePoint
from geo.segments import Segment
from ui import theme
from ui.canvas_render import arrow_path
from ui.math import draw_math

from .tracer import (
    point_ray_distance,
    polyline_distance,
    trace_light_path,
)


@register_geo("LightSource")
class LightSourcePoint(FreePoint):
    """点光源。

    第一版复用 FreePoint 的坐标与拖动能力，
    渲染时增加光源样式。
    """

    draggable = True

    def __init__(self, x, y):
        super().__init__(x, y)

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"])


@register_geo("PlaneMirror")
class PlaneMirror(Segment):
    """平面镜。

    基于 Segment：
    - 依赖两个端点
    - 可拖动端点
    - 可整体选择 / 删除
    - 背面绘制 /// 阴影线

    hatch_side:
        "right" 表示从 A 到 B 的屏幕右侧绘制阴影线
        "left"  表示从 A 到 B 的屏幕左侧绘制阴影线

    double_sided:
        True  表示双面反射
        False 表示仅反射面一侧反射
    """

    def __init__(self, a, b, hatch_side="right", double_sided=True):
        super().__init__(a, b)
        self.hatch_side = hatch_side
        self.double_sided = bool(double_sided)

    def dump(self):
        return {
            "hatch_side": self.hatch_side,
            "double_sided": bool(self.double_sided),
        }

    @classmethod
    def build(cls, parents, params):
        return cls(
            parents[0],
            parents[1],
            params.get("hatch_side", "right"),
            bool(params.get("double_sided", True)),
        )


@register_geo("LightRay")
class LightRay(GeoObject):
    """光线。

    依赖关系：
        parents[0] = source     光源点
        parents[1] = incident   入射点
        parents[2] = mirror     初始平面镜

    扩展后：
    - 支持多平面镜连续反射。
    - 最后一段未命中时表现为无限延伸。
    - 路径缓存不序列化，可由场景重新追迹。
    """

    def __init__(self, source, incident, mirror):
        super().__init__(parents=[source, incident, mirror])
        self.source = source
        self.incident = incident
        self.mirror = mirror

        self.path = []
        self.last_dir = None
        self.infinite = False
        self.stop_reason = ""
        self.reflection_count = 0
        self.hit_mirrors = []

        self._mirror_refs = []
        self._trace_settings = (16, True)
        self._last_mirror_version = None
        self._last_ray_sig = None
        self._last_trace_valid = False

        self.recompute()

    # ──────────────────────────────────────────
    # 内部工具
    # ──────────────────────────────────────────

    def _clear_trace(self):
        self.path = []
        self.last_dir = None
        self.infinite = False
        self.stop_reason = ""
        self.reflection_count = 0
        self.hit_mirrors = []

    def _resolved_cached_mirrors(self):
        """解析弱引用缓存中的镜子，只保留存在且可见的镜子。"""
        mirrors = []
        for ref in self._mirror_refs:
            try:
                m = ref()
            except Exception:
                m = None
            if m is None:
                continue
            if not getattr(m, "exists", False):
                continue
            if not getattr(m, "visible", True):
                continue
            mirrors.append(m)
        return mirrors

    def _trace(self, src, inc, mirrors, max_reflections, double_sided, initial_active):
        res = trace_light_path(
            src,
            inc,
            self.mirror,
            mirrors,
            max_reflections=max_reflections,
            global_double_sided=double_sided,
            initial_active=initial_active,
        )

        self.path = res["points"]
        self.last_dir = res["last_dir"]
        self.infinite = bool(res["infinite"])
        self.stop_reason = res["reason"]
        self.reflection_count = int(res["reflections"])
        self.hit_mirrors = res["hit_mirrors"]

    # ──────────────────────────────────────────
    # Document 依赖重算入口
    # ──────────────────────────────────────────

    def recompute(self):
        """父依赖变化时由 Document 调用。

        这里优先使用上一次场景同步缓存的镜子列表。
        真正的全场景同步由 physics.optics.scene.sync_optics 负责。
        """
        if not (self.source.exists and self.incident.exists and self.mirror.exists):
            self._clear_trace()
            self._last_trace_valid = False
            self._last_ray_sig = None
            return

        src = (float(self.source.x), float(self.source.y))
        inc = (float(self.incident.x), float(self.incident.y))

        mirrors = self._resolved_cached_mirrors()
        if not mirrors and self.mirror.exists and getattr(self.mirror, "visible", True):
            mirrors = [self.mirror]

        max_r, double = self._trace_settings
        initial_active = bool(getattr(self.mirror, "visible", True))

        ray_sig = (
            src[0],
            src[1],
            inc[0],
            inc[1],
            getattr(self.mirror, "id", 0),
            initial_active,
            max_r,
            double,
        )

        if self._last_trace_valid and self._last_ray_sig == ray_sig:
            return

        self._clear_trace()
        self._last_ray_sig = ray_sig
        self._trace(src, inc, mirrors, max_r, double, initial_active)
        self._last_trace_valid = True

    # ──────────────────────────────────────────
    # 场景同步入口
    # ──────────────────────────────────────────

    def update_trace(self, mirrors, max_reflections, double_sided, mirror_version=0):
        """由 sync_optics 调用，使用当前文档中的可见平面镜重新追迹。"""
        if not (self.source.exists and self.incident.exists and self.mirror.exists):
            self._clear_trace()
            self._last_trace_valid = False
            self._last_ray_sig = None
            return

        src = (float(self.source.x), float(self.source.y))
        inc = (float(self.incident.x), float(self.incident.y))

        max_r = max(1, min(256, int(max_reflections)))
        double = bool(double_sided)
        initial_active = bool(getattr(self.mirror, "visible", True))

        ray_sig = (
            src[0],
            src[1],
            inc[0],
            inc[1],
            getattr(self.mirror, "id", 0),
            initial_active,
            max_r,
            double,
        )

        if (
            self._last_trace_valid
            and self._last_mirror_version == mirror_version
            and self._last_ray_sig == ray_sig
        ):
            return

        self._clear_trace()
        self._trace_settings = (max_r, double)
        self._last_mirror_version = mirror_version
        self._last_ray_sig = ray_sig

        # 使用弱引用缓存镜子，避免已删除平面镜被光线长期持有。
        self._mirror_refs = []
        for m in mirrors:
            try:
                self._mirror_refs.append(weakref.ref(m))
            except Exception:
                continue

        self._trace(src, inc, mirrors, max_r, double, initial_active)
        self._last_trace_valid = True

    # ──────────────────────────────────────────
    # 拾取
    # ──────────────────────────────────────────

    def distance_to(self, x, y):
        """支持选择光线。

        包含：
        - 已命中的有限折线段
        - 最后一段无限延伸射线
        """
        if not self.path:
            return None

        best = polyline_distance(self.path, x, y)

        if self.infinite and self.last_dir is not None:
            d = point_ray_distance((x, y), self.path[-1], self.last_dir)
            if best is None or d < best:
                best = d

        return best

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


# ════════════════════════════════════════════════════════════
# 渲染器
# ════════════════════════════════════════════════════════════

@register_renderer(LightSourcePoint)
def draw_light_source(p, obj, view):
    """点光源：圆点 + 周围短射线。"""
    s = getattr(view.doc, "settings", None)
    if s is not None:
        r_sel = float(s.get("appearance.selected_point_radius", 6.0))
        r_def = float(s.get("appearance.default_point_radius", 4.0))
        ring_w = theme.default_line_width()
        math_scale = float(s.get("appearance.math_scale", 1.0))
    else:
        r_sel, r_def, ring_w, math_scale = 6.0, 4.0, 2.0, 1.0

    r = r_sel if obj.selected else r_def
    qpt = view.to_screen(obj.x, obj.y)

    p.setPen(theme.pen(theme.POINT_RING, ring_w))
    p.setBrush(theme.brush(theme.SELECTED if obj.selected else theme.POINT_FILL))
    p.drawEllipse(qpt, r, r)

    ray_color = theme.SELECTED if obj.selected else theme.MEASURE
    p.setPen(theme.pen(ray_color, 1.4))

    inner = r + 2.5
    outer = r + 8.0

    for i in range(8):
        ang = i * math.pi / 4.0
        x0 = qpt.x() + math.cos(ang) * inner
        y0 = qpt.y() + math.sin(ang) * inner
        x1 = qpt.x() + math.cos(ang) * outer
        y1 = qpt.y() + math.sin(ang) * outer
        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))

    label = getattr(obj, "name", "") or getattr(obj, "_auto_label", "")
    if not label:
        label = f"P{obj.id}"

    label_size = int(13 * math_scale)
    draw_math(
        p,
        qpt.x() + 10,
        qpt.y() - 8,
        label,
        label_size,
        theme.SELECTED if obj.selected else theme.LABEL,
    )


@register_renderer(PlaneMirror)
def draw_plane_mirror(p, obj, view):
    """平面镜：主反射面 + 背面 /// 阴影线。"""
    sa = view.to_screen(obj.a.x, obj.a.y)
    sb = view.to_screen(obj.b.x, obj.b.y)

    p.setPen(
        theme.pen(
            theme.SELECTED if obj.selected else theme.SEGMENT,
            3 if obj.selected else 2,
        )
    )
    p.drawLine(sa, sb)

    dx = sb.x() - sa.x()
    dy = sb.y() - sa.y()
    length = math.hypot(dx, dy)

    if length < 10.0:
        return

    ux = dx / length
    uy = dy / length

    if obj.hatch_side == "right":
        nx, ny = -uy, ux
    else:
        nx, ny = uy, -ux

    spacing = 8.0
    hatch_len = 8.0
    back_slant = 4.5

    p.setPen(theme.pen(theme.SUBINK, 1.0))

    count = int(length // spacing)
    for i in range(1, count + 1):
        t = i * spacing
        if t > length - 3.0:
            break

        x0 = sa.x() + ux * t
        y0 = sa.y() + uy * t
        x1 = x0 + nx * hatch_len - ux * back_slant
        y1 = y0 + ny * hatch_len - uy * back_slant

        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


def _clip_screen_ray(p0, d, w, h):
    """将屏幕空间射线裁剪到视口矩形。

    参数：
        p0: (x, y)
        d: (dx, dy)
        w: 视口宽度
        h: 视口高度

    返回：
        (x0, y0, x1, y1) 或 None
    """
    if w <= 0 or h <= 0:
        return None

    x, y = float(p0[0]), float(p0[1])
    dx, dy = float(d[0]), float(d[1])

    if abs(dx) < 1e-12 and abs(dy) < 1e-12:
        return None

    tmin = 0.0
    tmax = float("inf")

    for p, dd, low, high in (
        (x, dx, 0.0, float(w)),
        (y, dy, 0.0, float(h)),
    ):
        if abs(dd) < 1e-12:
            if p < low or p > high:
                return None
        else:
            t1 = (low - p) / dd
            t2 = (high - p) / dd
            if t1 > t2:
                t1, t2 = t2, t1

            tmin = max(tmin, t1)
            tmax = min(tmax, t2)

            if tmin > tmax:
                return None

    if tmax < 0.0:
        return None

    t0 = max(0.0, tmin)
    if tmax <= t0 + 1e-6:
        return None

    return (
        x + dx * t0,
        y + dy * t0,
        x + dx * tmax,
        y + dy * tmax,
    )


def _draw_ray_arrow(p, p0, p1, color):
    """在线段 p0 -> p1 的约 55% 位置绘制箭头。"""
    dx = p1.x() - p0.x()
    dy = p1.y() - p0.y()
    seg_len = math.hypot(dx, dy)

    if seg_len < 18.0:
        return

    mid = QPointF(
        p0.x() + dx * 0.55,
        p0.y() + dy * 0.55,
    )
    angle_deg = math.degrees(math.atan2(-dy, dx))

    p.setPen(theme.pen(color, 1.0))
    p.setBrush(theme.brush(color))
    p.drawPath(arrow_path(mid, angle_deg))


@register_renderer(LightRay)
def draw_light_ray(p, obj, view):
    """光线：多段折线 + 最后一段视口裁剪无限延伸。"""
    if not obj.path:
        return

    s = getattr(view.doc, "settings", None)
    show_arrows = bool(s.get("physics.optics_show_arrows", True)) if s is not None else True

    color = theme.SELECTED if obj.selected else theme.RAY
    p.setPen(theme.pen(color, 2.0))

    pts = [view.to_screen(x, y) for x, y in obj.path]

    # ── 已命中的有限段 ──
    for i in range(len(pts) - 1):
        p.drawLine(pts[i], pts[i + 1])

    if show_arrows:
        for i in range(len(pts) - 1):
            _draw_ray_arrow(p, pts[i], pts[i + 1], color)

    # ── 最后一段无限延伸射线 ──
    if obj.infinite and obj.last_dir is not None and obj.path:
        start_w = obj.path[-1]
        p0 = view.to_screen(start_w[0], start_w[1])

        # 世界坐标 y 向上，屏幕坐标 y 向下。
        d_screen = (
            float(obj.last_dir[0]) * float(view.scale),
            -float(obj.last_dir[1]) * float(view.scale),
        )

        clip = _clip_screen_ray(
            (p0.x(), p0.y()),
            d_screen,
            view.width(),
            view.height(),
        )

        if clip is not None:
            q0 = QPointF(clip[0], clip[1])
            q1 = QPointF(clip[2], clip[3])

            p.setPen(theme.pen(color, 2.0))
            p.drawLine(q0, q1)

            if show_arrows:
                _draw_ray_arrow(p, q0, q1, color)