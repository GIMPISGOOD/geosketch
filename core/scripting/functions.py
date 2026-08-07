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
    }

    return env