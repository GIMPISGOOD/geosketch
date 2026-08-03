"""图表数据向导：设置每项的标签 / 数值（支持 {表达式}）/ 颜色。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWizard, QWizardPage, QSpinBox, QFormLayout,
                               QVBoxLayout, QHBoxLayout, QWidget, QLineEdit,
                               QPushButton, QScrollArea, QColorDialog, QGridLayout)

from media.chart_obj import CHART_COLORS


class _CountPage(QWizardPage):
    def __init__(self, init_count=3):
        super().__init__()
        self.setTitle("① 数据项数量")
        layout = QFormLayout(self)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 20)
        self.count_spin.setValue(init_count)
        layout.addRow("项数：", self.count_spin)
        self.registerField("count", self.count_spin)


class _DataPage(QWizardPage):
    def __init__(self, init_data=None, init_labels=None, init_colors=None):
        super().__init__()
        self.setTitle("② 各项数据")
        self.setSubTitle("数值可填数字或 {表达式}（如 {a*2}），变量变化时自动更新")
        self._init_data = init_data
        self._init_labels = init_labels
        self._init_colors = init_colors
        outer = QVBoxLayout(self)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        outer.addWidget(self._scroll)
        self._container = None
        self._label_edits = {}
        self._value_edits = {}
        self._color_btns = {}
        self._colors = {}
        self._last_count = None

    def initializePage(self):
        count = self.wizard().field("count")
        if self._last_count != count:
            self._build(count)
            self._last_count = count

    def _build(self, count):
        self._label_edits.clear()
        self._value_edits.clear()
        self._color_btns.clear()
        self._colors.clear()
        container = QWidget()
        grid = QGridLayout(container)
        grid.addWidget(QWidget(), 0, 0)
        for c, head in enumerate(["标签", "数值", "颜色"]):
            pass
        for i in range(count):
            grid.addWidget(self._make_label_edit(i), i, 0)
            grid.addWidget(self._make_value_edit(i), i, 1)
            grid.addWidget(self._make_color_btn(i), i, 2)
        self._scroll.setWidget(container)
        self._container = container
        # 预填
        if self._init_data:
            for i in range(min(count, len(self._init_data))):
                self._value_edits[i].setText(str(self._init_data[i]))
        if self._init_labels:
            for i in range(min(count, len(self._init_labels))):
                self._label_edits[i].setText(self._init_labels[i])
        if self._init_colors:
            for i in range(min(count, len(self._init_colors))):
                if self._init_colors[i]:
                    self._set_color(i, self._init_colors[i])

    def _make_label_edit(self, i):
        e = QLineEdit(f"项{i+1}")
        self._label_edits[i] = e
        return e

    def _make_value_edit(self, i):
        e = QLineEdit("1")
        e.setPlaceholderText("{a*2}")
        self._value_edits[i] = e
        return e

    def _make_color_btn(self, i):
        b = QPushButton()
        b.setFixedSize(26, 26)
        b.setCursor(Qt.CursorShape.PointingHandCursor)
        default = CHART_COLORS[i % len(CHART_COLORS)]
        self._colors[i] = default
        b.setStyleSheet(f"background:{default};border:1px solid #888;border-radius:4px;")
        b.clicked.connect(lambda _=False, ii=i: self._pick(ii))
        self._color_btns[i] = b
        return b

    def _pick(self, i):
        color = QColorDialog.getColor(QColor(self._colors[i]), self, "选择颜色")
        if color.isValid():
            self._set_color(i, color.name())

    def _set_color(self, i, name):
        self._colors[i] = name
        self._color_btns[i].setStyleSheet(
            f"background:{name};border:1px solid #888;border-radius:4px;")

    def get_data(self):
        count = self.wizard().field("count")
        data, labels, colors = [], [], []
        for i in range(count):
            vtxt = self._value_edits[i].text().strip() if i in self._value_edits else "0"
            data.append(vtxt)
            labels.append(self._label_edits[i].text() if i in self._label_edits else f"项{i+1}")
            colors.append(self._colors.get(i, CHART_COLORS[i % len(CHART_COLORS)]))
        return data, labels, colors


class PieChartWizard(QWizard):
    def __init__(self, parent=None, data=None, labels=None, colors=None):
        super().__init__(parent)
        self.setWindowTitle("图表数据向导")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setMinimumSize(520, 460)
        init_count = len(data) if data else 3
        self._count_page = _CountPage(init_count)
        self._data_page = _DataPage(data, labels, colors)
        self.addPage(self._count_page)
        self.addPage(self._data_page)
        self.setButtonText(QWizard.WizardButton.FinishButton, "确定")
        self.setButtonText(QWizard.WizardButton.CancelButton, "取消")
        self.setButtonText(QWizard.WizardButton.NextButton, "下一步")
        self.setButtonText(QWizard.WizardButton.BackButton, "上一步")

    def get_data(self):
        return self._data_page.get_data()