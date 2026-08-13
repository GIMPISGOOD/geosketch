"""Document 补丁：添加 constraints 列表、solve_constraints、recompute_silent。"""
from core.document import Document
from geo.points import FreePoint
from .solver import ConstraintSolver
from .graph import get_affected_constraints

_original_init = Document.__init__
_original_recompute = Document.recompute_from
_original_remove = Document._remove


def _recompute_silent(self, roots):
    """静默重算：不 emit changed。"""
    roots = roots if isinstance(roots, (list, tuple)) else [roots]
    dirty = set()
    stack = list(roots)
    while stack:
        o = stack.pop()
        if o in dirty:
            continue
        dirty.add(o)
        stack.extend(o.children)
    for o in sorted(dirty, key=lambda o: o.id):
        o.exists = all(p.exists for p in o.parents)
        if o.exists:
            o.recompute()
    self._mutation_count += 1


def _new_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self.constraints = []


def _new_recompute(self, roots):
    _recompute_silent(self, roots)
    self.changed.emit()


def _new_remove(self, obj):
    doomed = _original_remove(self, obj)
    # 级联删除引用被删对象的约束
    doomed_ids = {o.id for o in doomed}
    if hasattr(self, 'constraints') and self.constraints:
        to_remove = [
            c for c in self.constraints
            if any(getattr(p, 'id', None) in doomed_ids for p in c.involved_points())
        ]
        for c in to_remove:
            self.constraints.remove(c)
    return doomed


def add_constraint(self, constraint):
    """添加约束并立即求解。"""
    self.constraints.append(constraint)
    self.solve_constraints()
    self.changed.emit()


def remove_constraint(self, constraint):
    """删除约束。"""
    if constraint in self.constraints:
        self.constraints.remove(constraint)
        self.changed.emit()


def solve_constraints(self, trigger_points=None, pinned_points=None, _depth=0):
    """求解约束系统。

    参数:
        trigger_points: 触发求解的点（缩小范围），None 则求解全部
        pinned_points: 固定不动的点（如正在拖动的点）
    """
    MAX_DEPTH = 5
    if not self.constraints or _depth >= MAX_DEPTH:
        return

    if trigger_points:
        affected = get_affected_constraints(trigger_points, self.constraints)
    else:
        affected = [c for c in self.constraints if c.enabled]

    if not affected:
        return

    # 收集可移动的自由点
    pinned_set = set(pinned_points or [])
    free_set = set()
    for c in affected:
        for p in c.involved_points():
            if isinstance(p, FreePoint) and p not in pinned_set:
                free_set.add(p)

    if not free_set:
        return

    # 求解
    solver = ConstraintSolver(max_iter=50, tol=1e-9)
    solver.solve(affected, list(free_set), list(pinned_set))

    # ★ 关键：静默更新依赖图（让线段、圆等跟随点更新）
    _recompute_silent(self, list(free_set))

    # 检查是否有新约束被触发（链式传播）
    moved = list(free_set)
    if moved:
        self.solve_constraints(moved, pinned_points, _depth + 1)


def patch_document():
    setattr(Document, "__init__", _new_init)
    setattr(Document, "recompute_from", _new_recompute)
    setattr(Document, "_recompute_silent", _recompute_silent)
    setattr(Document, "_remove", _new_remove)
    setattr(Document, "add_constraint", add_constraint)
    setattr(Document, "remove_constraint", remove_constraint)
    setattr(Document, "solve_constraints", solve_constraints)