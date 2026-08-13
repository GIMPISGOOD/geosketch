# constraints/__init__.py

def inject():
    """将约束系统注入到 GeoSketch 核心中。"""
    try:
        from . import document_ext
        from . import select_ext
        from . import serialization
        from .ui import overlay, tools

        document_ext.patch_document()
        select_ext.patch_select_tool()
        serialization.patch_save_load()
        overlay.patch_canvas()

        # ★ 新增：注入“约束”菜单
        patch_main_window_menu()

        import logging
        logging.getLogger(__name__).info("✔ 几何约束求解器已加载")
        return True
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"✘ 几何约束求解器加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def patch_main_window_menu():
    """动态向 MainWindow 的菜单栏注入「约束」菜单。"""
    from ui.main_window import MainWindow
    from core.registry import TOOL_REGISTRY

    original_init = MainWindow.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        # 获取菜单栏
        mb = self.menuBar()

        # 创建“约束”菜单
        cm = mb.addMenu("约束(&C)")

        # 收集 panel="constraint" 的工具
        constraint_specs = sorted(
            [s for s in TOOL_REGISTRY if s.get("panel") == "constraint"],
            key=lambda s: s.get("order", 99)
        )

        # 添加菜单项
        for spec in constraint_specs:
            cm.addAction(self._actions[spec["cls"]])

        # 如果没有约束工具，显示占位项
        if not constraint_specs:
            e = cm.addAction("（暂无约束工具）")
            e.setEnabled(False)

    MainWindow.__init__ = new_init


# 模块被 import 时自动注入
inject()