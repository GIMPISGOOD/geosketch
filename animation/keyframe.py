"""关键帧与插值器。"""
from __future__ import annotations
import math
from typing import List, Tuple, Optional


# ─────────────── 插值器 ───────────────
class Interpolator:
    """插值器基类。"""

    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        """t ∈ [0,1]，返回插值结果。"""
        raise NotImplementedError


class LinearInterpolator(Interpolator):
    """线性插值。"""
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        return v0 + (v1 - v0) * t


class EaseInOutInterpolator(Interpolator):
    """缓入缓出（正弦）。"""
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        # smoothstep
        s = t * t * (3.0 - 2.0 * t)
        return v0 + (v1 - v0) * s


class BezierInterpolator(Interpolator):
    """三次贝塞尔插值（简化：固定控制点 (0.42,0,0.58,1)）。"""
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        # cubic-bezier(0.42, 0, 0.58, 1)
        u = 1.0 - t
        s = 3 * u * u * t * 0.42 + 3 * u * t * t * 0.58 + t * t * t
        return v0 + (v1 - v0) * s


class StepInterpolator(Interpolator):
    """阶梯插值（保持前一帧值）。"""
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        return v0


# 插值器注册表
INTERPOLATORS = {
    "linear": LinearInterpolator,
    "ease_in_out": EaseInOutInterpolator,
    "bezier": BezierInterpolator,
    "step": StepInterpolator,
}

DEFAULT_INTERPOLATOR = "linear"


# ─────────────── 关键帧 ───────────────
class Keyframe:
    """单个关键帧：(time, value, interpolator)。"""

    __slots__ = ("time", "value", "interpolator")

    def __init__(self, time: float, value: float,
                 interpolator: str = DEFAULT_INTERPOLATOR):
        self.time = float(time)
        self.value = float(value)
        self.interpolator = interpolator

    def dump(self) -> dict:
        return {
            "time": self.time,
            "value": self.value,
            "interpolator": self.interpolator,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Keyframe":
        return cls(
            d.get("time", 0.0),
            d.get("value", 0.0),
            d.get("interpolator", DEFAULT_INTERPOLATOR),
        )


# ─────────────── 关键帧序列求值 ───────────────
def evaluate_keyframes(frames: List[Keyframe], time: float) -> Optional[float]:
    """在给定时间求值关键帧序列。返回 None 表示无关键帧。
    ★ 调用方必须保证 frames 已按 time 升序排列。
    """
    if not frames:
        return None
    if time <= frames[0].time:
        return frames[0].value
    if time >= frames[-1].time:
        return frames[-1].value
    for i in range(len(frames) - 1):
        f0 = frames[i]
        f1 = frames[i + 1]
        if f0.time <= time <= f1.time:
            dt = f1.time - f0.time
            if dt < 1e-12:
                return f1.value
            t = (time - f0.time) / dt
            t = max(0.0, min(1.0, t))
            interp_cls = INTERPOLATORS.get(f0.interpolator, LinearInterpolator)
            return interp_cls.evaluate(t, f0.value, f1.value)
    return frames[-1].value