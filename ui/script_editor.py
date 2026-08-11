"""脚本编辑器 v2：适配全新 DSL 语法。
功能：
- 新语法高亮（func, import, wait, 几何函数）
- 智能补全（内置几何函数、库名、文档对象名）
- 运行防抖（执行 wait 时禁用按钮）
- 错误红线与行号
"""

import re
from PySide6.QtCore import Qt, QRect, QSize, QStringListModel
from PySide6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
                           QPainter, QTextCursor, QTextFormat, QShortcut, QKeySequence)
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
                               QPushButton, QWidget, QTextEdit, QComboBox,
                               QLabel, QMessageBox, QCompleter, QApplication)

from core.scripting import run_script, parse
from core.scripting.errors import ScriptError
from ui import theme


# ═══════════════ 1. 自动补全数据源 ═══════════════
KEYWORDS = [
    "if", "如果", "elif", "否则如果", "else", "否则",
    "repeat", "重复", "for", "遍历", "from", "从", "to", "到",
    "func", "函数", "return", "返回",
    "import", "导入",
    "wait", "等待",
    "delete", "删除", "all", "所有",
    "global", "全局",
    "true", "真", "false", "假",
    "and", "并且", "or", "或者", "not", "非",
    "__keep", "__allow_delete_user"
]

# 内置几何函数与数学函数
FUNCS = [
    "point", "segment", "line", "ray", "circle", "ellipse", 
    "polygon", "regular_polygon", "midpoint", "division_point", 
    "intersect", "text", "function", "parametric", "polar",
    "distance", "length", "slope", "radius", "area", "perimeter",
    "sin", "cos", "tan", "arcsin", "arccos", "arctan",
    "sqrt", "abs", "ln", "log", "exp", "floor", "ceil", "round",
    "print", "math", "geo", "draw", "doc"
]

def get_completions(doc):
    """获取补全列表：关键字 + 函数 + 画布上的对象名 + 已导入的库"""
    obj_names = list(getattr(doc, "names", {}).keys())
    libs = list(getattr(doc, "script_libs", {}).keys())
    return list(set(KEYWORDS + FUNCS + obj_names + libs))


# ═══════════════ 2. 脚本模板库（新语法） ═══════════════
TEMPLATES = {
    "基础图形创建": """__keep = true

A = point(0, 0)
B = point(4, 0)
AB = segment(A, B)

C = circle(A, 2)
""",
    "自定义函数与循环": """__keep = true

func make_star(center, r, n) {
    for i from 0 to n - 1 {
        angle = i * 2 * pi / n
        P = point(center.x + r * cos(angle), center.y + r * sin(angle))
        if i > 0 {
            segment(prev_P, P)
        }
        prev_P = P
    }
}

O = point(0, 0)
make_star(O, 3, 5)
""",
    "动画与等待 (wait)": """A = point(0, 0)
B = point(1, 0)

for i from 1 to 5 {
    B = point(i, sin(i))
    wait 0.5
}

__keep = true
""",
    "导入数学库": """import math

__keep = true

A = point(0, 0)
B = point(math.cos(0), math.sin(math.pi / 2))
segment(A, B)
"""
}


# ═══════════════ 3. 语法高亮 ═══════════════
class ScriptHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.rules = []

        # 关键字
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#1971c2"))
        kw_format.setFontWeight(QFont.Weight.Bold)
        for pat in KEYWORDS:
            self.rules.append((re.compile(rf"\b{re.escape(pat)}\b"), kw_format))

        # 几何与数学函数
        fn_format = QTextCharFormat()
        fn_format.setForeground(QColor("#9c36b5"))
        for pat in FUNCS:
            self.rules.append((re.compile(rf"\b{re.escape(pat)}\b(?=\s*\()"), fn_format))

        # 数字
        num_format = QTextCharFormat()
        num_format.setForeground(QColor("#2f9e44"))
        self.rules.append((re.compile(r"\b\d+\.?\d*\b"), num_format))

        # 字符串
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#e8590c"))
        self.rules.append((re.compile(r"\"[^\"]*\""), str_format))
        self.rules.append((re.compile(r"'[^']*'"), str_format))

        # 注释
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#868e96"))
        self.rules.append((re.compile(r"#.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(), match.end() - match.start(), fmt)


# ═══════════════ 4. 行号区组件 ═══════════════
class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)

    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)


# ═══════════════ 5. 代码编辑器核心 ═══════════════
class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setTabStopDistance(28)
        
        self.lineNumberArea = LineNumberArea(self)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0)
        
        self._error_selections = []
        
        self.completer = QCompleter(self)
        self.completer.setWidget(self)
        self.completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insertCompletion)

    def lineNumberAreaWidth(self):
        digits = len(str(max(1, self.blockCount())))
        space = 10 + self.fontMetrics().horizontalAdvance('9') * digits
        return space

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy:
            self.lineNumberArea.scroll(0, dy)
        else:
            self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(),
                                              self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor(theme.PANEL_BG.name() if hasattr(theme, 'PANEL_BG') else "#f0f0f0"))

        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())

        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                painter.setPen(QColor(theme.SUBINK.name() if hasattr(theme, 'SUBINK') else "#888888"))
                painter.drawText(0, top, self.lineNumberArea.width() - 5,
                                 self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, number)
            block = block.next()
            top = bottom
            bottom = top + int(self.blockBoundingRect(block).height())
            blockNumber += 1

    def highlightCurrentLine(self):
        extraSelections = []
        if not self.isReadOnly():
            selection = QTextEdit.ExtraSelection()
            lineColor = QColor(Qt.GlobalColor.yellow).lighter(160)
            lineColor.setAlpha(40)
            selection.format.setBackground(lineColor)
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            selection.cursor = self.textCursor()
            selection.cursor.clearSelection()
            extraSelections.append(selection)
            
        extraSelections.extend(self._error_selections)
        self.setExtraSelections(extraSelections)
        
    def set_error_line(self, line_num):
        self._error_selections = []
        if line_num > 0:
            selection = QTextEdit.ExtraSelection()
            selection.format.setBackground(QColor(255, 0, 0, 60))
            selection.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
            
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down, QTextCursor.MoveMode.MoveAnchor, line_num - 1)
            selection.cursor = cursor
            
            self._error_selections.append(selection)
        self.highlightCurrentLine()

    def insertCompletion(self, completion):
        if self.completer.widget() != self:
            return
        tc = self.textCursor()
        extra = len(completion) - len(self.completer.completionPrefix())
        tc.movePosition(QTextCursor.MoveOperation.Left)
        tc.movePosition(QTextCursor.MoveOperation.EndOfWord)
        tc.insertText(completion[-extra:])
        self.setTextCursor(tc)

    def textUnderCursor(self):
        tc = self.textCursor()
        tc.select(QTextCursor.SelectionType.WordUnderCursor)
        return tc.selectedText()

    def keyPressEvent(self, e):
        if self.completer.popup().isVisible():
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return, Qt.Key.Key_Escape, Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
                e.ignore()
                return

        super().keyPressEvent(e)

        hasModifier = e.modifiers() != Qt.KeyboardModifier.NoModifier
        if hasModifier and e.text() == '':
            return

        completionPrefix = self.textUnderCursor()
        
        if not completionPrefix or (not completionPrefix.isidentifier() and not completionPrefix.isalnum()):
            self.completer.popup().hide()
            return

        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            popup = self.completer.popup()
            popup.setCurrentIndex(self.completer.completionModel().index(0, 0))

        cr = self.cursorRect()
        cr.setWidth(self.completer.popup().sizeHintForColumn(0) +
                    self.completer.popup().verticalScrollBar().sizeHint().width())
        self.completer.complete(cr)


