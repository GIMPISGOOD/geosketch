"""geo 内置库。"""

import math

from ..errors import ScriptError


def _vertices(obj):
    if hasattr(obj, "verts"):
        return list(obj.verts)

    if hasattr(obj, "path_pts"):
        return list(obj.path_pts)

    return None


def _polygon_area(verts):
    n = len(verts)

    if n < 3:
        return 0.0

    s = 0.0

    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        s += x1 * y2 - x2 * y1

    return abs(s) / 2.0


def _polygon_perimeter(verts):
    n = len(verts)

    if n < 2:
        return 0.0

    total = 0.0

    for i in range(n):
        x1, y1 = verts[i]
        x2, y2 = verts[(i + 1) % n]
        total += math.hypot(x2 - x1, y2 - y1)

    return total


def build_geo_lib(interp):
    def distance(a, b):
        if not hasattr(a, "x") or not hasattr(b, "x"):
            raise ScriptError("distance 需要两个点对象")

        return math.hypot(a.x - b.x, a.y - b.y)

    def length(obj):
        if hasattr(obj, "length") and callable(obj.length):
            return float(obj.length())

        raise ScriptError("该对象没有长度")

    def slope(obj):
        a = getattr(obj, "a", None)
        b = getattr(obj, "b", None)

        if a is None or b is None:
            raise ScriptError("slope 需要线段或直线对象")

        dx = b.x - a.x
        dy = b.y - a.y

        if abs(dx) < 1e-12:
            return 1e18

        return dy / dx

    def radius(obj):
        if hasattr(obj, "r"):
            return float(obj.r)

        raise ScriptError("该对象没有半径")

    def area(obj):
        tn = type(obj).__name__

        if tn in ("Circle", "ExprCircle"):
            return math.pi * obj.r * obj.r

        if tn == "Ellipse":
            return math.pi * abs(obj.ux * obj.vy - obj.uy * obj.vx)

        verts = _vertices(obj)

        if verts is not None:
            return _polygon_area(verts)

        raise ScriptError("该对象不支持面积")

    def perimeter(obj):
        tn = type(obj).__name__

        if tn in ("Circle", "ExprCircle"):
            return 2.0 * math.pi * obj.r

        if tn == "Ellipse":
            a = math.hypot(obj.ux, obj.uy)
            b = math.hypot(obj.vx, obj.vy)

            if a + b <= 0:
                return 0.0

            h = ((a - b) ** 2) / ((a + b) ** 2)
            return math.pi * (a + b) * (1.0 + 3.0 * h / (10.0 + math.sqrt(4.0 - 3.0 * h)))

        verts = _vertices(obj)

        if verts is not None:
            return _polygon_perimeter(verts)

        raise ScriptError("该对象不支持周长")

    return {
        "distance": distance,
        "length": length,
        "slope": slope,
        "radius": radius,
        "area": area,
        "perimeter": perimeter,
    }