"""插入表格向导：指定行列、每格数值与颜色；单元格支持 {表达式}。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWizard, QWizardPage, QFormLayout, QSpinBox,
                               QVBoxLayout, QGridLayout, QWidget, QLineEdit,
                               QPushButton, QScrollArea, QColorDialog, QHBoxLayout)


class _SizePage(QWizardPage):
    def __init__(self, init_rows=3, init_cols=3):
        super().__init__()
        self.setTitle("① 表格尺寸")
        self.setSubTitle("指定表格的行数与列数")
        layout = QFormLayout(self)
        self.rows_spin = QSpinBox()
        self.rows_spin.setRange(1, 30)
        self.rows_spin.setValue(init_rows)
        self.cols_spin = QSpinBox()
        self.cols_spin.setRange(1, 30)
        self.cols_spin.setValue(init_cols)
        layout.addRow("行数：", self.rows_spin)
        layout.addRow("列数：", self.cols_spin)
        self.registerField("rows", self.rows_spin)
        self.registerField("cols", self.cols_spin)


class _ContentPage(QWizardPage):
    def __init__(self, init_cells=None, init_colors=None):
        super().__init__()
        self.setTitle("② 单元格内容与颜色")
        self.setSubTitle("每格可填文本或 {表达式}（如 {a*2+1}），点右侧色块选格子颜色")
        self._init_cells = init_cells
        self._init_colors = init_colors
        outer = QVBoxLayout(self)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        outer.addWidget(self._scroll)
        self._grid_container = None
        self._cell_edits = {}
        self._cell_colors = {}
        self._cell_color_btns = {}
        self._last_dims = None

    def initializePage(self):
        rows = self.wizard().field("rows")
        cols = self.wizard().field("cols")
        if self._last_dims != (rows, cols):
            self._build_grid(rows, cols)
            self._last_dims = (rows, cols)

    def _build_grid(self, rows, cols):
        self._cell_edits.clear()
        self._cell_colors.clear()
        self._cell_color_btns.clear()
        container = QWidget()
        grid = QGridLayout(container)
        grid.setSpacing(4)
        for r in range(rows):
            for c in range(cols):
                grid.addWidget(self._make_cell(r, c), r, c)
        self._scroll.setWidget(container)       # 替换旧网格
        self._grid_container = container
        # 预填初始数据（编辑已有表格时）
        if self._init_cells:
            for r in range(min(rows, len(self._init_cells))):
                for c in range(min(cols, len(self._init_cells[r]))):
                    if (r, c) in self._cell_edits:
                        self._cell_edits[(r, c)].setText(self._init_cells[r][c])
        if self._init_colors:
            for r in range(min(rows, len(self._init_colors))):
                for c in range(min(cols, len(self._init_colors[r]))):
                    color = self._init_colors[r][c]
                    if color and (r, c) in self._cell_color_btns:
                        self._cell_colors[(r, c)] = color
                        self._cell_color_btns[(r, c)].setStyleSheet(
                            f"background:{color};border:1px solid #888;border-radius:3px;")

    def _make_cell(self, r, c):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        h.setSpacing(2)
        edit = QLineEdit()
        edit.setPlaceholderText("{a*2}")
        self._cell_edits[(r, c)] = edit
        color_btn = QPushButton()
        color_btn.setFixedSize(22, 22)
        color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        color_btn.setToolTip("选择格子颜色")
        color_btn.setStyleSheet("background:transparent;border:1px solid #888;border-radius:3px;")
        color_btn.clicked.connect(lambda _=False, rr=r, cc=c: self._pick_color(rr, cc))
        self._cell_color_btns[(r, c)] = color_btn
        h.addWidget(edit, 1)
        h.addWidget(color_btn)
        return w

    def _pick_color(self, r, c):
        color = QColorDialog.getColor(QColor("#ffffff"), self, "选择格子颜色")
        if color.isValid():
            self._cell_colors[(r, c)] = color.name()
            self._cell_color_btns[(r, c)].setStyleSheet(
                f"background:{color.name()};border:1px solid #888;border-radius:3px;")

    def get_cells(self):
        rows = self.wizard().field("rows")
        cols = self.wizard().field("cols")
        cells = [["" for _ in range(cols)] for _ in range(rows)]
        cell_colors = [[None for _ in range(cols)] for _ in range(rows)]
        for (r, c), edit in self._cell_edits.items():
            if r < rows and c < cols:
                cells[r][c] = edit.text()
        for (r, c), color in self._cell_colors.items():
            if r < rows and c < cols:
                cell_colors[r][c] = color
        return cells, cell_colors


class InsertTableWizard(QWizard):
    def __init__(self, parent=None, rows=3, cols=3, cells=None, cell_colors=None):
        super().__init__(parent)
        self.setWindowTitle("插入表格向导")
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.setMinimumSize(640, 520)
        self._size_page = _SizePage(rows, cols)
        self._content_page = _ContentPage(cells, cell_colors)
        self.addPage(self._size_page)
        self.addPage(self._content_page)
        self.setButtonText(QWizard.WizardButton.FinishButton, "插入")
        self.setButtonText(QWizard.WizardButton.CancelButton, "取消")
        self.setButtonText(QWizard.WizardButton.NextButton, "下一步")
        self.setButtonText(QWizard.WizardButton.BackButton, "上一步")

    def get_table_data(self):
        rows = self.field("rows")
        cols = self.field("cols")
        cells, cell_colors = self._content_page.get_cells()
        return rows, cols, cells, cell_colors