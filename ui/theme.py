"""多主题系统：内置 4 套主题，运行时动态切换。

所有渲染代码照旧写 theme.XXX —— 模块级 __getattr__（PEP 562）
始终返回当前主题的颜色，换肤时无需触碰任何绘制代码。
"""
from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont, QPen


def _c(v):
    """hex 字符串或 (r,g,b,a) 元组 → QColor"""
    return QColor(v) if isinstance(v, str) else QColor(*v)


THEMES = {
    "纸白": {
        "BG_TOP": "#f8fafd", "BG_BOTTOM": "#eaeff7",
        "GRID_MINOR": (96, 125, 168, 26), "GRID_MAJOR": (96, 125, 168, 62),
        "AXIS": "#33517e",
        "POINT_FILL": "#f08c00", "POINT_RING": "#ffffff",
        "SEGMENT": "#1971c2", "LINE": "#495057", "RAY": "#0b7285",
        "CIRCLE": "#2f9e44", "POLYGON": "#ff6b6b", "INTERSECT": "#0c8599",
        "MEASURE": "#e8590c", "SELECTED": "#e64980", "PREVIEW": "#f08c00",
        "LABEL": "#46566e", "ICON_INK": "#33415c", "ACCENT": "#1971c2",
        "INK": "#2c3a4e", "SUBINK": "#5a6b82",
        "PANEL_BG": "rgba(255,255,255,0.66)", "PANEL_BORDER": "rgba(255,255,255,0.95)",
        "PANEL_HOVER": "rgba(25,113,194,0.10)", "PANEL_CHECKED": "rgba(25,113,194,0.16)",
        "WINDOW_BG": "#eef2f8", "MENU_BG": "#ffffff",
        "MENU_HOVER": "#e7edf6", "BORDER": "#dde5ef",
        "ELLIPSE": "#862e9c", "BEZIER": "#087f5b",
    },
    "墨夜": {
        "BG_TOP": "#101826", "BG_BOTTOM": "#0a0f1a",
        "GRID_MINOR": (140, 170, 215, 20), "GRID_MAJOR": (140, 170, 215, 45),
        "AXIS": "#7fa3d0",
        "POINT_FILL": "#ffd166", "POINT_RING": "#0a0f1a",
        "SEGMENT": "#5ec8f5", "LINE": "#94a3b8", "RAY": "#53d8e0",
        "CIRCLE": "#7be0ad", "POLYGON": "#ff9f8a", "INTERSECT": "#53d8e0",
        "MEASURE": "#ffa94d", "SELECTED": "#ff7a90", "PREVIEW": "#ffd166",
        "LABEL": "#a8bcd8", "ICON_INK": "#c8d8ee", "ACCENT": "#5ec8f5",
        "INK": "#dbe7f7", "SUBINK": "#8aa0bf",
        "PANEL_BG": "rgba(28,40,60,0.72)", "PANEL_BORDER": "rgba(100,130,170,0.35)",
        "PANEL_HOVER": "rgba(94,200,245,0.12)", "PANEL_CHECKED": "rgba(94,200,245,0.20)",
        "WINDOW_BG": "#0d1420", "MENU_BG": "#16202f",
        "MENU_HOVER": "#223148", "BORDER": "#263449",
        "ELLIPSE": "#da77f2", "BEZIER": "#63e6be",
    },
    "蓝图": {
        "BG_TOP": "#143a6b", "BG_BOTTOM": "#0e2a50",
        "GRID_MINOR": (255, 255, 255, 30), "GRID_MAJOR": (255, 255, 255, 62),
        "AXIS": "#d5e6ff",
        "POINT_FILL": "#ffd43b", "POINT_RING": "#0e2a50",
        "SEGMENT": "#ffffff", "LINE": "#a5c8ff", "RAY": "#63e6be",
        "CIRCLE": "#9ec5ff", "POLYGON": "#ffa8a8", "INTERSECT": "#63e6be",
        "MEASURE": "#ffd43b", "SELECTED": "#ff8787", "PREVIEW": "#ffd43b",
        "LABEL": "#cfe0fa", "ICON_INK": "#dbe9ff", "ACCENT": "#74b3ff",
        "INK": "#e3eeff", "SUBINK": "#a3c2e8",
        "PANEL_BG": "rgba(20,50,95,0.72)", "PANEL_BORDER": "rgba(140,180,240,0.40)",
        "PANEL_HOVER": "rgba(116,179,255,0.16)", "PANEL_CHECKED": "rgba(116,179,255,0.28)",
        "WINDOW_BG": "#0c2344", "MENU_BG": "#123059",
        "MENU_HOVER": "#1c4076", "BORDER": "#2a5288",
        "ELLIPSE": "#e599f7", "BEZIER": "#96f2d7",
    },
    "黑板": {
        "BG_TOP": "#20362c", "BG_BOTTOM": "#17271f",
        "GRID_MINOR": (215, 232, 220, 18), "GRID_MAJOR": (215, 232, 220, 40),
        "AXIS": "#cfe3d6",
        "POINT_FILL": "#ffe08a", "POINT_RING": "#17271f",
        "SEGMENT": "#eef7f0", "LINE": "#9db8a8", "RAY": "#8adcf0",
        "CIRCLE": "#9fe8b8", "POLYGON": "#ffb3ab", "INTERSECT": "#8adcf0",
        "MEASURE": "#ffe08a", "SELECTED": "#ff9eae", "PREVIEW": "#ffe08a",
        "LABEL": "#c9dccf", "ICON_INK": "#dcebe0", "ACCENT": "#7fd6a4",
        "INK": "#e6f2e9", "SUBINK": "#a9c4b2",
        "PANEL_BG": "rgba(32,50,42,0.72)", "PANEL_BORDER": "rgba(150,190,165,0.35)",
        "PANEL_HOVER": "rgba(127,214,164,0.14)", "PANEL_CHECKED": "rgba(127,214,164,0.25)",
        "WINDOW_BG": "#142019", "MENU_BG": "#1c2c23",
        "MENU_HOVER": "#28402f", "BORDER": "#31503c",
        "ELLIPSE": "#eebefa", "BEZIER": "#8ce99a",
    },
}

