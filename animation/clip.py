"""动画片段：轨道容器 + 全局设置。"""
from __future__ import annotations
from typing import List

from .base import AnimationTrack
from .tracks import VariableTrack, GliderTrack, PropertyTrack


class AnimationClip:
    """动画片段：包含一组轨道和全局设置。"""

    def __init__(self, name: str = "动画 1"):
        self.name = name
        self.tracks: List[AnimationTrack] = []
        self.loop: bool = True
        self.speed: float = 1.0       # 播放速度倍率
        self.duration: float = 5.0    # 总时长（秒）

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