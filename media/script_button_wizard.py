"""脚本按钮向导：降低脚本按钮使用门槛。

用户不需要理解 __keep / __allow_delete_user / 脚本语法细节。
向导提供四种动作：
1. 创建示例图形
2. 清空脚本创建的对象
3. 显示提示
4. 自定义脚本
"""

import re

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


DEFAULT_CUSTOM_SCRIPT = """# 示例脚本：
# point(x, y) 创建点
# segment(A, B) 创建线段
# circle(O, r) 创建圆

A = point(0, 0)
B = point(3, 0)
segment(A, B)
"""


class ScriptButtonWizard(QDialog):
    """脚本按钮创建 / 简单编辑向导。"""

    def __init__(self, canvas, obj=None, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.obj = obj

        self.setWindowTitle("脚本按钮")
        self.setMinimumWidth(560)
        self.resize(620, 560)

        self.bg_color = QColor(getattr(obj, "color", "#1971c2") if obj else "#1971c2")
        self.text_color = QColor(getattr(obj, "text_color", "#ffffff") if obj else "#ffffff")

        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        # ---------- 按钮文字 ----------
        layout.addWidget(QLabel("按钮文字"))
        self.text_edit = QLineEdit(getattr(obj, "text", "运行") if obj else "运行")
        layout.addWidget(self.text_edit)

        # ---------- 动作类型 ----------
        layout.addWidget(QLabel("点击按钮后执行的动作"))
        self.action_combo = QComboBox()
        self.action_combo.addItems(
            [
                "创建示例图形",
                "清空脚本创建的对象",
                "显示提示",
                "自定义脚本",
            ]
        )
        self.action_combo.setCurrentIndex(0 if obj is None else 3)
        self.action_combo.currentIndexChanged.connect(lambda *_: self._sync_ui())
        layout.addWidget(self.action_combo)

        # ---------- 说明 ----------
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)

        # ---------- 高级选项（用友好文案包装） ----------
        self.keep_chk = QCheckBox("运行后保留创建的对象")
        self.keep_chk.setChecked(True)

        self.allow_delete_chk = QCheckBox("允许删除已有用户对象")
        self.allow_delete_chk.setChecked(False)

        layout.addWidget(self.keep_chk)
        layout.addWidget(self.allow_delete_chk)

        # ---------- 提示消息 ----------
        self.message_label = QLabel("提示内容")
        self.message_edit = QLineEdit("你好，GeoSketch！")
        layout.addWidget(self.message_label)
        layout.addWidget(self.message_edit)

        # ---------- 自定义脚本 ----------
        self.script_label = QLabel("自定义脚本")
        self.script_edit = QPlainTextEdit(DEFAULT_CUSTOM_SCRIPT)
        layout.addWidget(self.script_label)
        layout.addWidget(self.script_edit, 1)

        # ---------- 颜色 ----------
        color_row = QHBoxLayout()

        color_row.addWidget(QLabel("背景色"))
        self.bg_btn = QPushButton()
        self.bg_btn.setFixedSize(60, 22)
        self.bg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.bg_btn.clicked.connect(self._pick_bg_color)
        color_row.addWidget(self.bg_btn)

        color_row.addSpacing(14)

        color_row.addWidget(QLabel("文字颜色"))
        self.text_btn = QPushButton()
        self.text_btn.setFixedSize(60, 22)
        self.text_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.text_btn.clicked.connect(self._pick_text_color)
        color_row.addWidget(self.text_btn)

        color_row.addStretch(1)
        layout.addLayout(color_row)

        self._paint_color_buttons()

        # ---------- 按钮 ----------
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # ---------- 编辑已有按钮时预填 ----------
        if obj is not None:
            script = getattr(obj, "script", "") or ""
            self.keep_chk.setChecked("__keep = false" not in script)
            self.allow_delete_chk.setChecked("__allow_delete_user = true" in script)
            self.script_edit.setPlainText(self._strip_flags(script))
            self.action_combo.setCurrentIndex(3)

        self._sync_ui()

    # ================= UI 同步 =================

    def _sync_ui(self):
        idx = self.action_combo.currentIndex()

        self.message_label.setVisible(idx == 2)
        self.message_edit.setVisible(idx == 2)

        self.script_label.setVisible(idx == 3)
        self.script_edit.setVisible(idx == 3)

        if idx == 0:
            self.note_label.setText(
                "点击按钮后会创建一组示例点、线段和圆。\n"
                "适合快速体验脚本按钮。"
            )
        elif idx == 1:
            self.note_label.setText(
                "点击按钮后会删除由脚本按钮创建的对象。\n"
                "不会删除你手动创建的对象，除非勾选“允许删除已有用户对象”。"
            )
        elif idx == 2:
            self.note_label.setText(
                "点击按钮后会在状态栏输出一条提示信息。"
            )
        else:
            self.note_label.setText(
                "使用自定义脚本。\n"
                "可以使用 point / segment / circle / line / text 等函数。"
            )

    def _paint_color_buttons(self):
        self.bg_btn.setStyleSheet(
            f"background:{self.bg_color.name()};"
            f"border:1px solid rgba(0,0,0,0.30);"
            f"border-radius:5px;"
        )
        self.text_btn.setStyleSheet(
            f"background:{self.text_color.name()};"
            f"border:1px solid rgba(0,0,0,0.30);"
            f"border-radius:5px;"
        )

    def _pick_bg_color(self):
        c = QColorDialog.getColor(self.bg_color, self, "选择按钮背景色")
        if c.isValid():
            self.bg_color = c
            self._paint_color_buttons()

    def _pick_text_color(self):
        c = QColorDialog.getColor(self.text_color, self, "选择按钮文字颜色")
        if c.isValid():
            self.text_color = c
            self._paint_color_buttons()

    # ================= 脚本生成 =================

    @staticmethod
    def _strip_flags(script: str) -> str:
        return re.sub(
            r"^\s*__(keep|allow_delete_user)\s*=.*$\n?",
            "",
            script,
            flags=re.M,
        ).strip()

    def _example_lines(self):
        return [
            "# 示例图形",
            "O = point(0, 0)",
            "A = point(3, 0)",
            "B = point(0, 2)",
            "segment(O, A)",
            "segment(A, B)",
            "segment(B, O)",
            "circle(O, 1)",
        ]

    def _build_script(self) -> str:
        lines = []

        if self.keep_chk.isChecked():
            lines.append("__keep = true")
        else:
            lines.append("__keep = false")

        if self.allow_delete_chk.isChecked():
            lines.append("__allow_delete_user = true")

        idx = self.action_combo.currentIndex()

        if idx == 0:
            lines.extend(self._example_lines())

        elif idx == 1:
            lines.append("# 清空脚本创建的对象")
            lines.append("delete 脚本创建")

        elif idx == 2:
            msg = self.message_edit.text().strip().replace('"', '\\"')
            lines.append(f'print("{msg}")')

        else:
            user_script = self.script_edit.toPlainText().strip()
            user_script = self._strip_flags(user_script)
            if user_script:
                lines.append(user_script)

        return "\n".join(lines)

    # ================= 应用结果 =================

    def apply_to(self, obj):
        obj.text = self.text_edit.text().strip() or "运行"
        obj.color = self.bg_color.name()
        obj.text_color = self.text_color.name()
        obj.script = self._build_script()