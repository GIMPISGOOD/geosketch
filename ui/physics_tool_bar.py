"""画布底部物理工具条：支持自定义钉选工具与多模块扩展。"""
from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup, QToolButton, QHBoxLayout, QWidget,
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox, QLabel
)
from core.registry import TOOL_REGISTRY
from ui.icons import build_tool_icon
import qtawesome as qta

BTN_SIZE = 42
BTN_ICON = 24

class PinnedToolsConfigDialog(QDialog):
    """物理工具栏自定义配置对话框。"""
    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义物理工具栏")
        self.setMinimumSize(300, 400)
        self._settings = settings

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("勾选需要显示在底部工具栏的物理工具："))

        self._list = QListWidget()
        layout.addWidget(self._list)

        # 获取所有物理工具
        self._physics_specs = [
            s for s in TOOL_REGISTRY if s.get("panel", "").startswith("physics_")
        ]
        
        pinned = settings.get("physics.pinned_tools", [])

        for spec in self._physics_specs:
            item = QListWidgetItem(spec["name"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if spec["name"] in pinned else Qt.CheckState.Unchecked
            )
            # 存储模块信息用于显示
            module = spec.get("physics_module", "other")
            item.setToolTip(f"模块: {module}")
            self._list.addItem(item)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def get_pinned_tools(self):
        pinned = []
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                pinned.append(item.text())
        return pinned


class PhysicsToolBar(QWidget):
    tool_chosen = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("physicsToolBar")
        self.setFixedHeight(52)
        
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 6, 10, 6)
        self._layout.setSpacing(6)
        
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        
        # ★ 字典存储所有物理按钮，按需显隐
        self._all_buttons = {} 
        
        self._physics_specs = [
            s for s in TOOL_REGISTRY if s.get("panel", "").startswith("physics_")
        ]
        
        for spec in self._physics_specs:
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
            self._group.addButton(btn)
            self._layout.addWidget(btn)
            self._all_buttons[spec["name"]] = btn
            btn.hide() # 默认隐藏，由 refresh_from_settings 控制

        self._layout.addStretch(0)

        # ★ 新增：自定义配置按钮 (齿轮)
        self._config_btn = QToolButton(self)
        self._config_btn.setText("⚙")
        self._config_btn.setFont(self._config_btn.font())
        self._config_btn.setFixedSize(BTN_SIZE, BTN_SIZE)
        self._config_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._config_btn.setToolTip("自定义工具栏...")
        self._config_btn.clicked.connect(self._open_config)
        self._layout.addWidget(self._config_btn)

        self._update_size()
        self.hide()

    def _open_config(self):
        """打开自定义配置对话框。"""
        # 获取 settings 实例 (通过父级 canvas 获取)
        canvas = self.parent()
        if not hasattr(canvas, "doc"):
            return
            
        dlg = PinnedToolsConfigDialog(canvas.doc.settings, self) # type: ignore
        if dlg.exec():
            new_pinned = dlg.get_pinned_tools()
            assert canvas is not None
            canvas.doc.settings.set("physics.pinned_tools", new_pinned) # pyright: ignore[reportAttributeAccessIssue]
            # 强制触发刷新
            self.refresh_from_settings(canvas.doc.settings) # pyright: ignore[reportAttributeAccessIssue]

    def _update_size(self):
        visible_count = sum(1 for btn in self._all_buttons.values() if btn.isVisible())
        # 加上配置按钮
        total_btns = visible_count + 1 
        total_w = 20 + total_btns * BTN_SIZE + max(0, total_btns - 1) * 6
        self.setFixedWidth(max(total_w, 80))

    def sync(self, tool) -> None:
        for spec in self._physics_specs:
            btn = self._all_buttons.get(spec["name"])
            if btn:
                btn.setChecked(type(tool) is spec["cls"])

    def refresh_icons(self) -> None:
        for spec in self._physics_specs:
            btn = self._all_buttons.get(spec["name"])
            if btn:
                btn.setIcon(build_tool_icon(spec))

    def refresh_from_settings(self, settings) -> None:
        # 获取全局物理开关和钉选列表
        optics_enabled = bool(settings.get("physics.optics_enabled", False))
        pinned = settings.get("physics.pinned_tools", [])
        
        # 未来可扩展：检查各自模块的开关，如 mechanics_enabled
        
        any_visible = False
        for spec in self._physics_specs:
            btn = self._all_buttons.get(spec["name"])
            if not btn:
                continue
                
            # 判断是否应该显示：在钉选列表中 且 所属模块已启用
            is_pinned = spec["name"] in pinned
            module = spec.get("physics_module", "optics")
            
            # 目前只有 optics 模块，未来可在此处增加其他模块的开关判断
            module_enabled = optics_enabled if module == "optics" else False 
            
            should_show = is_pinned and module_enabled
            btn.setVisible(should_show)
            if should_show:
                any_visible = True

        # 配置按钮始终显示（只要有任何物理工具注册）
        self._config_btn.setVisible(bool(self._physics_specs))
        
        self._update_size()
        self.setVisible(any_visible or bool(self._physics_specs))