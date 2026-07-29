import json
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.registry import GEO_REGISTRY
from geo.base import GeoObject

from core.variables import get_store
from geo.constraints import ExprSegment, ExprAngle

UNDO_LIMIT = 100


class Document(QObject):
    """持有全部几何对象：增删、增量重算、级联删除、序列化、撤销/重做。"""
    changed = Signal()
    history_changed = Signal()          # 撤销栈变化 → 更新菜单项可用状态

    def __init__(self):
        super().__init__()
        self.objects = []
        self._undo = []                 # 历史状态快照栈
        self._redo = []
        self._group_depth = 0           # 动作分组深度（拖动/批量）
        self._mutation_count = 0        # 几何变更计数
        self._pending = None            # 按压前暂存的快照
        self._mut_before = 0
        self.vars = get_store()
        self.expr_objects = []

    # ================= 增删 =================
    def _add(self, obj):
        self._mutation_count += 1
        self.objects.append(obj)
        if isinstance(obj, (ExprSegment, ExprAngle)):
            self.expr_objects.append(obj)
        return obj

    def add(self, obj):
        self._add(obj)
        self.changed.emit()
        return obj

    def _remove(self, obj):
        """级联删除（不入栈、不发信号），返回被删集合。"""
        self._mutation_count += 1
        doomed, stack = set(), [obj]
        while stack:
            o = stack.pop()
            if o in doomed:
                continue
            doomed.add(o)
            stack.extend(o.children)
        for o in doomed:
            for p in o.parents:
                if o in p.children:
                    p.children.remove(o)
            if o in self.objects:
                self.objects.remove(o)
            if o in self.expr_objects:
                self.expr_objects.remove(o)
        return doomed

    def remove(self, obj):
        if self._group_depth == 0:
            self._push_undo()
        doomed = self._remove(obj)
        self.changed.emit()
        return doomed

    def remove_selected(self):
        sel = [o for o in self.objects if o.selected]
        if not sel:
            return
        self.begin_action()
        for o in sel:
            if o in self.objects:
                self._remove(o)
        self.end_action()
        self.changed.emit()

    def clear(self):
        if self.objects:
            self._push_undo()
        self.objects.clear()
        self.expr_objects.clear()
        self.changed.emit()

    # ================= 选择 =================
    def set_selection(self, objs):
        target = {id(o) for o in objs}
        for o in self.objects:
            o.selected = id(o) in target
        self.changed.emit()

    # ================= 增量重算 =================
    def recompute_from(self, roots):
        roots = roots if isinstance(roots, (list, tuple)) else [roots]
        dirty, stack = set(), list(roots)
        while stack:
            for c in stack.pop().children:
                if c not in dirty:
                    dirty.add(c)
                    stack.append(c)
        for o in sorted(dirty, key=lambda o: o.id):
            o.exists = all(p.exists for p in o.parents)
            if o.exists:
                o.recompute()
        self._mutation_count += 1
        self.changed.emit()

    # ================= 撤销 / 重做 =================
    def snapshot(self):
        return [{"id": o.id, "type": o.type_name,
                 "parents": [p.id for p in o.parents], "params": o.dump()}
                for o in self.objects]

    def _push_undo(self):
        self._undo.append(self.snapshot())
        if len(self._undo) > UNDO_LIMIT:
            self._undo.pop(0)
        self._redo.clear()
        self.history_changed.emit()

    def begin_action(self):
        if self._group_depth == 0:
            self._push_undo()
        self._group_depth += 1

    def end_action(self):
        self._group_depth = max(0, self._group_depth - 1)

    def refresh_variables(self):
        """变量变化后，重算所有表达式约束对象并联动其后代。"""
        moved = []
        for eo in sorted(self.expr_objects, key=lambda o: o.id):
            if eo.exists:
                eo.recompute()
                moved.extend(eo.moved_points())
        if moved:
            self.recompute_from(moved)
        else:
            self.changed.emit()

    @contextmanager
    def action(self):
        self.begin_action()
        try:
            yield
        finally:
            self.end_action()

    def _arm_undo(self):
        self._pending = self.snapshot()
        self._mut_before = self._mutation_count

    def _commit_undo_if_changed(self):
        if self._pending is not None and self._mutation_count != self._mut_before:
            self._undo.append(self._pending)
            if len(self._undo) > UNDO_LIMIT:
                self._undo.pop(0)
            self._redo.clear()
            self.history_changed.emit()
        self._pending = None

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    def undo(self):
        if not self._undo:
            return
        self._redo.append(self.snapshot())
        self._load_state(self._undo.pop())
        self.history_changed.emit()

    def redo(self):
        if not self._redo:
            return
        self._undo.append(self.snapshot())
        self._load_state(self._redo.pop())
        self.history_changed.emit()

    # ================= 序列化 =================
    def _load_state(self, data):
        self.objects.clear()
        pool = {}
        for item in data:
            cls = GEO_REGISTRY[item["type"]]
            parents = [pool[pid] for pid in item["parents"]]
            obj = cls.build(parents, item["params"])
            obj.id = item["id"]          # ★ 恢复原始 id：修复撤销/重做后标签变大的 bug
            pool[item["id"]] = self._add(obj)
        if data:
            GeoObject.bump_ids(max(item["id"] for item in data))
        self.changed.emit()

    def save(self, path):
        Path(path).write_text(
            json.dumps(self.snapshot(), ensure_ascii=False, indent=1), encoding="utf-8")

    def load(self, path):
        self._load_state(json.loads(Path(path).read_text(encoding="utf-8")))