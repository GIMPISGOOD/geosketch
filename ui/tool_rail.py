"""左侧悬浮工具栏：磨砂玻璃质感，按钮完全由 TOOL_REGISTRY 生成。
半透明白底叠在画布网格之上 + 柔和投影，形成毛玻璃观感。"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QButtonGroup, QGraphicsDropShadowEffect,
                               QToolButton, QVBoxLayout, QWidget)

from core.registry import TOOL_REGISTRY
from ui.icons import build_tool_icon


class ToolRail(QWidget):
    tool_chosen = Signal(object)          # 发出工具类

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolRail")    # QSS 锚点（见 main.py）
        self.setFixedWidth(58)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 10, 7, 10)
        layout.setSpacing(4)

        group = QButtonGroup(self)          # 互斥组：永远恰好一个选中
        group.setExclusive(True)
        self._buttons: list[tuple[type, QToolButton]] = []

        for spec in TOOL_REGISTRY:
            btn = QToolButton(self)
            btn.setIcon(build_tool_icon(spec))
            btn.setIconSize(QSize(26, 26))
            btn.setCheckable(True)
            tip = f"{spec['name']}（{spec['shortcut']}）" if spec["shortcut"] else spec["name"]
            btn.setToolTip(tip)
            # triggered 会传 bool，用 _=False 吃掉，避免顶掉 spec
            btn.clicked.connect(lambda _=False, s=spec: self.tool_chosen.emit(s["cls"]))
            group.addButton(btn)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._buttons.append((spec["cls"], btn))

        layout.addStretch(1)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(35, 60, 92, 46))
        self.setGraphicsEffect(shadow)

    def sync(self, tool) -> None:
        """外部切换工具时（快捷键），同步按钮选中态。"""
        for cls, btn in self._buttons:
            btn.setChecked(type(tool) is cls)