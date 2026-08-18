"""关键帧与插值器。"""
from __future__ import annotations
import math
from typing import List, Tuple, Optional


class Interpolator:
    """插值器基类。"""
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        raise NotImplementedError


class LinearInterpolator(Interpolator):
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        return v0 + (v1 - v0) * t


class EaseInOutInterpolator(Interpolator):
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        s = t * t * (3.0 - 2.0 * t)
        return v0 + (v1 - v0) * s


class BezierInterpolator(Interpolator):
    """三次贝塞尔插值（CSS cubic-bezier(0.42,0,0.58,1)）。
    使用牛顿法求解 x(u)=t，再计算 y(u)。
    """
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        if t <= 0.0:
            return v0
        if t >= 1.0:
            return v1
        u = t
        for _ in range(8):
            uu = 1.0 - u
            x = 3.0 * uu * uu * u * 0.42 + 3.0 * uu * u * u * 0.58 + u * u * u
            dx = 1.26 * uu * uu + 0.96 * uu * u + 1.26 * u * u
            if abs(dx) < 1e-12:
                break
            u -= (x - t) / dx
            u = max(0.0, min(1.0, u))
        uu = 1.0 - u
        y = 3.0 * uu * u * u + u * u * u
        return v0 + (v1 - v0) * y


class StepInterpolator(Interpolator):
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        return v0


class BounceInterpolator(Interpolator):
    """弹跳插值：模拟小球落地弹跳效果。"""
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        if t < 1.0 / 2.75:
            s = 7.5625 * t * t
        elif t < 2.0 / 2.75:
            t -= 1.5 / 2.75
            s = 7.5625 * t * t + 0.75
        elif t < 2.5 / 2.75:
            t -= 2.25 / 2.75
            s = 7.5625 * t * t + 0.9375
        else:
            t -= 2.625 / 2.75
            s = 7.5625 * t * t + 0.984375
        return v0 + (v1 - v0) * s


class ElasticInterpolator(Interpolator):
    """弹性插值：过冲后回弹。"""
    @staticmethod
    def evaluate(t: float, v0: float, v1: float) -> float:
        if t <= 0.0:
            return v0
        if t >= 1.0:
            return v1
        s = -(2.0 ** (10.0 * (t - 1.0))) * math.sin(
            (t - 1.0 - 0.075) * (2.0 * math.pi) / 0.3
        )
        return v0 + (v1 - v0) * (1.0 + s)


INTERPOLATORS = {
    "linear": LinearInterpolator,
    "ease_in_out": EaseInOutInterpolator,
    "bezier": BezierInterpolator,
    "step": StepInterpolator,
    "bounce": BounceInterpolator,
    "elastic": ElasticInterpolator,
}

DEFAULT_INTERPOLATOR = "linear"

# ★ 插值器中文名映射
INTERPOLATOR_NAMES_CN = {
    "linear": "线性",
    "ease_in_out": "缓入缓出",
    "bezier": "贝塞尔",
    "step": "阶梯",
    "bounce": "弹跳",
    "elastic": "弹性",
}


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

    def clone(self) -> "Keyframe":
        return Keyframe(self.time, self.value, self.interpolator)


def evaluate_keyframes(frames: List[Keyframe], time: float) -> Optional[float]:
    """在给定时间求值关键帧序列。
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


# ★ 关键帧批量操作工具函数
def offset_keyframes(frames: List[Keyframe], dt: float) -> List[Keyframe]:
    """整体平移关键帧时间。"""
    result = [Keyframe(f.time + dt, f.value, f.interpolator) for f in frames]
    result.sort(key=lambda f: f.time)
    return result


def scale_keyframes(frames: List[Keyframe], factor: float) -> List[Keyframe]:
    """缩放关键帧时间（以第一帧为锚点）。"""
    if not frames:
        return []
    t0 = frames[0].time
    result = [
        Keyframe(t0 + (f.time - t0) * factor, f.value, f.interpolator)
        for f in frames
    ]
    result.sort(key=lambda f: f.time)
    return result


def reverse_keyframes(frames: List[Keyframe]) -> List[Keyframe]:
    """反转关键帧顺序（时间镜像）。"""
    if not frames:
        return []
    t0 = frames[0].time
    t1 = frames[-1].time
    span = t1 - t0
    result = [
        Keyframe(t0 + (t1 - f.time), f.value, f.interpolator)
        for f in reversed(frames)
    ]
    result.sort(key=lambda f: f.time)
    return result


def merge_keyframes(a: List[Keyframe], b: List[Keyframe]) -> List[Keyframe]:
    """合并两组关键帧并按时间排序。"""
    result = [f.clone() for f in a] + [f.clone() for f in b]
    result.sort(key=lambda f: f.time)
    return result