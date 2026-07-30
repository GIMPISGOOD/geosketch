"""函数编辑器：Desmos 风格 —— 虚拟数学键盘 + 实时数学预览。"""
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QRadioButton, QButtonGroup,
                               QCheckBox, QDoubleSpinBox, QPushButton,
                               QColorDialog, QDialogButtonBox, QWidget)

from geo.function_curve import FunctionCurve, PALETTE
from ui import theme
from ui.math import draw_math


class MathPreview(QWidget):
    """实时把表达式渲染成排版后的数学式。"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._text = ""
        self.setMinimumHeight(48)
        self.setStyleSheet("background:rgba(0,0,0,0.04);border-radius:6px;")

    def set_text(self, text):
        self._text = text
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._text.strip():
            draw_math(p, 12, self.height() / 2 + 8, self._text, 18, theme.INK)
        else:
            p.setPen(theme.pen(theme.SUBINK))
            p.drawText(12, self.height() / 2 + 6, "在下方键盘输入表达式…")


class FormulaKeypad(QWidget):
    """Desmos 风格虚拟数学键盘：按键不抢焦点，直接插入当前输入框。"""
    # (显示, 插入文本, 样式类)；None 表示特殊键
    KEYS = [
        ("7", "7", "num"), ("8", "8", "num"), ("9", "9", "num"), ("a⁄b", "/", "op"), ("⌫", None, "util"),
        ("4", "4", "num"), ("5", "5", "num"), ("6", "6", "num"), ("×", "*", "op"), ("AC", None, "util"),
        ("1", "1", "num"), ("2", "2", "num"), ("3", "3", "num"), ("−", "-", "op"), ("sin(", "sin(", "fn"),
        ("0", "0", "num"), (".", ".", "num"), ("+", "+", "op"), ("(", "(", "op"), ("cos(", "cos(", "fn"),
        ("x", "x", "var"), ("t", "t", "var"), ("^", "^", "op"), (")", ")", "op"), ("tan(", "tan(", "fn"),
        ("π", "π", "const"), ("e", "e", "const"), ("√(", "sqrt(", "fn"), ("ln(", "ln(", "fn"), ("abs(", "abs(", "fn"),
    ]

    def __init__(self, target_getter, parent=None):
        super().__init__(parent)
        self.setObjectName("formulaKeypad")
        self._get_target = target_getter
        grid = QGridLayout(self)
        grid.setSpacing(5)
        grid.setContentsMargins(10, 10, 10, 10)
        for idx, (label, ins, cls) in enumerate(self.KEYS):
            b = QPushButton(label)
            b.setProperty("keyclass", cls)
            b.setFixedHeight(38)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)      # 关键：不抢输入框焦点
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            if ins is None:
                if label == "⌫":
                    b.clicked.connect(self._backspace)
                else:
                    b.clicked.connect(self._clear)
            else:
                b.clicked.connect(lambda _=False, t=ins: self._insert(t))
            grid.addWidget(b, idx // 5, idx % 5)
        self.setStyleSheet(self._style())

    def _style(self):
        ink, sub = theme.INK.name(), theme.SUBINK.name()
        accent = theme.ACCENT.name()
        return f"""
        #formulaKeypad QPushButton {{
            border: none; border-radius: 8px;
            font-size: 15px; font-weight: 600; color: {ink};
            background: rgba(120,140,170,0.12);
        }}
        #formulaKeypad QPushButton:hover {{ background: rgba(120,140,170,0.28); }}
        #formulaKeypad QPushButton:pressed {{ background: {accent}; color: #ffffff; }}
        #formulaKeypad QPushButton[keyclass="op"] {{ background: rgba(25,113,194,0.14); color: {accent}; }}
        #formulaKeypad QPushButton[keyclass="op"]:hover {{ background: rgba(25,113,194,0.30); }}
        #formulaKeypad QPushButton[keyclass="fn"] {{ background: rgba(90,105,130,0.10); color: {sub}; font-size: 13px; }}
        #formulaKeypad QPushButton[keyclass="var"] {{ background: rgba(240,140,0,0.16); color: #e8590c; }}
        #formulaKeypad QPushButton[keyclass="const"] {{ background: rgba(47,158,68,0.16); color: #2f9e44; }}
        #formulaKeypad QPushButton[keyclass="util"] {{ background: rgba(230,73,128,0.12); color: {sub}; }}
        """

    def _insert(self, text):
        le = self._get_target()
        if le is not None:
            le.insert(text)

    def _backspace(self):
        le = self._get_target()
        if le is not None:
            le.backspace()

    def _clear(self):
        le = self._get_target()
        if le is not None:
            le.clear()


class FormulaEditor(QDialog):
    def __init__(self, canvas, func=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.func = func
        self._active_field = None
        self.setWindowTitle("编辑函数" if func else "新建函数")
        self.setMinimumWidth(430)
        self._build()
        self._load()

    def _build(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # 类型（分段选择）
        kind_row = QHBoxLayout()
        self._kind_group = QButtonGroup(self)
        self._kinds = {}
        for key, label in [("explicit", "显函数 y=f(x)"),
                           ("parametric", "参数方程"),
                           ("polar", "极坐标 r=f(θ)")]:
            rb = QRadioButton(label)
            self._kind_group.addButton(rb)
            self._kinds[key] = rb
            rb.toggled.connect(self._on_kind_changed)
            kind_row.addWidget(rb)
        root.addLayout(kind_row)

        # 表达式输入 1
        self._expr1_lbl = QLabel("y =")
        self._expr1 = QLineEdit()
        self._expr1.installEventFilter(self)
        self._expr1.textChanged.connect(self._update_preview)
        row1 = QHBoxLayout(); row1.addWidget(self._expr1_lbl); row1.addWidget(self._expr1)
        root.addLayout(row1)

        # 表达式输入 2（仅参数方程）
        self._expr2_row = QHBoxLayout()
        self._expr2_lbl = QLabel("y(t) =")
        self._expr2 = QLineEdit()
        self._expr2.installEventFilter(self)
        self._expr2.textChanged.connect(self._update_preview)
        self._expr2_row.addWidget(self._expr2_lbl); self._expr2_row.addWidget(self._expr2)
        root.addLayout(self._expr2_row)

        # 实时数学预览
        self._preview = MathPreview()
        root.addWidget(self._preview)

        # 虚拟键盘（插入当前聚焦的输入框）
        self._keypad = FormulaKeypad(lambda: self._active_field or self._expr1)
        root.addWidget(self._keypad)

        # 定义域
        dom = QHBoxLayout()
        self._auto_dom = QCheckBox("自动（跟随视窗）")
        self._auto_dom.toggled.connect(self._on_auto_toggled)
        dom.addWidget(self._auto_dom)
        dom.addWidget(QLabel("从"))
        self._dom_a = QDoubleSpinBox(); self._dom_a.setRange(-1e6, 1e6); self._dom_a.setDecimals(3); self._dom_a.setValue(0)
        dom.addWidget(self._dom_a)
        dom.addWidget(QLabel("到"))
        self._dom_b = QDoubleSpinBox(); self._dom_b.setRange(-1e6, 1e6); self._dom_b.setDecimals(3); self._dom_b.setValue(6.283)
        dom.addWidget(self._dom_b)
        dom.addStretch(1)
        root.addLayout(dom)

        # 颜色
        crow = QHBoxLayout()
        crow.addWidget(QLabel("颜色"))
        self._color = QColor(self.func.color if self.func else PALETTE[0])
        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(48, 24)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        crow.addWidget(self._color_btn)
        crow.addStretch(1)
        root.addLayout(crow)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def eventFilter(self, obj, ev):
        if ev.type() == QEvent.Type.FocusIn and isinstance(obj, QLineEdit):
            self._active_field = obj
        return super().eventFilter(obj, ev)

    def _load(self):
        f = self.func
        if f:
            self._kinds[f.kind].setChecked(True)
            self._expr1.setText(f.expr)
            self._expr2.setText(f.expr2)
            if f.domain:
                self._auto_dom.setChecked(False)
                self._dom_a.setValue(f.domain[0])
                self._dom_b.setValue(f.domain[1])
            else:
                self._auto_dom.setChecked(True)
        else:
            self._kinds["explicit"].setChecked(True)
            self._auto_dom.setChecked(True)
        self._on_kind_changed()
        self._update_preview()

    def _current_kind(self):
        for key, rb in self._kinds.items():
            if rb.isChecked():
                return key
        return "explicit"

    def _on_kind_changed(self, *a):
        kind = self._current_kind()
        is_param = (kind == "parametric")
        for i in range(self._expr2_row.count()):
            w = self._expr2_row.itemAt(i).widget()
            if w:
                w.setVisible(is_param)
        if kind == "explicit":
            self._expr1_lbl.setText("y =")
            self._auto_dom.setVisible(True)
        elif kind == "parametric":
            self._expr1_lbl.setText("x(t) =")
            self._auto_dom.setVisible(False)
        else:
            self._expr1_lbl.setText("r =")
            self._auto_dom.setVisible(False)
        self._on_auto_toggled()
        self._update_preview()

    def _on_auto_toggled(self, *a):
        auto = self._auto_dom.isChecked() and self._current_kind() == "explicit"
        self._dom_a.setEnabled(not auto)
        self._dom_b.setEnabled(not auto)

    def _update_preview(self, *a):
        kind = self._current_kind()
        e1 = self._expr1.text().strip()
        if kind == "explicit":
            self._preview.set_text(f"y = {e1}" if e1 else "")
        elif kind == "parametric":
            e2 = self._expr2.text().strip()
            self._preview.set_text(f"({e1}, {e2})" if (e1 or e2) else "")
        else:
            self._preview.set_text(f"r = {e1}" if e1 else "")

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "选择曲线颜色")
        if c.isValid():
            self._color = c
            self._update_color_btn()

    def _update_color_btn(self):
        self._color_btn.setStyleSheet(
            f"background:{self._color.name()};border:1px solid rgba(0,0,0,0.3);border-radius:5px;")

    def build_function(self):
        kind = self._current_kind()
        e1 = self._expr1.text().strip()
        e2 = self._expr2.text().strip()
        if not e1 or (kind == "parametric" and not e2):
            return None
        if self._auto_dom.isChecked() and kind == "explicit":
            domain = None
        else:
            a, b = self._dom_a.value(), self._dom_b.value()
            if a > b:
                a, b = b, a
            domain = (a, b)
        if self.func:
            f = self.func
            f.kind, f.expr, f.expr2, f.domain = kind, e1, e2, domain
            f.color = self._color.name()
            return f
        return FunctionCurve(kind, e1, e2, domain, self._color.name())