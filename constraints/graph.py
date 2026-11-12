"""约束依赖图：局部连通分量 + 几何依赖闭包。

★ v3 修复（宿主端点触发漏检）：
旧实现只用 involved_points() 建邻接表，而 PointOnObject / IntersectPoint
等从动点的**宿主端点并不出现在 involved_points() 里**。
于是拖动宿主端点时 get_affected_constraints() 返回空集，约束在整个拖动
过程中静默漂移（|P−A| = t·L 随 L 线性增长）；漂移在下一次约束被激活时
一次性偿还，表现为「线段拉长后突然跳动」。

修复：先把触发点沿 GeoObject.children 向下闭包（穿过 Segment / Circle
等中间对象），把所有受影响的从动点一并作为 BFS 种子。

保留 v2 的两项性能修复：
① deque.popleft() 取代 list.pop(0)；
② 预建邻接表，避免全表扫描；
③ 同一约束不重复入队。
"""

from collections import deque
from typing import Any, Dict, Iterable, List, Set

from .base import GeometricConstraint


def _has_xy(obj: Any) -> bool:
    """是否为「点」——不引入 geo.points，避免图层反向依赖几何层。"""
    return hasattr(obj, "x") and hasattr(obj, "y")


def expand_trigger_points(trigger_points: Iterable[Any]) -> List[Any]:
    """触发点 → 触发点 ∪ 其几何下游从动点（含间接下游）。

    遍历穿过 Segment / Circle / DirectedLine 等中间对象，但只收集
    带 (x, y) 的点。对重复种子与依赖环安全（seen 去重）。

    返回按对象创建序（``obj.id``）稳定排序，保证求解列序可复现。
    """
    seen: Set[int] = set()
    found: Dict[int, Any] = {}
    stack = list(trigger_points)

    while stack:
        obj = stack.pop()
        oid = id(obj)
        if oid in seen:
            continue
        seen.add(oid)
        if _has_xy(obj):
            found[oid] = obj
        children = getattr(obj, "children", None)
        if children:
            stack.extend(children)

    return sorted(found.values(), key=lambda o: getattr(o, "id", 0))


def get_affected_constraints(
    trigger_points: List[Any],
    all_constraints: List[GeometricConstraint],
) -> List[GeometricConstraint]:
    """获取受触发点影响的约束连通分量。

    ★ v3：种子集先做几何依赖向下闭包，宿主端点拖动也能激活
    吸附点 / 交点上的约束。其余 BFS 语义与旧版完全一致。
    """
    if not trigger_points or not all_constraints:
        return []

    trigger_ids = {id(p) for p in expand_trigger_points(trigger_points)}

    # ★ 预建邻接表：点 id → 涉及该点的约束列表
    point_to_constraints: Dict[int, List[GeometricConstraint]] = {}
    for c in all_constraints:
        if not c.enabled:
            continue
        for p in c.involved_points():
            point_to_constraints.setdefault(id(p), []).append(c)

    # ★ 种子：直接涉及（闭包后）触发点的约束
    expanded_ids: Set[int] = set()
    frontier: deque = deque()
    for pid in trigger_ids:
        for c in point_to_constraints.get(pid, []):
            if id(c) not in expanded_ids:
                frontier.append(c)

    # ★ BFS：沿共享点扩展
    affected: List[GeometricConstraint] = []
    while frontier:
        c = frontier.popleft()
        cid = id(c)
        if cid in expanded_ids:
            continue
        expanded_ids.add(cid)
        affected.append(c)

        for p in c.involved_points():
            for c2 in point_to_constraints.get(id(p), []):
                if id(c2) not in expanded_ids:
                    frontier.append(c2)

    return affected