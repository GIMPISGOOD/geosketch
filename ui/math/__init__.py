"""迷你数学排版器对外接口：draw_math / measure_math。
★ 新增：parse 缓存 + measure 缓存，避免每帧重复解析。
★ 修复：自动将 sqrt(...) 和 √(...) 转换为 \\sqrt{...} 以支持根号渲染。
"""
from PySide6.QtGui import QColor, QPen
from .parser import parse
from .layout import MathLayout

# ★ 性能优化：AST 缓存（文本 → AST）
_parse_cache: dict[str, object] = {}
_PARSE_CACHE_MAX = 512

# ★ 性能优化：measure 缓存（(文本, 字号) → (宽, 升, 降)）
_measure_cache: dict[tuple, tuple] = {}
_MEASURE_CACHE_MAX = 512

def _convert_sqrt_to_latex(text: str) -> str:
    """将 sqrt(...) 函数调用和 √(...) 转换为 \\sqrt{...} LaTeX 命令。
    支持嵌套括号：sqrt(x^2+sqrt(x)) → \\sqrt{x^2+\\\\sqrt{x}}
    """
    if not isinstance(text, str):
        return str(text)
        
    # 1. 统一将 Unicode √ 替换为 sqrt
    result = text.replace("√(", "sqrt(").replace("√", "sqrt")
    
    # 2. 反复替换直到没有 sqrt( 为止（处理嵌套）
    max_iter = 20
    for _ in range(max_iter):
        idx = result.find("sqrt(")
        if idx == -1:
            break
        # 从 sqrt( 之后开始匹配括号
        start = idx + 5  # "sqrt(" 的长度
        depth = 1
        end = start
        while end < len(result) and depth > 0:
            if result[end] == "(":
                depth += 1
            elif result[end] == ")":
                depth -= 1
            end += 1
        
        # 如果括号匹配成功
        if depth == 0:
            inner = result[start:end - 1]
            # 替换为 \sqrt{inner}
            result = result[:idx] + "\\sqrt{" + inner + "}" + result[end:]
        else:
            # 括号不匹配，跳出避免死循环
            break
            
    return result

def parse_cached(text: str):
    """带缓存的 parse。AST 是只读的（layout 只遍历不修改），缓存安全。"""
    # ★ 修复：在缓存和解析前，先进行 sqrt 转换
    converted_text = _convert_sqrt_to_latex(text)
    
    cached = _parse_cache.get(converted_text)
    if cached is not None:
        return cached
    result = parse(converted_text)
    if len(_parse_cache) >= _PARSE_CACHE_MAX:
        _parse_cache.clear()
    _parse_cache[converted_text] = result
    return result

def draw_math(p, x, y, text, size=13, color=None):
    """在 (x, y)【基线左端】渲染数学表达式，返回实际宽度。"""
    if color is None:
        from ui import theme
        color = theme.LABEL
    color = QColor(color)
    p.setPen(QPen(color, 1.0))
    lay = MathLayout(p, size, color)
    return lay.draw(parse_cached(text), x, y)    # ★ 使用缓存（内部已转换）

def measure_math(text, size=13):
    """只度量不绘制，返回 (宽, 升, 降)。带缓存。"""
    # ★ 修复：度量前也进行转换
    converted_text = _convert_sqrt_to_latex(text)
    key = (converted_text, size)
    cached = _measure_cache.get(key)
    if cached is not None:
        return cached
    lay = MathLayout(None, size, QColor(0, 0, 0))
    result = lay.measure(parse_cached(converted_text))     # ★ 使用缓存
    if len(_measure_cache) >= _MEASURE_CACHE_MAX:
        _measure_cache.clear()
    _measure_cache[key] = result
    return result

def clear_math_caches():
    """清空数学排版缓存（主题切换 / 文档切换时调用）。"""
    _parse_cache.clear()
    _measure_cache.clear()