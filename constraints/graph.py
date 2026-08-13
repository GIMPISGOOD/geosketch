"""约束图：用于寻找局部连通分量，避免全局求解。"""
from typing import List, Any, Set
from .base import GeometricConstraint

def get_affected_constraints(
    trigger_points: List[Any], 
    all_constraints: List[GeometricConstraint]
) -> List[GeometricConstraint]:
    """获取受触发点影响的约束连通分量。"""
    trigger_ids = {id(p) for p in trigger_points}
    affected = []
    
    # 1. 找到直接涉及的约束
    frontier = []
    expanded_ids = set()
    for c in all_constraints:
        if any(id(p) in trigger_ids for p in c.involved_points()):
            frontier.append(c)
            
    # 2. BFS 扩展连通分量
    while frontier:
        c = frontier.pop(0)
        if id(c) in expanded_ids: continue
        expanded_ids.add(id(c))
        affected.append(c)
        
        for p in c.involved_points():
            for c2 in all_constraints:
                if id(c2) not in expanded_ids:
                    if any(id(p2) == id(p) for p2 in c2.involved_points()):
                        frontier.append(c2)
                        
    return affected