# ═══════════════ 6. 编辑器主对话框 ═══════════════
class ScriptEditorDialog(QDialog):
    def __init__(self, canvas, button_obj, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.button_obj = button_obj
        
        self.setWindowTitle(f"脚本编辑器 · {getattr(button_obj, 'name', '') or 'ScriptButton'}")
        self.resize(800, 600)
        
        layout = QVBoxLayout(self)
        
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("插入模板:"))
        self.template_combo = QComboBox()
        self.template_combo.addItem("-- 选择模板 --", None)
        for name, code in TEMPLATES.items():
            self.template_combo.addItem(name, code)
        self.template_combo.currentIndexChanged.connect(self._insert_template)
        top_bar.addWidget(self.template_combo, 1)
        layout.addLayout(top_bar)
        
        self.editor = CodeEditor()
        self.editor.setPlainText(button_obj.script)
        self.highlighter = ScriptHighlighter(self.editor.document())
        layout.addWidget(self.editor, 1)
        
        bottom_bar = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: red; font-weight: bold;")
        bottom_bar.addWidget(self.status_lbl, 1)
        
        self.run_btn = QPushButton("运行 (Ctrl+R)")
        save_btn = QPushButton("保存 (Ctrl+S)")
        cancel_btn = QPushButton("取消")
        
        self.run_btn.clicked.connect(self._run)
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)
        
        bottom_bar.addWidget(self.run_btn)
        bottom_bar.addWidget(save_btn)
        bottom_bar.addWidget(cancel_btn)
        layout.addLayout(bottom_bar)
        
        QShortcut(QKeySequence("Ctrl+R"), self, self._run)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        
        self._update_completer()
        
    def _update_completer(self):
        words = get_completions(self.canvas.doc)
        model = QStringListModel(words)
        self.editor.completer.setModel(model)
        
    def _insert_template(self, index):
        code = self.template_combo.itemData(index)
        if code:
            self.editor.insertPlainText(code)
            self.template_combo.setCurrentIndex(0)
            
    def _check_syntax(self):
        self.editor._error_selections = []
        self.status_lbl.setText("")
        self.status_lbl.setStyleSheet("color: red; font-weight: bold;")
        try:
            parse(self.editor.toPlainText())
            self.editor.highlightCurrentLine()
            return True
        except ScriptError as e:
            self.status_lbl.setText(f"语法错误: {e}")
            self.editor.set_error_line(e.line or 0)
            return False
        except Exception as e:
            self.status_lbl.setText(f"未知错误: {e}")
            return False

    def _save(self):
        if not self._check_syntax():
            return
        self.button_obj.script = self.editor.toPlainText()
        self.canvas.doc.changed.emit()
        self.accept()

    def _run(self):
        self.button_obj.script = self.editor.toPlainText()
        self.canvas.doc.changed.emit()
        
        if not self._check_syntax():
            return
            
        # ★ 防抖：运行期间禁用按钮，防止 wait 时重复点击
        self.run_btn.setEnabled(False)
        self.run_btn.setText("运行中...")
        QApplication.processEvents()
        
        try:
            rt = run_script(
                self.canvas.doc,
                self.button_obj.script,
                owner_id=self.button_obj.id,
                canvas=self.canvas
            )
            if rt and rt.error:
                self.status_lbl.setText(f"运行错误: {rt.error}")
                if hasattr(rt.error, 'line'):
                    self.editor.set_error_line(rt.error.line or 0)
            else:
                self.status_lbl.setText("✔ 运行成功")
                self.status_lbl.setStyleSheet("color: green; font-weight: bold;")
        finally:
            self.run_btn.setEnabled(True)
            self.run_btn.setText("运行 (Ctrl+R)")


def edit_script_button(canvas, button_obj):
    dlg = ScriptEditorDialog(canvas, button_obj, canvas)
    dlg.exec()