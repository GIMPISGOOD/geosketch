"""画布底部物理工具条：只显示 panel="physics_optics" 的工具。"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QToolButton, QHBoxLayout, QWidget

from core.registry import TOOL_REGISTRY
from ui.icons import build_tool_icon

BTN_SIZE = 42
BTN_ICON = 24


class PhysicsToolBar(QWidget):
    tool_chosen = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("physicsToolBar")
        self.setFixedHeight(52)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(6)

        group = QButtonGroup(self)
        group.setExclusive(True)

        self._buttons = []

        specs = [
            s for s in TOOL_REGISTRY
            if s.get("panel") == "physics_optics"
        ]

        for spec in specs:
            btn = QToolButton(self)
            btn.setIcon(build_tool_icon(spec))
            btn.setIconSize(QSize(BTN_ICON, BTN_ICON))
            btn.setFixedSize(BTN_SIZE, BTN_SIZE)
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(spec.get("hint") or spec["name"])
            btn.clicked.connect(
                lambda _=False, s=spec: self.tool_chosen.emit(s["cls"])
            )

            group.addButton(btn)
            layout.addWidget(btn)
            self._buttons.append((spec, btn))

        layout.addStretch(0)

        n = len(self._buttons)
        total_w = 20 + n * BTN_SIZE + max(0, n - 1) * 6
        self.setFixedWidth(max(total_w, 40))

        self.hide()

    def sync(self, tool) -> None:
        for spec, btn in self._buttons:
            btn.setChecked(type(tool) is spec["cls"])

    def refresh_icons(self) -> None:
        for spec, btn in self._buttons:
            btn.setIcon(build_tool_icon(spec))

    def refresh_from_settings(self, settings) -> None:
        enabled = bool(settings.get("physics.optics_enabled", False))
        self.setVisible(enabled and bool(self._buttons))