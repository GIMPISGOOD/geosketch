"""Document 补丁：添加 constraints 列表、solve_constraints、recompute_silent。
新增：过约束检测 —— add_constraint 时若约束冲突，弹窗提示并自动回滚。
"""
import math
from core.document import Document
from geo.points import FreePoint
from .solver import ConstraintSolver
from .graph import get_affected_constraints

# 过约束判定阈值：求解后残差范数超过此值视为冲突
OVERCONSTRAINT_TOL = 1e-3

_original_init = Document.__init__
_original_recompute = Document.recompute_from
_original_remove = Document._remove


# ─────────────── 过约束辅助 ───────────────

def _residual_norm(constraints):
    """计算约束列表的总残差范数（欧氏）。"""
    total = 0.0
    for c in constraints:
        if not getattr(c, "enabled", True):
            continue
        try:
            for f in c.residual():
                total += f * f
        except Exception:
            pass
    return math.sqrt(total)


def _notify_overconstrained():
    """弹窗提示过约束（无 GUI 环境静默失败）。"""
    try:
        import logging
        logging.getLogger(__name__).warning("过约束：约束冲突，已自动撤销")
    except Exception:
        pass
    try:
        from PySide6.QtWidgets import QMessageBox, QApplication
        parent = QApplication.activeWindow()
        QMessageBox.warning(
            parent,
            "过约束",
            "添加的约束与现有约束冲突（过约束）。\n"
            "系统已自动撤销本次操作，几何图形已恢复。",
        )
    except Exception:
        pass


# ─────────────── 原有补丁逻辑 ───────────────

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
    doomed_ids = {o.id for o in doomed}
    if hasattr(self, 'constraints') and self.constraints:
        to_remove = [
            c for c in self.constraints
            if any(getattr(p, 'id', None) in doomed_ids
                   for p in c.involved_points())
        ]
        for c in to_remove:
            self.constraints.remove(c)
    return doomed


def add_constraint(self, constraint):
    """添加约束并立即求解。过约束时弹窗提示并自动回滚。"""
    # 备份所有自由点坐标（用于过约束回滚）
    backup = [
        (p, p.x, p.y)
        for p in self.objects
        if isinstance(p, FreePoint)
    ]
    self.constraints.append(constraint)
    self.solve_constraints()
    # 过约束判定：求解后残差仍然过大
    if _residual_norm(self.constraints) > OVERCONSTRAINT_TOL:
        # 回滚：移除约束 + 恢复点坐标
        if constraint in self.constraints:
            self.constraints.remove(constraint)
        for p, x, y in backup:
            p.x, p.y = x, y
        if backup:
            self._recompute_silent([p for p, _, _ in backup])
        self.changed.emit()
        _notify_overconstrained()
        return
    self.changed.emit()


def remove_constraint(self, constraint):
    """删除约束。"""
    if constraint in self.constraints:
        self.constraints.remove(constraint)
        self.changed.emit()


def solve_constraints(self, trigger_points=None, pinned_points=None, _depth=0):
    """求解约束系统。返回是否收敛成功。"""
    MAX_DEPTH = 5
    if not self.constraints or _depth >= MAX_DEPTH:
        return True
    if trigger_points:
        affected = get_affected_constraints(trigger_points, self.constraints)
    else:
        affected = [c for c in self.constraints if c.enabled]
    if not affected:
        return True
    pinned_set = set(pinned_points or [])
    free_set = set()
    for c in affected:
        for p in c.involved_points():
            if isinstance(p, FreePoint) and p not in pinned_set:
                free_set.add(p)
    if not free_set:
        return True
    solver = ConstraintSolver(max_iter=50, tol=1e-9)
    success = solver.solve(affected, list(free_set), list(pinned_set))
    self._recompute_silent(list(free_set))
    moved = list(free_set)
    if moved:
        self.solve_constraints(moved, pinned_points, _depth + 1)
    return success


def patch_document():
    setattr(Document, "__init__", _new_init)
    setattr(Document, "recompute_from", _new_recompute)
    setattr(Document, "_recompute_silent", _recompute_silent)
    setattr(Document, "_remove", _new_remove)
    setattr(Document, "add_constraint", add_constraint)
    setattr(Document, "remove_constraint", remove_constraint)
    setattr(Document, "solve_constraints", solve_constraints)