"""变换系统测试：平移、旋转、缩放、反射、迭代点。"""

import math

import pytest

from geo.points import FreePoint
from transforms.objects import TransformDriver, TransformPoint, IterPoint


class TestTransformPoint:
    def test_translate_expr(self):
        p = FreePoint(1, 1)

        drv = TransformDriver(
            "translate",
            exprs={"mode": "expr", "dx": "2", "dy": "3"}
        )

        tp = TransformPoint(drv, p)

        assert tp.exists
        assert abs(tp.x - 3.0) < 1e-9
        assert abs(tp.y - 4.0) < 1e-9

    def test_rotate_90(self):
        center = FreePoint(0, 0)
        p = FreePoint(1, 0)

        drv = TransformDriver(
            "rotate",
            points=[center],
            exprs={"angle": "90"}
        )

        tp = TransformPoint(drv, p)

        assert tp.exists
        assert abs(tp.x) < 1e-9
        assert abs(tp.y - 1.0) < 1e-9

    def test_scale_factor(self):
        center = FreePoint(0, 0)
        p = FreePoint(1, 1)

        drv = TransformDriver(
            "scale",
            points=[center],
            exprs={"mode": "expr", "factor": "2"}
        )

        tp = TransformPoint(drv, p)

        assert tp.exists
        assert abs(tp.x - 2.0) < 1e-9
        assert abs(tp.y - 2.0) < 1e-9

    def test_reflect_x_axis(self):
        p1 = FreePoint(0, 0)
        p2 = FreePoint(1, 0)
        p = FreePoint(1, 2)

        drv = TransformDriver(
            "reflect",
            points=[p1, p2],
            exprs={}
        )

        tp = TransformPoint(drv, p)

        assert tp.exists
        assert abs(tp.x - 1.0) < 1e-9
        assert abs(tp.y + 2.0) < 1e-9


class TestIterPoint:
    def test_iteration_expression(self):
        base = FreePoint(0, 0)

        p = IterPoint(base, 1, "x + 1", "y + 2")

        assert p.exists
        assert abs(p.x - 1.0) < 1e-9
        assert abs(p.y - 2.0) < 1e-9