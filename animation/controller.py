"""动画控制器：QTimer 驱动，主线程安全。
★ 重构：轨迹录制与播放解耦，支持独立开关。
★ 新增：轨迹配置序列化。
"""
from __future__ import annotations
from typing import Any, Optional, List
from PySide6.QtCore import QTimer, Signal, QObject, QElapsedTimer
from PySide6.QtGui import QColor
from .clip import AnimationClip
from .tracks import VariableTrack, GliderTrack, PropertyTrack


class Trail:
    """单条轨迹：记录一个点在动画播放期间的运动路径。"""

    def __init__(self, point, color: str = "#e03131", max_points: int = 3000):
        self.point = point
        self.color = QColor(color)
        self.max_points = max_points
        self.points: List[tuple] = []

    def record(self):
        if not getattr(self.point, "exists", True):
            return
        x, y = self.point.x, self.point.y
        if self.points and abs(self.points[-1][0] - x) < 1e-9 \
                and abs(self.points[-1][1] - y) < 1e-9:
            return
        self.points.append((x, y))
        if len(self.points) > self.max_points:
            self.points.pop(0)

    def clear(self):
        self.points.clear()

    def simplified(self, tolerance: float = 2.0) -> List[tuple]:
        """★ 性能优化：Douglas-Peucker 降采样，减少绘制点数。"""
        pts = self.points
        if len(pts) <= 2:
            return pts
        return _douglas_peucker(pts, tolerance)


def _douglas_peucker(pts: List[tuple], eps: float) -> List[tuple]:
    """Douglas-Peucker 折线简化。"""
    if len(pts) <= 2:
        return pts
    dmax = 0.0
    idx = 0
    x1, y1 = pts[0]
    x2, y2 = pts[-1]
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5
    if length < 1e-12:
        return [pts[0], pts[-1]]
    for i in range(1, len(pts) - 1):
        px, py = pts[i]
        d = abs(dx * (y1 - py) - dy * (x1 - px)) / length
        if d > dmax:
            dmax = d
            idx = i
    if dmax > eps:
        left = _douglas_peucker(pts[:idx + 1], eps)
        right = _douglas_peucker(pts[idx:], eps)
        return left[:-1] + right
    return [pts[0], pts[-1]]


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
        self.trails: List[Trail] = []
        self._trail_picking = False
        # ★ 修复：轨迹录制独立开关，不再与播放强耦合
        self._trail_recording = False

    # ── 轨迹管理 ──────────────────────────────────────────

    @property
    def is_trail_recording(self) -> bool:
        return self._trail_recording

    def toggle_trail_recording(self):
        """切换轨迹录制模式。"""
        self._trail_recording = not self._trail_recording
        if self._trail_recording:
            for t in self.trails:
                t.clear()
        return self._trail_recording

    def add_trail(self, point, color: str = "#e03131"):
        for t in self.trails:
            if t.point is point:
                return
        palette = ["#e03131", "#1971c2", "#2f9e44",
                   "#f08c00", "#9c36b5", "#0c8599"]
        if color == "auto":
            color = palette[len(self.trails) % len(palette)]
        self.trails.append(Trail(point, color))

    def remove_trail(self, point):
        self.trails = [t for t in self.trails if t.point is not point]

    def clear_trails(self):
        for t in self.trails:
            t.clear()
        self.trails.clear()

    def start_trail_picking(self):
        self._trail_picking = True
        if hasattr(self.canvas, "cursor_info"):
            self.canvas.cursor_info.emit("🎯 点击一个点以添加轨迹…")

    @property
    def is_trail_picking(self):
        return self._trail_picking

    def cancel_trail_picking(self):
        self._trail_picking = False

    def try_pick_trail(self, hit) -> bool:
        if not self._trail_picking:
            return False
        from geo.points import AbstractPoint
        if isinstance(hit, AbstractPoint):
            self.add_trail(hit, color="auto")
            self._trail_picking = False
            if hasattr(self.canvas, "cursor_info"):
                name = getattr(hit, "name", "") or \
                       getattr(hit, "_auto_label", "") or f"P{hit.id}"
                self.canvas.cursor_info.emit(f"✔ 已为 {name} 添加轨迹")
            self.canvas.update()
            return True
        return False

    # ── 序列化 ────────────────────────────────────────────

    def dump_trail_config(self) -> list:
        """★ 序列化轨迹配置（哪些点有轨迹），不保存轨迹点数据。"""
        result = []
        for t in self.trails:
            pid = getattr(t.point, "id", None)
            if pid is not None:
                result.append({
                    "point_id": pid,
                    "color": t.color.name(),
                })
        return result

    def load_trail_config(self, config: list):
        """★ 从序列化数据恢复轨迹配置。"""
        self.clear_trails()
        obj_map = {o.id: o for o in self.doc.objects}
        for item in config:
            pid = item.get("point_id")
            color = item.get("color", "#e03131")
            obj = obj_map.get(pid)
            if obj is not None:
                self.add_trail(obj, color)

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
        # ★ 修复：仅在录制模式下才清空轨迹
        if self._trail_recording:
            for t in self.trails:
                t.clear()
        self.started.emit()

    def pause(self) -> None:
        if self._playing:
            self._timer.stop()
            self._playing = False
            self.stopped.emit()
            
    def reset_for_new_document(self):
        """新建文档时彻底重置控制器状态。"""
        self.stop()
        self.clip = None
        self._current_time = 0.0
        self._bound_version = -1
        self.clear_trails()
        self._trail_picking = False
        self._trail_recording = False
        
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
        # ★ 修复：仅在录制模式下记录轨迹
        if self._trail_recording and self.trails:
            for trail in self.trails:
                trail.record()
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