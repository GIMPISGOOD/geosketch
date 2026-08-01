"""函数编辑器：可折叠的停靠侧栏（QDockWidget），函数显示于此。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QColorDialog, QCheckBox,
                               QScrollArea, QFrame, QDockWidget, QMainWindow)

from geo.function_curve import FunctionCurve
from ui.variable_widgets import VariableSliderPanel
from ui import theme
from ui.math import draw_math


class ExprLabel(QWidget):
    def __init__(self, text, color, parent=None):
        super().__init__(parent)
        self._text, self._color = text, color
        self.setFixedHeight(30)
        self.setMinimumWidth(40)

    def set_text(self, text, color):
        self._text, self._color = text, color
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw_math(p, 2, self.height() - 9, self._text, 14, self._color)


class FunctionRow(QWidget):
    def __init__(self, func, editor, parent=None):
        super().__init__(parent)
        self.func, self.editor = func, editor
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 2, 4, 2)
        h.setSpacing(7)

        self.dot = QPushButton()
        self.dot.setFixedSize(13, 13)
        self.dot.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dot.setToolTip("更改颜色")
        self.dot.clicked.connect(lambda _=False, f=func: editor.recolor(f))
        h.addWidget(self.dot)

        self.expr = ExprLabel(func.default_label(), func.color)
        h.addWidget(self.expr, 1)

        self._ops = QWidget()                      # 不能叫 actions（与 QWidget.actions() 冲突）
        ah = QHBoxLayout(self._ops)
        ah.setContentsMargins(0, 0, 0, 0)
        ah.setSpacing(2)
        self.eye = QCheckBox()
        self.eye.setToolTip("显示/隐藏")
        self.eye.setChecked(func.visible)
        self.eye.toggled.connect(lambda on, f=func: editor.toggle(f, on))
        ah.addWidget(self.eye)
        edit = QPushButton("✎")
        edit.setFixedSize(22, 22)
        edit.setCursor(Qt.CursorShape.PointingHandCursor)
        edit.setStyleSheet("border:none;")
        edit.clicked.connect(lambda _=False, f=func: editor.edit(f))
        ah.addWidget(edit)
        rm = QPushButton("×")
        rm.setFixedSize(22, 22)
        rm.setCursor(Qt.CursorShape.PointingHandCursor)
        rm.setStyleSheet(f"border:none;color:{theme.SELECTED.name()};font-weight:700;")
        rm.clicked.connect(lambda _=False, f=func: editor.delete(f))
        ah.addWidget(rm)
        h.addWidget(self._ops)
        self._ops.hide()
        self.setToolTip(func.default_label())
        self._style()

    def _style(self):
        self.dot.setStyleSheet(
            f"background:{self.func.color};border-radius:6px;border:1px solid rgba(0,0,0,0.25);")
        self.expr.set_text(self.func.default_label(), self.func.color)

    def enterEvent(self, ev):
        self._ops.show()
        self.setStyleSheet("background:rgba(120,140,170,0.10);border-radius:7px;")

    def leaveEvent(self, ev):
        self._ops.hide()
        self.setStyleSheet("background:transparent;")


class FunctionEditorWidget(QWidget):
    collapse_requested = Signal(bool)

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 9, 8, 9)
        outer.setSpacing(6)

        # 头部：折叠 + 标题 + 新建函数
        head = QHBoxLayout()
        self._collapse_btn = QPushButton("«")
        self._collapse_btn.setFixedWidth(24)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setToolTip("折叠侧栏")
        self._collapse_btn.clicked.connect(lambda: self.collapse_requested.emit(True))
        head.addWidget(self._collapse_btn)
        self._cap = QLabel("函数编辑器")
        head.addWidget(self._cap)
        head.addStretch(1)
        self._add = QPushButton("＋ 函数")
        self._add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add.clicked.connect(self.new_function)
        head.addWidget(self._add)
        outer.addLayout(head)

        # 滚动区：变量区 + 函数区（同一个滚动区，不再各自浮动堆叠）
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setStyleSheet("background:transparent;border:none;")
        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)

        self.var_panel = VariableSliderPanel(canvas, self._content)   # 变量区
        cl.addWidget(self.var_panel)
        self._func_cap = QLabel("函数")
        cl.addWidget(self._func_cap)
        self._func_rows = QVBoxLayout()
        self._func_rows.setSpacing(2)
        cl.addLayout(self._func_rows)
        cl.addStretch(1)
        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

    def refresh(self):
        self._cap.setStyleSheet(
            f"font-weight:800;font-size:13px;letter-spacing:2px;color:{theme.INK.name()};")
        self._add.setStyleSheet(
            f"border:none;border-radius:8px;background:{theme.ACCENT.name()};"
            f"color:#fff;font-weight:700;padding:5px 10px;")
        self._func_cap.setStyleSheet(
            f"font-weight:800;font-size:12px;color:{theme.INK.name()};")
        self.var_panel.refresh()
        while self._func_rows.count():
            item = self._func_rows.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w:
                w.deleteLater()
        for i, f in enumerate(o for o in self.canvas.doc.objects
                              if isinstance(o, FunctionCurve)):
            self._func_rows.insertWidget(i, FunctionRow(f, self))

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

class FunctionEditorDock(QDockWidget):
    """可折叠函数编辑器侧栏：« 收成窄条，» 展开。"""
    def __init__(self, canvas, parent=None):
        super().__init__("函数编辑器", parent)
        self.setObjectName("functionEditorDock")
        self.canvas = canvas
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                         QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self._editor = FunctionEditorWidget(canvas, self)
        self._editor.collapse_requested.connect(self.set_collapsed)
        self._collapsed = False

        # 折叠后的窄条
        self._strip = QWidget()
        sl = QVBoxLayout(self._strip)
        sl.setContentsMargins(4, 8, 4, 8)
        sl.setSpacing(8)
        expand = QPushButton("»")
        expand.setCursor(Qt.CursorShape.PointingHandCursor)
        expand.setToolTip("展开函数编辑器")
        expand.clicked.connect(lambda: self.set_collapsed(False))
        sl.addWidget(expand)
        vlabel = QLabel("函\n数")
        vlabel.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(vlabel)
        sl.addStretch(1)

        self.setWidget(self._editor)
        self.setMinimumWidth(280)

    def set_collapsed(self, collapsed):
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        mw = self.parent()
        if collapsed:
            self.setWidget(self._strip)
            self.setMinimumWidth(36)
            if isinstance(mw, QMainWindow):
                mw.resizeDocks([self], [40], Qt.Orientation.Horizontal)
        else:
            self.setWidget(self._editor)
            self.setMinimumWidth(280)
            if isinstance(mw, QMainWindow):
                mw.resizeDocks([self], [300], Qt.Orientation.Horizontal)
            self._editor.refresh()

    def refresh(self):
        self._editor.refresh()