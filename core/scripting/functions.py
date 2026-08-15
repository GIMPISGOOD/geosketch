"""脚本全局内置函数。"""

import math


def build_global_env(interp):
    factory = interp.factory

    def _print(*args):
        text = " ".join(interp._format_value(a) for a in args)
        interp.logs.append(text)

        if interp.canvas is not None and hasattr(interp.canvas, "cursor_info"):
            interp.canvas.cursor_info.emit(text)

        return None

    env = {
        # 常量
        "pi": math.pi,
        "π": math.pi,
        "e": math.e,

        # ★ 内置数学函数（无需 import math 即可直接使用）
        "sin": math.sin, "cos": math.cos, "tan": math.tan,
        "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan,
        "asin": math.asin, "acos": math.acos, "atan": math.atan,
        "sqrt": math.sqrt, "abs": abs, 
        "ln": math.log, "log": math.log10, "exp": math.exp,
        "floor": math.floor, "ceil": math.ceil, 
        "round": lambda x: float(round(x)),
        "min": min, "max": max,

        # 输出 / 等待
        "print": _print,
        "打印": _print,

        # 几何构造
        "point": factory.point,
        "点": factory.point,

        "segment": factory.segment,
        "线段": factory.segment,

        "line": factory.line,
        "直线": factory.line,

        "ray": factory.ray,
        "射线": factory.ray,

        "circle": factory.circle,
        "圆": factory.circle,

        "ellipse": factory.ellipse,
        "椭圆": factory.ellipse,

        "regular_polygon": factory.regular_polygon,
        "正多边形": factory.regular_polygon,

        "polygon": factory.polygon,
        "多边形": factory.polygon,

        "midpoint": factory.midpoint,
        "中点": factory.midpoint,

        "division_point": factory.division_point,
        "等分点": factory.division_point,

        "intersect": factory.intersect,
        "交点": factory.intersect,

        "text": factory.text,
        "文本": factory.text,

        # 函数曲线
        "function_curve": factory.function_curve,
        "函数曲线": factory.function_curve,

        "function": factory.function,
        "parametric": factory.parametric,
        "polar": factory.polar,
        
        # 隐函数曲线
        "implicit_curve": factory.implicit_curve,
        "隐函数": factory.implicit_curve,
        "implicit": factory.implicit_curve,
    }

    return env