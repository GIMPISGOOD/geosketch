"""轨道编辑对话框：添加 / 编辑轨道的关键帧。"""
from __future__ import annotations
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QComboBox,
    QPushButton, QDialogButtonBox, QListWidget, QListWidgetItem,
    QMessageBox,
)

from ..base import AnimationTrack, TRACK_REGISTRY
from ..tracks import VariableTrack, GliderTrack, PropertyTrack
from ..keyframe import Keyframe, INTERPOLATORS


class KeyframeEditor(QDialog):
    """关键帧编辑对话框。"""

    def __init__(self, keyframes: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑关键帧")
        self.setMinimumWidth(400)
        self._keyframes = keyframes
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        self._list = QListWidget()
        layout.addWidget(self._list, 1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("＋ 添加")
        edit_btn = QPushButton("✎ 编辑")
        del_btn = QPushButton("× 删除")
        add_btn.clicked.connect(self._add)
        edit_btn.clicked.connect(self._edit)
        del_btn.clicked.connect(self._delete)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh(self):
        self._list.clear()
        for kf in self._keyframes:
            self._list.addItem(
                f"t={kf.time:.2f}s  v={kf.value:.3f}  [{kf.interpolator}]"
            )

    def _add(self):
        dlg = _KeyframeDialog(self)
        if dlg.exec():
            kf = dlg.get_keyframe()
            self._keyframes.append(kf)
            self._keyframes.sort(key=lambda f: f.time)
            self._refresh()

    def _edit(self):
        item = self._list.currentItem()
        if item is None:
            return
        idx = self._list.row(item)
        kf = self._keyframes[idx]
        dlg = _KeyframeDialog(self, kf)
        if dlg.exec():
            new_kf = dlg.get_keyframe()
            self._keyframes[idx] = new_kf
            self._keyframes.sort(key=lambda f: f.time)
            self._refresh()

    def _delete(self):
        item = self._list.currentItem()
        if item is None:
            return
        idx = self._list.row(item)
        self._keyframes.pop(idx)
        self._refresh()


class _KeyframeDialog(QDialog):
    """单个关键帧编辑。"""

    def __init__(self, parent=None, keyframe: Optional[Keyframe] = None):
        super().__init__(parent)
        self.setWindowTitle("关键帧")
        self.setMinimumWidth(300)
        layout = QFormLayout(self)

        self._time = QDoubleSpinBox()
        self._time.setRange(0.0, 100.0)
        self._time.setDecimals(3)
        self._time.setSingleStep(0.1)
        layout.addRow("时间 (秒):", self._time)

        self._value = QDoubleSpinBox()
        self._value.setRange(-1e6, 1e6)
        self._value.setDecimals(4)
        layout.addRow("值:", self._value)

        self._interp = QComboBox()
        self._interp.addItems(list(INTERPOLATORS.keys()))
        layout.addRow("插值:", self._interp)

        if keyframe:
            self._time.setValue(keyframe.time)
            self._value.setValue(keyframe.value)
            self._interp.setCurrentText(keyframe.interpolator)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_keyframe(self) -> Keyframe:
        return Keyframe(
            self._time.value(),
            self._value.value(),
            self._interp.currentText(),
        )


class AddTrackDialog(QDialog):
    """添加轨道对话框。"""

    def __init__(self, doc: Any, parent=None):
        super().__init__(parent)
        self.setWindowTitle("添加轨道")
        self.setMinimumWidth(400)
        self._doc = doc
        self._track: Optional[AnimationTrack] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self._type_combo = QComboBox()
        self._type_combo.addItems([
            "变量轨道 (variable)",
            "路径轨道 (glider)",
            "属性轨道 (property)",
        ])
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("轨道类型:", self._type_combo)

        self._target_combo = QComboBox()
        form.addRow("目标:", self._target_combo)

        self._attr_edit = QLineEdit()
        self._attr_edit.setPlaceholderText("属性名（仅属性轨道）")
        self._attr_edit.setVisible(False)
        form.addRow("属性名:", self._attr_edit)

        layout.addLayout(form)

        self._kf_btn = QPushButton("编辑关键帧…")
        self._kf_btn.clicked.connect(self._edit_keyframes)
        layout.addWidget(self._kf_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._keyframes: list = []
        self._refresh_targets()

    def _on_type_changed(self, index: int):
        self._attr_edit.setVisible(index == 2)
        self._refresh_targets()

    def _refresh_targets(self):
        self._target_combo.clear()
        idx = self._type_combo.currentIndex()

        if idx == 0:  # 变量轨道
            from core.variables import get_store
            store = get_store()
            for name in store.names():
                self._target_combo.addItem(name, name)
        elif idx == 1:  # 路径轨道
            from geo.points import PointOnObject
            for obj in self._doc.objects:
                if isinstance(obj, PointOnObject):
                    self._target_combo.addItem(
                        f"PointOnObject #{obj.id}", obj.id
                    )
        elif idx == 2:  # 属性轨道
            for obj in self._doc.objects:
                tn = type(obj).__name__
                self._target_combo.addItem(f"{tn} #{obj.id}", obj.id)

    def _edit_keyframes(self):
        dlg = KeyframeEditor(self._keyframes, self)
        dlg.exec()

    def _accept(self):
        idx = self._type_combo.currentIndex()
        target = self._target_combo.currentData()

        if idx == 0:  # 变量轨道
            if target is None:
                QMessageBox.warning(self, "提示", "请选择变量。")
                return
            self._track = VariableTrack(str(target), self._keyframes)
        elif idx == 1:  # 路径轨道
            if target is None:
                QMessageBox.warning(self, "提示", "请选择路径对象。")
                return
            self._track = GliderTrack(int(target), self._keyframes)
        elif idx == 2:  # 属性轨道
            if target is None:
                QMessageBox.warning(self, "提示", "请选择对象。")
                return
            attr = self._attr_edit.text().strip()
            if not attr:
                QMessageBox.warning(self, "提示", "请输入属性名。")
                return
            self._track = PropertyTrack(int(target), attr, self._keyframes)

        self.accept()

    def get_track(self) -> Optional[AnimationTrack]:
        return self._track


class EditTrackDialog(QDialog):
    """编辑已有轨道。"""

    def __init__(self, track: AnimationTrack, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"编辑轨道: {track.label()}")
        self.setMinimumWidth(400)
        self._track = track
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel(f"轨道: {self._track.label()}"))

        self._kf_btn = QPushButton("编辑关键帧…")
        self._kf_btn.clicked.connect(self._edit_keyframes)
        layout.addWidget(self._kf_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _edit_keyframes(self):
        if hasattr(self._track, "keyframes"):
            dlg = KeyframeEditor(self._track.keyframes, self)
            dlg.exec()