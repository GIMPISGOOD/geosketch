"""动画片段：轨道容器 + 全局设置 + 预设模板。"""
from __future__ import annotations
from typing import List, Optional
from .base import AnimationTrack


class AnimationClip:
    """动画片段：包含一组轨道和全局设置。"""

    def __init__(self, name: str = "动画 1"):
        self.name = name
        self.tracks: List[AnimationTrack] = []
        self.loop: bool = True
        self.speed: float = 1.0
        self.duration: float = 5.0

    def total_duration(self) -> float:
        """取所有轨道的最大时长。无有效时长时兜底返回 self.duration。"""
        if not self.tracks:
            return self.duration
        d = max(t.duration() for t in self.tracks)
        return d if d > 1e-6 else self.duration

    def add_track(self, track: AnimationTrack) -> None:
        self.tracks.append(track)

    def remove_track(self, track: AnimationTrack) -> None:
        if track in self.tracks:
            self.tracks.remove(track)

    def duplicate_track(self, track: AnimationTrack) -> Optional[AnimationTrack]:
        """复制一条轨道（深拷贝关键帧）。"""
        if track not in self.tracks:
            return None
        import copy
        new_track = copy.deepcopy(track)
        self.tracks.append(new_track)
        return new_track

    def dump(self) -> dict:
        return {
            "name": self.name,
            "loop": self.loop,
            "speed": self.speed,
            "duration": self.duration,
            "tracks": [t.dump() for t in self.tracks],
        }

    @classmethod
    def build(cls, doc, params: dict) -> "AnimationClip":
        from .base import TRACK_REGISTRY
        clip = cls(params.get("name", "动画 1"))
        clip.loop = params.get("loop", True)
        clip.speed = params.get("speed", 1.0)
        clip.duration = params.get("duration", 5.0)
        for td in params.get("tracks", []):
            ttype = td.get("type", "")
            cls_track = TRACK_REGISTRY.get(ttype)
            if cls_track:
                try:
                    track = cls_track.build(doc, td)
                    clip.add_track(track)
                except Exception:
                    pass
        return clip


# ★ 动画预设模板
PRESETS = {
    "匀速往返": {
        "description": "变量从 0 到 1 再回到 0，线性插值",
        "keyframes": [
            {"time": 0.0, "value": 0.0, "interpolator": "linear"},
            {"time": 2.5, "value": 1.0, "interpolator": "linear"},
            {"time": 5.0, "value": 0.0, "interpolator": "linear"},
        ],
    },
    "缓入缓出": {
        "description": "变量从 0 到 1，缓入缓出插值",
        "keyframes": [
            {"time": 0.0, "value": 0.0, "interpolator": "ease_in_out"},
            {"time": 3.0, "value": 1.0, "interpolator": "ease_in_out"},
        ],
    },
    "弹跳": {
        "description": "变量从 0 到 1，弹跳效果",
        "keyframes": [
            {"time": 0.0, "value": 0.0, "interpolator": "bounce"},
            {"time": 2.0, "value": 1.0, "interpolator": "bounce"},
        ],
    },
    "弹性过冲": {
        "description": "变量从 0 到 1，弹性过冲后回弹",
        "keyframes": [
            {"time": 0.0, "value": 0.0, "interpolator": "elastic"},
            {"time": 2.0, "value": 1.0, "interpolator": "elastic"},
        ],
    },
    "阶梯跳变": {
        "description": "变量在 0/0.5/1 之间阶梯跳变",
        "keyframes": [
            {"time": 0.0, "value": 0.0, "interpolator": "step"},
            {"time": 1.5, "value": 0.5, "interpolator": "step"},
            {"time": 3.0, "value": 1.0, "interpolator": "step"},
        ],
    },
    "正弦往返": {
        "description": "用多关键帧近似正弦曲线往返",
        "keyframes": [
            {"time": 0.0, "value": 0.0, "interpolator": "ease_in_out"},
            {"time": 1.25, "value": 0.5, "interpolator": "ease_in_out"},
            {"time": 2.5, "value": 1.0, "interpolator": "ease_in_out"},
            {"time": 3.75, "value": 0.5, "interpolator": "ease_in_out"},
            {"time": 5.0, "value": 0.0, "interpolator": "ease_in_out"},
        ],
    },
}


def apply_preset(preset_name: str) -> list:
    """根据预设名称返回关键帧列表。"""
    preset = PRESETS.get(preset_name)
    if preset is None:
        return []
    from .keyframe import Keyframe
    return [Keyframe.from_dict(d) for d in preset["keyframes"]]