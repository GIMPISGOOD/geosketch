"""脚本几何对象工厂。"""

import math

from geo.points import FreePoint, AbstractPoint
from geo.segments import Segment
from geo.circles import Circle
from geo.constraints import ExprCircle
from geo.division import DivisionPoint
from geo.intersects import IntersectPoint, INTERSECT_SOLVERS, _seg_circle, _circle_circle
from geo.function_curve import FunctionCurve
from geo.chain_fill import ChainFill, Span, FillStyle

from plugins.line_tool import Line
from plugins.ray_tool import Ray
from plugins.ellipse_tool import Ellipse
from plugins.polygon import RegularPolygon
from plugins.text_tool import TextObject

from .errors import ScriptError


# ------------------------------------------------------------
# 让 ExprCircle 参与交点系统
# ------------------------------------------------------------

def _register_expr_circle_solvers():
    INTERSECT_SOLVERS[(ExprCircle, Segment)] = (
        lambda c, s: _seg_circle(
            (s.a.x, s.a.y),
            (s.b.x, s.b.y),
            (c.center.x, c.center.y),
            c.r
        )
    )

    INTERSECT_SOLVERS[(ExprCircle, Circle)] = (
        lambda c1, c2: _circle_circle(
            (c1.center.x, c1.center.y),
            c1.r,
            (c2.center.x, c2.center.y),
            c2.r
        )
    )

    INTERSECT_SOLVERS[(ExprCircle, ExprCircle)] = (
        lambda c1, c2: _circle_circle(
            (c1.center.x, c1.center.y),
            c1.r,
            (c2.center.x, c2.center.y),
            c2.r
        )
    )


_register_expr_circle_solvers()


# ------------------------------------------------------------
# 对象属性
# ------------------------------------------------------------

def get_object_property(obj, name, line=None):
    if name == "x" and hasattr(obj, "x"):
        return float(obj.x)

    if name == "y" and hasattr(obj, "y"):
        return float(obj.y)

    if name in ("radius", "r") and hasattr(obj, "r"):
        return float(obj.r)

    if name == "length" and hasattr(obj, "length") and callable(obj.length):
        return float(obj.length())

    if name in ("sides", "n") and hasattr(obj, "n"):
        return float(obj.n)

    if name == "exists":
        return bool(getattr(obj, "exists", True))

    if name == "visible":
        return bool(getattr(obj, "visible", True))

    if name == "name":
        return getattr(obj, "name", "") or getattr(obj, "script_name", "")

    raise ScriptError(f"对象没有属性：{name}", line)


# ------------------------------------------------------------
# 工厂
# ------------------------------------------------------------

