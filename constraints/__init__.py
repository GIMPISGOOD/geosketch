"""几何约束求解器扩展包。
删除本包即可完全卸载约束功能，不影响原有系统。
★ 不再做猴子补丁。约束逻辑已原生集成到 core/document.py。
"""
import importlib
import pkgutil
import logging

logger = logging.getLogger(__name__)


def inject():
    try:
        # 加载所有约束类型（触发 @register_constraint）
        from . import types
        for _m in pkgutil.iter_modules(types.__path__):
            importlib.import_module(f"{types.__name__}.{_m.name}")

        # ★ 不再调用 document_ext.patch_document()
        # ★ 不再调用 select_ext.patch_select_tool()
        # ★ 不再调用 serialization.patch_save_load()

        from .ui import tools  # noqa: F401  注册约束工具
        # ★ 不再调用 overlay.patch_canvas()

        from ui.icons import TOOL_ICON_KEYS
        TOOL_ICON_KEYS.update({
            "constraint_horizontal": (
                "fa5s.arrows-alt-h", "mdi.arrow-expand-horizontal"),
            "constraint_vertical": (
                "fa5s.arrows-alt-v", "mdi.arrow-expand-vertical"),
            "constraint_angle": (
                "fa5s.drafting-compass", "mdi.angle-acute"),
            "constraint_parallel": (
                "fa5s.equals", "mdi.vector-parallel"),
            "constraint_perpendicular": (
                "mdi.angle-right", "fa5s.drafting-compass"),
            "constraint_collinear": (
                "mdi.vector-line", "fa5s.minus"),
            "constraint_tangent": (
                "fa5s.circle-notch", "mdi.circle-double"),
        })

        # ★ 不再调用 patch_main_window_menu()

        logger.info("✔ 几何约束求解器已加载 (包含 8 种核心约束)")
        return True
    except Exception as e:
        logger.warning(f"✘ 几何约束求解器加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


inject()