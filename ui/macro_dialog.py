"""宏管理器对话框。"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
    QPushButton, QInputDialog, QMessageBox
)


class MacroDialog(QDialog):
    def __init__(self, manager, parent=None):
        super().__init__(parent)

        self.manager = manager
        self.doc = manager.doc

        self.setWindowTitle("宏管理器")
        self.resize(460, 380)

        layout = QVBoxLayout(self)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        btn_row = QHBoxLayout()

        play_btn = QPushButton("回放")
        rename_btn = QPushButton("重命名")
        delete_btn = QPushButton("删除")
        close_btn = QPushButton("关闭")

        play_btn.clicked.connect(self._play)
        rename_btn.clicked.connect(self._rename)
        delete_btn.clicked.connect(self._delete)
        close_btn.clicked.connect(self.accept)

        btn_row.addWidget(play_btn)
        btn_row.addWidget(rename_btn)
        btn_row.addWidget(delete_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        self.list.itemDoubleClicked.connect(lambda *_: self._play())

        self._refresh()

    # -------------------- 基础 --------------------

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

    # -------------------- 按钮 --------------------

    def _play(self):
        index = self._selected_index()

        if index is None:
            return

        if self.manager.is_recording():
            QMessageBox.information(
                self,
                "宏",
                "正在录制宏，请先停止录制再回放。"
            )
            return

        self.manager.play(self._macros()[index])

    def _rename(self):
        index = self._selected_index()

        if index is None:
            return

        old_name = self._macros()[index].get("name", "")

        name, ok = QInputDialog.getText(
            self,
            "重命名宏",
            "宏名称：",
            text=old_name
        )

        if ok and name.strip():
            self.manager.rename_macro(index, name.strip())
            self._refresh()

    def _delete(self):
        index = self._selected_index()

        if index is None:
            return

        name = self._macros()[index].get("name", f"宏 {index + 1}")

        reply = QMessageBox.question(
            self,
            "删除宏",
            f"确定删除宏「{name}」吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.manager.delete_macro(index)
            self._refresh()