"""具体轨道类型：变量轨道、路径轨道、属性轨道。"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from .base import AnimationTrack, register_track
from .keyframe import Keyframe, evaluate_keyframes

# ★ 轨道类型中文名映射
TRACK_TYPE_NAMES_CN = {
    "variable": "变量轨道",
    "glider": "路径轨道（吸附点）",
    "property": "属性轨道",
}


@register_track("variable")
class VariableTrack(AnimationTrack):
    """变量轨道：驱动 VariableStore 中的变量。"""

    def __init__(self, var_name: str, keyframes: List[Keyframe] | None = None):
        super().__init__(target=None)
        self.var_name = var_name
        self.keyframes = keyframes or []

    def evaluate(self, time: float) -> None:
        if self.muted or not self.enabled:
            return
        val = evaluate_keyframes(self.keyframes, time)
        if val is None:
            return
        from core.variables import get_store
        store = get_store()
        var = store.get_var(self.var_name)
        if var is None or getattr(var, "expr", ""):
            return
        # ★ 静默修改，不触发 changed 信号
        if var.value != float(val):
            var.value = float(val)
            store.version += 1

    def duration(self) -> float:
        if not self.keyframes:
            return 0.0
        return max(f.time for f in self.keyframes)

    def label(self) -> str:
        return f"变量: {self.var_name}"

    def dump(self) -> dict:
        return {
            "type": self.type_name,
            "var_name": self.var_name,
            "keyframes": [kf.dump() for kf in self.keyframes],
            "enabled": self.enabled,
            "muted": self.muted,
        }

    @classmethod
    def build(cls, doc: Any, params: dict) -> "VariableTrack":
        frames = [Keyframe.from_dict(d) for d in params.get("keyframes", [])]
        frames.sort(key=lambda f: f.time)
        track = cls(params.get("var_name", ""), frames)
        track.enabled = params.get("enabled", True)
        track.muted = params.get("muted", False)
        return track


@register_track("glider")
class GliderTrack(AnimationTrack):
    """路径轨道：驱动 PointOnObject 的参数 t。"""

    def __init__(self, obj_id: int, keyframes: List[Keyframe] | None = None):
        super().__init__(target=None)
        self.obj_id = obj_id
        self.keyframes = keyframes or []

    def evaluate(self, time: float) -> None:
        if self.muted or not self.enabled:
            return
        if self.target is None:
            return
        val = evaluate_keyframes(self.keyframes, time)
        if val is None:
            return
        t = max(0.0, min(1.0, val))
        if hasattr(self.target, "t"):
            self.target.t = t

    def duration(self) -> float:
        if not self.keyframes:
            return 0.0
        return max(f.time for f in self.keyframes)

    def label(self) -> str:
        return f"路径: 对象#{self.obj_id}"

    def dump(self) -> dict:
        return {
            "type": self.type_name,
            "obj_id": self.obj_id,
            "keyframes": [kf.dump() for kf in self.keyframes],
            "enabled": self.enabled,
            "muted": self.muted,
        }

    @classmethod
    def build(cls, doc: Any, params: dict) -> "GliderTrack":
        frames = [Keyframe.from_dict(d) for d in params.get("keyframes", [])]
        frames.sort(key=lambda f: f.time)
        track = cls(params.get("obj_id", 0), frames)
        track.enabled = params.get("enabled", True)
        track.muted = params.get("muted", False)
        return track


@register_track("property")
class PropertyTrack(AnimationTrack):
    """属性轨道：驱动对象的数值属性。"""

    ALLOWED_ATTRS = {
        "size", "rotation", "width", "height", "opacity", "t"
    }

    # ★ 属性名中文映射
    ATTR_NAMES_CN = {
        "size": "大小",
        "rotation": "旋转角度",
        "width": "宽度",
        "height": "高度",
        "opacity": "透明度",
        "t": "参数 t",
    }

    def __init__(self, obj_id: int, attr_name: str,
                 keyframes: List[Keyframe] | None = None):
        super().__init__(target=None)
        self.obj_id = obj_id
        self.attr_name = attr_name
        self.keyframes = keyframes or []

    def evaluate(self, time: float) -> None:
        if self.muted or not self.enabled:
            return
        if self.target is None:
            return
        if self.attr_name not in self.ALLOWED_ATTRS:
            return
        val = evaluate_keyframes(self.keyframes, time)
        if val is None:
            return
        if hasattr(self.target, self.attr_name):
            setattr(self.target, self.attr_name, val)

    def duration(self) -> float:
        if not self.keyframes:
            return 0.0
        return max(f.time for f in self.keyframes)

    def label(self) -> str:
        cn_name = self.ATTR_NAMES_CN.get(self.attr_name, self.attr_name)
        return f"属性: {cn_name} (对象#{self.obj_id})"

    def dump(self) -> dict:
        return {
            "type": self.type_name,
            "obj_id": self.obj_id,
            "attr_name": self.attr_name,
            "keyframes": [kf.dump() for kf in self.keyframes],
            "enabled": self.enabled,
            "muted": self.muted,
        }

    @classmethod
    def build(cls, doc: Any, params: dict) -> "PropertyTrack":
        frames = [Keyframe.from_dict(d) for d in params.get("keyframes", [])]
        frames.sort(key=lambda f: f.time)
        track = cls(
            params.get("obj_id", 0),
            params.get("attr_name", ""),
            frames,
        )
        track.enabled = params.get("enabled", True)
        track.muted = params.get("muted", False)
        return track