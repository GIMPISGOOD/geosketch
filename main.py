import sys
import os
from PySide6.QtCore import qInstallMessageHandler, QtMsgType
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui import theme
from core.settings import DEFAULTS  

def _shutdown_all_threads():
    """程序退出前安全终止所有后台线程。"""
    from geo.function_sampler import shutdown_sampler
    shutdown_sampler()
    # 隐函数采样器（可能不存在则跳过）
    try:
        from geo.implicit_sampler import shutdown_implicit_sampler
        shutdown_implicit_sampler()
    except ImportError:
        pass
    
def _qt_message_filter(msg_type, context, message):
    """过滤 Qt 内部的无害字体警告，避免控制台刷屏。"""
    # 过滤 DirectWrite 位图字体加载失败（Windows 遗留字体）
    if msg_type == QtMsgType.QtWarningMsg and "CreateFontFaceFromHDC" in message:
        return
    # 其余消息正常输出
    print(message)

def load_constraints() -> None:
    """加载几何约束求解器扩展"""
    try:
        import constraints
    except Exception as e:
        print("无法加载几何约束求解器扩展，请确保已正确安装依赖。")
        print("错误信息:", e)

def load_animation() -> None:
    """加载动画系统扩展"""
    try:
        import animation
    except Exception as e:
        print("无法加载动画系统扩展。")
        print("错误信息:", e)

def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GeoSketch 几何画板")
    # ── 使用 DEFAULTS 中的默认值初始化全局字体 ──
    font = QFont()
    families = DEFAULTS["appearance"]["ui_font_family"]
    font.setFamilies(families if isinstance(families, list) else [families])
    font.setPointSize(int(DEFAULTS["appearance"]["ui_font_size"]))
    app.setFont(font)
    app.setStyleSheet(theme.app_stylesheet())
    app.aboutToQuit.connect(_shutdown_all_threads)
    app.aboutToQuit.connect(lambda: win.doc._cleanup_temp_images())
    win = MainWindow()
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".wgeo") and os.path.exists(sys.argv[1]):
        win.doc.load(sys.argv[1])
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    load_constraints()
    load_animation()
    main()