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

    def delete_object(self, obj, line=None):
        if obj is None:
            raise ScriptError("delete 对象为空", line)

        if obj not in self.interp.doc.objects:
            raise ScriptError("对象不在文档中，无法删除", line)

        if not self._can_delete(obj):
            raise ScriptError(
                "默认禁止删除用户对象。若允许，请设置 __allow_delete_user = true",
                line
            )

        self.interp.doc._remove(obj)
        self.interp.doc.changed.emit()

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
                if getattr(o, "script_created", False)
                or getattr(o, "script_owner", None) == self.interp.owner_id
            ]

        changed = False

        for obj in candidates:
            if obj not in doc.objects:
                continue

            if not self._can_delete(obj):
                continue

            doc._remove(obj)
            changed = True

        if changed:
            doc.changed.emit()