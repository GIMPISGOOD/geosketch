"""脚本对象销毁器。"""

from geo.points import AbstractPoint
from .errors import ScriptError


class ObjectDestructor:
    def __init__(self, interp):
        self.interp = interp

    def _is_protected(self, obj):
        return type(obj).__name__ == "ScriptButtonObject"

    def _can_delete(self, obj):
        if self._is_protected(obj):
            return False

        if getattr(obj, "script_owner", None) == self.interp.owner_id:
            return True

        if getattr(obj, "script_created", False):
            return True

        return bool(self.interp.special.get("__allow_delete_user", False))

    def _can_delete_constraint(self, c):
        if getattr(c, "script_owner", None) == self.interp.owner_id:
            return True

        if getattr(c, "script_created", False):
            return True

        return bool(self.interp.special.get("__allow_delete_user", False))

    def delete_object(self, obj, line=None):
        if obj is None:
            raise ScriptError("delete 对象为空", line)

        doc = self.interp.doc

        # ── 如果删除的是约束 ──
        if hasattr(obj, "cid") and obj in doc.constraints:
            if not self._can_delete_constraint(obj):
                raise ScriptError(
                    "默认禁止删除用户约束。若允许，请设置 __allow_delete_user = true",
                    line
                )

            doc.remove_constraint(obj)

            try:
                if obj in self.interp.created_constraints:
                    self.interp.created_constraints.remove(obj)
            except Exception:
                pass

            return

        # ── 如果删除的是几何对象 ──
        if obj not in doc.objects:
            raise ScriptError("对象不在文档中，无法删除", line)

        if not self._can_delete(obj):
            raise ScriptError(
                "默认禁止删除用户对象。若允许，请设置 __allow_delete_user = true",
                line
            )

        doc._remove(obj)
        doc.changed.emit()

    def delete_all(self, target, line=None):
        doc = self.interp.doc
        candidates = list(doc.objects)

        if target == "points":
            candidates = [o for o in candidates if isinstance(o, AbstractPoint)]

        elif target == "circles":
            candidates = [
                o for o in candidates
                if type(o).__name__ in ("Circle", "ExprCircle")
            ]

        elif target == "created":
            candidates = [
                o for o in candidates
                if getattr(obj, "script_created", False)
                or getattr(obj, "script_owner", None) == self.interp.owner_id
            ]

        changed = False

        for obj in candidates:
            if obj not in doc.objects:
                continue

            if not self._can_delete(obj):
                continue

            doc._remove(obj)
            changed = True

        # ── delete all / delete created 时，也清理可删除的脚本约束 ──
        if target in ("all", "created"):
            for c in list(doc.constraints):
                if not self._can_delete_constraint(c):
                    continue

                try:
                    doc.constraints.remove(c)
                except Exception:
                    pass

                try:
                    if c in self.interp.created_constraints:
                        self.interp.created_constraints.remove(c)
                except Exception:
                    pass

                changed = True

        if changed:
            doc.changed.emit()