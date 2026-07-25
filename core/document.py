import json
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.registry import GEO_REGISTRY
from geo.base import GeoObject


class Document(QObject):
    """持有全部几何对象。真相在模型里，视图只是渲染结果。"""
    changed = Signal()

    def __init__(self):
        super().__init__()
        self.objects: list = []

    # ---------- 增删 ----------
    def add(self, obj):
        self.objects.append(obj)
        self.changed.emit()
        return obj

    def remove(self, obj):
        """级联删除：依赖它的整棵子树（如删点会连带删掉过它的线段）"""
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
        self.changed.emit()
        return doomed

    def remove_selected(self):
        for o in [o for o in self.objects if o.selected]:
            if o in self.objects:          # 可能已被前面的级联删掉
                self.remove(o)

    def clear(self):
        self.objects.clear()
        GeoObject.reset_ids()
        self.changed.emit()

    # ---------- 选择 ----------
    def set_selection(self, objs):
        target = {id(o) for o in objs}
        for o in self.objects:
            o.selected = id(o) in target
        self.changed.emit()

    # ---------- 增量重算 ----------
    def recompute_from(self, roots):
        """拖动一个点后，把它的全部后代按拓扑序重算。
        关键技巧：对象总在依赖之后创建 → 创建顺序(id)就是合法拓扑序。"""
        roots = roots if isinstance(roots, (list, tuple)) else [roots]
        dirty, stack = set(), list(roots)
        while stack:
            for c in stack.pop().children:
                if c not in dirty:
                    dirty.add(c)
                    stack.append(c)
        for o in sorted(dirty, key=lambda o: o.id):
            o.exists = all(p.exists for p in o.parents)   # 失效向下传播
            if o.exists:
                o.recompute()
        self.changed.emit()

    # ---------- 序列化：注册表的用武之地 ----------
    def save(self, path):
        data = [{
            "id": o.id,
            "type": o.type_name,                 # ← 注册过的类型名
            "parents": [p.id for p in o.parents],
            "params": o.dump(),
        } for o in self.objects]
        Path(path).write_text(
            json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")

    def load(self, path):
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        self.objects.clear()
        pool = {}
        for item in raw:                          # 保存顺序即拓扑序，依次重建
            cls = GEO_REGISTRY[item["type"]]      # ← 按名字查注册表
            parents = [pool[pid] for pid in item["parents"]]
            pool[item["id"]] = self.add_no_signal(cls.build(parents, item["params"]))
        if raw:
            GeoObject.bump_ids(max(item["id"] for item in raw))
        self.changed.emit()

    def add_no_signal(self, obj):
        self.objects.append(obj)
        return obj