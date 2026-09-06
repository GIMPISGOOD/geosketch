"""几何光学对象。

第一版包含：
- LightSourcePoint：点光源
- PlaneMirror：平面镜
- LightRay：光线（入射 + 反射）

这些对象全部继承现有 GeoObject 体系，
通过 parents/children 接入 Document 的增量重算、撤销重做和序列化。
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from geo.points import FreePoint
from geo.segments import Segment
from ui import theme
from ui.canvas_render import arrow_path
from ui.math import draw_math

from .tracer import ray_mirror_reflect, polyline_distance


# ═══════════════════════════════════════════════════════════
# 点光源
# ═══════════════════════════════════════════════════════════

@register_geo("LightSource")
class LightSourcePoint(FreePoint):
    """点光源。

    第一版先复用 FreePoint 的坐标与拖动能力，
    渲染时增加光源样式。
    """

    draggable = True

    def __init__(self, x, y):
        super().__init__(x, y)

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"])


# ═══════════════════════════════════════════════════════════
# 平面镜
# ═══════════════════════════════════════════════════════════

@register_geo("PlaneMirror")
class PlaneMirror(Segment):
    """平面镜。

    第一版基于 Segment：
    - 依赖两个端点
    - 可拖动端点
    - 可整体选择/删除
    - 背面绘制 /// 阴影线

    hatch_side:
        "right" 表示从 A 到 B 的屏幕右侧绘制阴影线
        "left"  表示从 A 到 B 的屏幕左侧绘制阴影线
    """

    def __init__(self, a, b, hatch_side="right"):
        super().__init__(a, b)
        self.hatch_side = hatch_side

    def dump(self):
        return {
            "hatch_side": self.hatch_side,
        }

    @classmethod
    def build(cls, parents, params):
        return cls(
            parents[0],
            parents[1],
            params.get("hatch_side", "right"),
        )


# ═══════════════════════════════════════════════════════════
# 光线
# ═══════════════════════════════════════════════════════════

@register_geo("LightRay")
class LightRay(GeoObject):
    """光线。

    依赖关系：
        parents[0] = source     光源点
        parents[1] = incident   入射点（通常为吸附在平面镜上的点）
        parents[2] = mirror     平面镜

    recompute() 中计算：
        光源 → 入射点 → 反射终点

    第一版反射线长度等于入射线长度，便于作图观察。
    """

    def __init__(self, source, incident, mirror):
        super().__init__(parents=[source, incident, mirror])
        self.source = source
        self.incident = incident
        self.mirror = mirror

        # 世界坐标折线路径：
        # [光源点, 入射点, 反射终点]
        self.path = []

        self.recompute()

    def recompute(self):
        self.path = []

        if not (self.source.exists and self.incident.exists and self.mirror.exists):
            return

        src = (self.source.x, self.source.y)
        inc = (self.incident.x, self.incident.y)

        a = (self.mirror.a.x, self.mirror.a.y)
        b = (self.mirror.b.x, self.mirror.b.y)

        reflected_dir = ray_mirror_reflect(src, inc, a, b)

        if reflected_dir is None:
            self.path = [src, inc]
            return

        length = math.hypot(inc[0] - src[0], inc[1] - src[1])
        if length < 1e-9:
            length = 1.0

        end = (
            inc[0] + reflected_dir[0] * length,
            inc[1] + reflected_dir[1] * length,
        )

        self.path = [src, inc, end]

    def distance_to(self, x, y):
        """支持选择光线。"""
        return polyline_distance(self.path, x, y)

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], parents[2])


# ═══════════════════════════════════════════════════════════
# 渲染：点光源
# ═══════════════════════════════════════════════════════════

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

    # 中心点
    p.setPen(theme.pen(theme.POINT_RING, ring_w))
    p.setBrush(theme.brush(theme.SELECTED if obj.selected else theme.POINT_FILL))
    p.drawEllipse(qpt, r, r)

    # 光源短射线
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

    # 标签
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


# ═══════════════════════════════════════════════════════════
# 渲染：平面镜
# ═══════════════════════════════════════════════════════════

@register_renderer(PlaneMirror)
def draw_plane_mirror(p, obj, view):
    """平面镜：主反射面 + 背面 /// 阴影线。"""

    sa = view.to_screen(obj.a.x, obj.a.y)
    sb = view.to_screen(obj.b.x, obj.b.y)

    # 主镜面线
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

    # 屏幕坐标下，从 A 到 B 的右侧法线为 (-uy, ux)
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

        # 标准斜线：向背面延伸，同时略微向后倾斜
        x1 = x0 + nx * hatch_len - ux * back_slant
        y1 = y0 + ny * hatch_len - uy * back_slant

        p.drawLine(QPointF(x0, y0), QPointF(x1, y1))


# ═══════════════════════════════════════════════════════════
# 渲染：光线
# ═══════════════════════════════════════════════════════════

@register_renderer(LightRay)
def draw_light_ray(p, obj, view):
    """光线：实线 + 中段箭头。"""

    if len(obj.path) < 2:
        return

    pts = [view.to_screen(x, y) for x, y in obj.path]

    color = theme.SELECTED if obj.selected else theme.RAY

    # 线段
    p.setPen(theme.pen(color, 2.0))
    for i in range(len(pts) - 1):
        p.drawLine(pts[i], pts[i + 1])

    # 箭头
    p.setPen(theme.pen(color, 1.0))
    p.setBrush(theme.brush(color))

    for i in range(len(pts) - 1):
        p0 = pts[i]
        p1 = pts[i + 1]

        dx = p1.x() - p0.x()
        dy = p1.y() - p0.y()
        seg_len = math.hypot(dx, dy)

        if seg_len < 18.0:
            continue

        # 箭头画在线段中后段，避免与点重叠
        mid = QPointF(
            p0.x() + dx * 0.55,
            p0.y() + dy * 0.55,
        )

        # 屏幕坐标 Y 轴向下，arrow_path 需要数学方向角
        angle_deg = math.degrees(math.atan2(-dy, dx))
        p.drawPath(arrow_path(mid, angle_deg))