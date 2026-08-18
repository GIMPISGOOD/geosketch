"""时间轴面板：QDockWidget，包含播放控制、时间滑杆、轨道列表、录制。"""
from __future__ import annotations
from typing import Any
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QSlider, QListWidget, QListWidgetItem,
    QCheckBox, QComboBox, QDoubleSpinBox, QMenu,
)
from PySide6.QtGui import QAction
from ui import theme


class TimelineDock(QDockWidget):
    """动画时间轴面板（增强版）。"""

    def __init__(self, controller: Any, canvas: Any, parent=None):
        super().__init__("动画时间轴", parent)
        self.setObjectName("timelineDock")
        self.controller = controller
        self.canvas = canvas
        self._recorder = None
        self._build_ui()
        self._connect_signals()

    def _build_ui(self):
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # 播放控制行
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(6)
        self._play_btn = QPushButton("▶ 播放")
        self._play_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ctrl_row.addWidget(self._play_btn)
        self._stop_btn = QPushButton("■ 停止")
        self._stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        ctrl_row.addWidget(self._stop_btn)
        ctrl_row.addSpacing(20)
        ctrl_row.addWidget(QLabel("速度:"))
        self._speed_spin = QDoubleSpinBox()
        self._speed_spin.setRange(0.1, 10.0)
        self._speed_spin.setValue(1.0)
        self._speed_spin.setSingleStep(0.1)
        ctrl_row.addWidget(self._speed_spin)
        self._loop_chk = QCheckBox("循环")
        self._loop_chk.setChecked(True)
        ctrl_row.addWidget(self._loop_chk)
        ctrl_row.addStretch(1)
        self._time_lbl = QLabel("0.00s")
        self._time_lbl.setFont(theme.LABEL_FONT)
        ctrl_row.addWidget(self._time_lbl)
        layout.addLayout(ctrl_row)

        # 时间滑杆
        self._time_slider = QSlider(Qt.Orientation.Horizontal)
        self._time_slider.setRange(0, 1000)
        self._time_slider.setValue(0)
        layout.addWidget(self._time_slider)

        # 轨道行
        track_row = QHBoxLayout()
        track_row.addWidget(QLabel("轨道列表:"))
        add_btn = QPushButton("＋ 添加轨道")
        add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        track_row.addWidget(add_btn)
        record_btn = QPushButton("● 录制")
        record_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        record_btn.setToolTip("录制变量变化，自动生成关键帧")
        track_row.addWidget(record_btn)
        track_row.addStretch(1)
        layout.addLayout(track_row)

        # 轨道列表
        self._track_list = QListWidget()
        self._track_list.setMaximumHeight(180)
        layout.addWidget(self._track_list)

        self.setWidget(widget)
        self.setMinimumHeight(220)
        self._add_btn = add_btn
        self._record_btn = record_btn

    def _connect_signals(self):
        self._play_btn.clicked.connect(self._on_play)
        self._stop_btn.clicked.connect(self._on_stop)
        self._time_slider.sliderMoved.connect(self._on_seek)
        self._speed_spin.valueChanged.connect(self._on_speed)
        self._loop_chk.toggled.connect(self._on_loop)
        self._add_btn.clicked.connect(self._on_add_track)
        self._record_btn.clicked.connect(self._on_toggle_record)
        self._track_list.itemDoubleClicked.connect(self._on_edit_track)
        self._track_list.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self._track_list.customContextMenuRequested.connect(
            self._on_track_menu)
        self.controller.ticked.connect(self._on_ticked)
        self.controller.started.connect(self._on_started)
        self.controller.stopped.connect(self._on_stopped)

    def _on_play(self):
        if self.controller.is_playing:
            self.controller.pause()
            self._play_btn.setText("▶ 播放")
        else:
            self.controller.play()
            self._play_btn.setText("⏸ 暂停")

    def _on_stop(self):
        self.controller.stop()
        self._play_btn.setText("▶ 播放")
        self._time_slider.setValue(0)
        self._time_lbl.setText("0.00s")

    def _on_seek(self, value: int):
        clip = self.controller.clip
        if clip is None:
            return
        total = clip.total_duration()
        t = value / 1000.0 * total
        self.controller.seek(t)
        self._time_lbl.setText(f"{t:.2f}s")

    def _on_speed(self, value: float):
        clip = self.controller.clip
        if clip:
            clip.speed = value

    def _on_loop(self, checked: bool):
        clip = self.controller.clip
        if clip:
            clip.loop = checked

    def _on_ticked(self, time: float):
        clip = self.controller.clip
        if clip is None:
            return
        total = clip.total_duration()
        if total > 0:
            self._time_slider.setValue(int(time / total * 1000))
            self._time_lbl.setText(f"{time:.2f}s")

    def _on_started(self):
        self._play_btn.setText("⏸ 暂停")

    def _on_stopped(self):
        self._play_btn.setText("▶ 播放")

    def _on_add_track(self):
        from .track_editor import AddTrackDialog
        dlg = AddTrackDialog(self.canvas.doc, self)
        if dlg.exec():
            track = dlg.get_track()
            if track:
                clip = self.controller.clip
                if clip is None:
                    from ..clip import AnimationClip
                    clip = AnimationClip("动画 1")
                    self.controller.set_clip(clip)
                    if not hasattr(self.canvas.doc, "animations"):
                        self.canvas.doc.animations = []
                    if not self.canvas.doc.animations:
                        self.canvas.doc.animations.append(clip)
                clip.add_track(track)
                self._refresh_track_list()

    def _on_toggle_record(self):
        """切换录制状态。"""
        from ..recorder import AnimationRecorder
        from core.variables import get_store

        if self._recorder is None:
            self._recorder = AnimationRecorder(self.canvas.doc)

        if self._recorder.is_recording:
            # 停止录制
            frames = self._recorder.stop_recording()
            self._record_btn.setText("● 录制")
            self._record_btn.setStyleSheet("")
            self._apply_recorded_frames(frames)
        else:
            # 开始录制
            store = get_store()
            var_names = store.names()
            if not var_names:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    self, "录制", "当前没有变量，无法录制。")
                return
            self._recorder.start_recording(var_names=var_names)
            self._record_btn.setText("■ 停止录制")
            self._record_btn.setStyleSheet(
                "color: #e03131; font-weight: bold;")

    def _apply_recorded_frames(self, frames: dict):
        """把录制的关键帧应用到当前 clip。"""
        from ..tracks import VariableTrack
        clip = self.controller.clip
        if clip is None:
            from ..clip import AnimationClip
            clip = AnimationClip("动画 1")
            self.controller.set_clip(clip)
            if not hasattr(self.canvas.doc, "animations"):
                self.canvas.doc.animations = []
            if not self.canvas.doc.animations:
                self.canvas.doc.animations.append(clip)

        for key, kfs in frames.items():
            if not kfs:
                continue
            if key.startswith("obj:"):
                continue
            track = VariableTrack(key, kfs)
            clip.add_track(track)
        self._refresh_track_list()

    def _on_edit_track(self, item: QListWidgetItem):
        idx = self._track_list.row(item)
        clip = self.controller.clip
        if clip is None or idx >= len(clip.tracks):
            return
        from .track_editor import EditTrackDialog
        track = clip.tracks[idx]
        dlg = EditTrackDialog(track, self)
        if dlg.exec():
            self._refresh_track_list()

    def _on_track_menu(self, pos):
        item = self._track_list.itemAt(pos)
        if item is None:
            return
        idx = self._track_list.row(item)
        clip = self.controller.clip
        if clip is None or idx >= len(clip.tracks):
            return
        track = clip.tracks[idx]
        menu = QMenu(self)
        mute_act = QAction(
            "静音" if not track.muted else "取消静音", self)
        mute_act.triggered.connect(lambda: self._toggle_mute(track))
        menu.addAction(mute_act)
        dup_act = QAction("复制轨道", self)
        dup_act.triggered.connect(lambda: self._duplicate_track(track))
        menu.addAction(dup_act)
        delete_act = QAction("删除轨道", self)
        delete_act.triggered.connect(lambda: self._delete_track(track))
        menu.addAction(delete_act)
        menu.exec(self._track_list.mapToGlobal(pos))

    def _toggle_mute(self, track):
        track.muted = not track.muted
        self._refresh_track_list()

    def _duplicate_track(self, track):
        clip = self.controller.clip
        if clip:
            clip.duplicate_track(track)
            self._refresh_track_list()

    def _delete_track(self, track):
        clip = self.controller.clip
        if clip:
            clip.remove_track(track)
            self._refresh_track_list()

    def _refresh_track_list(self):
        self._track_list.clear()
        clip = self.controller.clip
        if clip is None:
            return
        for track in clip.tracks:
            label = track.label()
            if track.muted:
                label = f"[静音] {label}"
            item = QListWidgetItem(label)
            self._track_list.addItem(item)