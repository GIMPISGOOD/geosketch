"""注入 Document：添加 constraints 列表、静默重算、求解入口。"""
from core.document import Document
from geo.points import FreePoint
from .solver import ConstraintSolver
from .graph import get_affected_constraints

_original_init = Document.__init__
_original_recompute = Document.recompute_from
_original_remove = Document._remove

def _recompute_silent(self, roots):
    """静默重算：不 emit changed，供求解器内部迭代使用。"""
    roots = roots if isinstance(roots, (list, tuple)) else [roots]
    dirty = set()
    stack = list(roots)
    while stack:
        o = stack.pop()
        if o in dirty: continue
        dirty.add(o)
        stack.extend(o.children)
    for o in sorted(dirty, key=lambda o: o.id):
        o.exists = all(p.exists for p in o.parents)
        if o.exists: o.recompute()
    self._mutation_count += 1

def _new_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self.constraints = []

def _new_recompute(self, roots):
    _recompute_silent(self, roots)
    self.changed.emit()

def _new_remove(self, obj):
    doomed = _original_remove(self, obj)
    # 级联删除约束
    doomed_ids = {o.id for o in doomed}
    if hasattr(self, 'constraints'):
        to_remove = [c for c in self.constraints 
                     if any(getattr(p, 'id', None) in doomed_ids for p in c.involved_points())]
        for c in to_remove:
            self.constraints.remove(c)
    return doomed

def add_constraint(self, constraint):
    self.constraints.append(constraint)
    self.solve_constraints()
    self.changed.emit()

def remove_constraint(self, constraint):
    if constraint in self.constraints:
        self.constraints.remove(constraint)
        self.changed.emit()

def solve_constraints(self, trigger_points=None, pinned_points=None):
    if not self.constraints: return
    
    if trigger_points:
        affected = get_affected_constraints(trigger_points, self.constraints)
    else:
        affected = self.constraints
        
    if not affected: return
    
    # 收集自由点 (只允许 FreePoint 被移动)
    free_set = set()
    pinned_set = set(pinned_points or [])
    
    for c in affected:
        for p in c.involved_points():
            if isinstance(p, FreePoint) and p not in pinned_set:
                free_set.add(p)
                
    if not free_set: return
    
    solver = ConstraintSolver()
    solver.solve(affected, list(free_set), list(pinned_set))
    
    # 静默更新依赖图
    _recompute_silent(self, list(free_set))

def patch_document():
    Document.__init__ = _new_init
    Document.recompute_from = _new_recompute
    Document._recompute_silent = _recompute_silent
    Document._remove = _new_remove
    Document.add_constraint = add_constraint
    Document.remove_constraint = remove_constraint
    Document.solve_constraints = solve_constraints