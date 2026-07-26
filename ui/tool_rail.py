"""左侧悬浮工具栏：磨砂玻璃质感，按钮由 TOOL_REGISTRY 中 panel="rail" 的工具生成。
支持主题切换时的图标热刷新。"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QToolButton, QVBoxLayout, QWidget)

from core.registry import TOOL_REGISTRY
from ui.icons import build_tool_icon


class ToolRail(QWidget):
    tool_chosen = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolRail")
        self.setFixedWidth(58)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(7, 10, 7, 10)
        layout.setSpacing(4)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._buttons = []  # 记录 (spec, btn) 用于换肤和同步状态
        
        # 只收集归属于左侧面板 (rail) 的工具
        specs = [s for s in TOOL_REGISTRY if s.get("panel", "rail") == "rail"]
        for spec in specs:
            btn = QToolButton(self)
            btn.setIcon(build_tool_icon(spec))
            btn.setIconSize(QSize(26, 26))
            btn.setCheckable(True)
            tip = f"{spec['name']}（{spec['shortcut']}）" if spec["shortcut"] else spec["name"]
            btn.setToolTip(tip)
            btn.clicked.connect(lambda _=False, s=spec: self.tool_chosen.emit(s["cls"]))
            group.addButton(btn)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._buttons.append((spec, btn))
            
        layout.addStretch(1)

    def sync(self, tool) -> None:
        """外部切换工具时（如快捷键），同步按钮选中态。"""
        for spec, btn in self._buttons:
            btn.setChecked(type(tool) is spec["cls"])

    def refresh_icons(self) -> None:
        """换肤时调用：重新生成并设置图标，使颜色跟随新主题。"""
        for spec, btn in self._buttons:
            btn.setIcon(build_tool_icon(spec))