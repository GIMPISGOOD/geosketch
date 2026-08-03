import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui import theme


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GeoSketch 几何画板")
    font = QFont()
    font.setFamilies(["Segoe UI", "PingFang SC", "Microsoft YaHei", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(theme.app_stylesheet())

    win = MainWindow()
    # ★ 命令行第一个参数若为 .wgeo，直接载入（启动器靠这个打开课件草图）
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".wgeo"):
        win.doc.load(sys.argv[1])
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()