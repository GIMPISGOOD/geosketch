"""draw 内置库。"""


def build_draw_lib(interp):
    f = interp.factory

    return {
        "point": f.point,
        "segment": f.segment,
        "line": f.line,
        "ray": f.ray,
        "circle": f.circle,
        "ellipse": f.ellipse,
        "regular_polygon": f.regular_polygon,
        "polygon": f.polygon,
        "midpoint": f.midpoint,
        "division_point": f.division_point,
        "intersect": f.intersect,
        "text": f.text,

        "function_curve": f.function_curve,
        "function": f.function,
        "parametric": f.parametric,
        "polar": f.polar,
    }