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

_color_cache: dict[tuple, QColor] = {}
_pen_cache: dict[tuple, QPen] = {}
_brush_cache: dict[str, QBrush] = {}

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
        # ★ 切换主题时清空所有缓存
        _color_cache.clear()
        _pen_cache.clear()
        _brush_cache.clear()
        bus.changed.emit(name)

def __getattr__(name):
    """动态取色：永远返回当前主题下的 QColor（带缓存）。"""
    key = (_active, name)
    cached = _color_cache.get(key)
    if cached is not None:
        return cached
    t = THEMES[_active]
    if name in t:
        c = _c(t[name])
        _color_cache[key] = c
        return c
    if name in THEMES["纸白"]:
        c = _c(THEMES["纸白"][name])
        _color_cache[key] = c
        return c
    raise AttributeError(name)

# ───────────────────────── 样式表生成 ─────────────────────────
def app_stylesheet() -> str:
    """全局样式：主窗口 / 菜单 / 状态栏 / 输入控件。"""
    t = THEMES[_active]
    return f"""
    QDockWidget {{ background: {t["MENU_BG"]}; color: {t["INK"]}; }}
    QDockWidget::title {{
        background: {t["PANEL_BG"]}; padding: 6px;
        border-bottom: 1px solid {t["BORDER"]};
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
    QComboBox, QLineEdit, QCheckBox, QDoubleSpinBox, QSpinBox {{
        background: {t["WINDOW_BG"]}; color: {t["INK"]};
        border: 1px solid {t["PANEL_BORDER"]}; border-radius: 6px; padding: 3px 6px;
    }}
    """

def canvas_qss() -> str:
    """画布内所有悬浮面板的样式（磨砂玻璃）——面板都是 canvas 子控件，必须放这里。"""
    t = THEMES[_active]
    return f"""
background: {t["PANEL_BG"]};
border: 1px solid {t["PANEL_BORDER"]};
border-radius: 14px;
}}
border: none; background: transparent; border-radius: 9px;
color: {t["INK"]}; font-weight: 600;
}}
background: {t["PANEL_HOVER"]};
}}
background: {t["ACCENT"]}; color: #ffffff;
}}
color: {t["SUBINK"]}; font-weight: 600;
}}
background: {t["PANEL_BG"]};
border: 1px solid {t["SELECTED"]};
border-radius: 14px;
}}
background: transparent; width: 8px; margin: 2px;
}}
background: rgba(120,140,170,0.35); border-radius: 3px; min-height: 24px;
}}
background: rgba(120,140,170,0.60);
}}
/* ================= 属性面板专属样式 ================= */
#propertyPanel {{
background: {t["PANEL_BG"]};
border: 1px solid {t["PANEL_BORDER"]};
border-radius: 12px;
}}
#propertyPanel QScrollArea {{
background: transparent;
border: none;
}}
#propertyPanel QScrollArea > QWidget > QWidget {{
background: transparent;
}}
#propertyPanel QWidget {{
background: transparent;
}}
#propertyPanel QLabel {{
color: {t["INK"]};
background: transparent;
}}
#propertyPanel #panelTitle {{
font-size: 15px;
font-weight: 700;
color: {t["INK"]};
background: transparent;
}}
#propertyPanel #panelSubtitle {{
font-size: 11px;
color: {t["SUBINK"]};
background: transparent;
}}
#propertyPanel QLineEdit,
#propertyPanel QDoubleSpinBox,
#propertyPanel QComboBox {{
background: {t["WINDOW_BG"]};
color: {t["INK"]};
border: 1px solid {t["PANEL_BORDER"]};
border-radius: 6px;
padding: 3px 6px;
font-size: 12px;
}}
#propertyPanel QCheckBox {{
color: {t["INK"]};
background: transparent;
}}
#propertyPanel QPushButton {{
background: {t["PANEL_HOVER"]};
color: {t["INK"]};
border: 1px solid {t["PANEL_BORDER"]};
border-radius: 6px;
padding: 4px 10px;
font-size: 12px;
}}
#propertyPanel QPushButton:hover {{
background: {t["PANEL_CHECKED"]};
}}
#propertyPanel #collapseBtn,
#propertyPanel #expandBtn {{
background: transparent;
border: 1px solid rgba(120,140,170,0.5);
border-radius: 4px;
color: {t["SUBINK"]};
font-size: 13px;
font-weight: bold;
padding: 2px;
}}
#propertyPanel #collapseBtn:hover,
#propertyPanel #expandBtn:hover {{
background: {t["PANEL_HOVER"]};
border-color: {t["ACCENT"]};
color: {t["ACCENT"]};
}}
/* ===================================================== */
"""

# ───────────────────────── 绘图工具（签名不变）─────────────────────────
# ───────────────────────── 绘图工具（带缓存）─────────────────────────

def pen(color, width=1.0):
    """实线画笔（带缓存）。返回副本，调用者可安全修改。"""
    if isinstance(color, QColor):
        ckey = color.name(QColor.NameFormat.HexArgb)
    else:
        ckey = str(color)
    key = (ckey, float(width))
    cached = _pen_cache.get(key)
    if cached is not None:
        return QPen(cached)           # 隐式共享副本，极低成本
    p = QPen(QColor(color), float(width))
    _pen_cache[key] = p
    return QPen(p)

def dashed_pen(color, width=1.0):
    """虚线画笔（带缓存）。返回副本，调用者可安全修改。"""
    if isinstance(color, QColor):
        ckey = color.name(QColor.NameFormat.HexArgb)
    else:
        ckey = str(color)
    key = ("dash", ckey, float(width))
    cached = _pen_cache.get(key)
    if cached is not None:
        return QPen(cached)
    c = QColor(color) if isinstance(color, QColor) else _c(color)
    p = QPen(c, float(width))
    p.setStyle(Qt.PenStyle.CustomDashLine)
    p.setDashPattern([6.0, 4.0])
    p.setCapStyle(Qt.PenCapStyle.FlatCap)
    p.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    _pen_cache[key] = p
    return QPen(p)

def brush(color):
    """画刷（带缓存）。返回副本，调用者可安全修改。"""
    if isinstance(color, QColor):
        key = color.name(QColor.NameFormat.HexArgb)
    else:
        key = str(color)
    cached = _brush_cache.get(key)
    if cached is not None:
        return QBrush(cached)
    b = QBrush(QColor(color))
    _brush_cache[key] = b
    return QBrush(b)

LABEL_FONT = QFont("Consolas", 9)
LABEL_FONT.setStyleHint(QFont.StyleHint.Monospace)

AXIS_FONT = QFont("Georgia", 11, QFont.Weight.DemiBold)
AXIS_FONT.setItalic(True)

# ───────────── 自定义主题 ─────────────
def save_custom_theme(name, colors_dict):
    """把当前颜色字典保存为自定义主题（写入 THEMES）。"""
    THEMES[name] = dict(colors_dict)

def delete_custom_theme(name):
    if name in THEMES and name not in ("纸白", "墨夜", "蓝图", "黑板"):
        del THEMES[name]

def export_theme(name, path):
    """把主题导出为 JSON 文件。"""
    import json
    from pathlib import Path
    t = THEMES.get(name, THEMES["纸白"])
    Path(path).write_text(json.dumps(t, ensure_ascii=False, indent=2), encoding="utf-8")

def import_theme(path):
    """从 JSON 文件导入主题。"""
    import json
    from pathlib import Path
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    name = data.get("_name", "自定义")
    THEMES[name] = data
    return name