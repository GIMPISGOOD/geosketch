"""动画系统顶层包。
删除本包即可完全卸载动画功能，不影响原有系统。
★ 不再做猴子补丁。动画序列化已原生集成到 core/document.py。
"""
import logging

logger = logging.getLogger(__name__)


def inject():
    try:
        # ★ 不再调用 serialization.patch_document()
        # ★ 不再调用 patch_main_window()

        from . import tracks  # noqa: F401
        from . import recorder  # noqa: F401

        logger.info("✔ 动画系统已加载（含录制、预设、中文翻译）")
        return True
    except Exception as e:
        logger.warning(f"✘ 动画系统加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


inject()