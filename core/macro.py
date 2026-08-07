"""宏录制与回放系统。

宏命令类型：
- add      创建对象
- move     移动对象
- delete   删除对象
- set_var  设置变量
- clear    清空文档
"""

from PySide6.QtCore import QObject, Signal

from core.registry import GEO_REGISTRY


# ------------------------------------------------------------
# 全局宏管理器访问入口
# ------------------------------------------------------------

_macro_manager = None


def set_macro_manager(manager):
    global _macro_manager
    _macro_manager = manager


def get_macro_manager():
    return _macro_manager


# ------------------------------------------------------------
# 宏数据结构
# ------------------------------------------------------------

class Macro:
    def __init__(self, name, commands):
        self.name = name
        self.commands = list(commands)

    def to_dict(self):
        return {
            "name": self.name,
            "commands": self.commands,
        }

    @classmethod
    def from_dict(cls, d):
        return cls(
            d.get("name", "宏"),
            d.get("commands", []),
        )


# ------------------------------------------------------------
# 宏录制器
# ------------------------------------------------------------

class MacroRecorder(QObject):
    """监听 Document 的对象增删与外部调用，录制宏命令。"""

    def __init__(self, doc, manager):
        super().__init__(doc)

        self.doc = doc
        self.manager = manager

        self.active = False
        self.paused = False

        self.commands = []
        self.aliases = {}
        self.counter = 0

    # ================= 启停 =================

    def start(self):
        if self.active:
            return

        self.active = True
        self.paused = False
        self.commands = []
        self.aliases = {}
        self.counter = 0

        self.doc.object_added.connect(self._on_object_added)
        self.doc.object_removed.connect(self._on_object_removed)

        if hasattr(self.doc, "cleared"):
            self.doc.cleared.connect(self._on_cleared)

    def stop(self):
        if not self.active:
            return None

        self._disconnect_doc()

        self.active = False
        self.paused = False

        if not self.commands:
            return None

        name = f"宏 {len(getattr(self.doc, 'macros', [])) + 1}"
        return Macro(name, self.commands)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def _disconnect_doc(self):
        try:
            self.doc.object_added.disconnect(self._on_object_added)
        except Exception:
            pass

        try:
            self.doc.object_removed.disconnect(self._on_object_removed)
        except Exception:
            pass

        try:
            if hasattr(self.doc, "cleared"):
                self.doc.cleared.disconnect(self._on_cleared)
        except Exception:
            pass

    # ================= 工具 =================

    def _enabled(self):
        return (
            self.active
            and not self.paused
            and not getattr(self.doc, "_macro_suppress", False)
        )

    def _new_alias(self):
        self.counter += 1
        return f"o{self.counter}"

    def _can_record(self, obj):
        tn = getattr(obj, "type_name", None)
        if not tn:
            return False

        if tn not in GEO_REGISTRY:
            return False

        cls = GEO_REGISTRY[tn]

        return hasattr(cls, "build")

    # ================= 对象录制 =================

    def ensure_recorded(self, obj):
        """确保对象已被录制，返回宏别名。"""

        if obj is None:
            return None

        alias = self.aliases.get(obj)
        if alias is not None:
            return alias

        if not self._can_record(obj):
            return None

        parent_aliases = []

        for p in obj.parents:
            pa = self.ensure_recorded(p)

            if pa is None:
                return None

            parent_aliases.append(pa)

        try:
            params = obj.dump()
        except Exception:
            return None

        alias = self._new_alias()
        self.aliases[obj] = alias

        self.commands.append({
            "type": "add",
            "class": obj.type_name,
            "alias": alias,
            "parents": parent_aliases,
            "params": params,
        })

        return alias

    # ================= Document 信号 =================

    def _on_object_added(self, obj):
        if not self._enabled():
            return

        self.ensure_recorded(obj)

    def _on_object_removed(self, obj):
        if not self._enabled():
            return

        alias = self.aliases.get(obj)

        # 如果删除的是录制前已经存在的对象，
        # 为保证宏自包含，先补录该对象，再录删除。
        if alias is None:
            alias = self.ensure_recorded(obj)

        if alias is not None:
            self.commands.append({
                "type": "delete",
                "alias": alias,
            })

    def _on_cleared(self):
        if not self._enabled():
            return

        self.commands.append({
            "type": "clear",
        })

        # 清空后旧对象别名全部失效
        self.aliases.clear()

    # ================= 外部调用录制 =================

    def record_move(self, obj):
        """由 SelectTool 拖动结束后调用。"""

        if not self._enabled():
            return

        alias = self.aliases.get(obj)

        if alias is None:
            alias = self.ensure_recorded(obj)

        if alias is None:
            return

        try:
            params = obj.dump()
        except Exception:
            return

        # 如果连续移动同一个对象，只保留最后一次状态
        if (
            self.commands
            and self.commands[-1].get("type") == "move"
            and self.commands[-1].get("alias") == alias
        ):
            self.commands[-1]["params"] = params
        else:
            self.commands.append({
                "type": "move",
                "alias": alias,
                "params": params,
            })

    def record_set_var(self, name, value):
        """变量滑杆 / 编辑变量后调用。"""

        if not self._enabled():
            return

        var = self.doc.vars.get_var(name)

        # 从动变量不能被手动设置
        if var is not None and getattr(var, "expr", ""):
            return

        try:
            value = float(value)
        except Exception:
            return

        # 如果连续修改同一个变量，只保留最后一次值
        if (
            self.commands
            and self.commands[-1].get("type") == "set_var"
            and self.commands[-1].get("name") == name
        ):
            self.commands[-1]["value"] = value
        else:
            self.commands.append({
                "type": "set_var",
                "name": name,
                "value": value,
            })


