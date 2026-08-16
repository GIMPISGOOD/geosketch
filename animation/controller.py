"""动画控制器：QTimer 驱动，主线程安全。"""
from __future__ import annotations
from typing import Any, Optional

from PySide6.QtCore import QTimer, Signal, QObject, QElapsedTimer

from .clip import AnimationClip
from .tracks import VariableTrack, GliderTrack, PropertyTrack


class AnimationController(QObject):
    """动画播放控制器。

    - 使用 QTimer 以 60fps 触发
    - 每帧遍历所有轨道，调用 evaluate(time)
    - 播放结束后 emit finished 信号
    """

    started = Signal()
    stopped = Signal()
    ticked = Signal(float)   # 当前时间（秒）
    finished = Signal()

    def __init__(self, doc, canvas):
        super().__init__()
        self.doc = doc
        self.canvas = canvas
        self.clip = None
        self._current_time = 0.0
        self._playing = False
        
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        
        # ★ 修复：使用高精度计时器计算真实 dt
        self._elapsed_timer = QElapsedTimer()

    # ─────────────── 对外接口 ───────────────
    def set_clip(self, clip: AnimationClip) -> None:
        self.clip = clip
        self._current_time = 0.0

    def play(self) -> None:
        if self.clip is None:
            self.clip = self._get_clip_from_doc()
        if self.clip is None:
            return
        self._current_time = 0.0
        self._playing = True
        self._elapsed_timer.start()
        self._last_elapsed = 0
        self._timer.start()
        self.started.emit()

    def pause(self) -> None:
        if self._playing:
            self._timer.stop()
            self._playing = False
            self.stopped.emit()

    def stop(self) -> None:
        self._timer.stop()
        self._playing = False
        self._current_time = 0.0
        self.stopped.emit()

    def seek(self, time: float) -> None:
        """跳转到指定时间并求值。"""
        self._current_time = max(0.0, time)
        if self.clip:
            self._evaluate(self._current_time)

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def current_time(self) -> float:
        return self._current_time

    # ─────────────── 内部 ───────────────
    def _get_clip_from_doc(self) -> Optional[AnimationClip]:
        """从文档中获取当前动画片段。"""
        clips = getattr(self.doc, "animations", [])
        if clips:
            return clips[0]
        return None

    def _tick(self):
        if not self._playing or self.clip is None: return

        # ★ 修复：计算真实经过的时间（秒），而不是固定 0.016
        real_dt = self._elapsed_timer.elapsed() / 1000.0
        self._elapsed_timer.restart() # 重置计时器
        
        self._current_time += real_dt * self.clip.speed

        total = self.clip.total_duration()
        if self._current_time >= total:
            if self.clip.loop:
                self._current_time = 0.0
            else:
                self.stop()
                self.finished.emit()
                return

        self._evaluate(self._current_time)
        self.ticked.emit(self._current_time)

    def _evaluate(self, time: float) -> None:
        """求值所有轨道。"""
        if self.clip is None:
            return

        # 绑定目标对象（延迟查找）
        self._bind_targets()

        for track in self.clip.tracks:
            if not track.enabled or track.muted:
                continue
            try:
                track.evaluate(time)
            except Exception:
                pass

        # 触发文档重算
        self.doc.refresh_variables()

    def _bind_targets(self) -> None:
        """为 GliderTrack 和 PropertyTrack 绑定目标对象。"""
        if self.clip is None:
            return
        obj_map = {o.id: o for o in self.doc.objects}
        for track in self.clip.tracks:
            if isinstance(track, (GliderTrack, PropertyTrack)):
                if track.target is None:
                    track.target = obj_map.get(track.obj_id)