from __future__ import annotations

from typing import Tuple

from geo.points import AbstractPoint, FreePoint, PointOnObject, nearest_point
from geo.base import GeoObject



WorldPt = Tuple[float, float]


from geo.base import GeoObject


def _snappable(obj):
    """对象是否真正支持参数化吸附（重写了 point_at/project，而非基类的抛错版本）。"""
    return (type(obj).point_at is not GeoObject.point_at
            and type(obj).project is not GeoObject.project)


def point_or_snap(canvas, wpt, hit):
    """磁吸建点：优先复用附近已有点 → 落在可吸附对象上建吸附点 → 否则建自由点。"""
    from geo.points import nearest_point, PointOnObject, FreePoint
    pt = nearest_point(canvas.doc, canvas.scale, wpt)
    if pt is not None:
        return pt
    if hit is not None and _snappable(hit):
        return canvas.doc.add(PointOnObject(hit, hit.project(*wpt)))
    return canvas.doc.add(FreePoint(*wpt))


def snap_target(canvas, wpt: WorldPt, hit):
    """按压/抓取决策：优先磁吸附近已有点，否则用拾取结果。"""
    pt = nearest_point(canvas.doc, canvas.scale, wpt)
    return pt if pt is not None else hit


class Tool:
    """工具 = 鼠标事件状态机 + 可选覆盖层。类属性由 @register_tool 注入。"""
    tool_name: str = ""
    shortcut: str | None = None
    hint: str = ""

    def activated(self, canvas) -> None: ...
    def deactivated(self, canvas) -> None: ...
    def press(self, canvas, wpt: WorldPt, hit) -> None: ...
    def move(self, canvas, wpt: WorldPt, hit) -> None: ...
    def release(self, canvas, wpt: WorldPt, hit) -> None: ...
    def cancel(self, canvas) -> None: ...
    def draw_overlay(self, p, view) -> None: ...