"""几何对象测试：点、线段、圆、等分点、吸附点、多边形、椭圆、填充、交点、函数曲线。"""

import math

import pytest

from geo.points import FreePoint, PointOnObject
from geo.segments import Segment
from geo.circles import Circle
from geo.division import DivisionPoint
from geo.chain_fill import ChainFill, Span, FillStyle
from geo.intersects import IntersectPoint
from geo.function_curve import FunctionCurve

from plugins.line_tool import Line
from plugins.ray_tool import Ray
from plugins.polygon import RegularPolygon
from plugins.ellipse_tool import Ellipse


class TestPoint:
    def test_free_point_dump_build(self):
        p = FreePoint(1.5, -2.5)

        cls = type(p)
        p2 = cls.build([], p.dump())

        assert abs(p2.x - 1.5) < 1e-9
        assert abs(p2.y + 2.5) < 1e-9

    def test_point_distance(self):
        p = FreePoint(0, 0)

        assert abs(p.distance_to(3, 4) - 5.0) < 1e-9


class TestSegment:
    def test_length(self):
        a = FreePoint(0, 0)
        b = FreePoint(3, 4)
        s = Segment(a, b)

        assert abs(s.length() - 5.0) < 1e-9

    def test_point_at(self):
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)
        s = Segment(a, b)

        x, y = s.point_at(0.5)

        assert abs(x - 2.0) < 1e-9
        assert abs(y) < 1e-9

    def test_project(self):
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)
        s = Segment(a, b)

        t = s.project(1, 0)

        assert abs(t - 0.25) < 1e-9

    def test_project_clamped(self):
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)
        s = Segment(a, b)

        assert s.project(-10, 0) == 0.0
        assert s.project(10, 0) == 1.0


class TestCircle:
    def test_radius(self):
        center = FreePoint(0, 0)
        through = FreePoint(2, 0)

        c = Circle(center, through)

        assert abs(c.r - 2.0) < 1e-9

    def test_point_at(self):
        center = FreePoint(0, 0)
        through = FreePoint(2, 0)

        c = Circle(center, through)

        x, y = c.point_at(0.0)

        assert abs(x - 2.0) < 1e-9
        assert abs(y) < 1e-9

    def test_project(self):
        center = FreePoint(0, 0)
        through = FreePoint(2, 0)

        c = Circle(center, through)

        t = c.project(0, 2)

        assert abs(t - 0.25) < 1e-9

    def test_distance_to(self):
        center = FreePoint(0, 0)
        through = FreePoint(2, 0)

        c = Circle(center, through)

        assert abs(c.distance_to(3, 0) - 1.0) < 1e-9


class TestLineRay:
    def test_line_point_at(self):
        a = FreePoint(0, 0)
        b = FreePoint(1, 1)

        line = Line(a, b)

        x, y = line.point_at(2.0)

        assert abs(x - 2.0) < 1e-9
        assert abs(y - 2.0) < 1e-9

    def test_ray_project_non_negative(self):
        a = FreePoint(0, 0)
        b = FreePoint(1, 0)

        ray = Ray(a, b)

        assert ray.project(-5, 0) == 0.0
        assert abs(ray.project(3, 0) - 3.0) < 1e-9


class TestDivisionPoint:
    def test_midpoint(self):
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)

        m = DivisionPoint(a, b, 0.5)

        assert abs(m.x - 2.0) < 1e-9
        assert abs(m.y) < 1e-9

    def test_follows_endpoint(self):
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)

        m = DivisionPoint(a, b, 0.5)

        b.x = 8.0
        m.recompute()

        assert abs(m.x - 4.0) < 1e-9


