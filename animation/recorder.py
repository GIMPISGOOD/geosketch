"""动画录制器：录制变量/对象变化，自动生成关键帧。"""
from __future__ import annotations
from typing import Any, Dict, List, Optional
from PySide6.QtCore import QObject, Signal, QTimer, QElapsedTimer
from .keyframe import Keyframe, DEFAULT_INTERPOLATOR


class AnimationRecorder(QObject):
    """录制动画：监听变量变化，自动生成关键帧。

    用法：
        recorder = AnimationRecorder(doc)
        recorder.start_recording(["a", "b"])  # 录制变量 a, b
        # ... 用户拖动滑杆 ...
        recorder.stop_recording()  # 生成关键帧
    """

    recording_started = Signal()
    recording_stopped = Signal()
    frame_recorded = Signal(float)  # 当前录制时间

    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        self._recording = False
        self._var_names: List[str] = []
        self._obj_trackers: Dict[int, str] = {}  # obj_id -> attr_name
        self._frames: Dict[str, List[Keyframe]] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(50)  # 20fps 采样
        self._timer.timeout.connect(self._sample)
        self._elapsed = QElapsedTimer()
        self._start_time = 0.0
        self._last_values: Dict[str, float] = {}
        self._interpolator = DEFAULT_INTERPOLATOR

    @property
    def is_recording(self) -> bool:
        return self._recording

    @property
    def recorded_frames(self) -> Dict[str, List[Keyframe]]:
        return self._frames

    def start_recording(self, var_names: List[str] = None,
                        obj_trackers: Dict[int, str] = None,
                        interpolator: str = DEFAULT_INTERPOLATOR):
        """开始录制。
        var_names: 要录制的变量名列表
        obj_trackers: {obj_id: attr_name} 要录制的对象属性
        """
        if self._recording:
            return
        self._var_names = var_names or []
        self._obj_trackers = obj_trackers or {}
        self._interpolator = interpolator
        self._frames = {}
        for name in self._var_names:
            self._frames[name] = []
        for obj_id, attr in self._obj_trackers.items():
            self._frames[f"obj:{obj_id}:{attr}"] = []
        self._last_values = {}
        self._recording = True
        self._elapsed.start()
        self._start_time = 0.0
        self._timer.start()
        self.recording_started.emit()

    def stop_recording(self) -> Dict[str, List[Keyframe]]:
        """停止录制，返回 {track_key: [Keyframe, ...]}。"""
        if not self._recording:
            return {}
        self._recording = False
        self._timer.stop()
        self.recording_stopped.emit()
        return self._frames

    def set_interpolator(self, interp: str):
        self._interpolator = interp

    def _sample(self):
        """每 50ms 采样一次当前值。"""
        if not self._recording:
            return
        elapsed = self._elapsed.elapsed() / 1000.0
        changed = False

        # 采样变量
        from core.variables import get_store
        store = get_store()
        for name in self._var_names:
            var = store.get_var(name)
            if var is None:
                continue
            val = var.value
            key = name
            last = self._last_values.get(key)
            if last is None or abs(val - last) > 1e-9:
                self._frames[key].append(
                    Keyframe(elapsed, val, self._interpolator))
                self._last_values[key] = val
                changed = True

        # 采样对象属性
        obj_map = {o.id: o for o in self.doc.objects}
        for obj_id, attr in self._obj_trackers.items():
            obj = obj_map.get(obj_id)
            if obj is None or not hasattr(obj, attr):
                continue
            val = getattr(obj, attr)
            if not isinstance(val, (int, float)):
                continue
            val = float(val)
            key = f"obj:{obj_id}:{attr}"
            last = self._last_values.get(key)
            if last is None or abs(val - last) > 1e-9:
                self._frames[key].append(
                    Keyframe(elapsed, val, self._interpolator))
                self._last_values[key] = val
                changed = True

        if changed:
            self.frame_recorded.emit(elapsed)

    def get_duration(self) -> float:
        """获取录制时长。"""
        max_t = 0.0
        for frames in self._frames.values():
            if frames:
                max_t = max(max_t, frames[-1].time)
        return max_t