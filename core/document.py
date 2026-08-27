import json
import math
import os
import zipfile
import datetime
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from core.registry import GEO_REGISTRY
from geo.base import GeoObject
from geo.points import FreePoint, AbstractPoint, _index_to_letters, _index_to_subscript
from core.variables import get_store
from geo.constraints import ExprSegment, ExprAngle, ExprCircle, ExprPoint

UNDO_LIMIT = 100

# ── 可选导入：约束求解器 ──────────────────────────────────
try:
    from constraints.solver import ConstraintSolver
    from constraints.graph import get_affected_constraints
    from constraints.base import CONSTRAINT_REGISTRY
    _HAS_CONSTRAINTS = True
except ImportError:
    _HAS_CONSTRAINTS = False

# ── 可选导入：动画 ────────────────────────────────────────
try:
    from animation.clip import AnimationClip
    _HAS_ANIMATION = True
except ImportError:
    _HAS_ANIMATION = False


class Document(QObject):
    """持有全部几何对象：增删、增量重算、级联删除、序列化、撤销/重做。
    ★ 原生集成约束求解与动画序列化（不再依赖猴子补丁）。
    """

    changed = Signal()
    history_changed = Signal()
    object_added = Signal(object)
    object_removed = Signal(object)
    cleared = Signal()

    def __init__(self):
        super().__init__()
        self.objects = []
        self._undo = []
        self._redo = []
        self._group_depth = 0
        self._mutation_count = 0
        self._pending = None
        self._mut_before = 0
        self.vars = get_store()
        self.expr_objects = []
        self._clipboard = None
        self.meta = {"title": "", "author": "", "theme": "纸白",
                     "created": "", "modified": ""}
        self.macros = []
        self._macro_suppress = False
        self.names = {}
        self._name_counters = {}
        self._objects_version = 0
        self._type_cache = {}
        self._type_cache_version = -1
        self._temp_image_dir = None
        # ★ 约束系统（原 constraints/document_ext._new_init）
        self.constraints = []
        # ★ 动画系统（原 animation/serialization）
        self.animations = []


    # ──────────────────────────────────────────────────────
    #  临时图片管理
    # ──────────────────────────────────────────────────────
    def _cleanup_temp_images(self):
        if self._temp_image_dir and os.path.isdir(self._temp_image_dir):
            import shutil
            try:
                shutil.rmtree(self._temp_image_dir, ignore_errors=True)
            except Exception:
                pass
        self._temp_image_dir = None

    # ──────────────────────────────────────────────────────
    #  命名
    # ──────────────────────────────────────────────────────
    def _auto_name(self, obj):
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
        i = self._name_counters.get(prefix, 1)
        while f"{prefix}{i}" in self.names:
            i += 1
        self._name_counters[prefix] = i + 1
        return f"{prefix}{i}"

    def _assign_point_labels(self):
        center_ids = set()
        for o in self.objects:
            tn = type(o).__name__
            if tn in ('Circle', 'ExprCircle', 'ThreePointCircle', 'InvertedCircle'):
                c = getattr(o, 'center', None)
                if isinstance(c, AbstractPoint):
                    center_ids.add(id(c))
        p_idx = 1
        c_idx = 1
        for o in self.objects:
            if not isinstance(o, AbstractPoint):
                continue
            if getattr(o, 'name', ''):
                continue
            if id(o) in center_ids:
                o._auto_label = "O" + _index_to_subscript(c_idx)
                c_idx += 1
            else:
                o._auto_label = _index_to_letters(p_idx)
                p_idx += 1

    def _unique_name(self, desired, obj):
        if not desired:
            return self._auto_name(obj)
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
        if isinstance(obj, AbstractPoint) and not getattr(obj, "name", ""):
            return
        obj.name = self._unique_name(getattr(obj, "name", ""), obj)
        self.names[obj.name] = obj

    def _unregister_name(self, obj):
        name = getattr(obj, "name", "")
        if name and self.names.get(name) is obj:
            del self.names[name]

    def rename_object(self, obj, new_name):
        self._unregister_name(obj)
        obj.name = self._unique_name(new_name, obj)
        self.names[obj.name] = obj
        self._assign_point_labels()
        self.changed.emit()

    # ──────────────────────────────────────────────────────
    #  增删
    # ──────────────────────────────────────────────────────
    def _add(self, obj):
        self._mutation_count += 1
        self._objects_version += 1
        self.objects.append(obj)
        if isinstance(obj, (ExprSegment, ExprAngle, ExprCircle, ExprPoint)) or \
                getattr(obj, "expr_driver", False):
            self.expr_objects.append(obj)
        if not getattr(self, "_macro_suppress", False):
            self.object_added.emit(obj)
        self._assign_point_labels()
        return obj

    def _collect_with_deps(self, objs):
        seen = set()

        def collect(o):
            if id(o) in seen:
                return
            seen.add(id(o))
            for p in o.parents:
                collect(p)

        for o in objs:
            collect(o)
        return sorted((o for o in self.objects if id(o) in seen),
                      key=lambda o: o.id)

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
        try:
            for item in self._clipboard:
                type_name = item["type"]
                cls = GEO_REGISTRY.get(type_name)
                if cls is None:
                    continue
                # ★ 修复：安全获取父对象，跳过缺失依赖的项
                parents = []
                skip = False
                for pid in item["parents"]:
                    p = id_map.get(pid)
                    if p is None:
                        skip = True
                        break
                    parents.append(p)
                if skip:
                    continue
                obj = cls.build(parents, item["params"])
                obj.name = ""
                if isinstance(obj, FreePoint):
                    obj.x += offset[0]
                    obj.y += offset[1]
                id_map[item["id"]] = obj
                self._add(obj)
                new_objs.append(obj)
        except Exception:
            # ★ 修复：粘贴过程中任何异常不应导致文档状态损坏
            pass
        finally:
            self.end_action()
        for o in self.objects:
            o.selected = False
        for o in new_objs:
            o.selected = True
        self.vars.update_bindings(self)
        self.changed.emit()

    def add(self, obj):
        self._add(obj)
        self.changed.emit()
        return obj

    def _remove(self, obj):
        """级联删除（不入栈、不发信号），返回被删集合。
        ★ 整合原 constraints/document_ext._new_remove 的约束清理。
        """
        self._mutation_count += 1
        self._objects_version += 1
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
        # ★ 清理引用了被删对象的约束
        if self.constraints:
            doomed_ids = {o.id for o in doomed}
            self.constraints = [
                c for c in self.constraints
                if not any(getattr(p, 'id', None) in doomed_ids
                           for p in c.involved_points())
            ]
        if not getattr(self, "_macro_suppress", False):
            self.object_removed.emit(obj)
        self._assign_point_labels()
        return doomed

    def remove(self, obj):
        if self._group_depth == 0:
            self._push_undo()
        doomed = self._remove(obj)
        self.vars.update_bindings(self)
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
        self.vars.update_bindings(self)
        self.changed.emit()

    def clear(self):
        if self.objects:
            self._push_undo()
        self._cleanup_temp_images()

        # ★ 修复①：打破所有对象的双向依赖引用，防止循环引用阻止 GC
        for obj in self.objects:
            obj.parents.clear()
            obj.children.clear()
            obj.selected = False

        # ★ 修复②：清空命名注册表，解除对旧对象的强引用
        self.names.clear()
        self._name_counters.clear()

        # ★ 修复③：清空对象列表
        self.objects.clear()
        self.expr_objects.clear()
        self.constraints.clear()

        # ★ 修复⑤：清空类型缓存，防止后续查询返回幽灵对象
        self._type_cache.clear()
        self._type_cache_version = -1

        # ★ 修复⑥：递增 _mutation_count，强制画布渲染缓存失效
        self._mutation_count += 1
        self._objects_version += 1

        # ★ 修复⑦：清空剪贴板与待处理的撤销快照
        self._clipboard = None
        self._pending = None

        if not getattr(self, "_macro_suppress", False):
            self.cleared.emit()
        self._assign_point_labels()
        self.vars.update_bindings(self)
        self.changed.emit()

    def set_selection(self, objs):
        target = {id(o) for o in objs}
        for o in self.objects:
            o.selected = id(o) in target
        self.changed.emit()

    def get_typed(self, type_name):
        if self._type_cache_version != self._objects_version:
            self._type_cache.clear()
            self._type_cache_version = self._objects_version
        if type_name not in self._type_cache:
            self._type_cache[type_name] = [
                o for o in self.objects if type(o).__name__ == type_name
            ]
        return self._type_cache[type_name]

    # ──────────────────────────────────────────────────────
    #  重算
    # ──────────────────────────────────────────────────────
    def recompute_silent(self, roots):
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

    def recompute_from(self, roots):
        """增量重算 + 更新绑定变量 + emit changed。
        ★ 修复：保留 update_bindings 调用（原猴子补丁丢失了此调用）。
        """
        self.recompute_silent(roots)
        if self.vars.update_bindings(self):
            self.refresh_variables()
        else:
            self.changed.emit()

    # ──────────────────────────────────────────────────────
    #  约束求解（原 constraints/document_ext）
    # ──────────────────────────────────────────────────────
    def add_constraint(self, constraint):
        """添加约束。如果导致过约束（冲突），自动回滚并提示。"""
        if not _HAS_CONSTRAINTS:
            return
        backup = [(p, p.x, p.y) for p in self.objects
                  if isinstance(p, FreePoint)]
        self.constraints.append(constraint)
        success = self.solve_constraints()
        total_err = 0.0
        for c in self.constraints:
            try:
                for v in c.residual():
                    total_err += v * v
            except Exception:
                pass
        if not success or math.sqrt(total_err) > 1e-3:
            if constraint in self.constraints:
                self.constraints.remove(constraint)
            for p, x, y in backup:
                p.x, p.y = x, y
            if backup:
                self.recompute_silent([p for p, _, _ in backup])
            self.changed.emit()
            try:
                from PySide6.QtWidgets import QMessageBox, QApplication
                parent = QApplication.activeWindow()
                QMessageBox.warning(parent, "过约束",
                                    "添加的约束与现有约束冲突，已自动撤销。")
            except Exception:
                pass
            return
        self.changed.emit()

    def remove_constraint(self, constraint):
        if constraint in self.constraints:
            self.constraints.remove(constraint)
            self.changed.emit()

    def solve_constraints(self, trigger_points=None, pinned_points=None,
                          _depth=0, quick=False):
        if not _HAS_CONSTRAINTS or not self.constraints or _depth >= 5:
            return True
        if trigger_points:
            affected = get_affected_constraints(trigger_points,
                                                self.constraints)
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
        if quick:
            solver = ConstraintSolver(max_iter=12, tol=1e-6)
        else:
            solver = ConstraintSolver(max_iter=50, tol=1e-9)
        success = solver.solve(affected, list(free_set), list(pinned_set))
        self.recompute_silent(list(free_set))
        if list(free_set):
            self.solve_constraints(list(free_set), pinned_points,
                                   _depth + 1, quick=quick)
        return success

    # ──────────────────────────────────────────────────────
    #  快照 / 撤销
    # ──────────────────────────────────────────────────────
    def snapshot(self):
        """★ 整合约束 + 动画序列化。"""
        data = [
            {
                "id": o.id,
                "type": o.type_name,
                "name": getattr(o, "name", ""),
                "visible": getattr(o, "visible", True),
                "parents": [p.id for p in o.parents],
                "params": o.dump()
            }
            for o in self.objects
        ]
        # 约束
        if self.constraints:
            c_data = []
            for c in self.constraints:
                try:
                    d = c.dump()
                    d["__ctype__"] = c.type_name
                    d["__cid__"] = c.cid
                    c_data.append(d)
                except Exception:
                    pass
            if c_data:
                data.append({"__constraints__": c_data})
        # 动画
        if self.animations:
            a_data = []
            for clip in self.animations:
                try:
                    a_data.append(clip.dump())
                except Exception:
                    pass
            if a_data:
                data.append({"__animations__": a_data})

        return data

    def _full_state(self):
        return {
            "objects": self.snapshot(),
            "vars": self.vars.to_dict(),
        }

    def _push_undo(self):
        self._undo.append(self._full_state())
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
        self.vars.update_bindings(self)
        from geo.function_curve import FunctionCurve
        for obj in self.get_typed("FunctionCurve"):
            obj.invalidate_cache()
        for obj in self.get_typed("ImplicitCurve"):
            obj.invalidate_cache()
        moved = []
        for eo in sorted(self.expr_objects, key=lambda o: o.id):
            if eo.exists:
                eo.recompute()
            moved.extend(eo.moved_points())
        if moved:
            self.recompute_silent(moved)
        d = self.vars.as_dict()
        for n, v in self.vars._vars.items():
            if v.expr and n in d:
                v.value = d[n]
        self.changed.emit()

    @contextmanager
    def action(self):
        self.begin_action()
        try:
            yield
        finally:
            self.end_action()

    def _arm_undo(self):
        self._pending = self._full_state()
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
        self._redo.append(self._full_state())
        self._load_state(self._undo.pop())
        self.history_changed.emit()

    def redo(self):
        if not self._redo:
            return
        self._undo.append(self._full_state())
        self._load_state(self._redo.pop())
        self.history_changed.emit()

    def _load_state(self, data):
        """★ 整合约束 + 动画恢复。"""
        vars_state = None
        if isinstance(data, dict):
            vars_state = data.get("vars")
            data = data.get("objects", [])

        # 分离约束 / 动画 / 几何数据
        c_data = []
        a_data = []
        geo_data = []
        for item in data:
            if isinstance(item, dict) and "__constraints__" in item:
                c_data = item["__constraints__"]
            elif isinstance(item, dict) and "__animations__" in item:
                a_data = item["__animations__"]
            else:
                geo_data.append(item)

        # 恢复变量
        if vars_state is not None:
            self.vars.blockSignals(True)
            try:
                self.vars.load_dict(vars_state)
            finally:
                self.vars.blockSignals(False)
        # 恢复几何对象
        # ★ 修复：清空命名注册表与类型缓存，防止旧对象残留
        self.names.clear()
        self._name_counters.clear()
        self._type_cache.clear()
        self._type_cache_version = -1

        self.objects.clear()
        self.expr_objects.clear()
        self._mutation_count += 1
        self._objects_version += 1
        pool = {}
        self._macro_suppress = True
        try:
            for item in geo_data:
                cls = GEO_REGISTRY[item["type"]]
                parents = [pool[pid] for pid in item["parents"]]
                obj = cls.build(parents, item["params"])
                obj.id = item["id"]
            obj.name = item.get("name", "")
            obj.visible = item.get("visible", True)
            pool[item["id"]] = self._add(obj)
            # ★ 修复：恢复后重新注册名字，保证 names 字典与对象同步
            if obj.name:
                self.names[obj.name] = obj
            if geo_data:
                GeoObject.bump_ids(max(item["id"] for item in geo_data))
        finally:
            self._macro_suppress = False

        # ★ 恢复约束
        if _HAS_CONSTRAINTS and c_data:
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
                    except Exception:
                        pass
        else:
            self.constraints = []

        # ★ 恢复动画
        if _HAS_ANIMATION and a_data:
            self.animations = []
            for item in a_data:
                try:
                    self.animations.append(AnimationClip.build(self, item))
                except Exception:
                    pass
        else:
            self.animations = []

        self._assign_point_labels()
        self.vars.update_bindings(self)
        self.changed.emit()

    # ──────────────────────────────────────────────────────
    #  保存 / 加载（★ 整合约束 + 动画文件级序列化）
    # ──────────────────────────────────────────────────────
    def save(self, path):
        from ui import theme as _theme
        self.meta["theme"] = _theme.active_name()
        self.meta["modified"] = datetime.datetime.now().isoformat(
            timespec="seconds")
        if not self.meta.get("created"):
            self.meta["created"] = self.meta["modified"]

        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("sketch.json",
                        json.dumps(self.snapshot(), ensure_ascii=False,
                                   indent=1))
            zf.writestr("meta.data",
                        json.dumps(self.meta, ensure_ascii=False, indent=1))
            zf.writestr("variables.json",
                        json.dumps(self.vars.to_dict(), ensure_ascii=False,
                                   indent=1))
            zf.writestr("macros.json",
                        json.dumps(getattr(self, "macros", []),
                                   ensure_ascii=False, indent=1))
            if hasattr(self, "script_libs") and self.script_libs:
                zf.writestr("script_libs.json",
                            json.dumps(self.script_libs, ensure_ascii=False,
                                       indent=1))
            # 内嵌图片
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

        # ★ 追加约束文件（原 constraints/serialization._new_save）
        if self.constraints:
            c_file_data = []
            for c in self.constraints:
                try:
                    c_file_data.append({
                        "id": c.cid,
                        "type": c.type_name,
                        "params": c.dump()
                    })
                except Exception:
                    pass
            if c_file_data:
                with zipfile.ZipFile(path, "a") as zf:
                    zf.writestr("constraints.json",
                                json.dumps(c_file_data, ensure_ascii=False,
                                           indent=1))

        # ★ 追加动画文件（原 animation/serialization._new_save）
        if self.animations:
            a_file_data = [clip.dump() for clip in self.animations]
            with zipfile.ZipFile(path, "a") as zf:
                zf.writestr("animations.json",
                            json.dumps(a_file_data, ensure_ascii=False,
                                       indent=1))

    def load(self, path):
        import tempfile
        from ui import theme as _theme

        self._cleanup_temp_images()
        with zipfile.ZipFile(path, "r") as zf:
            names = zf.namelist()
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

            # ★ 加载文件级约束（原 constraints/serialization._new_load）
            if _HAS_CONSTRAINTS and "constraints.json" in names:
                try:
                    c_file_data = json.loads(zf.read("constraints.json"))
                    point_map = {o.id: o for o in self.objects}
                    existing_cids = {c.cid for c in self.constraints}
                    for item in c_file_data:
                        if item.get("id") in existing_cids:
                            continue
                        cls = CONSTRAINT_REGISTRY.get(item["type"])
                        if cls:
                            try:
                                c = cls.build(point_map, item["params"])
                                c.cid = item["id"]
                                self.constraints.append(c)
                            except Exception:
                                pass
                except Exception:
                    pass

            # ★ 加载文件级动画（原 animation/serialization._new_load）
            if _HAS_ANIMATION and "animations.json" in names:
                try:
                    a_file_data = json.loads(zf.read("animations.json"))
                    self.animations = []
                    for item in a_file_data:
                        try:
                            self.animations.append(
                                AnimationClip.build(self, item))
                        except Exception:
                            pass
                except Exception:
                    pass

            if "script_libs.json" in names:
                try:
                    self.script_libs = json.loads(
                        zf.read("script_libs.json"))
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