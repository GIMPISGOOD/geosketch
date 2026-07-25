import sys

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow

STYLE = """
    QMainWindow { background: #eef2f8; }
    QMenuBar { background: #fbfcfe; color: #2c3a4e;
               border-bottom: 1px solid #dde5ef; padding: 2px; }
    QMenuBar::item { padding: 5px 10px; border-radius: 6px; }
    QMenuBar::item:selected { background: #e7edf6; }
    QMenu { background: #ffffff; color: #2c3a4e; border: 1px solid #dde5ef; }
    QMenu::item { padding: 6px 24px; }
    QMenu::item:selected { background: #e7edf6; }
    QStatusBar { background: #fbfcfe; border-top: 1px solid #dde5ef; }
    QStatusBar QLabel { color: #5a6b82; }

    /* 磨砂玻璃：半透明白 + 亮边 + 圆角，叠在画布网格上由投影托起 */
    #toolRail, #zoomBar {
        background: rgba(255, 255, 255, 0.62);
        border: 1px solid rgba(255, 255, 255, 0.95);
        border-radius: 14px;
    }
    #toolRail QToolButton, #zoomBar QToolButton {
        border: none; background: transparent; border-radius: 10px;
        color: #33415c; font-size: 15px;
    }
    #toolRail QToolButton { padding: 7px; }
    #zoomBar  QToolButton { padding: 4px 9px; }
    #toolRail QToolButton:hover, #zoomBar QToolButton:hover {
        background: rgba(25, 113, 194, 0.10);
    }
    #toolRail QToolButton:checked { background: rgba(25, 113, 194, 0.16); }
    #zoomBar QLabel { color: #33415c; font-weight: 600; }
"""


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("GeoSketch 几何画板")
    font = QFont()
    font.setFamilies(["Segoe UI", "PingFang SC", "Microsoft YaHei"])
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(STYLE)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()