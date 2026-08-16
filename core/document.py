import json
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.registry import GEO_REGISTRY
from geo.base import GeoObject
from geo.points import FreePoint, AbstractPoint
from core.variables import get_store
from geo.constraints import ExprSegment, ExprAngle, ExprCircle, ExprPoint

UNDO_LIMIT = 100


class Document(QObject):
    """持有全部几何对象：增删、增量重算、级联删除、序列化、撤销/重做。"""
    changed = Signal()
    history_changed = Signal()
    object_added = Signal(object)
    object_removed = Signal(object)
    cleared = Signal()    # 撤销栈变化 → 更新菜单项可用状态

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
        self._clipboard = None
        self.meta = {"title": "", "author": "", "theme": "纸白", "created": "", "modified": ""}
        self.macros = []
        self._macro_suppress = False
        self.names = {}
        self._objects_version = 0
        self._type_cache = {}
        self._type_cache_version = -1

        # ★ 约束系统预留（当前为空列表，零开销）
        self.constraints = []
        
    # ================= 对象命名 =================

    def _auto_name(self, obj):
        """根据对象类型自动生成名字：P1、S1、C1、Btn1 等。"""
        tn = type(obj).__name__

        if isinstance(obj, AbstractPoint):
            prefix = "P"
        elif tn == "Segment":
            prefix = "S"
        elif tn == "Line":
            prefix = "L"
        elif tn == "Ray":
            prefix = "R"
        elif tn in ("Circle", "ExprCircle"):
            prefix = "C"
        elif tn == "RegularPolygon":
            prefix = "Poly"
        elif tn == "TextObject":
            prefix = "T"
        elif tn == "ChainFill":
            prefix = "Fill"
        elif tn == "ScriptButtonObject":
            prefix = "Btn"
        elif tn == "FunctionCurve":
            prefix = "f"
        else:
            prefix = tn[:3] or "Obj"

        i = 1
        while f"{prefix}{i}" in self.names:
            i += 1

        return f"{prefix}{i}"

    def _unique_name(self, desired, obj):
        """确保名字唯一；重复则自动加后缀。"""
        if not desired:
            return self._auto_name(obj)

        # 脚本引用要求名字必须是合法标识符
        if not desired.isidentifier():
            cleaned = "".join(
                ch if (ch.isalnum() or ch == "_") else "_"
                for ch in desired
            )
            if not cleaned or cleaned[0].isdigit():
                cleaned = "_" + cleaned
            desired = cleaned or self._auto_name(obj)

        base = desired
        i = 2

        while True:
            old = self.names.get(base)
            if old is None or old is obj:
                return base
            base = f"{desired}_{i}"
            i += 1

    def _register_name(self, obj):
        if not hasattr(obj, "name"):
            obj.name = ""

        # ★ 点对象默认不固定名字，交回 geo/points.py 的动态点名：
        # 普通点 A/B/C/D...
        # 圆心 O₁/O₂/O₃...
        #
        # 只有用户/脚本显式给了名字，才注册进 self.names。
        if isinstance(obj, AbstractPoint) and not getattr(obj, "name", ""):
            return

        obj.name = self._unique_name(getattr(obj, "name", ""), obj)
        self.names[obj.name] = obj

    def _unregister_name(self, obj):
        name = getattr(obj, "name", "")
        if name and self.names.get(name) is obj:
            del self.names[name]

    def rename_object(self, obj, new_name):
        """供未来属性面板/右键菜单调用。"""
        self._unregister_name(obj)
        obj.name = self._unique_name(new_name, obj)
        self.names[obj.name] = obj
        self.changed.emit()
        
    # ================= 增删 =================
    def _add(self, obj):
        self._mutation_count += 1
        self._objects_version += 1
        self.objects.append(obj)
    # ★ 修复：expr_driver 对象（TransformDriver, IterPoint 等）也参与变量联动
        if isinstance(obj, (ExprSegment, ExprAngle, ExprCircle, ExprPoint)) or \
            getattr(obj, "expr_driver", False):
            self.expr_objects.append(obj)
        if not getattr(self, "_macro_suppress", False):
            self.object_added.emit(obj)
        return obj

    def _collect_with_deps(self, objs):
        """收集对象及其全部依赖，按拓扑序（id 升序）。"""
        seen = set()
        def collect(o):
            if id(o) in seen:
                return
            seen.add(id(o))
            for p in o.parents:
                collect(p)
        for o in objs:
            collect(o)
        return sorted((o for o in self.objects if id(o) in seen), key=lambda o: o.id)

    def copy_selection(self):
        sel = [o for o in self.objects if o.selected]
        if not sel:
            return
        self._clipboard = [
            {
                "id": o.id,
                "type": o.type_name,
                "name": getattr(o, "name", ""),
                "parents": [p.id for p in o.parents],
                "params": o.dump()
            }
            for o in self._collect_with_deps(sel)
        ]

    def cut_selection(self):
        self.copy_selection()
        self.remove_selected()

    def paste(self, offset=(1.0, -1.0)):
        if not self._clipboard:
            return
        self.begin_action()
        id_map, new_objs = {}, []
        for item in self._clipboard:
            cls = GEO_REGISTRY[item["type"]]
            parents = [id_map[pid] for pid in item["parents"]]
            obj = cls.build(parents, item["params"])
            obj.name = ""
            if isinstance(obj, FreePoint):        # 只偏移自由点，派生对象自动跟随
                obj.x += offset[0]
                obj.y += offset[1]
            id_map[item["id"]] = obj
            self._add(obj)
            new_objs.append(obj)
        for o in self.objects:
            o.selected = False
        for o in new_objs:
            o.selected = True
        self.end_action()
        self.changed.emit()

    def add(self, obj):
        self._add(obj)
        self.changed.emit()
        return obj

    def _remove(self, obj):
        """级联删除（不入栈、不发信号），返回被删集合。"""
        self._mutation_count += 1
        self._objects_version += 1          # ★ 结构变化
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
            self._unregister_name(o)
        if not getattr(self, "_macro_suppress", False):
            self.object_removed.emit(obj)
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
            self._objects_version += 1      # ★ 结构变化
            # ★ 宏录制：通知清空
            if not getattr(self, "_macro_suppress", False):
                self.cleared.emit()
            self.changed.emit()
        
    # ================= 选择 =================
    def set_selection(self, objs):
        target = {id(o) for o in objs}
        for o in self.objects:
            o.selected = id(o) in target
        self.changed.emit()
    # ================= 类型缓存 =================

    def get_typed(self, type_name):
        """按类型名返回对象列表（带缓存，对象增删时自动失效）。

        用法示例：
            for fc in doc.get_typed("FunctionCurve"):
                fc.invalidate_cache()
        """
        if self._type_cache_version != self._objects_version:
            self._type_cache.clear()
            self._type_cache_version = self._objects_version
        if type_name not in self._type_cache:
            self._type_cache[type_name] = [
                o for o in self.objects if type(o).__name__ == type_name
            ]
        return self._type_cache[type_name]

    # ================= 静默重算 =================

    def recompute_silent(self, roots):
        """静默重算：与 recompute_from 相同的依赖传播，但不 emit changed。

        用途：
        - 约束求解器内部多轮迭代（每轮只改坐标，最后统一 emit）
        - refresh_variables 内部（先静默重算，最后统一 emit）
        - 任何需要"改完再刷新"的批量操作
        """
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

    # ================= 约束求解预留 =================

    def solve_constraints(self, trigger_points=None, pinned_points=None):
        """约束求解入口（预留）。

        当前无约束时立即返回，零开销。
        未来实现时：
        1. 收集 trigger_points 所在的约束连通分量
        2. 收集分量内的 FreePoint 作为自由变量
        3. LM 迭代求解
        4. recompute_silent(moved_points)
        5. 链式检查是否有新约束被触发（最多 N 轮）
        """
        if not self.constraints:
            return
        
    # ================= 增量重算 =================
    def recompute_from(self, roots):
        """增量重算 + emit changed（对外接口，行为不变）。"""
        self.recompute_silent(roots)
        self.changed.emit()

    # ================= 撤销 / 重做 =================
    def snapshot(self):
        return [
        {
            "id": o.id,
            "type": o.type_name,
            "name": getattr(o, "name", ""),
            # ★ 修复：持久化 visible 状态
            "visible": getattr(o, "visible", True),
            "parents": [p.id for p in o.parents],
            "params": o.dump()
        }
        for o in self.objects
        ]

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
        from geo.function_curve import FunctionCurve
        # ★ 使用类型缓存，避免全量扫描 objects
        for obj in self.get_typed("FunctionCurve"):
            obj.invalidate_cache()
        # ★ 新增：隐函数曲线缓存失效
        for obj in self.get_typed("ImplicitCurve"):
            obj.invalidate_cache()
        moved = []
        for eo in sorted(self.expr_objects, key=lambda o: o.id):
            if eo.exists:
                eo.recompute()
            moved.extend(eo.moved_points())
        if moved:
            self.recompute_silent(moved)
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
        self.expr_objects.clear()
        self._objects_version += 1
        pool = {}
        self._macro_suppress = True
        try:
            for item in data:
                cls = GEO_REGISTRY[item["type"]]
                parents = [pool[pid] for pid in item["parents"]]
                obj = cls.build(parents, item["params"])
                obj.id = item["id"]
                # ★ 修复：恢复自定义名称和可见性
                obj.name = item.get("name", "")
                obj.visible = item.get("visible", True)
                pool[item["id"]] = self._add(obj)
            if data:
                GeoObject.bump_ids(max(item["id"] for item in data))
        finally:
            self._macro_suppress = False
        self.changed.emit()

    def save(self, path):
        import zipfile
        import datetime
        import os
        from ui import theme as _theme
        self.meta["theme"] = _theme.active_name()
        self.meta["modified"] = datetime.datetime.now().isoformat(timespec="seconds")
        if not self.meta.get("created"):
            self.meta["created"] = self.meta["modified"]
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                "sketch.json",
                json.dumps(self.snapshot(), ensure_ascii=False, indent=1)
            )
            zf.writestr(
                "meta.data",
                json.dumps(self.meta, ensure_ascii=False, indent=1)
            )
            zf.writestr(
                "variables.json",
                json.dumps(self.vars.to_dict(), ensure_ascii=False, indent=1)
            )
            zf.writestr(
                "macros.json",
                json.dumps(getattr(self, "macros", []), ensure_ascii=False, indent=1)
            )
            if hasattr(self, "script_libs") and self.script_libs:
                zf.writestr(
                    "script_libs.json",
                    json.dumps(self.script_libs, ensure_ascii=False, indent=1)
                )
            # ★ 内嵌图片：把 ImageObject 的图片写入 media/images/
            for obj in self.objects:
                if type(obj).__name__ == "ImageObject":
                    img_path = getattr(obj, "path", None)
                    if img_path and os.path.exists(img_path):
                        ext = os.path.splitext(img_path)[1] or ".png"
                        arcname = f"media/images/{obj.id}{ext}"
                        try:
                            zf.write(img_path, arcname)
                        except Exception:
                            pass

    def load(self, path):
        import zipfile
        import tempfile
        import os
        from ui import theme as _theme
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()

            # ★ 解压内嵌图片到临时目录
            self._temp_image_dir = tempfile.mkdtemp(prefix="geosketch_img_")
            for name in names:
                if name.startswith("media/images/"):
                    try:
                        data = zf.read(name)
                        fname = os.path.basename(name)
                        tmp_path = os.path.join(self._temp_image_dir, fname)
                        with open(tmp_path, "wb") as f:
                            f.write(data)
                    except Exception:
                        pass

            if "variables.json" in names:
                self.vars.load_dict(json.loads(zf.read("variables.json")))
            else:
                self.vars.load_dict({})

            # ★ 把 sketch.json 中 ImageObject 的 image_name 转为临时路径
            sketch_data = json.loads(zf.read("sketch.json"))
            for item in sketch_data:
                if item.get("type") == "ImageObject":
                    params = item.get("params", {})
                    img_name = params.get("image_name")
                    if img_name:
                        params["path"] = os.path.join(
                            self._temp_image_dir, img_name)
                        params.pop("image_name", None)

            self._load_state(sketch_data)

            if "script_libs.json" in names:
                try:
                    self.script_libs = json.loads(zf.read("script_libs.json"))
                except Exception:
                    self.script_libs = {}
            else:
                self.script_libs = {}
            if "meta.data" in names:
                self.meta = json.loads(zf.read("meta.data"))
                if self.meta.get("theme") in _theme.theme_names():
                    _theme.set_theme(self.meta["theme"])
            if "macros.json" in names:
                try:
                    self.macros = json.loads(zf.read("macros.json"))
                except Exception:
                    self.macros = []
            else:
                self.macros = []
            self.refresh_variables()