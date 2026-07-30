"""函数列表面板：Desmos 风格 —— 数学渲染的表达式行，悬停显示操作。
函数多时列表内部滚动，面板高度按行数自适应，绝不被裁切。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QColorDialog, QCheckBox,
                               QScrollArea, QFrame)

from geo.function_curve import FunctionCurve
from ui import theme
from ui.math import draw_math


class ExprLabel(QWidget):
    """用 draw_math 渲染表达式（数学排版，而非纯文本）。"""
    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self._text = text
        self._color = color
        self.setFixedHeight(30)
        self.setMinimumWidth(40)

    def set_text(self, text, color):
        self._text = text
        self._color = color
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_math(p, 2, self.height() - 9, self._text, 14, self._color)


class FunctionRow(QWidget):
    """单条函数：色点 + 数学表达式 + 悬停操作（显隐/编辑/删除）。"""
    def __init__(self, func, panel, parent=None):
        super().__init__(parent)
        self.func = func
        self.panel = panel
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 2, 4, 2)
        h.setSpacing(7)

        self.dot = QPushButton()
        self.dot.setFixedSize(13, 13)
        self.dot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dot.setToolTip("更改颜色")
        self.dot.clicked.connect(lambda _=False, f=func: panel.recolor(f))
        h.addWidget(self.dot)

        self.expr = ExprLabel(func.default_label(), func.color)
        h.addWidget(self.expr, 1)

        # 操作区（默认隐藏，悬停浮现）
        # 注意：不能命名为 actions —— 会与 QWidget.actions() 内置方法冲突
        self._ops = QWidget()
        ah = QHBoxLayout(self._ops)
        ah.setContentsMargins(0, 0, 0, 0)
        ah.setSpacing(2)
        self.eye = QCheckBox()
        self.eye.setToolTip("显示/隐藏")
        self.eye.setChecked(func.visible)
        self.eye.toggled.connect(lambda on, f=func: panel.toggle(f, on))
        ah.addWidget(self.eye)
        edit = QPushButton("✎")
        edit.setFixedSize(22, 22)
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.setStyleSheet("border:none;")
        edit.clicked.connect(lambda _=False, f=func: panel.edit(f))
        ah.addWidget(edit)
        rm = QPushButton("×")
        rm.setFixedSize(22, 22)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setStyleSheet(f"border:none;color:{theme.SELECTED.name()};font-weight:700;")
        rm.clicked.connect(lambda _=False, f=func: panel.delete(f))
        ah.addWidget(rm)
        h.addWidget(self._ops)
        self._ops.hide()

        self.setToolTip(func.default_label())      # 悬停看完整表达式
        self._style()

    def _style(self):
        self.dot.setStyleSheet(
            f"background:{self.func.color};border-radius:6px;"
            f"border:1px solid rgba(0,0,0,0.25);")
        self.expr.set_text(self.func.default_label(), self.func.color)

    def enterEvent(self, ev):
        self._ops.show()
        self.setStyleSheet("background:rgba(120,140,170,0.10);border-radius:7px;")

    def leaveEvent(self, ev):
        self._ops.hide()
        self.setStyleSheet("background:transparent;")


class FunctionPanel(QWidget):
    PANEL_W = 340          # 面板宽度：保证典型表达式完整显示

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setObjectName("functionPanel")
        self.canvas = canvas
        self.setFixedWidth(self.PANEL_W)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 9, 8, 9)
        outer.setSpacing(6)

        # 头部：标题 + 新建
        head = QHBoxLayout()
        self._cap = QLabel("函 数")
        head.addWidget(self._cap)
        head.addStretch(1)
        self._add = QPushButton("＋")
        self._add.setFixedSize(26, 26)
        self._add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add.setToolTip("新建函数")
        self._add.clicked.connect(self.new_function)
        head.addWidget(self._add)
        outer.addLayout(head)

        # 可滚动的函数列表
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("background:transparent;border:none;")
        self._list = QWidget()
        self._list.setStyleSheet("background:transparent;")
        self._rows = QVBoxLayout(self._list)
        self._rows.setContentsMargins(0, 0, 0, 0)
        self._rows.setSpacing(2)
        self._rows.addStretch(1)                   # 行全部顶到最上
        self._scroll.setWidget(self._list)
        outer.addWidget(self._scroll, 1)

    def refresh(self):
        self._cap.setStyleSheet(
            f"font-weight:800;font-size:13px;letter-spacing:3px;color:{theme.INK.name()};")
        self._add.setStyleSheet(
            f"border:none;border-radius:13px;background:{theme.ACCENT.name()};"
            f"color:#fff;font-weight:700;font-size:15px;")
        # 清空旧行（保留末尾 stretch）
        while self._rows.count() > 1:
            item = self._rows.takeAt(0)
            if item is not None:
                w = item.widget()
                if w is not None:
                    w.deleteLater()
        funcs = [o for o in self.canvas.doc.objects if isinstance(o, FunctionCurve)]
        for i, f in enumerate(funcs):
            self._rows.insertWidget(i, FunctionRow(f, self))
        self.reposition()
        self.show()
        self.raise_()

    def reposition(self):
        self._fit_height()
        # 位于工具栏右侧；想放右侧改为：self.move(self.canvas.width() - self.width() - 14, 14)
        self.move(80, 14)

    def _fit_height(self):
        """按行数确定高度（不依赖 sizeHint 时序），封顶 画布高-40，超出内部滚动。"""
        n = max(self._rows.count() - 1, 0)       # 减去末尾 stretch
        row_h = 34
        header_h = 44
        margin = 18
        content_h = header_h + margin + n * row_h
        max_h = self.canvas.height() - 40
        self.setFixedHeight(max(72, min(content_h, max_h)))

    # ───────── 操作 ─────────
    def new_function(self):
        from ui.formula_editor import FormulaEditor
        dlg = FormulaEditor(self.canvas, None, self)
        if dlg.exec():
            f = dlg.build_function()
            if f:
                self.canvas.doc.add(f)
                self.refresh()

    def edit(self, f):
        from ui.formula_editor import FormulaEditor
        dlg = FormulaEditor(self.canvas, f, self)
        if dlg.exec():
            dlg.build_function()
            self.canvas.doc.changed.emit()
            self.refresh()

    def recolor(self, f):
        c = QColorDialog.getColor(QColor(f.color), self, "选择曲线颜色")
        if c.isValid():
            f.color = c.name()
            self.canvas.doc.changed.emit()
            self.refresh()

    def toggle(self, f, on):
        f.visible = on
        self.canvas.doc.changed.emit()

    def delete(self, f):
        self.canvas.doc.remove(f)
        self.refresh()