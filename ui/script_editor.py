"""脚本编辑器 v3：集成 AI 补全 / 生成 + 日志面板。

新增功能：
  • 日志面板（print 输出、运行状态、AI 消息）
  • AI 代码补全（Ctrl+Space）
  • AI 代码生成（工具栏按钮）
  • print 输出重定向到日志面板（不再写入底层状态栏）
"""
import re
from PySide6.QtCore import Qt, QRect, QSize, QStringListModel, QTimer
from PySide6.QtGui import (QColor, QFont, QSyntaxHighlighter, QTextCharFormat,
                           QPainter, QTextCursor, QTextFormat, QShortcut,
                           QKeySequence)
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                               QPlainTextEdit, QPushButton, QWidget,
                               QTextEdit, QComboBox, QLabel, QMessageBox,
                               QCompleter, QApplication, QInputDialog,
                               QSplitter)

from core.scripting import run_script, parse
from core.scripting.errors import ScriptError
from core.scripting.functions import set_log_callback
from ui import theme


# ═══════════════ 1. 自动补全数据源 ═══════════════

KEYWORDS = [
    "if ",  "如果 ",  "elif ",  "否则如果 ",  "else ",  "否则 ",
    "repeat ",  "重复 ",  "for ",  "遍历 ",  "from ",  "从 ",  "to ",  "到 ",
    "func ",  "函数 ",  "return ",  "返回 ",
    "import ",  "导入 ",
    "wait ",  "等待 ",
    "delete ",  "删除 ",  "all ",  "所有 ",
    "global ",  "全局 ",
    "true ",  "真 ",  "false ",  "假 ",
    "and ",  "并且 ",  "or ",  "或者 ",  "not ",  "非 ",
    "__keep ",  "__allow_delete_user "
]

FUNCS = [
    "point ",  "segment ",  "line ",  "ray ",  "circle ",  "ellipse ",
    "polygon ",  "regular_polygon ",  "midpoint ",  "division_point ",
    "intersect ",  "text ",  "function ",  "parametric ",  "polar ",
    "distance ",  "length ",  "slope ",  "radius ",  "area ",  "perimeter ",
    "sin ",  "cos ",  "tan ",  "cot ",  "sec ",  "csc ",
    "arcsin ",  "arccos ",  "arctan ",  "asin ",  "acos ",  "atan ",
    "sinh ",  "cosh ",  "tanh ",
    "sqrt ",  "abs ",  "ln ",  "log ",  "exp ",
    "floor ",  "ceil ",  "round ",  "sign ",  "min ",  "max ",
    "print ",  "math ",  "geo ",  "draw ",  "doc "
]


def get_completions(doc):
    obj_names = list(getattr(doc, "names", {}).keys())
    libs = list(getattr(doc, "script_libs", {}).keys())
    return list(set(KEYWORDS + FUNCS + obj_names + libs))


