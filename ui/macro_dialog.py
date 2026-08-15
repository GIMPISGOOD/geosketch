
"""宏管理器对话框：回放 / 重命名 / 删除 / 转为脚本。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QInputDialog, QMessageBox,
    QPlainTextEdit, QLabel, QApplication
)


class ScriptPreviewDialog(QDialog):
    """脚本预览对话框：显示转换后的脚本，支持一键复制。"""

    def __init__(self, script: str, macro_name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"宏转脚本 · {macro_name}" if macro_name else "宏转脚本")
        self.resize(640, 520)

        layout = QVBoxLayout(self)

        # 提示
        tip = QLabel("以下是由宏自动生成的脚本代码，可直接复制使用或在脚本编辑器中进一步修改。")
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #5a6b82; font-size: 12px; margin-bottom: 6px;")
        layout.addWidget(tip)

        # 代码区
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(script)
        self.editor.setReadOnly(True)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        self.editor.setTabStopDistance(28)
        layout.addWidget(self.editor, 1)

        # 统计
        lines = script.split("\n")
        total = len(lines)
        supported = sum(1 for l in lines if l.strip() and not l.strip().startswith("#"))
        comments = sum(1 for l in lines if l.strip().startswith("#"))
        self.stats_label = QLabel(f"共 {total} 行 · {supported} 行有效代码 · {comments} 行注释/提示")
        self.stats_label.setStyleSheet("color: #8a8f98; font-size: 11px;")
        layout.addWidget(self.stats_label)

        # 按钮
        btn_row = QHBoxLayout()
        copy_btn = QPushButton("📋 复制全部")
        copy_btn.clicked.connect(self._copy)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_row.addStretch(1)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _copy(self):
        QApplication.clipboard().setText(self.editor.toPlainText())
        self.stats_label.setText("✔ 已复制到剪贴板")


class MacroDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.doc = manager.doc
        self.setWindowTitle("宏管理器")
        self.resize(520, 400)

        layout = QVBoxLayout(self)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        btn_row = QHBoxLayout()
        play_btn = QPushButton("▶ 回放")
        rename_btn = QPushButton("✏ 重命名")
        delete_btn = QPushButton("🗑 删除")
        to_script_btn = QPushButton("📜 转为脚本")
        to_script_btn.setStyleSheet("font-weight: bold;")
        close_btn = QPushButton("关闭")

        play_btn.clicked.connect(self._play)
        rename_btn.clicked.connect(self._rename)
        delete_btn.clicked.connect(self._delete)
        to_script_btn.clicked.connect(self._to_script)
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(play_btn)
        btn_row.addWidget(rename_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addWidget(to_script_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self.list.itemDoubleClicked.connect(lambda *_: self._play())
        self._refresh()

    # ─────────────── 基础 ───────────────
    def _macros(self):
        return getattr(self.doc, "macros", [])

    def _refresh(self):
        self.list.clear()
        for i, m in enumerate(self._macros()):
            name = m.get("name", f"宏 {i + 1}")
            count = len(m.get("commands", []))
            self.list.addItem(f"{name}（{count} 步）")

    def _selected_index(self):
        row = self.list.currentRow()
        macros = self._macros()
        if 0 <= row < len(macros):
            return row
        return None

    # ─────────────── 回放 ───────────────
    def _play(self):
        index = self._selected_index()
        if index is None:
            return
        if self.manager.is_recording():
            QMessageBox.information(self, "宏", "正在录制宏，请先停止录制再回放。")
            return
        self.manager.play(self._macros()[index])

    # ─────────────── 重命名 ───────────────
    def _rename(self):
        index = self._selected_index()
        if index is None:
            return
        old_name = self._macros()[index].get("name", "")
        name, ok = QInputDialog.getText(self, "重命名宏", "宏名称：", text=old_name)
        if ok and name.strip():
            self.manager.rename_macro(index, name.strip())
            self._refresh()

    # ─────────────── 删除 ───────────────
    def _delete(self):
        index = self._selected_index()
        if index is None:
            return
        name = self._macros()[index].get("name", f"宏 {index + 1}")
        reply = QMessageBox.question(
            self, "删除宏", f"确定删除宏「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.delete_macro(index)
            self._refresh()

    # ─────────────── 转为脚本 ───────────────
    def _to_script(self):
        index = self._selected_index()
        if index is None:
            QMessageBox.information(self, "提示", "请先选择一个宏。")
            return

        macro = self._macros()[index]
        macro_name = macro.get("name", f"宏 {index + 1}")

        try:
            from core.scripting.macro_converter import macro_to_script
            script = macro_to_script(macro, keep=True)
        except Exception as e:
            QMessageBox.critical(self, "转换失败", f"宏转脚本时出错：\n{e}")
            return

        if not script.strip():
            QMessageBox.warning(self, "提示", "该宏为空，无法转换。")
            return

        # 弹出预览对话框
        dlg = ScriptPreviewDialog(script, macro_name, self)
        dlg.exec()