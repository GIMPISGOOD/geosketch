"""脚本库管理器：管理 doc.script_libs。
限制：库文件只能包含 func 定义和 import，不允许执行几何操作。
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                               QPushButton, QInputDialog, QMessageBox, QPlainTextEdit, QLabel)
from PySide6.QtGui import QFont

from core.scripting import parse
from core.scripting.errors import ScriptError
from core.scripting.ast_nodes import FuncDef, Import


class LibraryEditorDialog(QDialog):
    """受限的库编辑器"""
    def __init__(self, name, source, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"编辑库: {name}")
        self.resize(600, 500)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("⚠️ 库文件只能包含 func 定义和 import 语句，不能包含执行代码。"))
        
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(source)
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.editor.setFont(font)
        layout.addWidget(self.editor, 1)
        
        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存")
        cancel_btn = QPushButton("取消")
        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addStretch(1)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)
        
    def get_source(self):
        return self.editor.toPlainText()

    def accept(self):
        source = self.get_source()
        try:
            prog = parse(source)
            # ★ 校验：只允许 FuncDef 和 Import
            for stmt in prog.statements:
                if not isinstance(stmt, (FuncDef, Import)):
                    raise ScriptError("库文件只能包含 func 定义和 import，不能包含执行语句。", stmt.line)
            super().accept()
        except ScriptError as e:
            QMessageBox.critical(self, "语法校验失败", str(e))
        except Exception as e:
            QMessageBox.critical(self, "解析错误", str(e))


class ScriptLibraryManager(QDialog):
    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self.setWindowTitle("脚本库管理器")
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        self.list = QListWidget()
        layout.addWidget(self.list, 1)
        
        btn_row = QHBoxLayout()
        new_btn = QPushButton("新建库")
        edit_btn = QPushButton("编辑")
        del_btn = QPushButton("删除")
        close_btn = QPushButton("关闭")
        
        new_btn.clicked.connect(self._new)
        edit_btn.clicked.connect(self._edit)
        del_btn.clicked.connect(self._delete)
        close_btn.clicked.connect(self.accept)
        
        btn_row.addWidget(new_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)
        
        self.list.itemDoubleClicked.connect(self._edit)
        self._refresh()
        
    def _refresh(self):
        self.list.clear()
        libs = getattr(self.doc, "script_libs", {})
        for name in libs.keys():
            self.list.addItem(name)
            
    def _new(self):
        name, ok = QInputDialog.getText(self, "新建库", "库名称 (例如 my_math):")
        if ok and name.strip():
            name = name.strip()
            if not hasattr(self.doc, "script_libs"):
                self.doc.script_libs = {}
            if name in self.doc.script_libs:
                QMessageBox.warning(self, "提示", "库名称已存在。")
                return
            
            dlg = LibraryEditorDialog(name, "", self)
            if dlg.exec():
                self.doc.script_libs[name] = dlg.get_source()
                self.doc.changed.emit()
                self._refresh()
                
    def _edit(self):
        item = self.list.currentItem()
        if not item: return
        name = item.text()
        source = self.doc.script_libs.get(name, "")
        
        dlg = LibraryEditorDialog(name, source, self)
        if dlg.exec():
            self.doc.script_libs[name] = dlg.get_source()
            self.doc.changed.emit()
            
    def _delete(self):
        item = self.list.currentItem()
        if not item: return
        name = item.text()
        
        reply = QMessageBox.question(self, "删除库", f"确定删除库 '{name}' 吗？")
        if reply == QMessageBox.StandardButton.Yes:
            del self.doc.script_libs[name]
            self.doc.changed.emit()
            self._refresh()