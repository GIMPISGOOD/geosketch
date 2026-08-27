"""动画控制器：QTimer 驱动，主线程安全。
★ 轨迹功能已移至 plugins/trace_tool.py，本文件不再包含任何轨迹逻辑。
"""
from __future__ import annotations
from typing import Optional

from PySide6.QtCore import QTimer, Signal, QObject, QElapsedTimer

from .clip import AnimationClip
from .tracks import VariableTrack, GliderTrack, PropertyTrack


class AnimationController(QObject):
    """动画播放控制器。"""

    started = Signal()
    stopped = Signal()
    ticked = Signal(float)
    finished = Signal()
    clip_changed = Signal()

    def __init__(self, doc, canvas):
        super().__init__()
        self.doc = doc
        self.canvas = canvas
        self.clip: Optional[AnimationClip] = None
        self._current_time = 0.0
        self._playing = False
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)
        self._elapsed_timer = QElapsedTimer()
        self._bound_version = -1

    # ── 播放控制 ──────────────────────────────────────────

    def set_clip(self, clip: AnimationClip) -> None:
        self.clip = clip
        self._current_time = 0.0
        self._bound_version = -1
        self.clip_changed.emit()

    def play(self) -> None:
        if self.clip is None:
            self.clip = self._get_clip_from_doc()
        if self.clip is None:
            return
        self._current_time = 0.0
        self._playing = True
        self._elapsed_timer.start()
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
        self._current_time = max(0.0, time)
        if self.clip:
            self._evaluate(self._current_time)

    @property
    def is_playing(self) -> bool:
        return self._playing

    @property
    def current_time(self) -> float:
        return self._current_time

    def _get_clip_from_doc(self) -> Optional[AnimationClip]:
        clips = getattr(self.doc, "animations", [])
        if clips:
            return clips[0]
        return None

    def _tick(self):
        if not self._playing or self.clip is None:
            return
        real_dt = self._elapsed_timer.elapsed() / 1000.0
        self._elapsed_timer.restart()
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
        if self.clip is None:
            return
        self._bind_targets()
        moved = []
        for track in self.clip.tracks:
            if not track.enabled or track.muted:
                continue
            try:
                track.evaluate(time)
            except Exception:
                pass
            if isinstance(track, (GliderTrack, PropertyTrack)):
                if track.target is not None:
                    moved.append(track.target)
        if moved:
            self.doc.recompute_silent(moved)
            if hasattr(self.doc, 'constraints') and self.doc.constraints:
                try:
                    self.doc.solve_constraints(
                        trigger_points=moved,
                        pinned_points=moved,
                        quick=True,
                    )
                except Exception:
                    pass
        self.doc.refresh_variables()
        self.canvas.update()

    def _bind_targets(self) -> None:
        if self.clip is None:
            return
        if self._bound_version == self.doc._mutation_count:
            return
        self._bound_version = self.doc._mutation_count
        obj_map = {o.id: o for o in self.doc.objects}
        for track in self.clip.tracks:
            if isinstance(track, (GliderTrack, PropertyTrack)):
                if track.target is None or \
                        track.target not in self.doc.objects:
                    track.target = obj_map.get(
                        getattr(track, "obj_id", None))