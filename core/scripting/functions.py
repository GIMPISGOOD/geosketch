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
        "floor": math.floor,
        "ceil": math.ceil,
        "round": lambda x: float(round(x)),
        "sign": lambda x: (x > 0) - (x < 0),
        "min": min,
        "max": max,
        "sec": lambda x: 1.0 / math.cos(x),
        "csc": lambda x: 1.0 / math.sin(x),
        "cot": lambda x: 1.0 / math.tan(x),
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
        
        "build_object": factory.build_object,
        "构造对象": factory.build_object,

        "point_on_object": factory.point_on_object,
        "吸附点": factory.point_on_object,

        "perp_line": factory.perp_line,
        "垂线": factory.perp_line,

        "parallel_line": factory.parallel_line,
        "平行线": factory.parallel_line,

        "angle_bisector": factory.angle_bisector,
        "角平分线": factory.angle_bisector,

        "angle_div_line": factory.angle_div_line,
        "等分角线": factory.angle_div_line,

        "perp_bisector": factory.perp_bisector,
        "中垂线": factory.perp_bisector,

        "three_point_circle": factory.three_point_circle,
        "过三点圆": factory.three_point_circle,

        "incenter": factory.incenter,
        "内心": factory.incenter,

        "centroid": factory.centroid,
        "重心": factory.centroid,

        "cubic_bezier": factory.cubic_bezier,
        "贝塞尔": factory.cubic_bezier,

        "angle_measure": factory.angle_measure,
        "角度度量": factory.angle_measure,

        "ratio_measure": factory.ratio_measure,
        "比例度量": factory.ratio_measure,

        "measure": factory.measure,
        "度量": factory.measure,

        "region_measure": factory.region_measure,
        "区域度量": factory.region_measure,

        "expr_segment": factory.expr_segment,
        "表达式线段": factory.expr_segment,

        "expr_angle": factory.expr_angle,
        "表达式角度": factory.expr_angle,

        "expr_point": factory.expr_point,
        "表达式点": factory.expr_point,

        "polygon_vertex": factory.polygon_vertex,
        "多边形顶点": factory.polygon_vertex,
        
    }

    return env