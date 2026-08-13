"""几何约束求解器扩展入口。

设计原则：
- 删除本包即可完全卸载，不影响任何原有功能
- 通过 Monkey Patch 注入，不修改原有文件
- 约束类型自动注册：在 types/ 下新建文件即可扩展
"""
import importlib
import pkgutil
import logging

logger = logging.getLogger(__name__)


def inject():
    """将约束系统注入到 GeoSketch 核心中。"""
    try:
        # 1. 自动扫描 types/ 子包，触发所有约束类型注册
        from . import types
        for _m in pkgutil.iter_modules(types.__path__):
            importlib.import_module(f"{types.__name__}.{_m.name}")

        # 2. 注入 Document 扩展（constraints 列表、solve_constraints 等）
        from . import document_ext
        document_ext.patch_document()

        # 3. 注入 SelectTool 扩展（拖动时触发约束求解）
        from . import select_ext
        select_ext.patch_select_tool()

        # 4. 注入序列化扩展（保存/加载 constraints.json）
        from . import serialization
        serialization.patch_save_load()

        # 5. 注入 Canvas 渲染扩展（绘制约束标记）
        from .ui import overlay
        overlay.patch_canvas()

        # 6. 注入 UI 工具（注册到 TOOL_REGISTRY，出现在「约束」菜单）
        from .ui import tools  # noqa: F401  导入即触发注册

        logger.info("✔ 几何约束求解器已加载")
        return True

    except Exception as e:
        logger.warning(f"✘ 几何约束求解器加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


# 模块被 import 时自动注入
inject()