"""具体轨道类型：变量轨道、路径轨道、属性轨道。"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

from .base import AnimationTrack, register_track
from .keyframe import Keyframe, evaluate_keyframes


@register_track("variable")
class VariableTrack(AnimationTrack):
    """变量轨道：驱动 VariableStore 中的变量。

    绑定变量名，随时间改变变量值。
    """

    def __init__(self, var_name: str, keyframes: List[Keyframe] | None = None):
        super().__init__(target=None)
        self.var_name = var_name
        self.keyframes = keyframes or []

    def evaluate(self, time: float) -> None:
        if self.muted or not self.enabled: return
        val = evaluate_keyframes(self.keyframes, time)
        if val is None: return
        
        from core.variables import get_store
        store = get_store()
        var = store.get_var(self.var_name)
        
        # ★ 修复：拦截从动变量，避免静默失效
        if var is None or getattr(var, "expr", ""):
            return 
            
        store.set(self.var_name, val)

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
        track = cls(params.get("var_name", ""), frames)
        track.enabled = params.get("enabled", True)
        track.muted = params.get("muted", False)
        return track


@register_track("glider")
class GliderTrack(AnimationTrack):
    """路径轨道：驱动 PointOnObject 的参数 t。

    绑定 PointOnObject 对象，随时间改变 t ∈ [0,1]。
    """

    def __init__(self, obj_id: int, keyframes: List[Keyframe] | None = None):
        super().__init__(target=None)
        self.obj_id = obj_id
        self.keyframes = keyframes or []

    def _find_target(self) -> Any:
        """从文档中查找目标对象。"""
        from geo.points import PointOnObject
        from core.document import Document
        # 通过全局单例获取文档（AnimationController 会传入）
        # 这里用延迟查找
        return None  # 由 controller 注入 target

    def evaluate(self, time: float) -> None:
        if self.muted or not self.enabled:
            return
        if self.target is None:
            return
        val = evaluate_keyframes(self.keyframes, time)
        if val is None:
            return
        # 夹到 [0,1]
        t = max(0.0, min(1.0, val))
        if hasattr(self.target, "t"):
            self.target.t = t

    def duration(self) -> float:
        if not self.keyframes:
            return 0.0
        return max(f.time for f in self.keyframes)

    def label(self) -> str:
        return f"路径: obj#{self.obj_id}"

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
        track = cls(params.get("obj_id", 0), frames)
        track.enabled = params.get("enabled", True)
        track.muted = params.get("muted", False)
        return track


@register_track("property")
class PropertyTrack(AnimationTrack):
    """属性轨道：驱动对象的数值属性（如 TextObject.size、MediaObject.rotation）。

    绑定对象 + 属性名，随时间改变属性值。
    """
    ALLOWED_ATTRS = {
        "size", "rotation", "width", "height", "opacity", 
        "color", "text_color", "t"
    }
    
    def __init__(self, obj_id: int, attr_name: str,
                 keyframes: List[Keyframe] | None = None):
        super().__init__(target=None)
        self.obj_id = obj_id
        self.attr_name = attr_name
        self.keyframes = keyframes or []

    def evaluate(self, time: float) -> None:
        if self.muted or not self.enabled: return
        if self.target is None: return
        
        # 校验白名单
        if self.attr_name not in self.ALLOWED_ATTRS:
            return
            
        val = evaluate_keyframes(self.keyframes, time)
        if val is None: return
        
        if hasattr(self.target, self.attr_name):
            setattr(self.target, self.attr_name, val)

    def duration(self) -> float:
        if not self.keyframes:
            return 0.0
        return max(f.time for f in self.keyframes)

    def label(self) -> str:
        return f"属性: {self.attr_name} (obj#{self.obj_id})"

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
        track = cls(
            params.get("obj_id", 0),
            params.get("attr_name", ""),
            frames,
        )
        track.enabled = params.get("enabled", True)
        track.muted = params.get("muted", False)
        return track