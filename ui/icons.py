"""图标库：基于轻量第三方库 qtawesome（内置 Font Awesome / Material Design Icons）。

安装：pip install qtawesome

约定：注册工具时只传字符串键（icon="select"）；
每个键给出一组候选图标名按序尝试，库版本差异时自动回退。
"""
from PySide6.QtGui import QIcon

import qtawesome as qta

from ui import theme

# 工具键 → 候选图标名（按序尝试，全部失败则返回空图标）
TOOL_ICON_KEYS: dict[str, tuple[str, ...]] = {
    "select":    ("fa5s.mouse-pointer", "fa.mouse-pointer", "mdi.cursor-default-outline"),
    "point":     ("fa5s.dot-circle", "fa.dot-circle-o", "mdi.circle-small"),
    "segment":   ("fa5s.slash", "mdi.vector-line", "fa.minus"),
    "circle":    ("fa5.circle", "mdi.circle-outline", "fa5s.circle"),
    "intersect": ("fa5s.crosshairs", "fa.crosshairs", "mdi.target"),
    "polygon":   ("fa5s.draw-polygon", "mdi.vector-polygon", "fa5s.shapes"),
    "midpoint":  ("mdi.circle-double", "fa5s.dot-circle"),
    "divide":    ("fa5s.divide", "mdi.division"),
    "line":      ("mdi.vector-line", "fa5s.minus"),
    "ray":       ("fa5s.long-arrow-alt-right", "mdi.arrow-right-bold"),
    "angle":     ("fa5s.drafting-compass", "mdi.angle-acute"),
    "ratio":     ("fa5s.balance-scale", "mdi.scale-balance"),
    "text":      ("fa5s.font", "mdi.format-text"),
    "perp":      ("mdi.angle-right", "fa5s.drafting-compass"),
    "parallel":  ("fa5s.equals", "mdi.vector-parallel"),
    "bisector":  ("fa5s.drafting-compass", "mdi.vector-radius"),
    "angle_divide": ("fa5s.chart-pie", "mdi.pie-chart-outline"),
    "ellipse":   ("mdi.ellipse-outline", "fa5s.circle"),
    "bezier":    ("fa5s.bezier-curve", "mdi.vector-bezier"),
    "box":       ("fa5s.vector-square", "mdi.vector-rectangle"),
    "length":    ("fa5s.ruler", "mdi.ruler"),
    "fixedangle": ("mdi.angle-acute", "fa5s.drafting-compass"),
    "freefill":  ("fa5s.shapes", "mdi.shape"),
    "distance":  ("fa5s.arrows-alt-h", "mdi.arrow-expand-horizontal"),
    "area":      ("fa5s.draw-polygon", "mdi.texture-box"),
    "perimeter": ("fa5s.vector-square", "mdi.ruler-square"),
    "radius":    ("fa5s.circle-notch", "mdi.radius"),
    "diameter":  ("fa5s.circle", "mdi.circle-diameter"),
    "slope":     ("fa5s.chart-line", "mdi.slope-downhill"),
    "coord":     ("fa5s.crosshairs", "mdi.crosshairs-gps"),
    "ink":       ("fa5s.pen-fancy", "mdi.fountain-pen-tip"),
    "insert_image": ("fa5s.image", "mdi.image"),
    "insert_table": ("fa5s.table", "mdi.table"),
    "insert_pie":   ("fa5s.chart-pie", "mdi.chart-pie"),
    "insert_bar":   ("fa5s.chart-bar", "mdi.chart-bar"),
}


def _icon(names: tuple[str, ...], **opts) -> QIcon:
    for name in names:
        try:
            return qta.icon(name, **opts)
        except Exception:          # 图标名在当前库版本不存在 → 试下一个
            continue
    return QIcon()


def tool_icon(key: str) -> QIcon:
    """工具图标：Off 态墨色，On 态强调色（供按钮选中态切换）。"""
    names = TOOL_ICON_KEYS.get(key, ())
    ink = _icon(names, color=theme.ICON_INK.name())
    on = _icon(names, color=theme.ACCENT.name())
    icon = QIcon()
    for size in (24, 48):          # 双尺寸兼顾 HiDPI
        icon.addPixmap(ink.pixmap(size, size), QIcon.Mode.Normal, QIcon.State.Off)
        icon.addPixmap(on.pixmap(size, size), QIcon.Mode.Normal, QIcon.State.On)
    return icon


def trash_icon() -> QIcon:
    """删除按钮：常态红色，悬停（Active 态）变白。"""
    return _icon(("fa5s.trash-alt", "fa.trash", "mdi.trash-can-outline"),
                 color=theme.SELECTED.name(), color_active="#ffffff")


def zoom_icon(kind: str) -> QIcon:
    keys = {
        "in":    ("fa5s.search-plus",  "fa.search-plus",  "mdi.magnify-plus-outline"),
        "out":   ("fa5s.search-minus", "fa.search-minus", "mdi.magnify-minus-outline"),
        "reset": ("fa5s.expand-arrows-alt", "fa.arrows-alt", "mdi.fit-to-screen-outline"),
    }
    return _icon(keys[kind], color=theme.ICON_INK.name())


def build_tool_icon(spec: dict) -> QIcon:
    """tool_rail 的接口：从注册表里的字符串键解析图标。"""
    return tool_icon(spec.get("icon") or "")