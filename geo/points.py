"""几何点对象库：自由点、吸附点，以及磁吸查询。

分层铁律 —— 本模块位于依赖链底层：
    points ──→ base          （只向下依赖）
    ✗ base 反向导入 points    （会循环导入）

对外契约（其他文件依赖下列名字，重构不得改动）：
    AbstractPoint · FreePoint · PointOnObject · nearest_point · SNAP_PX
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme

WorldPt = tuple[float, float]


# ───────────────────────────── 基类 ─────────────────────────────
class AbstractPoint(GeoObject):
    """点的公共基类：携带坐标、可拾取。渲染器注册于此，两种点经 MRO 共用。"""

    x: float
    y: float

    def __init__(self, parents: tuple[GeoObject, ...] = ()) -> None:
        super().__init__(parents)
        self.x = 0.0
        self.y = 0.0

    def distance_to(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, self.y - y)


# ─────────────────────────── 两种点 ───────────────────────────
@register_geo("FreePoint")
class FreePoint(AbstractPoint):
    """自由点：平面上任意拖动，无依赖。"""

    draggable = True

    def __init__(self, x: float, y: float) -> None:
        super().__init__()
        self.x, self.y = x, y

    def drag_to(self, wpt: WorldPt) -> None:
        self.x, self.y = wpt

    def dump(self) -> dict:
        return {"x": self.x, "y": self.y}

    @classmethod
    def build(cls, parents, params) -> FreePoint:
        return cls(params["x"], params["y"])


@register_geo("PointOnObject")
class PointOnObject(AbstractPoint):
    """吸附点：钉在宿主对象上，位置由参数 t ∈ [0,1] 描述。
    宿主只要实现 point_at / project，吸附与沿宿主拖动即自动生效。"""

    draggable = True

    def __init__(self, host: GeoObject, t: float = 0.5) -> None:
        super().__init__(parents=(host,))
        self.host = host
        self.t = t
        self.recompute()

    def recompute(self) -> None:
        self.x, self.y = self.host.point_at(self.t)

    def drag_to(self, wpt: WorldPt) -> None:
        self.t = self.host.project(*wpt)

    def dump(self) -> dict:
        return {"t": self.t}

    @classmethod
    def build(cls, parents, params) -> PointOnObject:
        return cls(parents[0], params["t"])


# ───────────────────────────── 命名 ─────────────────────────────
def _index_to_letters(n: int) -> str:
    """序号 → 字母：1→a, 2→b, …, 26→z, 27→aa。"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(ord('a') + r) + s
    return s


def _index_to_subscript(n: int) -> str:
    """序号 → Unicode 下标：1→₁, 12→₁₂。"""
    return ''.join(chr(0x2080 + int(d)) for d in str(n))


def _point_label(obj: AbstractPoint, view) -> str:
    """计算点的显示名：
    - 圆心点（被某个 Circle 引用为 center）→ O₁, O₂, …
    - 其余点 → a, b, c, …
    序号按 id 升序在同类中动态计算，删除/撤销后自动重排，永远连续。
    """
    doc = view.doc
    # 先找出所有"圆心点"（只认 Circle 的 center，多边形中心不算）
    center_ids = set()
    for o in doc.objects:
        if type(o).__name__ == 'Circle':
            c = getattr(o, 'center', None)
            if isinstance(c, AbstractPoint):
                center_ids.add(id(c))

    is_center = id(obj) in center_ids
    # 在同类点（同为圆心 / 同非圆心）中按 id 升序确定序号
    idx = 1
    for o in doc.objects:
        if not isinstance(o, AbstractPoint):
            continue
        if (id(o) in center_ids) != is_center:
            continue
        if o is obj:
            break
        idx += 1

    return ("O" + _index_to_subscript(idx)) if is_center else _index_to_letters(idx)


# ───────────────────────────── 渲染 ─────────────────────────────
@register_renderer(AbstractPoint)
def draw_point(p, obj: AbstractPoint, view) -> None:
    """两种点共用：选中时放大换色，右上角标注名称。"""
    qpt = view.to_screen(obj.x, obj.y)
    radius = 6.0 if obj.selected else 4.0
    p.setPen(theme.pen(theme.POINT_RING, 2))
    p.setBrush(theme.brush(theme.SELECTED if obj.selected else theme.POINT_FILL))
    p.drawEllipse(qpt, radius, radius)
    p.setPen(theme.pen(theme.LABEL))
    p.setFont(theme.LABEL_FONT)
    p.drawText(qpt + QPointF(9, -8), _point_label(obj, view))


# ───────────────────────────── 磁吸 ─────────────────────────────
SNAP_PX: float = 18.0        # 磁吸半径（屏幕像素）：手感恒定，世界半径 = SNAP_PX / scale


def nearest_point(doc, scale: float, wpt: WorldPt) -> AbstractPoint | None:
    """磁吸半径内离光标最近的点；无则返回 None。
    世界半径 = SNAP_PX / scale —— 屏幕恒定 18px，随坐标系缩放自动换算。"""
    tol = SNAP_PX / scale
    best: AbstractPoint | None = None
    best_d = tol
    for obj in doc.objects:
        if isinstance(obj, AbstractPoint) and obj.visible and obj.exists:
            d = obj.distance_to(*wpt)
            if d < best_d:
                best, best_d = obj, d
    return best