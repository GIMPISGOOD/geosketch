"""动画轨道基类与注册表。"""
from __future__ import annotations
from typing import Any, Callable, Dict, Type


class AnimationTrack:
    """动画轨道基类。

    子类必须实现：
        evaluate(time: float) -> None   在给定时间更新目标
        dump() -> dict                  序列化
        build(cls, doc, params) -> track  反序列化

    可选实现：
        duration() -> float             轨道总时长（秒）
        label() -> str                  显示名称
    """

    type_name: str = ""

    def __init__(self, target: Any = None):
        self.target = target
        self.enabled: bool = True
        self.muted: bool = False

    def evaluate(self, time: float) -> None:
        raise NotImplementedError

    def duration(self) -> float:
        return 1.0

    def label(self) -> str:
        return f"{self.type_name}"

    # ── 序列化接口 ──
    def dump(self) -> dict:
        raise NotImplementedError

    @classmethod
    def build(cls, doc: Any, params: dict) -> "AnimationTrack":
        raise NotImplementedError


# ─────────────── 注册表 ───────────────
TRACK_REGISTRY: Dict[str, Type[AnimationTrack]] = {}


def register_track(type_name: str):
    """装饰器：注册轨道类型。"""
    def deco(cls: Type[AnimationTrack]) -> Type[AnimationTrack]:
        cls.type_name = type_name
        TRACK_REGISTRY[type_name] = cls
        return cls
    return deco