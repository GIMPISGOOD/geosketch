"""交点偏导数验证：解析结果与数值差分对比。"""
import math
import pytest
from geo.base import GeoObject
from geo.points import FreePoint
from geo.segments import Segment
from geo.circles import Circle
from geo.intersects import IntersectPoint
from constraints.chain_rule import get_coordinate_derivatives


@pytest.fixture(autouse=True)
def reset_ids():
    GeoObject.reset_ids()
    yield


class TestLineLineDerivatives:
    def test_seg_seg_perpendicular(self):
        """两垂直线段交点的偏导数。"""
        a = FreePoint(0, 0)
        b = FreePoint(2, 0)
        c = FreePoint(1, -1)
        d = FreePoint(1, 1)
        seg1 = Segment(a, b)
        seg2 = Segment(c, d)
        ip = IntersectPoint(seg1, seg2, branch=0)

        assert ip.exists
        assert abs(ip.x - 1.0) < 1e-9
        assert abs(ip.y - 0.0) < 1e-9

        derivs = get_coordinate_derivatives(ip)
        assert len(derivs) > 0, "应返回非空偏导数"

        # 数值验证：移动 a.x，检查交点变化
        eps = 1e-6
        a.x += eps
        seg1.recompute()
        ip.recompute()
        numeric_dpx = (ip.x - 1.0) / eps
        a.x -= eps

        analytic = derivs.get(id(a))
        assert analytic is not None, "a 的偏导数应存在"
        assert abs(analytic[0] - numeric_dpx) < 1e-3, \
            f"∂px/∂ax: 解析={analytic[0]:.6f}, 数值={numeric_dpx:.6f}"

    def test_seg_seg_oblique(self):
        """斜交线段的偏导数。"""
        a = FreePoint(0, 0)
        b = FreePoint(3, 1)
        c = FreePoint(0, 1)
        d = FreePoint(3, 0)
        seg1 = Segment(a, b)
        seg2 = Segment(c, d)
        ip = IntersectPoint(seg1, seg2, branch=0)

        assert ip.exists
        derivs = get_coordinate_derivatives(ip)
        assert len(derivs) >= 2, "至少两个自由点有偏导"

        # 数值验证所有自由点
        for fp in [a, b, c, d]:
            analytic = derivs.get(id(fp))
            if analytic is None:
                continue
            for axis in range(2):
                old = fp.x if axis == 0 else fp.y
                if axis == 0:
                    fp.x = old + 1e-6
                else:
                    fp.y = old + 1e-6
                seg1.recompute()
                seg2.recompute()
                ip.recompute()
                px_plus, py_plus = ip.x, ip.y

                if axis == 0:
                    fp.x = old - 1e-6
                else:
                    fp.y = old - 1e-6
                seg1.recompute()
                seg2.recompute()
                ip.recompute()
                px_minus, py_minus = ip.x, ip.y

                if axis == 0:
                    fp.x = old
                else:
                    fp.y = old
                seg1.recompute()
                seg2.recompute()
                ip.recompute()

                num_dpx = (px_plus - px_minus) / (2e-6)
                num_dpy = (py_plus - py_minus) / (2e-6)

                if axis == 0:
                    assert abs(analytic[0] - num_dpx) < 0.01, \
                        f"∂px/∂{fp.name}.x"
                    assert abs(analytic[2] - num_dpy) < 0.01, \
                        f"∂py/∂{fp.name}.x"
                else:
                    assert abs(analytic[1] - num_dpx) < 0.01, \
                        f"∂px/∂{fp.name}.y"
                    assert abs(analytic[3] - num_dpy) < 0.01, \
                        f"∂py/∂{fp.name}.y"


class TestCircleCircleDerivatives:
    def test_two_circles(self):
        """两圆交点的偏导数。"""
        c1_center = FreePoint(0, 0)
        c1_through = FreePoint(1, 0)
        c2_center = FreePoint(1.5, 0)
        c2_through = FreePoint(2.5, 0)

        cir1 = Circle(c1_center, c1_through)
        cir2 = Circle(c2_center, c2_through)
        ip = IntersectPoint(cir1, cir2, branch=0)

        assert ip.exists
        derivs = get_coordinate_derivatives(ip)
        assert len(derivs) >= 2

        # 数值验证圆心1
        analytic = derivs.get(id(c1_center))
        assert analytic is not None

        eps = 1e-6
        old_x = c1_center.x
        c1_center.x = old_x + eps
        cir1.recompute()
        ip.recompute()
        px_plus = ip.x
        c1_center.x = old_x - eps
        cir1.recompute()
        ip.recompute()
        px_minus = ip.x
        c1_center.x = old_x
        cir1.recompute()
        ip.recompute()

        num_dpx = (px_plus - px_minus) / (2 * eps)
        assert abs(analytic[0] - num_dpx) < 0.05, \
            f"∂px/∂c1.x: 解析={analytic[0]:.6f}, 数值={num_dpx:.6f}"

    def test_tangent_circles_fallback(self):
        """相切圆（退化）应回退到数值差分而非崩溃。"""
        c1_center = FreePoint(0, 0)
        c1_through = FreePoint(1, 0)
        c2_center = FreePoint(2, 0)
        c2_through = FreePoint(3, 0)

        cir1 = Circle(c1_center, c1_through)
        cir2 = Circle(c2_center, c2_through)
        ip = IntersectPoint(cir1, cir2, branch=0)

        # 相切时只有一个交点，行列式接近零
        derivs = get_coordinate_derivatives(ip)
        # 不应崩溃，可能返回空或数值结果
        assert isinstance(derivs, dict)


class TestSegCircleDerivatives:
    def test_seg_circle(self):
        """线段与圆的交点偏导数。"""
        a = FreePoint(-2, 0)
        b = FreePoint(2, 0)
        center = FreePoint(0, 0)
        through = FreePoint(0, 1)

        seg = Segment(a, b)
        cir = Circle(center, through)
        ip = IntersectPoint(seg, cir, branch=0)

        assert ip.exists
        derivs = get_coordinate_derivatives(ip)
        assert len(derivs) >= 1

        # 数值验证
        analytic = derivs.get(id(center))
        if analytic is not None:
            eps = 1e-6
            old_y = center.y
            center.y = old_y + eps
            cir.recompute()
            ip.recompute()
            px_plus = ip.x if ip.exists else 0
            center.y = old_y - eps
            cir.recompute()
            ip.recompute()
            px_minus = ip.x if ip.exists else 0
            center.y = old_y
            cir.recompute()
            ip.recompute()

            if ip.exists:
                num_dpx = (px_plus - px_minus) / (2 * eps)
                assert abs(analytic[1] - num_dpx) < 0.1


class TestNonexistentIntersection:
    def test_parallel_lines_no_deriv(self):
        """平行线段无交点，偏导数应为空。"""
        a = FreePoint(0, 0)
        b = FreePoint(1, 0)
        c = FreePoint(0, 1)
        d = FreePoint(1, 1)
        seg1 = Segment(a, b)
        seg2 = Segment(c, d)
        ip = IntersectPoint(seg1, seg2, branch=0)

        assert not ip.exists
        derivs = get_coordinate_derivatives(ip)
        assert derivs == {}