# ------------------------------------------------------------
# 宏回放器
# ------------------------------------------------------------

class MacroPlayer(QObject):
    def __init__(self, doc, manager):
        super().__init__(doc)

        self.doc = doc
        self.manager = manager

    def play(self, macro):
        if self.manager.is_recording():
            return False

        if isinstance(macro, Macro):
            macro = macro.to_dict()

        commands = macro.get("commands", [])

        if not commands:
            return False

        self.manager.recorder.pause()

        old_suppress = getattr(self.doc, "_macro_suppress", False)
        self.doc._macro_suppress = True

        # 整个宏作为一个撤销动作
        self.doc.begin_action()

        aliases = {}
        vars_changed = False

        try:
            for cmd in commands:
                try:
                    t = cmd.get("type")

                    if t == "add":
                        self._add(cmd, aliases)

                    elif t == "move":
                        self._move(cmd, aliases)

                    elif t == "delete":
                        self._delete(cmd, aliases)

                    elif t == "set_var":
                        self._set_var(cmd)
                        vars_changed = True

                    elif t == "clear":
                        self._clear(aliases)

                except Exception:
                    import traceback
                    traceback.print_exc()

            if vars_changed:
                self.doc.refresh_variables()

            self.doc.changed.emit()

        finally:
            self.doc.end_action()
            self.doc._macro_suppress = old_suppress
            self.manager.recorder.resume()

        return True

    # ================= 命令执行 =================

    def _add(self, cmd, aliases):
        cls = GEO_REGISTRY.get(cmd.get("class"))

        if cls is None:
            return

        parent_aliases = cmd.get("parents", [])
        parents = []

        for a in parent_aliases:
            obj = aliases.get(a)

            if obj is None:
                return

            parents.append(obj)

        obj = cls.build(parents, cmd.get("params", {}))

        alias = cmd.get("alias")

        if alias:
            aliases[alias] = obj

        self.doc._add(obj)

    def _move(self, cmd, aliases):
        obj = aliases.get(cmd.get("alias"))

        if obj is None:
            return

        params = cmd.get("params", {})

        for k, v in params.items():
            if hasattr(obj, k):
                setattr(obj, k, v)

        self.doc.recompute_from(obj)

    def _delete(self, cmd, aliases):
        obj = aliases.get(cmd.get("alias"))

        if obj is None:
            return

        if obj in self.doc.objects:
            self.doc._remove(obj)

    def _set_var(self, cmd):
        name = cmd.get("name")
        value = float(cmd.get("value", 0.0))

        store = self.doc.vars
        var = store.get_var(name)

        if var is not None and getattr(var, "expr", ""):
            return

        store.blockSignals(True)

        try:
            if var is not None:
                store.set(name, value)
            else:
                store.define(
                    name=name,
                    value=value,
                    vmin=value - 10.0,
                    vmax=value + 10.0,
                    expr="",
                )
        finally:
            store.blockSignals(False)

    def _clear(self, aliases):
        self.doc.objects.clear()
        self.doc.expr_objects.clear()

        if hasattr(self.doc, "names"):
            self.doc.names.clear()

        aliases.clear()

        self.doc._mutation_count += 1


# ------------------------------------------------------------
# 宏管理器
# ------------------------------------------------------------

class MacroManager(QObject):
    changed = Signal()

    def __init__(self, doc):
        super().__init__(doc)

        self.doc = doc

        if not hasattr(self.doc, "macros"):
            self.doc.macros = []

        self.recorder = MacroRecorder(doc, self)
        self.player = MacroPlayer(doc, self)

    # ================= 录制 =================

    def is_recording(self):
        return self.recorder.active

    def toggle_recording(self):
        if self.is_recording():
            self.stop_recording()
        else:
            self.start_recording()

    def start_recording(self):
        if self.is_recording():
            return

        self.recorder.start()
        self.changed.emit()

    def stop_recording(self):
        if not self.is_recording():
            return None

        macro = self.recorder.stop()

        if macro is not None and macro.commands:
            self.doc.macros.append(macro.to_dict())
            self.changed.emit()

        return macro

    # ================= 回放 =================

    def play_last(self):
        macros = getattr(self.doc, "macros", [])

        if not macros:
            return False

        return self.play(macros[-1])

    def play(self, macro):
        if self.is_recording():
            return False

        return self.player.play(macro)

    # ================= 管理 =================

    def delete_macro(self, index):
        macros = getattr(self.doc, "macros", [])

        if 0 <= index < len(macros):
            macros.pop(index)
            self.changed.emit()

    def rename_macro(self, index, name):
        macros = getattr(self.doc, "macros", [])

        if 0 <= index < len(macros):
            macros[index]["name"] = name
            self.changed.emit()