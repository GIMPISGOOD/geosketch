"""变量 UI：两步创建向导 + 画布左下角的滑杆面板。"""
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
                               QLineEdit, QDoubleSpinBox, QPushButton, QSlider,
                               QWidget, QWizard, QWizardPage, QDialog,
                               QDialogButtonBox, QGraphicsDropShadowEffect, QCheckBox)

from core.variables import is_valid_name
from ui import theme


# ───────────── 创建向导（两步）─────────────
class _NamePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("① 变量名")
        self.setSubTitle("支持中文、希腊字母等任意 UTF-8 字符（如 边长、a、α）")
        layout = QVBoxLayout(self)
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("输入变量名…")
        self.hint = QLabel(" ")
        layout.addWidget(self.edit)
        layout.addWidget(self.hint)
        layout.addStretch(1)
        self.edit.textChanged.connect(self._validate)
        self._ok = False

    def _validate(self, text):
        self._ok = is_valid_name(text)
        if not text.strip():
            self.hint.setText("请输入变量名")
            self.hint.setStyleSheet("color:#8a8f98;")
        elif self._ok:
            self.hint.setText("✓ 变量名合法")
            self.hint.setStyleSheet("color:#2f9e44;")
        else:
            self.hint.setText("✗ 不能含空格/运算符，且不能是 pi、e、sqrt 等保留名")
            self.hint.setStyleSheet("color:#e03131;")
        self.completeChanged.emit()

    def isComplete(self):
        return self._ok


class _ValuePage(QWizardPage):
    def __init__(self):
        super().__init__()
        self.setTitle("② 初始值与滑杆范围")
        self.setSubTitle("创建后可在画布左下角用滑杆实时调整")
        form = QFormLayout(self)
        
        self.is_dependent = QCheckBox("作为从动变量（由表达式决定，不可手动拖动）")
        self.is_dependent.toggled.connect(self._on_dependent_toggled)
        form.addRow(self.is_dependent)
        
        self.expr_edit = QLineEdit()
        self.expr_edit.setPlaceholderText("如: a * 2 + 1 (可引用其他变量)")
        self.expr_edit.setVisible(False)
        form.addRow("表达式:", self.expr_edit)
        
        self.value = QDoubleSpinBox(); self.value.setRange(-1e6, 1e6)
        self.value.setValue(3.0); self.value.setDecimals(3)
        self.vmin = QDoubleSpinBox(); self.vmin.setRange(-1e6, 1e6)
        self.vmin.setValue(0.0); self.vmin.setDecimals(3)
        self.vmax = QDoubleSpinBox(); self.vmax.setRange(-1e6, 1e6)
        self.vmax.setValue(10.0); self.vmax.setDecimals(3)
        
        form.addRow("初始值", self.value)
        form.addRow("滑杆最小值", self.vmin)
        form.addRow("滑杆最大值", self.vmax)

    def _on_dependent_toggled(self, checked):
        self.expr_edit.setVisible(checked)
        self.value.setEnabled(not checked)
        self.vmin.setEnabled(not checked)
        self.vmax.setEnabled(not checked)

    def validatePage(self):
        if self.is_dependent.isChecked():
            return True
        lo, hi = self.vmin.value(), self.vmax.value()
        if lo > hi:
            self.vmin.setValue(hi); self.vmax.setValue(lo); lo, hi = hi, lo
        self.value.setValue(min(max(self.value.value(), lo), hi))
        return True


class VariableWizard(QWizard):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("新建变量")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setMinimumSize(440, 330)
        self.setButtonText(QWizard.WizardButton.NextButton, "下一步")
        self.setButtonText(QWizard.WizardButton.BackButton, "上一步")
        self.setButtonText(QWizard.WizardButton.FinishButton, "完成")
        self.setButtonText(QWizard.WizardButton.CancelButton, "取消")
        self._name_page = _NamePage()
        self._value_page = _ValuePage()
        self.addPage(self._name_page)
        self.addPage(self._value_page)

    def result_data(self):
        name = self._name_page.edit.text().strip()
        vp = self._value_page
        if vp.is_dependent.isChecked():
            return name, 0.0, 0.0, 10.0, vp.expr_edit.text().strip()
        lo, hi = vp.vmin.value(), vp.vmax.value()
        if lo > hi:
            lo, hi = hi, lo
        val = min(max(vp.value.value(), lo), hi)
        return name, val, lo, hi, ""


