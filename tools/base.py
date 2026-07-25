from __future__ import annotations

from typing import Tuple

from geo.points import AbstractPoint, FreePoint, PointOnObject, nearest_point

WorldPt = Tuple[float, float]


def point_or_snap(canvas, wpt: WorldPt, hit) -> AbstractPoint:
    """构造类工具的统一落点决策（注意第一个参数现在是 canvas，因为要读 scale）：
    ① 磁吸：吸附半径内有已有点 → 直接复用（最高优先级）
    ② 落在可吸附对象上 → 生成吸附点
    ③ 空白处 → 自由点
    """
    pt = nearest_point(canvas.doc, canvas.scale, wpt)
    if pt is not None:
        return pt
    if hit is not None and hasattr(hit, "point_at") and hasattr(hit, "project"):
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