"""几何约束求解器扩展包。
删除本包即可完全卸载约束功能，不影响原有系统。
"""
import importlib
import pkgutil
import logging

logger = logging.getLogger(__name__)

def inject():
    try:
        # 1. 自动扫描 types/ 子包，触发所有约束类型注册
        from . import types
        for _m in pkgutil.iter_modules(types.__path__):
            importlib.import_module(f"{types.__name__}.{_m.name}")

        # 2. 注入 Document 扩展
        from . import document_ext
        document_ext.patch_document()

        # 3. 注入 SelectTool 扩展
        from . import select_ext
        select_ext.patch_select_tool()

        # 4. 注入序列化扩展
        from . import serialization
        serialization.patch_save_load()

        # 5. 注入 UI 工具（注册到 TOOL_REGISTRY）
        from .ui import tools  # noqa: F401

        # 6. 注入 Canvas 渲染
        from .ui import overlay
        overlay.patch_canvas()

        # ★ 7. 零侵入图标注入：动态向全局图标字典追加约束专属图标
        from ui.icons import TOOL_ICON_KEYS
        TOOL_ICON_KEYS.update({
            "constraint_horizontal": ("fa5s.arrows-alt-h", "mdi.arrow-expand-horizontal"),
            "constraint_vertical": ("fa5s.arrows-alt-v", "mdi.arrow-expand-vertical"),
            "constraint_angle": ("fa5s.drafting-compass", "mdi.angle-acute"),
            "constraint_parallel": ("fa5s.equals", "mdi.vector-parallel"),
            "constraint_perpendicular": ("mdi.angle-right", "fa5s.drafting-compass"),
            "constraint_collinear": ("mdi.vector-line", "fa5s.minus"),
        })

        # 8. 动态向 MainWindow 的菜单栏注入「约束」菜单
        patch_main_window_menu()

        logger.info("✔ 几何约束求解器已加载 (包含 8 种核心约束)")
        return True
    except Exception as e:
        logger.warning(f"✘ 几何约束求解器加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def patch_main_window_menu():
    from ui.main_window import MainWindow
    from core.registry import TOOL_REGISTRY

    original_init = MainWindow.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        mb = self.menuBar()
        cm = mb.addMenu("约束(&C)")
        
        constraint_specs = sorted(
            [s for s in TOOL_REGISTRY if s.get("panel") == "constraint"],
            key=lambda s: s.get("order", 99)
        )
        for spec in constraint_specs:
            cm.addAction(self._actions[spec["cls"]])

        if not constraint_specs:
            e = cm.addAction("（暂无约束工具）")
            e.setEnabled(False)

        # 将“约束”菜单移动到“构造”或“工具”菜单之后
        for i, action in enumerate(mb.actions()):
            if action.text() in ("构造(&C)", "工具(&T)"):
                mb.removeAction(cm.menuAction())
                mb.insertMenu(mb.actions()[i + 1], cm)
                break

    setattr(MainWindow, "__init__", new_init)

inject()