_active = "纸白"


class _Bus(QObject):
    changed = Signal(str)


bus = _Bus()


def theme_names():
    return list(THEMES)


def active_name():
    return _active


def set_theme(name):
    global _active
    if name in THEMES and name != _active:
        _active = name
        bus.changed.emit(name)


def __getattr__(name):
    """动态取色：永远返回当前主题下的 QColor（缺失键回退到纸白）。"""
    t = THEMES[_active]
    if name in t:
        return _c(t[name])
    if name in THEMES["纸白"]:
        return _c(THEMES["纸白"][name])
    raise AttributeError(name)


# ───────────────────────── 样式表生成 ─────────────────────────
def app_stylesheet() -> str:
    t = THEMES[_active]
    return f"""
    #toolRail, #zoomBar, #sidesPicker, #dividePicker, #textEditor,
    #infoPanel, #lengthPanel, #anglePanel, #fillConfigPanel {{
        background: {t["PANEL_BG"]};
        border: 1px solid {t["PANEL_BORDER"]};
        border-radius: 14px;
    }}
    QMainWindow {{ background: {t["WINDOW_BG"]}; }}
    QMenuBar {{ background: {t["MENU_BG"]}; color: {t["INK"]};
               border-bottom: 1px solid {t["BORDER"]}; padding: 2px; }}
    QMenuBar::item {{ padding: 5px 10px; border-radius: 6px; }}
    QMenuBar::item:selected {{ background: {t["MENU_HOVER"]}; }}
    QMenu {{ background: {t["MENU_BG"]}; color: {t["INK"]};
            border: 1px solid {t["BORDER"]}; }}
    QMenu::item {{ padding: 6px 24px; }}
    QMenu::item:selected {{ background: {t["MENU_HOVER"]}; }}
    QStatusBar {{ background: {t["MENU_BG"]}; border-top: 1px solid {t["BORDER"]}; }}
    QStatusBar QLabel {{ color: {t["SUBINK"]}; }}
    QComboBox, QLineEdit, QCheckBox {{
        background: {t["PANEL_BG"]}; color: {t["INK"]};
        border: 1px solid {t["PANEL_BORDER"]}; border-radius: 6px; padding: 3px 6px;
    }}
    """


def canvas_qss() -> str:
    t = THEMES[_active]
    return f"""
    #toolRail, #zoomBar, #sidesPicker, #dividePicker, #textEditor {{
        background: {t["PANEL_BG"]};
        border: 1px solid {t["PANEL_BORDER"]};
        border-radius: 14px;
    }}
    #toolRail QToolButton, #zoomBar QToolButton,
    #sidesPicker QToolButton, #dividePicker QToolButton {{
        border: none; background: transparent; border-radius: 9px;
        color: {t["INK"]}; font-weight: 600;
    }}
    #toolRail QToolButton {{ padding: 7px; }}
    #zoomBar QToolButton {{ padding: 4px 9px; }}
    #sidesPicker QToolButton, #dividePicker QToolButton {{ padding: 5px 8px; }}
    #toolRail QToolButton:hover, #zoomBar QToolButton:hover,
    #sidesPicker QToolButton:hover, #dividePicker QToolButton:hover {{
        background: {t["PANEL_HOVER"]};
    }}
    #toolRail QToolButton:checked {{ background: {t["PANEL_CHECKED"]}; }}
    #sidesPicker QToolButton:checked, #dividePicker QToolButton:checked {{
        background: {t["ACCENT"]}; color: #ffffff;
    }}
    #zoomBar QLabel, #sidesPicker QLabel, #dividePicker QLabel {{
        color: {t["SUBINK"]}; font-weight: 600;
    }}
    #trashBtn {{
        background: {t["PANEL_BG"]};
        border: 1px solid {t["SELECTED"]};
        border-radius: 14px;
    }}
    #trashBtn:hover {{ background: {t["SELECTED"]}; }}
    """


# ───────────────────────── 绘图工具（签名不变）─────────────────────────
def pen(color, width=1.0):
    return QPen(QColor(color), float(width))


def dashed_pen(color, width=1.0):
    p = QPen(QColor(color), float(width), Qt.PenStyle.DashLine)
    p.setDashPattern([6, 4])
    return p


def brush(color):
    return QBrush(QColor(color))


LABEL_FONT = QFont("Consolas", 9)
LABEL_FONT.setStyleHint(QFont.StyleHint.Monospace)
AXIS_FONT = QFont("Georgia", 11, QFont.Weight.DemiBold)
AXIS_FONT.setItalic(True)