import sys
import os
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow
from ui import theme


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


def load_constraints() -> None:
    """加载几何约束求解器扩展"""
    try:
        import constraints
    except Exception as e:
        print("无法加载几何约束求解器扩展，请确保已正确安装依赖。")
        print("错误信息:", e)


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GeoSketch 几何画板")
    font = QFont()
    font.setFamilies(["Segoe UI", "PingFang SC", "Microsoft YaHei", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(theme.app_stylesheet())
    # ★ 应用退出前安全终止所有后台采样线程
    app.aboutToQuit.connect(_shutdown_all_threads)
    win = MainWindow()
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".wgeo") and os.path.exists(sys.argv[1]):
        win.doc.load(sys.argv[1])
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    load_constraints()
    main()