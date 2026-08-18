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
    """三次贝塞尔插值（CSS cubic-bezier(0.42, 0, 0.58, 1)）。
    ★ 修复：原实现直接计算 x(t) 作为进度值，数学上是错误的。
    正确做法：给定时间比例 t，用牛顿法求解 x(u)=t 得到参数 u，再返回 y(u)。
    """
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        if t <= 0.0:
            return v0
        if t >= 1.0:
            return v1
        # 控制点：P0=(0,0), P1=(0.42,0), P2=(0.58,1), P3=(1,1)
        # x(u) = 3(1-u)²u·0.42 + 3(1-u)u²·0.58 + u³
        # y(u) = 3(1-u)u² + u³
        # 牛顿法求解 x(u) = t
        u = t  # 初始猜测
        for _ in range(8):
            uu = 1.0 - u
            x = 3.0 * uu * uu * u * 0.42 + 3.0 * uu * u * u * 0.58 + u * u * u
            # x'(u) = 3(1-u)²(P1x-P0x) + 6(1-u)u(P2x-P1x) + 3u²(P3x-P2x)
            #       = 1.26(1-u)² + 0.96(1-u)u + 1.26u²
            dx = 1.26 * uu * uu + 0.96 * uu * u + 1.26 * u * u
            if abs(dx) < 1e-12:
                break
            u -= (x - t) / dx
            u = max(0.0, min(1.0, u))
        uu = 1.0 - u
        y = 3.0 * uu * u * u + u * u * u
        return v0 + (v1 - v0) * y


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