"""迷你数学排版器对外接口：draw_math / measure_math。"""
from PySide6.QtGui import QColor, QPen

from .parser import parse
from .layout import MathLayout


def draw_math(p, x, y, text, size=13, color=None):
    """在 (x, y)【基线左端】渲染数学表达式，返回实际宽度。"""
    if color is None:
        from ui import theme
        color = theme.LABEL
    color = QColor(color)
    p.setPen(QPen(color, 1.0))
    lay = MathLayout(p, size, color)
    return lay.draw(parse(text), x, y)


def measure_math(text, size=13):
    """只度量不绘制，返回 (宽, 升, 降)。"""
    lay = MathLayout(None, size, QColor(0, 0, 0))
    return lay.measure(parse(text))