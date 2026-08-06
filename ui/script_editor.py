"""脚本编辑器基础版。

当前支持：
- 多行编辑
- 简单关键字高亮
- 运行
- 保存

后续步骤会加：
- 行号
- 自动补全
- 函数提醒
- 错误红线
"""

import re

from PySide6.QtGui import QColor, QFont, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QPushButton
)

from core.scripting import run_script


KEYWORD_PATTERNS = [
    r"repeat", r"重复",
    r"for", r"遍历",
    r"from", r"从",
    r"to", r"到",
    r"if", r"如果",
    r"elif", r"否则如果",
    r"else", r"否则",
    r"global", r"全局",
    r"set", r"设置",
    r"true", r"真",
    r"false", r"假",
    r"and", r"并且", r"且",
    r"or", r"或者",
    r"not", r"非",
    r"add", r"新增", r"添加",
    r"delete", r"删除",
    r"print", r"打印",
    r"point", r"点",
    r"segment", r"线段",
    r"line", r"直线",
    r"circle", r"圆",
    r"polygon", r"多边形",
    r"text", r"文本",
    r"at", r"在",
    r"center", r"圆心",
    r"radius", r"半径",
    r"points", r"点集",
    r"object", r"对象",
]


class ScriptHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)

        self.rules = []

        # 关键字
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#1971c2"))
        kw_format.setFontWeight(QFont.Weight.Bold)

        for pat in KEYWORD_PATTERNS:
            self.rules.append((re.compile(pat), kw_format))

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
            it = pattern.globalMatch(text)

            while it.hasNext():
                m = it.next()
                self.setFormat(m.capturedStart(), m.capturedLength(), fmt)


class ScriptEditorDialog(QDialog):
    def __init__(self, canvas, button_obj, parent=None):
        super().__init__(parent)

        self.canvas = canvas
        self.button_obj = button_obj

        self.setWindowTitle(f"脚本编辑器 · {getattr(button_obj, 'name', '') or 'ScriptButton'}")
        self.resize(760, 560)

        layout = QVBoxLayout(self)

        self.editor = QPlainTextEdit()
        self.editor.setPlainText(button_obj.script)
        self.editor.setTabStopDistance(28)

        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(11)
        self.editor.setFont(font)

        self.highlighter = ScriptHighlighter(self.editor.document())

        layout.addWidget(self.editor, 1)

        btn_row = QHBoxLayout()

        run_btn = QPushButton("运行")
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")

        run_btn.clicked.connect(self._run)
        save_btn.clicked.connect(self._save)
        cancel_btn.clicked.connect(self.reject)

        btn_row.addStretch(1)
        btn_row.addWidget(run_btn)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)

        layout.addLayout(btn_row)

    def _save(self):
        self.button_obj.script = self.editor.toPlainText()
        self.canvas.doc.changed.emit()
        self.accept()

    def _run(self):
        # 运行时先保存当前文本
        self.button_obj.script = self.editor.toPlainText()
        self.canvas.doc.changed.emit()

        run_script(
            self.canvas.doc,
            self.button_obj.script,
            owner_id=self.button_obj.id,
            canvas=self.canvas
        )


def edit_script_button(canvas, button_obj):
    dlg = ScriptEditorDialog(canvas, button_obj, canvas)
    dlg.exec()