class TestPointOnObject:
    def test_point_on_segment(self):
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)
        seg = Segment(a, b)

        p = PointOnObject(seg, 0.5)

        assert abs(p.x - 2.0) < 1e-9

    def test_drag_projects_back(self):
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)
        seg = Segment(a, b)

        p = PointOnObject(seg, 0.5)

        p.drag_to((10, 5))
        p.recompute()

        assert abs(p.x - 4.0) < 1e-9
        assert abs(p.y) < 1e-9

    def test_point_on_circle(self):
        center = FreePoint(0, 0)
        through = FreePoint(3, 0)
        c = Circle(center, through)

        p = PointOnObject(c, 0.0)

        assert abs(p.x - 3.0) < 1e-9
        assert abs(p.y) < 1e-9


class TestRegularPolygon:
    def test_vertices(self):
        center = FreePoint(0, 0)
        vertex = FreePoint(1, 0)

        poly = RegularPolygon(center, vertex, 4)

        assert len(poly.verts) == 4

    def test_distance_to_vertex(self):
        center = FreePoint(0, 0)
        vertex = FreePoint(1, 0)

        poly = RegularPolygon(center, vertex, 4)

        assert poly.distance_to(1, 0) < 1e-9


class TestEllipse:
    def test_point_at(self):
        center = FreePoint(0, 0)
        axis_a = FreePoint(2, 0)
        axis_b = FreePoint(0, 1)

        e = Ellipse(center, axis_a, axis_b)

        x, y = e.point_at(0.0)

        assert abs(x - 2.0) < 1e-9
        assert abs(y) < 1e-9

    def test_project_top_point(self):
        center = FreePoint(0, 0)
        axis_a = FreePoint(2, 0)
        axis_b = FreePoint(0, 1)

        e = Ellipse(center, axis_a, axis_b)

        t = e.project(0, 1)

        assert abs(t - 0.25) < 1e-6


class TestChainFill:
    def test_triangle_fill_exists(self):
        p1 = FreePoint(0, 0)
        p2 = FreePoint(1, 0)
        p3 = FreePoint(0, 1)

        spans = [
            Span(p1, p2, None),
            Span(p2, p3, None),
            Span(p3, p1, None),
        ]

        style = FillStyle("#ff0000", 0.5, "solid")
        fill = ChainFill(spans, style)

        assert fill.exists
        assert len(fill.path_pts) >= 3

    def test_area_positive(self):
        p1 = FreePoint(0, 0)
        p2 = FreePoint(1, 0)
        p3 = FreePoint(0, 1)

        spans = [
            Span(p1, p2, None),
            Span(p2, p3, None),
            Span(p3, p1, None),
        ]

        style = FillStyle("#ff0000", 0.5, "solid")
        fill = ChainFill(spans, style)

        assert abs(abs(fill._area()) - 0.5) < 1e-9


class TestIntersect:
    def test_circle_circle_intersection(self):
        c1 = Circle(FreePoint(0, 0), FreePoint(2, 0))
        c2 = Circle(FreePoint(1, 0), FreePoint(3, 0))

        p0 = IntersectPoint(c1, c2, 0)
        p1 = IntersectPoint(c1, c2, 1)

        assert p0.exists
        assert p1.exists

    def test_no_intersection_hidden(self):
        c1 = Circle(FreePoint(0, 0), FreePoint(1, 0))
        c2 = Circle(FreePoint(10, 0), FreePoint(11, 0))

        p = IntersectPoint(c1, c2, 0)

        assert not p.exists


class TestFunctionCurve:
    def test_explicit_eval_point(self):
        f = FunctionCurve(kind="explicit", expr="x^2")

        p = f._eval_point(2.0)

        assert p is not None
        assert abs(p[0] - 2.0) < 1e-9
        assert abs(p[1] - 4.0) < 1e-9

    def test_parametric_eval_point(self):
        f = FunctionCurve(kind="parametric", expr="cos(t)", expr2="sin(t)")

        p = f._eval_point(0.0)

        assert p is not None
        assert abs(p[0] - 1.0) < 1e-9
        assert abs(p[1]) < 1e-9

    def test_polar_eval_point(self):
        f = FunctionCurve(kind="polar", expr="1")

        p = f._eval_point(0.0)

        assert p is not None
        assert abs(p[0] - 1.0) < 1e-9
        assert abs(p[1]) < 1e-9