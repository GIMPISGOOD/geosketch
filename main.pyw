import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow
from ui import theme


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GeoSketch 几何画板")
    
    # 设置全局默认字体
    font = QFont()
    font.setFamilies(["Segoe UI", "PingFang SC", "Microsoft YaHei", "sans-serif"])
    font.setPointSize(10)
    app.setFont(font)
    
    # 应用主题系统生成的全局样式表（取代以前硬编码的 STYLE 字符串）
    app.setStyleSheet(theme.app_stylesheet())

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()