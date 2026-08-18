"""轨道编辑对话框：添加 / 编辑轨道的关键帧。"""
from __future__ import annotations
from typing import Any, Optional
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QComboBox,
    QPushButton, QDialogButtonBox, QListWidget, QListWidgetItem,
    QMessageBox, QMenu,
)
from PySide6.QtGui import QAction
from ..base import AnimationTrack, TRACK_REGISTRY
from ..tracks import VariableTrack, GliderTrack, PropertyTrack, TRACK_TYPE_NAMES_CN
from ..keyframe import (
    Keyframe, INTERPOLATORS, INTERPOLATOR_NAMES_CN,
    offset_keyframes, scale_keyframes, reverse_keyframes,
)
from ..clip import PRESETS, apply_preset


class KeyframeEditor(QDialog):
    """关键帧编辑对话框（增强版：批量操作 + 预设）。"""

    def __init__(self, keyframes: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("编辑关键帧")
        self.setMinimumWidth(480)
        self._keyframes = keyframes
        self._build_ui()
        self._refresh()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        self._list = QListWidget()
        self._list.setSelectionMode(
            QListWidget.SelectionMode.ExtendedSelection)
        layout.addWidget(self._list, 1)

        # 第一行：增删改
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

        # 第二行：批量操作
        batch_row = QHBoxLayout()
        offset_btn = QPushButton("平移…")
        scale_btn = QPushButton("缩放…")
        reverse_btn = QPushButton("反转")
        preset_btn = QPushButton("应用预设…")
        offset_btn.clicked.connect(self._offset)
        scale_btn.clicked.connect(self._scale)
        reverse_btn.clicked.connect(self._reverse)
        preset_btn.clicked.connect(self._apply_preset)
        batch_row.addWidget(offset_btn)
        batch_row.addWidget(scale_btn)
        batch_row.addWidget(reverse_btn)
        batch_row.addWidget(preset_btn)
        batch_row.addStretch(1)
        layout.addLayout(batch_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _refresh(self):
        self._list.clear()
        for kf in self._keyframes:
            interp_cn = INTERPOLATOR_NAMES_CN.get(
                kf.interpolator, kf.interpolator)
            self._list.addItem(
                f"t={kf.time:.2f}秒  v={kf.value:.3f}  [{interp_cn}]"
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
        items = self._list.selectedItems()
        if not items:
            return
        indices = sorted(
            [self._list.row(item) for item in items], reverse=True)
        for idx in indices:
            self._keyframes.pop(idx)
        self._refresh()

    def _offset(self):
        from PySide6.QtWidgets import QInputDialog
        dt, ok = QInputDialog.getDouble(
            self, "平移关键帧", "时间偏移 (秒)：", 0.5, -100.0, 100.0, 3)
        if ok:
            result = offset_keyframes(self._keyframes, dt)
            self._keyframes.clear()
            self._keyframes.extend(result)
            self._refresh()

    def _scale(self):
        from PySide6.QtWidgets import QInputDialog
        factor, ok = QInputDialog.getDouble(
            self, "缩放关键帧", "时间缩放因子：", 2.0, 0.01, 100.0, 3)
        if ok:
            result = scale_keyframes(self._keyframes, factor)
            self._keyframes.clear()
            self._keyframes.extend(result)
            self._refresh()

    def _reverse(self):
        result = reverse_keyframes(self._keyframes)
        self._keyframes.clear()
        self._keyframes.extend(result)
        self._refresh()

    def _apply_preset(self):
        menu = QMenu(self)
        for name, preset in PRESETS.items():
            act = QAction(f"{name} - {preset['description']}", self)
            act.triggered.connect(
                lambda _=False, n=name: self._do_apply_preset(n))
            menu.addAction(act)
        menu.exec(self.mapToGlobal(self.rect().center()))

    def _do_apply_preset(self, name: str):
        frames = apply_preset(name)
        if frames:
            self._keyframes.clear()
            self._keyframes.extend(frames)
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
        for key, cn_name in INTERPOLATOR_NAMES_CN.items():
            self._interp.addItem(cn_name, key)
        layout.addRow("插值方式:", self._interp)

        if keyframe:
            self._time.setValue(keyframe.time)
            self._value.setValue(keyframe.value)
            idx = self._interp.findData(keyframe.interpolator)
            if idx >= 0:
                self._interp.setCurrentIndex(idx)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addRow(buttons)

    def get_keyframe(self) -> Keyframe:
        return Keyframe(
            self._time.value(),
            self._value.value(),
            self._interp.currentData(),
        )


class AddTrackDialog(QDialog):
    """添加轨道对话框（中文化 + 属性校验）。"""

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
        self._type_combo.addItem("变量轨道 (variable)", "variable")
        self._type_combo.addItem("路径轨道 (glider)", "glider")
        self._type_combo.addItem("属性轨道 (property)", "property")
        self._type_combo.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("轨道类型:", self._type_combo)

        self._target_combo = QComboBox()
        form.addRow("目标:", self._target_combo)

        self._attr_combo = QComboBox()
        self._attr_combo.setEditable(True)
        self._attr_combo.setPlaceholderText("选择或输入属性名")
        for attr, cn in PropertyTrack.ATTR_NAMES_CN.items():
            self._attr_combo.addItem(f"{cn} ({attr})", attr)
        self._attr_combo.setVisible(False)
        form.addRow("属性名:", self._attr_combo)

        layout.addLayout(form)

        self._kf_btn = QPushButton("编辑关键帧…")
        self._kf_btn.clicked.connect(self._edit_keyframes)
        layout.addWidget(self._kf_btn)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._keyframes: list = []
        self._refresh_targets()

    def _on_type_changed(self, index: int):
        self._attr_combo.setVisible(index == 2)
        self._refresh_targets()

    def _refresh_targets(self):
        self._target_combo.clear()
        idx = self._type_combo.currentIndex()
        if idx == 0:
            from core.variables import get_store
            store = get_store()
            for name in store.names():
                self._target_combo.addItem(name, name)
        elif idx == 1:
            from geo.points import PointOnObject
            for obj in self._doc.objects:
                if isinstance(obj, PointOnObject):
                    self._target_combo.addItem(
                        f"吸附点 #{obj.id}", obj.id)
        elif idx == 2:
            for obj in self._doc.objects:
                tn = type(obj).__name__
                self._target_combo.addItem(f"{tn} #{obj.id}", obj.id)

    def _edit_keyframes(self):
        dlg = KeyframeEditor(self._keyframes, self)
        dlg.exec()

    def _accept(self):
        idx = self._type_combo.currentIndex()
        target = self._target_combo.currentData()
        if idx == 0:
            if target is None:
                QMessageBox.warning(self, "提示", "请选择变量。")
                return
            self._track = VariableTrack(str(target), self._keyframes)
        elif idx == 1:
            if target is None:
                QMessageBox.warning(self, "提示", "请选择路径对象。")
                return
            self._track = GliderTrack(int(target), self._keyframes)
        elif idx == 2:
            if target is None:
                QMessageBox.warning(self, "提示", "请选择对象。")
                return
            attr = self._attr_combo.currentData()
            if not attr:
                attr = self._attr_combo.currentText().strip()
            if not attr:
                QMessageBox.warning(self, "提示", "请输入属性名。")
                return
            if attr not in PropertyTrack.ALLOWED_ATTRS:
                QMessageBox.warning(
                    self, "提示",
                    f"不支持的属性名 '{attr}'。\n"
                    f"可选：{', '.join(sorted(PropertyTrack.ALLOWED_ATTRS))}")
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
            QDialogButtonBox.StandardButton.Ok |
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _edit_keyframes(self):
        if hasattr(self._track, "keyframes"):
            dlg = KeyframeEditor(self._track.keyframes, self)
            dlg.exec()