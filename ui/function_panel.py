"""函数编辑器：可折叠停靠侧栏，按类型分页显示函数。"""
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QColorDialog, QCheckBox,
                               QScrollArea, QFrame, QDockWidget, QMainWindow)
from geo.function_curve import FunctionCurve
from ui.variable_widgets import VariableSliderPanel
from ui import theme
from ui.math import draw_math

# 分页定义
PAGES = [
    ("all", "全部"),
    ("explicit", "显函数"),
    ("parametric", "参数"),
    ("polar", "极坐标"),
    ("implicit", "隐函数"),
]


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

        label = self._get_label(func)
        self.expr = ExprLabel(label, getattr(func, "color", "#1971c2"))
        h.addWidget(self.expr, 1)

        self._ops = QWidget()
        ah = QHBoxLayout(self._ops)
        ah.setContentsMargins(0, 0, 0, 0)
        ah.setSpacing(2)
        self.eye = QCheckBox()
        self.eye.setToolTip("显示/隐藏")
        self.eye.setChecked(getattr(func, "visible", True))
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
        rm.setStyleSheet(f"border:none;color:{theme.SELECTED.name()};"
                         f"font-weight:700;")
        rm.clicked.connect(lambda _=False, f=func: editor.delete(f))
        ah.addWidget(rm)
        h.addWidget(self._ops)
        self._ops.hide()
        self.setToolTip(label)
        self._style()

    @staticmethod
    def _get_label(func):
        from geo.implicit_curve import ImplicitCurve
        if isinstance(func, ImplicitCurve):
            return func.expr
        if hasattr(func, "default_label"):
            return func.default_label()
        return getattr(func, "expr", "")

    def _style(self):
        color = getattr(self.func, "color", "#1971c2")
        self.dot.setStyleSheet(
            f"background:{color};border-radius:6px;"
            f"border:1px solid rgba(0,0,0,0.25);")
        self.expr.set_text(self._get_label(self.func), color)

    def enterEvent(self, ev):
        self._ops.show()
        self.setStyleSheet("background:rgba(120,140,170,0.10);"
                           "border-radius:7px;")

    def leaveEvent(self, ev):
        self._ops.hide()
        self.setStyleSheet("background:transparent;")


class FunctionEditorWidget(QWidget):
    collapse_requested = Signal(bool)

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self._current_page = "all"

        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 9, 8, 9)
        outer.setSpacing(6)

        # 头部
        head = QHBoxLayout()
        self._collapse_btn = QPushButton("«")
        self._collapse_btn.setFixedWidth(24)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setToolTip("折叠侧栏")
        self._collapse_btn.clicked.connect(
            lambda: self.collapse_requested.emit(True))
        head.addWidget(self._collapse_btn)
        self._cap = QLabel("函数编辑器")
        head.addWidget(self._cap)
        head.addStretch(1)
        self._add = QPushButton("＋ 函数")
        self._add.setCursor(Qt.CursorShape.PointingHandCursor)
        self._add.clicked.connect(self.new_function)
        head.addWidget(self._add)
        outer.addLayout(head)

        # 滚动区
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("background:transparent;border:none;")
        self._content = QWidget()
        self._content.setStyleSheet("background:transparent;")
        cl = QVBoxLayout(self._content)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(10)

        self.var_panel = VariableSliderPanel(canvas, self._content)
        cl.addWidget(self.var_panel)

        # ★ 分页按钮
        self._page_btns = {}
        page_row = QHBoxLayout()
        page_row.setSpacing(4)
        for kind, label in PAGES:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=kind: self._switch_page(k))
            page_row.addWidget(btn)
            self._page_btns[kind] = btn
        page_row.addStretch(1)
        cl.addLayout(page_row)

        # 函数列表容器
        self._func_rows = QVBoxLayout()
        self._func_rows.setSpacing(2)
        cl.addLayout(self._func_rows)
        cl.addStretch(1)

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll, 1)

        self._switch_page("all")

    def _switch_page(self, kind):
        self._current_page = kind
        for k, btn in self._page_btns.items():
            btn.setChecked(k == kind)
        self.refresh()

    def refresh(self):
        self._cap.setStyleSheet(
            f"font-weight:800;font-size:13px;letter-spacing:2px;"
            f"color:{theme.INK.name()};")
        self._add.setStyleSheet(
            f"border:none;border-radius:8px;background:{theme.ACCENT.name()};"
            f"color:#fff;font-weight:700;padding:5px 10px;")
        # 分页按钮样式
        for k, btn in self._page_btns.items():
            if k == self._current_page:
                btn.setStyleSheet(
                    f"background:{theme.ACCENT.name()};color:#fff;"
                    f"border:none;border-radius:6px;padding:4px 8px;"
                    f"font-weight:600;")
            else:
                btn.setStyleSheet(
                    f"background:transparent;color:{theme.SUBINK.name()};"
                    f"border:none;border-radius:6px;padding:4px 8px;")
        self.var_panel.refresh()

        # 清空函数列表
        while self._func_rows.count():
            item = self._func_rows.takeAt(0)
            if item is None:
                break
            w = item.widget()
            if w:
                w.deleteLater()

        # 按当前分页填充
        from geo.implicit_curve import ImplicitCurve
        for o in self.canvas.doc.objects:
            if self._current_page == "all":
                if isinstance(o, (FunctionCurve, ImplicitCurve)):
                    self._func_rows.addWidget(FunctionRow(o, self))
            elif self._current_page == "implicit":
                if isinstance(o, ImplicitCurve):
                    self._func_rows.addWidget(FunctionRow(o, self))
            else:
                if isinstance(o, FunctionCurve) and o.kind == self._current_page:
                    self._func_rows.addWidget(FunctionRow(o, self))

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
        c = QColorDialog.getColor(QColor(getattr(f, "color", "#1971c2")),
                                  self, "选择曲线颜色")
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
    """可折叠函数编辑器侧栏。"""
    def __init__(self, canvas, parent=None):
        super().__init__("函数编辑器", parent)
        self.setObjectName("functionEditorDock")
        self.canvas = canvas
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea |
                             Qt.DockWidgetArea.RightDockWidgetArea)
        self.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable |
                         QDockWidget.DockWidgetFeature.DockWidgetFloatable |
                         QDockWidget.DockWidgetFeature.DockWidgetClosable)
        self._editor = FunctionEditorWidget(canvas, self)
        self._editor.collapse_requested.connect(self.set_collapsed)
        self._collapsed = False

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