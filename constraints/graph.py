"""约束图：用于寻找局部连通分量，避免全局求解。

★ P1-7 修复：
  ① list.pop(0) → collections.deque.popleft()，O(n)→O(1)
  ② 全表扫描 → 预建邻接表，O(n²k)→O(nk)
  ③ 防止同一约束重复入队
"""
from collections import deque
from typing import List, Any

from .base import GeometricConstraint


def get_affected_constraints(
    trigger_points: List[Any],
    all_constraints: List[GeometricConstraint]
) -> List[GeometricConstraint]:
    """获取受触发点影响的约束连通分量。"""
    if not trigger_points or not all_constraints:
        return []

    trigger_ids = {id(p) for p in trigger_points}

    # ★ 预建邻接表：点 id → 涉及该点的约束列表
    point_to_constraints: dict = {}
    for c in all_constraints:
        if not c.enabled:
            continue
        for p in c.involved_points():
            pid = id(p)
            if pid not in point_to_constraints:
                point_to_constraints[pid] = []
            point_to_constraints[pid].append(c)

    # ★ 种子：直接涉及触发点的约束
    expanded_ids: set = set()
    frontier: deque = deque()
    for pid in trigger_ids:
        for c in point_to_constraints.get(pid, []):
            if id(c) not in expanded_ids:
                frontier.append(c)

    # ★ BFS
    affected: list = []
    while frontier:
        c = frontier.popleft()
        cid = id(c)
        if cid in expanded_ids:
            continue
        expanded_ids.add(cid)
        affected.append(c)
        # 沿共享点扩展
        for p in c.involved_points():
            for c2 in point_to_constraints.get(id(p), []):
                if id(c2) not in expanded_ids:
                    frontier.append(c2)

    return affected