# ───────────── 左下滑杆面板 ─────────────
class VariableSliderPanel(QWidget):
    """变量滑杆区：嵌入函数面板使用，列出所有变量及其滑杆。"""
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(4)
        head = QHBoxLayout()
        self._cap = QLabel("变量")
        head.addWidget(self._cap)
        head.addStretch(1)
        self._add = QPushButton("＋")
        self._add.setFixedWidth(24)
        self._add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add.setToolTip("新建变量")
        self._add.clicked.connect(self._new_var)
        head.addWidget(self._add)
        layout.addLayout(head)
        self._rows = QVBoxLayout()
        self._rows.setSpacing(4)
        layout.addLayout(self._rows)
        self._dragging = False 

    def refresh(self):
        if self._dragging:              # ★ 新增：拖动时不重建滑杆
            return
        self._cap.setStyleSheet(
            f"font-weight:800;font-size:12px;color:{theme.INK.name()};")
        self._add.setStyleSheet(
            f"border:none;border-radius:6px;background:{theme.ACCENT.name()};"
            f"color:#fff;font-weight:700;")
        while self._rows.count():
            item = self._rows.takeAt(0)
            if item is not None:    
                w = item.widget()
            if w:
                w.deleteLater()
        for name in self.canvas.doc.vars.names():
            var = self.canvas.doc.vars.get_var(name)
            if var is not None:
                self._rows.addWidget(self._make_row(name, var))

    def _make_row(self, name, var):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(6)
        lbl = QLabel(f"{name} = {var.value:.2f}")
        lbl.setFont(theme.LABEL_FONT)
        lbl.setMinimumWidth(90)
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(0, 1000)
        span = (var.vmax - var.vmin) or 1.0
        slider.setValue(int((var.value - var.vmin) / span * 1000))
        slider.setMinimumWidth(110)
        slider.valueChanged.connect(
            lambda v, n=name, l=lbl, a=var.vmin, b=var.vmax: self._on_slide(n, v, l, a, b))
        rm = QPushButton("×")
        rm.setFixedSize(20, 20)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setStyleSheet(f"border:none;color:{theme.SELECTED.name()};font-weight:700;")
        rm.clicked.connect(lambda _=False, n=name: self._delete(n))
        h.addWidget(lbl)
        h.addWidget(slider, 1)
        h.addWidget(rm)
        return w

    def _on_slide(self, name, v, lbl, vmin, vmax):
        self._dragging = True
        val = vmin + (vmax - vmin) * v / 1000
        lbl.setText(f"{name} = {val:.2f}")
        self.canvas.doc.vars.set(name, val)
        self.canvas.doc.refresh_variables()
        self._dragging = False

    def _delete(self, name):
        self.canvas.doc.vars.delete(name)
        self.canvas.doc.refresh_variables()
        self.refresh()

    def _new_var(self):
        wiz = VariableWizard(self.window())
        if wiz.exec():
            name, val, lo, hi, expr = wiz.result_data()
            self.canvas.doc.vars.define(name, val, lo, hi, expr)
            self.canvas.doc.refresh_variables()
            self.refresh()

class VariableRangeDialog(QDialog):
    """修改变量的滑杆范围（最小值 / 最大值）。"""
    def __init__(self, name, vmin, vmax, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"修改范围 · {name}")
        self.setMinimumWidth(300)
        form = QFormLayout(self)
        self.vmin = QDoubleSpinBox()
        self.vmin.setRange(-1e6, 1e6); self.vmin.setDecimals(3); self.vmin.setValue(vmin)
        self.vmax = QDoubleSpinBox()
        self.vmax.setRange(-1e6, 1e6); self.vmax.setDecimals(3); self.vmax.setValue(vmax)
        self._name_page: Optional[Any] = None
        self._value_page: Optional[Any] = None
        form.addRow("最小值", self.vmin)
        form.addRow("最大值", self.vmax)
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        form.addRow(btns)

    def result_data(self):
        lo = self.vmin.value()
        hi = self.vmax.value()
        if lo > hi:
            lo, hi = hi, lo
        return lo, hi