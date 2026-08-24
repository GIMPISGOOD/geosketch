"""左侧悬浮工具栏：磨砂玻璃质感，按钮由 TOOL_REGISTRY 中 panel="rail" 的工具生成。"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QToolButton, QVBoxLayout, QWidget)
from core.registry import TOOL_REGISTRY
from ui.icons import build_tool_icon

BTN_SIZE = 42
BTN_ICON = 24


class ToolRail(QWidget):
    tool_chosen = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("toolRail")
        self.setFixedWidth(66)     # ★ 58 → 66

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(6)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self._buttons = []

        specs = [s for s in TOOL_REGISTRY if s.get("panel", "rail") == "rail"]
        for spec in specs:
            btn = QToolButton(self)
            btn.setIcon(build_tool_icon(spec))
            btn.setIconSize(QSize(BTN_ICON, BTN_ICON))
            btn.setFixedSize(BTN_SIZE, BTN_SIZE)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            tip = (f"{spec['name']}（{spec['shortcut']}）"
                   if spec["shortcut"] else spec["name"])
            btn.setToolTip(tip)
            btn.clicked.connect(
                lambda _=False, s=spec: self.tool_chosen.emit(s["cls"]))
            group.addButton(btn)
            layout.addWidget(btn, 0, Qt.AlignmentFlag.AlignHCenter)
            self._buttons.append((spec, btn))

        layout.addStretch(0)

        n = len(self._buttons)
        total_h = 10 + n * BTN_SIZE + (n - 1) * 6 + 10
        self.setFixedHeight(total_h)

    def sync(self, tool) -> None:
        for spec, btn in self._buttons:
            btn.setChecked(type(tool) is spec["cls"])

    def refresh_icons(self) -> None:
        for spec, btn in self._buttons:
            btn.setIcon(build_tool_icon(spec))