# ═══════════════ 2. 脚本模板库 ═══════════════

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
        kw_format = QTextCharFormat()
        kw_format.setForeground(QColor("#1971c2"))
        kw_format.setFontWeight(QFont.Weight.Bold)
        for pat in KEYWORDS:
            self.rules.append(
                (re.compile(rf"\b{re.escape(pat)}\b"), kw_format))
        fn_format = QTextCharFormat()
        fn_format.setForeground(QColor("#9c36b5"))
        for pat in FUNCS:
            self.rules.append(
                (re.compile(rf"\b{re.escape(pat)}\b(?=\s*\()"), fn_format))
        num_format = QTextCharFormat()
        num_format.setForeground(QColor("#2f9e44"))
        self.rules.append((re.compile(r"\b\d+\.?\d*\b"), num_format))
        str_format = QTextCharFormat()
        str_format.setForeground(QColor("#e8590c"))
        self.rules.append((re.compile(r"\"[^\"]*\""), str_format))
        self.rules.append((re.compile(r"'[^']*'"), str_format))
        comment_format = QTextCharFormat()
        comment_format.setForeground(QColor("#868e96"))
        self.rules.append((re.compile(r"#.*"), comment_format))

    def highlightBlock(self, text):
        for pattern, fmt in self.rules:
            for match in pattern.finditer(text):
                self.setFormat(match.start(),
                               match.end() - match.start(), fmt)


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
        self.completer.setCompletionMode(
            QCompleter.CompletionMode.PopupCompletion)
        self.completer.setCaseSensitivity(
            Qt.CaseSensitivity.CaseInsensitive)
        self.completer.activated.connect(self.insert_completion)

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
            self.lineNumberArea.update(
                0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(
            QRect(cr.left(), cr.top(),
                  self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        bg = theme.PANEL_BG.name() if hasattr(theme, 'PANEL_BG') else "#f0f0f0"
        painter.fillRect(event.rect(), QColor(bg))
        block = self.firstVisibleBlock()
        blockNumber = block.blockNumber()
        top = int(self.blockBoundingGeometry(block)
                  .translated(self.contentOffset()).top())
        bottom = top + int(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                number = str(blockNumber + 1)
                fg = theme.SUBINK.name() if hasattr(theme, 'SUBINK') else "#888888"
                painter.setPen(QColor(fg))
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
            selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection, True)
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
            selection.format.setProperty(
                QTextFormat.Property.FullWidthSelection, True)
            cursor = self.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            cursor.movePosition(QTextCursor.MoveOperation.Down,
                                QTextCursor.MoveMode.MoveAnchor,
                                line_num - 1)
            selection.cursor = cursor
            self._error_selections.append(selection)
        self.highlightCurrentLine()

    def insert_completion(self, completion):
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
        if self.completer.popup().isVisible(): # pyright: ignore[reportOptionalMemberAccess]
            if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return,
                           Qt.Key.Key_Escape, Qt.Key.Key_Tab,
                           Qt.Key.Key_Backtab):
                e.ignore()
                return
        super().keyPressEvent(e)
        hasModifier = e.modifiers() != Qt.KeyboardModifier.NoModifier
        if hasModifier and e.text() == '':
            return
        completionPrefix = self.textUnderCursor()
        if (not completionPrefix
                or (not completionPrefix.isidentifier()
                    and not completionPrefix.isalnum())):
            self.completer.popup().hide() # pyright: ignore[reportOptionalMemberAccess]
            return
        if completionPrefix != self.completer.completionPrefix():
            self.completer.setCompletionPrefix(completionPrefix)
            popup = self.completer.popup()
            popup.setCurrentIndex(      # type: ignore
                self.completer.completionModel().index(0, 0))
        cr = self.cursorRect()
        cr.setWidth(
            self.completer.popup().sizeHintForColumn(0)# type: ignore
            + self.completer.popup().verticalScrollBar()# type: ignore
              .sizeHint().width())
        self.completer.complete(cr)


# ═══════════════ 6. 日志面板 ═══════════════

_MAX_LOG_LINES = 500

class LogPanel(QPlainTextEdit):
    """只读日志面板，显示 print 输出、运行状态、AI 消息。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setMaximumHeight(120)
        font = QFont("Consolas", 9)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.setFont(font)
        self.setPlaceholderText("日志输出…")
        self._line_count = 0

    def append_log(self, text: str, color: str | None = None):
        """追加一行日志。color 可选（用于区分类型）。"""
        if color:
            self.appendHtml(
                f'<span style="color:{color};">{text}</span>')
        else:
            self.appendPlainText(text)
        self._line_count += 1
        # 防止无限增长
        if self._line_count > _MAX_LOG_LINES:
            self.clear()
            self._line_count = 0

    def log_print(self, text: str):
        self.append_log(f"  print: {text}", "#2f9e44")

    def log_run(self, text: str, ok: bool = True):
        c = "#2f9e44" if ok else "#e03131"
        self.append_log(f"  {text}", c)

    def log_ai(self, text: str):
        self.append_log(f"  AI: {text}", "#1971c2")

    def log_error(self, text: str):
        self.append_log(f"  ✕ {text}", "#e03131")


# ═══════════════ 7. 编辑器主对话框 ═══════════════

class ScriptEditorDialog(QDialog):
    def __init__(self, canvas, button_obj, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.button_obj = button_obj
        self._ai_service = None

        self.setWindowTitle(
            f"脚本编辑器 · "
            f"{getattr(button_obj, 'name', '') or 'ScriptButton'}")
        self.resize(800, 650)
        layout = QVBoxLayout(self)

        # ── 顶部工具栏 ──
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("插入模板:"))
        self.template_combo = QComboBox()
        self.template_combo.addItem("-- 选择模板 --", None)
        for name, code in TEMPLATES.items():
            self.template_combo.addItem(name, code)
        self.template_combo.currentIndexChanged.connect(
            self._insert_template)
        top_bar.addWidget(self.template_combo, 1)

        # ★ AI 按钮
        self._ai_complete_btn = QPushButton("🤖 AI 补全")
        self._ai_generate_btn = QPushButton("🤖 AI 生成")
        self._ai_complete_btn.clicked.connect(self._ai_complete)
        self._ai_generate_btn.clicked.connect(self._ai_generate)
        top_bar.addWidget(self._ai_complete_btn)
        top_bar.addWidget(self._ai_generate_btn)
        layout.addLayout(top_bar)

        # ── 代码编辑区 ──
        self.editor = CodeEditor()
        self.editor.setPlainText(button_obj.script)
        self.highlighter = ScriptHighlighter(self.editor.document())
        layout.addWidget(self.editor, 1)

        # ── 日志面板 ──
        self._log = LogPanel()
        layout.addWidget(self._log)

        # ── 底部按钮栏 ──
        bottom_bar = QHBoxLayout()
        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: red; font-weight: bold;")
        bottom_bar.addWidget(self.status_lbl, 1)

        self._ai_status_lbl = QLabel("")
        bottom_bar.addWidget(self._ai_status_lbl)

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

        # ── 快捷键 ──
        QShortcut(QKeySequence("Ctrl+R"), self, self._run)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save)
        QShortcut(QKeySequence("Ctrl+Space"), self, self._ai_complete)

        self._update_completer()
        self._init_ai()

    # ── AI 初始化 ──────────────────────────────────

    def _init_ai(self):
        """按设置决定是否初始化 AI 服务。"""
        try:
            from core.ai_service import AIService
            svc = AIService(self.canvas.doc.settings, self)
            if not svc.is_configured():
                self._ai_complete_btn.setEnabled(False)
                self._ai_generate_btn.setEnabled(False)
                self._ai_status_lbl.setText("")
                return
            self._ai_service = svc
            svc.loaded.connect(self._on_ai_loaded)
            svc.load_failed.connect(self._on_ai_load_failed)
            svc.result_ready.connect(self._on_ai_result)
            svc.error.connect(self._on_ai_error)
            # 后台加载
            self._ai_status_lbl.setText("AI 加载中…")
            self._ai_complete_btn.setEnabled(False)
            self._ai_generate_btn.setEnabled(False)
            svc.ensure_loaded()
        except Exception:
            self._ai_complete_btn.setEnabled(False)
            self._ai_generate_btn.setEnabled(False)

    def _on_ai_loaded(self):
        self._ai_status_lbl.setText("AI ● 就绪")
        self._ai_status_lbl.setStyleSheet("color: #2f9e44;")
        self._ai_complete_btn.setEnabled(True)
        self._ai_generate_btn.setEnabled(True)

    def _on_ai_load_failed(self, msg: str):
        self._ai_status_lbl.setText("AI ✕ 不可用")
        self._ai_status_lbl.setStyleSheet("color: #e03131;")
        self._ai_complete_btn.setEnabled(False)
        self._ai_generate_btn.setEnabled(False)
        self._log.log_error(f"AI 加载失败: {msg}")

    def _on_ai_error(self, msg: str):
        self._log.log_error(f"AI 错误: {msg}")

    # ── AI 补全 ────────────────────────────────────
    
    def _ai_complete(self):
        if self._ai_service is None:
            return
        usage = self.canvas.doc.settings.get("ai.usage", "both")
        if usage == "generate":
            return
        cursor = self.editor.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.setPosition(self.editor.textCursor().position(),
                           QTextCursor.MoveMode.KeepAnchor)
        context = cursor.selectedText()
        max_chars = int(
            self.canvas.doc.settings.get("ai.context_tokens", 512)) * 4
        if len(context) > max_chars:
            context = context[-max_chars:]
        prompt = (
            "补全以下 GeoSketch DSL 代码。"
            "只输出需要补全的代码行，不要重复已有代码，"
            "不要解释，不要使用代码块标记。\n"
            + context
        )
        self._ai_status_lbl.setText("AI 思考中…")
        self._ai_service.request(prompt, "complete")

    # ── AI 生成 ────────────────────────────────────

    def _ai_generate(self):
        if self._ai_service is None:
            return
        usage = self.canvas.doc.settings.get("ai.usage", "both")
        if usage == "complete":
            return
        desc, ok = QInputDialog.getText(
            self, "AI 代码生成",
            "用自然语言描述你想要的几何图形：\n"
            "（例如：画一个等边三角形，边长为 5，再作它的外接圆）")
        if not ok or not desc.strip():
            return
        prompt = (
            f"根据以下描述，直接输出 GeoSketch DSL 代码。"
            f"不要解释，不要使用代码块标记，第一行就是代码。\n"
            f"描述：{desc.strip()}"
        )
        self._ai_status_lbl.setText("AI 生成中…")
        self._log.log_ai(f"生成请求: {desc.strip()}")
        self._ai_service.request(prompt, "generate")

    # ── AI 结果回调 ────────────────────────────────

    def _on_ai_result(self, text: str, mode: str):
        self._ai_status_lbl.setText("AI ● 就绪")
        self._ai_status_lbl.setStyleSheet("color: #2f9e44;")
        if not text.strip():
            self._log.log_ai("（无结果）")
            return
        if mode == "complete":
            # 直接插入到光标位置
            self.editor.insertPlainText(text)
            self._log.log_ai(f"补全: {text[:80]}…")
        elif mode == "generate":
            self._log.log_ai(f"生成结果:\n{text}")
            # 询问用户是否插入
            reply = QMessageBox.question(
                self, "AI 生成结果",
                "是否将生成的代码插入编辑器？",
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.editor.insertPlainText(text)

    # ── 日志回调（注入到 print） ──────────────────

    def _log_callback(self, text: str):
        self._log.log_print(text)

    # ── 原有功能 ──────────────────────────────────

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
        self.run_btn.setEnabled(False)
        self.run_btn.setText("运行中...")
        self._log.log_run("▶ 开始运行")
        QApplication.processEvents()

        # ★ 注入日志回调，print 输出到日志面板
        set_log_callback(self._log_callback)
        try:
            rt = run_script(
                self.canvas.doc,
                self.button_obj.script,
                owner_id=self.button_obj.id,
                canvas=self.canvas
            )
            if rt and rt.error:
                self.status_lbl.setText(f"运行错误: {rt.error}")
                self._log.log_run(f"✕ 运行错误: {rt.error}", ok=False)
                if hasattr(rt.error, 'line'):
                    self.editor.set_error_line(rt.error.line or 0)
            else:
                self.status_lbl.setText("✔ 运行成功")
                self.status_lbl.setStyleSheet(
                    "color: green; font-weight: bold;")
                self._log.log_run("✔ 运行成功")
        except Exception as e:
            self.status_lbl.setText(f"运行异常: {e}")
            self._log.log_run(f"✕ 运行异常: {e}", ok=False)
        finally:
            set_log_callback(None)    # ★ 恢复默认输出
            self.run_btn.setEnabled(True)
            self.run_btn.setText("运行 (Ctrl+R)")

    # ── 关闭时清理 ────────────────────────────────

    def reject(self):
        self._cleanup_ai()
        super().reject()

    def accept(self):
        self._cleanup_ai()
        super().accept()

    def closeEvent(self, event):
        self._cleanup_ai()
        super().closeEvent(event)

    def _cleanup_ai(self):
        if self._ai_service is not None:
            try:
                self._ai_service.unload()
            except Exception:
                pass
            self._ai_service = None


def edit_script_button(canvas, button_obj):
    dlg = ScriptEditorDialog(canvas, button_obj, canvas)
    dlg.exec()