class ObjectFactory:
    def __init__(self, interp):
        self.interp = interp

    # -------------------- 工具 --------------------

    def _num(self, value, line=None):
        return self.interp._as_number(value, line)

    def _point(self, value, line=None):
        if isinstance(value, AbstractPoint):
            return value

        if hasattr(value, "x") and hasattr(value, "y"):
            return value

        raise ScriptError("此处需要点对象", line)

    def _text(self, value, line=None):
        if isinstance(value, str):
            return value

        raise ScriptError("此处需要字符串", line)

    # -------------------- 基础图元 --------------------

    def point(self, x, y):
        x = self._num(x)
        y = self._num(y)

        obj = FreePoint(x, y)
        return self.interp.add_created_object(obj)

    def segment(self, a, b):
        a = self._point(a)
        b = self._point(b)

        obj = Segment(a, b)
        return self.interp.add_created_object(obj)

    def line(self, a, b):
        a = self._point(a)
        b = self._point(b)

        obj = Line(a, b)
        return self.interp.add_created_object(obj)

    def ray(self, a, b):
        a = self._point(a)
        b = self._point(b)

        obj = Ray(a, b)
        return self.interp.add_created_object(obj)

    def circle(self, center, arg):
        center = self._point(center)

        if isinstance(arg, str):
            obj = ExprCircle(center, arg)
        elif isinstance(arg, AbstractPoint):
            obj = Circle(center, arg)
        else:
            r = self._num(arg)
            obj = ExprCircle(center, str(r))

        return self.interp.add_created_object(obj)

    def ellipse(self, center, axis_a, axis_b):
        center = self._point(center)
        axis_a = self._point(axis_a)
        axis_b = self._point(axis_b)

        obj = Ellipse(center, axis_a, axis_b)
        return self.interp.add_created_object(obj)

    def regular_polygon(self, center, vertex, sides):
        center = self._point(center)
        vertex = self._point(vertex)
        sides = int(self._num(sides))

        if sides < 3:
            raise ScriptError("正多边形至少需要 3 条边")

        obj = RegularPolygon(center, vertex, sides)
        return self.interp.add_created_object(obj)

    def polygon(self, *points):
        if len(points) < 3:
            raise ScriptError("多边形至少需要 3 个点")

        pts = [self._point(p) for p in points]

        spans = []

        for i in range(len(pts) - 1):
            spans.append(Span(pts[i], pts[i + 1], None))

        spans.append(Span(pts[-1], pts[0], None))

        style = FillStyle("#4dabf7", 0.35, "solid")
        obj = ChainFill(spans, style)

        return self.interp.add_created_object(obj)

    def midpoint(self, a, b):
        a = self._point(a)
        b = self._point(b)

        obj = DivisionPoint(a, b, 0.5)
        return self.interp.add_created_object(obj)

    def division_point(self, a, b, t):
        a = self._point(a)
        b = self._point(b)
        t = self._num(t)

        obj = DivisionPoint(a, b, t)
        return self.interp.add_created_object(obj)

    def intersect(self, obj1, obj2, branch=0):
        if obj1 is None or obj2 is None:
            raise ScriptError("交点需要两个几何对象")

        branch = int(self._num(branch))

        obj = IntersectPoint(obj1, obj2, branch)
        return self.interp.add_created_object(obj)

    def text(self, x, y, content, size=16, color="#1f2937"):
        x = self._num(x)
        y = self._num(y)

        content = self.interp._format_value(content)
        size = int(self._num(size))

        obj = TextObject(content, color, size, anchor=None, pos=(x, y))
        return self.interp.add_created_object(obj)

    # -------------------- 函数曲线 --------------------

    def function_curve(self, *args):
        if not args:
            raise ScriptError("function_curve 缺少参数")

        if isinstance(args[0], str) and args[0] in ("explicit", "parametric", "polar"):
            kind = args[0]
            rest = args[1:]
        else:
            kind = "explicit"
            rest = args

        if kind == "explicit":
            if len(rest) < 1:
                raise ScriptError("explicit 函数需要表达式")

            expr = self._text(rest[0])

            domain = None
            if len(rest) >= 3:
                domain = (self._num(rest[1]), self._num(rest[2]))

            obj = FunctionCurve("explicit", expr, "", domain)
            return self.interp.add_created_object(obj)

        if kind == "parametric":
            if len(rest) < 2:
                raise ScriptError("parametric 需要 x(t) 和 y(t)")

            expr = self._text(rest[0])
            expr2 = self._text(rest[1])

            if len(rest) >= 4:
                domain = (self._num(rest[2]), self._num(rest[3]))
            else:
                domain = (0.0, 2.0 * math.pi)

            obj = FunctionCurve("parametric", expr, expr2, domain)
            return self.interp.add_created_object(obj)

        if kind == "polar":
            if len(rest) < 1:
                raise ScriptError("polar 需要 r(t)")

            expr = self._text(rest[0])

            if len(rest) >= 3:
                domain = (self._num(rest[1]), self._num(rest[2]))
            else:
                domain = (0.0, 2.0 * math.pi)

            obj = FunctionCurve("polar", expr, "", domain)
            return self.interp.add_created_object(obj)

        raise ScriptError(f"未知函数曲线类型：{kind}")

    def function(self, expr):
        expr = self._text(expr)
        obj = FunctionCurve("explicit", expr, "", None)
        return self.interp.add_created_object(obj)

    def parametric(self, expr_x, expr_y, start=0.0, end=None):
        expr_x = self._text(expr_x)
        expr_y = self._text(expr_y)

        start = self._num(start)

        if end is None:
            end = 2.0 * math.pi
        else:
            end = self._num(end)

        obj = FunctionCurve("parametric", expr_x, expr_y, (start, end))
        return self.interp.add_created_object(obj)

    def polar(self, expr, start=0.0, end=None):
        expr = self._text(expr)

        start = self._num(start)

        if end is None:
            end = 2.0 * math.pi
        else:
            end = self._num(end)

        obj = FunctionCurve("polar", expr, "", (start, end))
        return self.interp.add_created_object(obj)
    
    # -------------------- 隐函数曲线 --------------------
    def implicit_curve(self, expr, domain=None, color=None):
        """创建隐函数曲线 F(x,y)=0。
        expr: 方程字符串，如 "x^2+y^2=1" 或 "sin(x)*cos(y)=0.5"
        domain: 可选 (x0, x1, y0, y1)，默认 (-5, 5, -5, 5)
        color: 可选颜色字符串
        """
        from geo.implicit_curve import ImplicitCurve
        expr = self._text(expr)
        if domain is not None:
            if isinstance(domain, (list, tuple)) and len(domain) == 4:
                domain = tuple(self._num(v) for v in domain)
            else:
                domain = None
        color_str = self._text(color) if color is not None else None
        obj = ImplicitCurve(expr, domain=domain, color=color_str)
        return self.interp.add_created_object(obj)