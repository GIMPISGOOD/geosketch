"""迷你数学排版器对外接口：draw_math / measure_math。
★ 新增：parse 缓存 + measure 缓存，避免每帧重复解析。"""

from PySide6.QtGui import QColor, QPen
from .parser import parse
from .layout import MathLayout

# ★ 性能优化：AST 缓存（文本 → AST）
_parse_cache: dict[str, object] = {}
_PARSE_CACHE_MAX = 512

# ★ 性能优化：measure 缓存（(文本, 字号) → (宽, 升, 降)）
_measure_cache: dict[tuple, tuple] = {}
_MEASURE_CACHE_MAX = 512


def parse_cached(text: str):
    """带缓存的 parse。AST 是只读的（layout 只遍历不修改），缓存安全。"""
    cached = _parse_cache.get(text)
    if cached is not None:
        return cached
    result = parse(text)
    if len(_parse_cache) >= _PARSE_CACHE_MAX:
        _parse_cache.clear()
    _parse_cache[text] = result
    return result


def draw_math(p, x, y, text, size=13, color=None):
    """在 (x, y)【基线左端】渲染数学表达式，返回实际宽度。"""
    if color is None:
        from ui import theme
        color = theme.LABEL
    color = QColor(color)
    p.setPen(QPen(color, 1.0))
    lay = MathLayout(p, size, color)
    return lay.draw(parse_cached(text), x, y)    # ★ 使用缓存


def measure_math(text, size=13):
    """只度量不绘制，返回 (宽, 升, 降)。带缓存。"""
    key = (text, size)
    cached = _measure_cache.get(key)
    if cached is not None:
        return cached
    lay = MathLayout(None, size, QColor(0, 0, 0))
    result = lay.measure(parse_cached(text))     # ★ 使用缓存
    if len(_measure_cache) >= _MEASURE_CACHE_MAX:
        _measure_cache.clear()
    _measure_cache[key] = result
    return result


def clear_math_caches():
    """清空数学排版缓存（主题切换 / 文档切换时调用）。"""
    _parse_cache.clear()
    _measure_cache.clear()