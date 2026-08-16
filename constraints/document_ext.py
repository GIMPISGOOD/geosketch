"""Document 补丁：约束序列化、撤销恢复、过约束回滚。"""
from core.document import Document
from geo.points import FreePoint
from .solver import ConstraintSolver
from .graph import get_affected_constraints
from .base import CONSTRAINT_REGISTRY

_original_init = Document.__init__
_original_recompute = Document.recompute_from
_original_remove = Document._remove
_original_snapshot = Document.snapshot
_original_load_state = Document._load_state

def _recompute_silent(self, roots):
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
    doomed_ids = {o.id for o in doomed}
    if hasattr(self, 'constraints') and self.constraints:
        to_remove = [c for c in self.constraints 
                     if any(getattr(p, 'id', None) in doomed_ids for p in c.involved_points())]
        for c in to_remove: self.constraints.remove(c)
    return doomed

# ═══════════════ ★ 核心修复：撤销/重做支持约束 ═══════════════
def _new_snapshot(self):
    """快照 = 几何对象 + 约束数据。"""
    data = _original_snapshot(self)
    if hasattr(self, 'constraints') and self.constraints:
        c_data = []
        for c in self.constraints:
            try:
                d = c.dump()
                d["__ctype__"] = c.type_name
                d["__cid__"] = c.cid
                c_data.append(d)
            except: pass
        if c_data:
            data.append({"__constraints__": c_data})
    return data

def _new_load_state(self, data):
    """恢复状态：先恢复几何，再重建约束并绑定新实例。"""
    c_data = []
    geo_data = []
    for item in data:
        if isinstance(item, dict) and "__constraints__" in item:
            c_data = item["__constraints__"]
        else:
            geo_data.append(item)
            
    _original_load_state(self, geo_data)
    
    if hasattr(self, 'constraints'):
        point_map = {o.id: o for o in self.objects}
        self.constraints = []
        for item in c_data:
            ctype = item.pop("__ctype__", "")
            cid = item.pop("__cid__", "")
            cls = CONSTRAINT_REGISTRY.get(ctype)
            if cls:
                try:
                    c = cls.build(point_map, item)
                    c.cid = cid
                    self.constraints.append(c)
                except: pass

# ═══════════════ ★ 核心修复：过约束检测与回滚 ═══════════════
def add_constraint(self, constraint):
    """添加约束。如果导致过约束（冲突），自动回滚并提示。"""
    backup = [(p, p.x, p.y) for p in self.objects if isinstance(p, FreePoint)]
    self.constraints.append(constraint)
    
    success = self.solve_constraints()
    
    # 检查残差是否过大（过约束）
    import math
    total_err = 0.0
    for c in self.constraints:
        try:
            for v in c.residual(): total_err += v * v
        except: pass
        
    if not success or math.sqrt(total_err) > 1e-3:
        # 回滚
        if constraint in self.constraints:
            self.constraints.remove(constraint)
        for p, x, y in backup:
            p.x, p.y = x, y
        if backup:
            _recompute_silent(self, [p for p, _, _ in backup])
        self.changed.emit()
        
        # 弹窗提示（静默失败保护）
        try:
            from PySide6.QtWidgets import QMessageBox, QApplication
            parent = QApplication.activeWindow()
            QMessageBox.warning(parent, "过约束", "添加的约束与现有约束冲突，已自动撤销。")
        except: pass
        return

    self.changed.emit()

def remove_constraint(self, constraint):
    if constraint in self.constraints:
        self.constraints.remove(constraint)
        self.changed.emit()

def solve_constraints(self, trigger_points=None, pinned_points=None, _depth=0):
    MAX_DEPTH = 5
    if not self.constraints or _depth >= MAX_DEPTH:
        return True
    if trigger_points:
        affected = get_affected_constraints(trigger_points, self.constraints)
    else:
        affected = [c for c in self.constraints if c.enabled]
    if not affected: return True
    
    pinned_set = set(pinned_points or [])
    free_set = set()
    for c in affected:
        for p in c.involved_points():
            if isinstance(p, FreePoint) and p not in pinned_set:
                free_set.add(p)
    if not free_set: return True
    
    solver = ConstraintSolver(max_iter=50, tol=1e-9)
    success = solver.solve(affected, list(free_set), list(pinned_set))
    _recompute_silent(self, list(free_set))
    
    if list(free_set):
        self.solve_constraints(list(free_set), pinned_points, _depth + 1)
    return success

def patch_document():
    setattr(Document, "__init__", _new_init)
    setattr(Document, "recompute_from", _new_recompute)
    setattr(Document, "_recompute_silent", _recompute_silent)
    setattr(Document, "_remove", _new_remove)
    setattr(Document, "snapshot", _new_snapshot)          # ★ 新增
    setattr(Document, "_load_state", _new_load_state)    # ★ 新增
    setattr(Document, "add_constraint", add_constraint)
    setattr(Document, "remove_constraint", remove_constraint)
    setattr(Document, "solve_constraints", solve_constraints)