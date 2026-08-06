import sys
import os

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui import theme

from geo.function_sampler import shutdown_sampler


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GeoSketch 几何画板")

    font = QFont()
    font.setFamilies(["Segoe UI", "PingFang SC", "Microsoft YaHei", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)

    app.setStyleSheet(theme.app_stylesheet())

    # ★ 应用退出前安全终止后台采样线程
    app.aboutToQuit.connect(shutdown_sampler)

    win = MainWindow()

    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".wgeo") and os.path.exists(sys.argv[1]):
        win.doc.load(sys.argv[1])

    win.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()