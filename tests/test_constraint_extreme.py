"""tests/test_constraint_extreme.py
约束求解模块极端情况与回归测试。

覆盖范围：
  A. 解析雅可比 vs 数值差分交叉验证（全部 14 种约束）
  B. P0-1  PointOnObject 切线方向雅可比
  C. P0-2  数值回退中的子对象树重算
  D. P0-3  删除对象后约束清理
  E. P1-7  BFS 邻接表正确性与性能
  F. P1-8  递归求解语义
  G. 退化几何（零长度/零半径/重合/共线/平行）
  H. 过约束回滚与状态恢复
  I. 求解器鲁棒性（大坐标/小坐标/混合约束/幂等性）
  J. 约束启用/禁用
  K. 表达式边界

运行：pytest tests/test_constraint_extreme.py -v --tb=short
"""

import math
import time
import pytest

# ═══════════════════════ 夹具 ═══════════════════════

@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def doc(qapp):
    from core.document import Document
    d = Document()
    yield d
    d.objects.clear()
    d.constraints.clear()


# ═══════════════════════ 辅助 ═══════════════════════

def _add(doc, *objs):
    for o in objs:
        doc.objects.append(o)


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


def _numeric_jacobian_check(constraint, vars_map, eps=1e-5):
    """用数值差分验证解析雅可比：逐元素比较，返回最大绝对误差。"""
    from numpy import asarray, float64
    analytic = asarray(constraint._jacobian_analytic(vars_map), dtype=float64)
    numeric = constraint._numeric_jacobian(vars_map)
    if analytic.shape != numeric.shape:
        return float('inf')
    return float(abs(analytic - numeric).max())


def _on_circle(p, circle, tol=1e-4):
    d = math.hypot(p.x - circle.center.x, p.y - circle.center.y)
    return abs(d - circle.r) < tol


def _on_segment(p, seg, tol=1e-4):
    ax, ay = seg.a.x, seg.a.y
    bx, by = seg.b.x, seg.b.y
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 < 1e-12:
        return math.hypot(p.x - ax, p.y - ay) < tol
    t = max(0.0, min(1.0, ((p.x - ax) * dx + (p.y - ay) * dy) / l2))
    px, py = ax + t * dx, ay + t * dy
    return math.hypot(p.x - px, p.y - py) < tol


# ═══════════════════════════════════════════════════════
#  A. 解析雅可比 vs 数值差分（全部 14 种约束）
# ═══════════════════════════════════════════════════════

class TestAnalyticJacobian:
    """每个有 _jacobian_analytic 的约束，解析结果必须与数值差分一致。"""

    def test_distance(self, doc):
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(1, 2), FreePoint(4, 6)
        _add(doc, p1, p2)
        c = DistanceConstraint(p1, p2, "5")
        vm = {id(p1): 0, id(p2): 1}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_fixed(self, doc):
        from geo.points import FreePoint
        from constraints.types.fixed import FixedConstraint
        p = FreePoint(3, 7)
        _add(doc, p)
        c = FixedConstraint(p, 3, 7)
        vm = {id(p): 0}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_horizontal(self, doc):
        from geo.points import FreePoint
        from constraints.types.horizontal import HorizontalConstraint
        p1, p2 = FreePoint(0, 1), FreePoint(5, 3)
        _add(doc, p1, p2)
        c = HorizontalConstraint(p1, p2)
        vm = {id(p1): 0, id(p2): 1}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_vertical(self, doc):
        from geo.points import FreePoint
        from constraints.types.vertical import VerticalConstraint
        p1, p2 = FreePoint(2, 0), FreePoint(5, 8)
        _add(doc, p1, p2)
        c = VerticalConstraint(p1, p2)
        vm = {id(p1): 0, id(p2): 1}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_angle(self, doc):
        from geo.points import FreePoint
        from constraints.types.angle import AngleConstraint
        p1, v, p2 = FreePoint(1, 0), FreePoint(0, 0), FreePoint(0, 1)
        _add(doc, p1, v, p2)
        c = AngleConstraint(p1, v, p2, "90")
        vm = {id(p1): 0, id(v): 1, id(p2): 2}
        assert _numeric_jacobian_check(c, vm) < 1e-4

    def test_angle_acute(self, doc):
        """锐角 30°：验证非直角时雅可比也正确。"""
        from geo.points import FreePoint
        from constraints.types.angle import AngleConstraint
        p1 = FreePoint(math.cos(math.radians(30)),
                       math.sin(math.radians(30)))
        v = FreePoint(0, 0)
        p2 = FreePoint(1, 0)
        _add(doc, p1, v, p2)
        c = AngleConstraint(p1, v, p2, "30")
        vm = {id(p1): 0, id(v): 1, id(p2): 2}
        assert _numeric_jacobian_check(c, vm) < 1e-4

    def test_parallel(self, doc):
        from geo.points import FreePoint
        from constraints.types.parallel import ParallelConstraint
        a1, b1 = FreePoint(0, 0), FreePoint(3, 1)
        a2, b2 = FreePoint(0, 2), FreePoint(3, 3.5)
        _add(doc, a1, b1, a2, b2)
        c = ParallelConstraint(a1, b1, a2, b2)
        vm = {id(a1): 0, id(b1): 1, id(a2): 2, id(b2): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-4

    def test_perpendicular(self, doc):
        from geo.points import FreePoint
        from constraints.types.perpendicular import PerpendicularConstraint
        a1, b1 = FreePoint(0, 0), FreePoint(3, 0)
        a2, b2 = FreePoint(0, 0), FreePoint(0.2, 4)
        _add(doc, a1, b1, a2, b2)
        c = PerpendicularConstraint(a1, b1, a2, b2)
        vm = {id(a1): 0, id(b1): 1, id(a2): 2, id(b2): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-4

    def test_collinear(self, doc):
        from geo.points import FreePoint
        from constraints.types.collinear import CollinearConstraint
        p1, p2, p3 = FreePoint(0, 0), FreePoint(1, 0.1), FreePoint(2, -0.1)
        _add(doc, p1, p2, p3)
        c = CollinearConstraint(p1, p2, p3)
        vm = {id(p1): 0, id(p2): 1, id(p3): 2}
        assert _numeric_jacobian_check(c, vm) < 1e-4

    def test_concentric(self, doc):
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import ConcentricConstraint
        c1c, c1t = FreePoint(0, 0), FreePoint(2, 0)
        c2c, c2t = FreePoint(1, 1), FreePoint(4, 1)
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, c1c, c1t, cir1, c2c, c2t, cir2)
        c = ConcentricConstraint(cir1, cir2)
        vm = {id(c1c): 0, id(c2c): 1}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_equal_radius(self, doc):
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import EqualRadiusConstraint
        c1c, c1t = FreePoint(0, 0), FreePoint(3, 0)
        c2c, c2t = FreePoint(10, 0), FreePoint(12, 0)
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, c1c, c1t, cir1, c2c, c2t, cir2)
        c = EqualRadiusConstraint(cir1, cir2)
        vm = {id(c1c): 0, id(c1t): 1, id(c2c): 2, id(c2t): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_tangent_circles_outer(self, doc):
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import TangentCirclesConstraint
        c1c, c1t = FreePoint(0, 0), FreePoint(2, 0)
        c2c, c2t = FreePoint(5, 0), FreePoint(6, 0)
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, c1c, c1t, cir1, c2c, c2t, cir2)
        c = TangentCirclesConstraint(cir1, cir2, mode="outer")
        vm = {id(c1c): 0, id(c1t): 1, id(c2c): 2, id(c2t): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_tangent_circles_inner(self, doc):
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import TangentCirclesConstraint
        c1c, c1t = FreePoint(0, 0), FreePoint(5, 0)   # r1=5
        c2c, c2t = FreePoint(1, 0), FreePoint(3, 0)   # r2=2
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, c1c, c1t, cir1, c2c, c2t, cir2)
        c = TangentCirclesConstraint(cir1, cir2, mode="inner")
        vm = {id(c1c): 0, id(c1t): 1, id(c2c): 2, id(c2t): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_tangent_line_circle(self, doc):
        from geo.points import FreePoint
        from geo.segments import Segment
        from geo.circles import Circle
        from constraints.types.circle_constraints import TangentLineCircleConstraint
        a, b = FreePoint(0, 0), FreePoint(10, 0)
        seg = Segment(a, b)
        ctr, thr = FreePoint(5, 3), FreePoint(7, 3)  # r=2
        cir = Circle(ctr, thr)
        _add(doc, a, b, seg, ctr, thr, cir)
        c = TangentLineCircleConstraint(seg, cir)
        vm = {id(a): 0, id(b): 1, id(ctr): 2, id(thr): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-4

    def test_tangent_cc_points(self, doc):
        from geo.points import FreePoint
        from constraints.types.tangent import TangentCC
        c1c, c1t = FreePoint(0, 0), FreePoint(2, 0)
        c2c, c2t = FreePoint(5, 0), FreePoint(6, 0)
        _add(doc, c1c, c1t, c2c, c2t)
        c = TangentCC(c1c, c1t, c2c, c2t, mode="external")
        vm = {id(c1c): 0, id(c1t): 1, id(c2c): 2, id(c2t): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-5

    def test_tangent_cl_points(self, doc):
        from geo.points import FreePoint
        from constraints.types.tangent import TangentCL
        ctr, thr = FreePoint(5, 3), FreePoint(7, 3)
        a, b = FreePoint(0, 0), FreePoint(10, 0)
        _add(doc, ctr, thr, a, b)
        c = TangentCL(ctr, thr, a, b)
        vm = {id(ctr): 0, id(thr): 1, id(a): 2, id(b): 3}
        assert _numeric_jacobian_check(c, vm) < 1e-4


# ═══════════════════════════════════════════════════════
#  B. P0-1：PointOnObject 切线方向雅可比
# ═══════════════════════════════════════════════════════

class TestPointOnObjectFreedom:

    def test_poo_jacobian_tangent_direction_circle(self, doc):
        """圆上吸附点：雅可比应沿切线方向，垂直分量 ≈ 0。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(3, 0)
        cir = Circle(O, R)
        P = PointOnObject(cir, 0.25)  # (0, 3) → 切线方向 (-1, 0)
        P.recompute()
        Q = FreePoint(5, 3)
        _add(doc, O, R, cir, P, Q)
        c = DistanceConstraint(P, Q, "5")
        vm = {id(P): 0}
        jac = c.jacobian(vm)
        # P 在 (0,3)，切线方向 (-1,0)
        # 雅可比应主要在 x 方向，y 方向接近 0
        assert abs(jac[0][1]) < abs(jac[0][0]) * 0.15, \
            f"垂直分量过大: jac={jac}"

    def test_poo_jacobian_tangent_direction_segment(self, doc):
        """线段上吸附点：雅可比应沿线段方向。"""
        from geo.points import FreePoint, PointOnObject
        from geo.segments import Segment
        from constraints.types.distance import DistanceConstraint
        A, B = FreePoint(0, 0), FreePoint(10, 0)
        seg = Segment(A, B)
        P = PointOnObject(seg, 0.5)  # (5, 0) → 切线方向 (1, 0)
        P.recompute()
        Q = FreePoint(5, 5)
        _add(doc, A, B, seg, P, Q)
        c = DistanceConstraint(P, Q, "5")
        vm = {id(P): 0}
        jac = c.jacobian(vm)
        # 线段水平，切线 (1,0)，距离约束在 y 方向有梯度
        # 但投影到切线后，y 分量应为 0
        assert abs(jac[0][1]) < 1e-6, \
            f"线段水平时 y 方向雅可比应为 0: jac={jac}"

    def test_poo_on_circle_slides_correctly(self, doc):
        """拖动自由点 → 吸附点沿圆滑动，不脱离。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(3, 0)
        cir = Circle(O, R)
        P = PointOnObject(cir, 0.25)
        P.recompute()
        Q = FreePoint(P.x + 5, P.y)
        con = DistanceConstraint(P, Q, "5")
        _add(doc, O, R, cir, P, Q)
        doc.constraints.append(con)

        Q.x, Q.y = 2.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)
        assert _on_circle(P, cir), f"P 脱离圆 ({P.x:.4f},{P.y:.4f})"
        assert _dist(P, Q) == pytest.approx(5.0, abs=0.15)

    def test_poo_on_segment_slides_correctly(self, doc):
        """拖动自由点 → 吸附点沿线段滑动，不脱离。"""
        from geo.points import FreePoint, PointOnObject
        from geo.segments import Segment
        from constraints.types.distance import DistanceConstraint
        A, B = FreePoint(0, 0), FreePoint(10, 0)
        seg = Segment(A, B)
        P = PointOnObject(seg, 0.5)
        P.recompute()
        Q = FreePoint(P.x, P.y + 4)
        con = DistanceConstraint(P, Q, "4")
        _add(doc, A, B, seg, P, Q)
        doc.constraints.append(con)

        Q.x, Q.y = 5.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)
        assert _on_segment(P, seg), f"P 脱离线段 ({P.x:.4f},{P.y:.4f})"
        assert _dist(P, Q) == pytest.approx(4.0, abs=0.15)

    def test_multiple_poo_same_host(self, doc):
        """同一圆上两个吸附点，各自受不同距离约束。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(5, 0)
        cir = Circle(O, R)
        P1 = PointOnObject(cir, 0.0)
        P2 = PointOnObject(cir, 0.5)
        P1.recompute(); P2.recompute()
        Q1 = FreePoint(P1.x + 3, P1.y)
        Q2 = FreePoint(P2.x + 3, P2.y)
        _add(doc, O, R, cir, P1, P2, Q1, Q2)
        doc.constraints.extend([
            DistanceConstraint(P1, Q1, "3"),
            DistanceConstraint(P2, Q2, "3"),
        ])
        Q1.x, Q1.y = 2.0, 1.0
        Q2.x, Q2.y = -2.0, -6.0
        doc.solve_constraints(trigger_points=[Q1, Q2],
                              pinned_points=[Q1, Q2], quick=False)
        assert _on_circle(P1, cir), "P1 脱离圆"
        assert _on_circle(P2, cir), "P2 脱离圆"
        assert _dist(P1, Q1) == pytest.approx(3.0, abs=0.3)
        assert _dist(P2, Q2) == pytest.approx(3.0, abs=0.3)

    def test_poo_t_stays_in_range(self, doc):
        """多帧拖动后 t 始终在 [0,1]。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(3, 0)
        cir = Circle(O, R)
        P = PointOnObject(cir, 0.25)
        P.recompute()
        Q = FreePoint(P.x + 5, P.y)
        _add(doc, O, R, cir, P, Q)
        doc.constraints.append(DistanceConstraint(P, Q, "5"))
        for qx, qy in [(2, 1), (-1, 2), (-2, -1), (1, -2), (0, 4)]:
            Q.x, Q.y = qx, qy
            doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                                  quick=True)
            assert 0.0 <= P.t <= 1.0, f"P.t={P.t} 越界 (Q=({qx},{qy}))"
            assert _on_circle(P, cir), f"P 脱离圆 (Q=({qx},{qy}))"


# ═══════════════════════════════════════════════════════
#  C. P0-2：数值回退中的子对象树重算
# ═══════════════════════════════════════════════════════

class TestNumericFallbackRecompute:

    def test_intersect_circle_recompute(self, doc):
        """圆参与交点时，扰动自由点后必须重算圆半径。"""
        from geo.points import FreePoint
        from geo.circles import Circle
        from geo.segments import Segment
        from geo.intersects import IntersectPoint
        from constraints.types.distance import DistanceConstraint
        O = FreePoint(0, 0)
        R = FreePoint(3, 0)
        cir = Circle(O, R)
        A, B = FreePoint(-5, 0), FreePoint(5, 0)
        seg = Segment(A, B)
        _add(doc, O, R, cir, A, B, seg)
        ip = IntersectPoint(cir, seg, 0)
        _add(doc, ip)
        assert ip.exists, "交点应存在"
        P = FreePoint(ip.x + 2, ip.y)
        _add(doc, P)
        con = DistanceConstraint(ip, P, "2")
        doc.constraints.append(con)
        P.x, P.y = ip.x + 3, ip.y + 1
        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=False)
        assert _dist(ip, P) == pytest.approx(2.0, abs=0.2)

    def test_deep_chain_recompute(self, doc):
        """FreePoint → Circle → IntersectPoint 三层依赖链。"""
        from geo.points import FreePoint
        from geo.circles import Circle
        from geo.segments import Segment
        from geo.intersects import IntersectPoint
        from constraints.types.distance import DistanceConstraint
        O = FreePoint(0, 0)
        R = FreePoint(4, 0)
        cir = Circle(O, R)
        A, B = FreePoint(-10, 2), FreePoint(10, 2)
        seg = Segment(A, B)
        _add(doc, O, R, cir, A, B, seg)
        ip = IntersectPoint(cir, seg, 0)
        _add(doc, ip)
        if not ip.exists:
            pytest.skip("交点不存在（几何不满足）")
        P = FreePoint(ip.x + 1, ip.y)
        _add(doc, P)
        doc.constraints.append(DistanceConstraint(ip, P, "1"))
        # 移动圆心 → 圆半径不变但位置变 → 交点应跟随
        old_ip = (ip.x, ip.y)
        O.x, O.y = 1.0, 0.5
        doc.recompute_silent(doc.objects)
        assert (ip.x, ip.y) != old_ip, "交点应跟随圆心移动"

    def test_fallback_state_fully_restored(self, doc):
        """数值回退后，所有点坐标必须完全恢复。"""
        from geo.points import FreePoint
        from geo.segments import Segment
        from geo.intersects import IntersectPoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(10, 10)
        p3, p4 = FreePoint(0, 10), FreePoint(10, 0)
        s1, s2 = Segment(p1, p2), Segment(p3, p4)
        _add(doc, p1, p2, s1, p3, p4, s2)
        ip = IntersectPoint(s1, s2, 0)
        _add(doc, ip)
        P = FreePoint(5, 8)
        _add(doc, P)
        con = DistanceConstraint(ip, P, "2")
        coords_before = [(o.x, o.y) for o in doc.objects
                         if hasattr(o, 'x')]
        con.jacobian({id(P): 0})
        coords_after = [(o.x, o.y) for o in doc.objects
                        if hasattr(o, 'x')]
        for i, (before, after) in enumerate(
                zip(coords_before, coords_after)):
            assert before[0] == pytest.approx(after[0], abs=1e-12), \
                f"对象 {i} x 坐标未恢复"
            assert before[1] == pytest.approx(after[1], abs=1e-12), \
                f"对象 {i} y 坐标未恢复"


# ═══════════════════════════════════════════════════════
#  D. P0-3：删除对象后约束清理
# ═══════════════════════════════════════════════════════

class TestConstraintCleanup:

    def test_delete_circle_removes_tangent(self, doc):
        """删除圆 → 涉及该圆的相切约束必须被移除。"""
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import TangentCirclesConstraint
        c1c, c1t = FreePoint(0, 0), FreePoint(2, 0)
        c2c, c2t = FreePoint(5, 0), FreePoint(6, 0)
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, c1c, c1t, cir1, c2c, c2t, cir2)
        con = TangentCirclesConstraint(cir1, cir2)
        doc.constraints.append(con)
        assert len(doc.constraints) == 1
        doc.remove(cir1)
        assert len(doc.constraints) == 0, \
            "删除圆后相切约束未被清理"

    def test_delete_circle_removes_concentric(self, doc):
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import ConcentricConstraint
        c1c, c1t = FreePoint(0, 0), FreePoint(2, 0)
        c2c, c2t = FreePoint(1, 1), FreePoint(4, 1)
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, c1c, c1t, cir1, c2c, c2t, cir2)
        doc.constraints.append(ConcentricConstraint(cir1, cir2))
        doc.remove(cir2)
        assert len(doc.constraints) == 0

    def test_delete_point_removes_distance(self, doc):
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(3, 4)
        _add(doc, p1, p2)
        doc.constraints.append(DistanceConstraint(p1, p2, "5"))
        doc.remove(p1)
        assert len(doc.constraints) == 0

    def test_delete_segment_endpoint_removes_constraints(self, doc):
        """删除线段端点 → 级联删除线段 → 涉及线段端点的约束被清理。"""
        from geo.points import FreePoint
        from geo.segments import Segment
        from constraints.types.horizontal import HorizontalConstraint
        a, b = FreePoint(0, 0), FreePoint(5, 0)
        seg = Segment(a, b)
        _add(doc, a, b, seg)
        doc.constraints.append(HorizontalConstraint(a, b))
        doc.remove(a)  # 级联删除 seg
        assert len(doc.constraints) == 0

    def test_delete_preserves_unrelated(self, doc):
        """删除一个对象不应影响无关约束。"""
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        from constraints.types.circle_constraints import TangentCirclesConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(3, 4)
        c1c, c1t = FreePoint(10, 0), FreePoint(12, 0)
        c2c, c2t = FreePoint(15, 0), FreePoint(16, 0)
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, p1, p2, c1c, c1t, cir1, c2c, c2t, cir2)
        doc.constraints.append(DistanceConstraint(p1, p2, "5"))
        doc.constraints.append(TangentCirclesConstraint(cir1, cir2))
        assert len(doc.constraints) == 2
        doc.remove(p1)
        assert len(doc.constraints) == 1, "无关约束被误删"
        assert doc.constraints[0].type_name == "tangent_circles"

    def test_cascade_delete_cleans_all(self, doc):
        """级联删除：圆 → 吸附点 → 约束全部清理。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(3, 0)
        cir = Circle(O, R)
        P = PointOnObject(cir, 0.5)
        P.recompute()
        Q = FreePoint(5, 5)
        _add(doc, O, R, cir, P, Q)
        doc.constraints.append(DistanceConstraint(P, Q, "3"))
        doc.remove(cir)  # 级联删除 P
        assert len(doc.constraints) == 0


# ═══════════════════════════════════════════════════════
#  E. P1-7：BFS 邻接表正确性
# ═══════════════════════════════════════════════════════

class TestBFSOptimization:

    def test_disconnected_components(self, doc):
        """两组不相连的约束，触发一组不影响另一组。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        from constraints.graph import get_affected_constraints
        p1, p2 = FreePoint(0, 0), FreePoint(1, 0)
        p3, p4 = FreePoint(10, 10), FreePoint(11, 10)
        _add(doc, p1, p2, p3, p4)
        c1 = DistanceConstraint(p1, p2, "1")
        c2 = DistanceConstraint(p3, p4, "1")
        doc.constraints.extend([c1, c2])
        affected = get_affected_constraints([p1], doc.constraints)
        assert c1 in affected
        assert c2 not in affected, "不相连的约束不应被包含"

    def test_connected_component_expands(self, doc):
        """共享点的约束应被完整扩展。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        from constraints.graph import get_affected_constraints
        p1, p2, p3 = FreePoint(0, 0), FreePoint(1, 0), FreePoint(2, 0)
        _add(doc, p1, p2, p3)
        c1 = DistanceConstraint(p1, p2, "1")
        c2 = DistanceConstraint(p2, p3, "1")
        doc.constraints.extend([c1, c2])
        affected = get_affected_constraints([p1], doc.constraints)
        assert c1 in affected
        assert c2 in affected, "通过共享点 p2 连通的约束应被包含"

    def test_no_duplicates(self, doc):
        """BFS 不应产生重复约束。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        from constraints.types.horizontal import HorizontalConstraint
        from constraints.graph import get_affected_constraints
        p1, p2 = FreePoint(0, 0), FreePoint(1, 0)
        _add(doc, p1, p2)
        c1 = DistanceConstraint(p1, p2, "1")
        c2 = HorizontalConstraint(p1, p2)
        doc.constraints.extend([c1, c2])
        affected = get_affected_constraints([p1], doc.constraints)
        assert len(affected) == len(set(id(c) for c in affected)), \
            "BFS 产生了重复约束"

    def test_empty_trigger(self, doc):
        from constraints.graph import get_affected_constraints
        assert get_affected_constraints([], []) == []

    def test_large_graph_performance(self, doc):
        """100 个约束的图，BFS 应在 50ms 内完成。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        from constraints.graph import get_affected_constraints
        pts = [FreePoint(float(i), 0) for i in range(101)]
        _add(doc, *pts)
        for i in range(100):
            doc.constraints.append(
                DistanceConstraint(pts[i], pts[i + 1], "1"))
        t0 = time.perf_counter()
        affected = get_affected_constraints([pts[0]], doc.constraints)
        elapsed = (time.perf_counter() - t0) * 1000
        assert elapsed < 50, f"BFS 耗时 {elapsed:.1f}ms > 50ms"
        assert len(affected) == 100, "链式约束应全部连通"

    def test_disabled_constraint_excluded(self, doc):
        """禁用的约束不参与图扩展。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        from constraints.graph import get_affected_constraints
        p1, p2, p3 = FreePoint(0, 0), FreePoint(1, 0), FreePoint(2, 0)
        _add(doc, p1, p2, p3)
        c1 = DistanceConstraint(p1, p2, "1")
        c2 = DistanceConstraint(p2, p3, "1")
        c2.enabled = False
        doc.constraints.extend([c1, c2])
        affected = get_affected_constraints([p1], doc.constraints)
        assert c2 not in affected, "禁用约束不应参与扩展"


# ═══════════════════════════════════════════════════════
#  F. P1-8：递归求解语义
# ═══════════════════════════════════════════════════════

class TestRecursiveSolve:

    def test_pinned_not_moved_in_recursion(self, doc):
        """递归求解不应移动已钉住的点。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(3, 0)
        cir = Circle(O, R)
        P = PointOnObject(cir, 0.25)
        P.recompute()
        Q = FreePoint(P.x + 5, P.y)
        _add(doc, O, R, cir, P, Q)
        doc.constraints.append(DistanceConstraint(P, Q, "5"))
        Q.x, Q.y = 2.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)
        assert Q.x == pytest.approx(2.0, abs=1e-9), "Q.x 被递归篡改"
        assert Q.y == pytest.approx(2.0, abs=1e-9), "Q.y 被递归篡改"

    def test_three_hop_chain(self, doc):
        """A → P(圆上) → B → C 三跳链。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(3, 0)
        cir = Circle(O, R)
        P = PointOnObject(cir, 0.0)
        P.recompute()
        A = FreePoint(P.x - 4, P.y)
        B = FreePoint(P.x + 6, P.y)
        C = FreePoint(B.x + 3, B.y)
        _add(doc, O, R, cir, P, A, B, C)
        doc.constraints.extend([
            DistanceConstraint(A, P, "4"),
            DistanceConstraint(P, B, "6"),
            DistanceConstraint(B, C, "3"),
        ])
        A.x, A.y = 1.0, 2.0
        doc.solve_constraints(trigger_points=[A], pinned_points=[A],
                              quick=False)
        assert _on_circle(P, cir), "P 脱离圆"
        assert _dist(A, P) == pytest.approx(4.0, abs=0.3)
        assert _dist(P, B) == pytest.approx(6.0, abs=0.3)
        assert _dist(B, C) == pytest.approx(3.0, abs=0.3)

    def test_depth_limit_no_infinite_loop(self, doc):
        """深度限制防止无限递归。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(1, 0)
        _add(doc, p1, p2)
        doc.constraints.append(DistanceConstraint(p1, p2, "1"))
        # 不应抛出 RecursionError
        doc.solve_constraints(trigger_points=[p1], pinned_points=[p1],
                              quick=True)


# ═══════════════════════════════════════════════════════
#  G. 退化几何
# ═══════════════════════════════════════════════════════

class TestDegenerateCases:

    def test_zero_length_segment(self, doc):
        """零长度线段：约束不应崩溃。"""
        from geo.points import FreePoint
        from geo.segments import Segment
        from constraints.types.parallel import ParallelConstraint
        a1, b1 = FreePoint(0, 0), FreePoint(0, 0)
        a2, b2 = FreePoint(1, 0), FreePoint(2, 0)
        _add(doc, a1, b1, a2, b2)
        c = ParallelConstraint(a1, b1, a2, b2)
        r = c.residual()
        assert len(r) == 1
        assert r[0] == 0.0, "退化时应返回 0 残差"

    def test_zero_radius_circle(self, doc):
        """零半径圆：等半径约束不应崩溃。"""
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import EqualRadiusConstraint
        c1c, c1t = FreePoint(0, 0), FreePoint(0, 0)  # r=0
        c2c, c2t = FreePoint(5, 0), FreePoint(8, 0)  # r=3
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        _add(doc, c1c, c1t, cir1, c2c, c2t, cir2)
        c = EqualRadiusConstraint(cir1, cir2)
        # 不应抛异常
        vm = {id(c1c): 0, id(c1t): 1, id(c2c): 2, id(c2t): 3}
        jac = c.jacobian(vm)
        assert jac is not None

    def test_coincident_points_distance(self, doc):
        """重合点的距离约束：不应除以零。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(5, 5), FreePoint(5, 5)
        _add(doc, p1, p2)
        c = DistanceConstraint(p1, p2, "3")
        vm = {id(p1): 0, id(p2): 1}
        jac = c.jacobian(vm)
        # 应返回全零雅可比（无法确定方向）
        assert all(abs(v) < 1e-10 for v in jac[0])

    def test_coincident_points_angle(self, doc):
        """顶点与边端点重合：角度约束不应崩溃。"""
        from geo.points import FreePoint
        from constraints.types.angle import AngleConstraint
        p1, v, p2 = FreePoint(0, 0), FreePoint(0, 0), FreePoint(1, 0)
        _add(doc, p1, v, p2)
        c = AngleConstraint(p1, v, p2, "90")
        r = c.residual()
        assert r[0] == 0.0, "退化时应返回 0"

    def test_perfectly_parallel_lines(self, doc):
        """已经完全平行的线：残差应为 0。"""
        from geo.points import FreePoint
        from constraints.types.parallel import ParallelConstraint
        a1, b1 = FreePoint(0, 0), FreePoint(5, 0)
        a2, b2 = FreePoint(0, 3), FreePoint(5, 3)
        _add(doc, a1, b1, a2, b2)
        c = ParallelConstraint(a1, b1, a2, b2)
        assert abs(c.residual()[0]) < 1e-10

    def test_perfectly_perpendicular_lines(self, doc):
        """已经完全垂直的线：残差应为 0。"""
        from geo.points import FreePoint
        from constraints.types.perpendicular import PerpendicularConstraint
        a1, b1 = FreePoint(0, 0), FreePoint(5, 0)
        a2, b2 = FreePoint(0, 0), FreePoint(0, 5)
        _add(doc, a1, b1, a2, b2)
        c = PerpendicularConstraint(a1, b1, a2, b2)
        assert abs(c.residual()[0]) < 1e-10

    def test_perfectly_collinear(self, doc):
        """已经完全共线的三点：残差应为 0。"""
        from geo.points import FreePoint
        from constraints.types.collinear import CollinearConstraint
        p1, p2, p3 = FreePoint(0, 0), FreePoint(1, 0), FreePoint(2, 0)
        _add(doc, p1, p2, p3)
        c = CollinearConstraint(p1, p2, p3)
        assert abs(c.residual()[0]) < 1e-10

    def test_angle_180_degrees(self, doc):
        """180° 角度约束（平角）。"""
        from geo.points import FreePoint
        from constraints.types.angle import AngleConstraint
        p1 = FreePoint(-1, 0)
        v = FreePoint(0, 0)
        p2 = FreePoint(1, 0.1)
        _add(doc, p1, v, p2)
        c = AngleConstraint(p1, v, p2, "180")
        doc.constraints.append(c)
        doc.solve_constraints(quick=False)
        assert abs(c.residual()[0]) < 1e-4

    def test_angle_very_small(self, doc):
        """极小角度 1°。"""
        from geo.points import FreePoint
        from constraints.types.angle import AngleConstraint
        p1 = FreePoint(math.cos(math.radians(5)),
                       math.sin(math.radians(5)))
        v = FreePoint(0, 0)
        p2 = FreePoint(1, 0)
        _add(doc, p1, v, p2)
        c = AngleConstraint(p1, v, p2, "1")
        doc.constraints.append(c)
        doc.solve_constraints(quick=False)
        assert abs(c.residual()[0]) < 1e-3

    def test_tangent_concentric_degenerate(self, doc):
        """同心圆相切（退化：d=0）。"""
        from geo.points import FreePoint
        from geo.circles import Circle
        from constraints.types.circle_constraints import TangentCirclesConstraint
        O = FreePoint(0, 0)
        t1, t2 = FreePoint(3, 0), FreePoint(5, 0)
        cir1, cir2 = Circle(O, t1), Circle(O, t2)
        _add(doc, O, t1, cir1, t2, cir2)
        c = TangentCirclesConstraint(cir1, cir2, mode="outer")
        r = c.residual()
        # d=0, r1+r2=8 → 残差 = -8
        assert len(r) == 1
        # 不应崩溃
        vm = {id(O): 0, id(t1): 1, id(t2): 2}
        jac = c.jacobian(vm)
        assert jac is not None


# ═══════════════════════════════════════════════════════
#  H. 过约束回滚
# ═══════════════════════════════════════════════════════

class TestOverConstraint:

    def test_conflicting_distances_rollback(self, doc):
        """两个矛盾的距离约束 → 第二个应被回滚。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(5, 0)
        _add(doc, p1, p2)
        doc.add_constraint(DistanceConstraint(p1, p2, "5"))
        assert len(doc.constraints) == 1
        # 同一对点约束为 10 → 冲突
        doc.add_constraint(DistanceConstraint(p1, p2, "10"))
        assert len(doc.constraints) == 1, "冲突约束应被回滚"

    def test_conflicting_fixed_positions(self, doc):
        """固定在不同位置 → 冲突。"""
        from geo.points import FreePoint
        from constraints.types.fixed import FixedConstraint
        p = FreePoint(0, 0)
        _add(doc, p)
        doc.add_constraint(FixedConstraint(p, 0, 0))
        assert len(doc.constraints) == 1
        doc.add_constraint(FixedConstraint(p, 10, 10))
        assert len(doc.constraints) == 1, "矛盾固定约束应被回滚"

    def test_rollback_restores_coordinates(self, doc):
        """回滚后所有点坐标必须恢复。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(5, 0)
        _add(doc, p1, p2)
        doc.add_constraint(DistanceConstraint(p1, p2, "5"))
        old = [(p.x, p.y) for p in doc.objects]
        doc.add_constraint(DistanceConstraint(p1, p2, "10"))
        new = [(p.x, p.y) for p in doc.objects]
        for o, n in zip(old, new):
            assert o[0] == pytest.approx(n[0], abs=1e-9)
            assert o[1] == pytest.approx(n[1], abs=1e-9)

    def test_rollback_restores_poo_t(self, doc):
        """回滚后吸附点的 t 值必须恢复（P0 修复验证）。"""
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint
        O, R = FreePoint(0, 0), FreePoint(3, 0)
        cir = Circle(O, R)
        P = PointOnObject(cir, 0.25)
        P.recompute()
        Q = FreePoint(P.x + 5, P.y)
        _add(doc, O, R, cir, P, Q)
        doc.add_constraint(DistanceConstraint(P, Q, "5"))
        old_t = P.t
        # 添加不可满足的约束（P 在圆上，Q 被固定）
        Q.x, Q.y = 100.0, 100.0
        doc.add_constraint(DistanceConstraint(P, Q, "1"))
        assert P.t == pytest.approx(old_t, abs=1e-6), \
            f"回滚后 P.t 未恢复: {P.t} vs {old_t}"

    def test_compatible_constraints_both_kept(self, doc):
        """兼容的约束都应保留。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        from constraints.types.horizontal import HorizontalConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(5, 0)
        _add(doc, p1, p2)
        doc.add_constraint(DistanceConstraint(p1, p2, "5"))
        doc.add_constraint(HorizontalConstraint(p1, p2))
        assert len(doc.constraints) == 2, "兼容约束不应被回滚"


# ═══════════════════════════════════════════════════════
#  I. 求解器鲁棒性
# ═══════════════════════════════════════════════════════

class TestSolverRobustness:

    def test_very_large_coordinates(self, doc):
        """大坐标（1e6 量级）下求解器不应崩溃。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1 = FreePoint(1e6, 1e6)
        p2 = FreePoint(1e6 + 3, 1e6 + 4)
        _add(doc, p1, p2)
        doc.constraints.append(DistanceConstraint(p1, p2, "5"))
        p2.x, p2.y = 1e6 + 1, 1e6 + 1
        doc.solve_constraints(trigger_points=[p2], pinned_points=[p2],
                              quick=False)
        assert _dist(p1, p2) == pytest.approx(5.0, abs=0.1)

    def test_very_small_coordinates(self, doc):
        """小坐标（1e-6 量级）下求解器不应崩溃。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1 = FreePoint(0, 0)
        p2 = FreePoint(3e-6, 4e-6)
        _add(doc, p1, p2)
        doc.constraints.append(DistanceConstraint(p1, p2, "5e-6"))
        doc.solve_constraints(quick=False)
        assert _dist(p1, p2) == pytest.approx(5e-6, abs=1e-7)

    def test_many_constraints_same_point(self, doc):
        """一个点同时受 5 个约束。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        center = FreePoint(0, 0)
        _add(doc, center)
        others = []
        for i in range(5):
            ang = 2 * math.pi * i / 5
            p = FreePoint(math.cos(ang), math.sin(ang))
            _add(doc, p)
            others.append(p)
            doc.constraints.append(DistanceConstraint(center, p, "1"))
        center.x, center.y = 0.5, 0.5
        doc.solve_constraints(trigger_points=[center],
                              pinned_points=[center], quick=False)
        for p in others:
            assert _dist(center, p) == pytest.approx(1.0, abs=0.2)

    def test_mixed_constraint_types(self, doc):
        """距离 + 水平 + 角度混合约束。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        from constraints.types.horizontal import HorizontalConstraint
        from constraints.types.angle import AngleConstraint
        p1 = FreePoint(0, 0)
        p2 = FreePoint(5, 0)
        p3 = FreePoint(5, 5)
        _add(doc, p1, p2, p3)
        doc.constraints.extend([
            DistanceConstraint(p1, p2, "5"),
            HorizontalConstraint(p1, p2),
            AngleConstraint(p1, p2, p3, "90"),
        ])
        doc.solve_constraints(quick=False)
        assert _dist(p1, p2) == pytest.approx(5.0, abs=0.1)
        assert abs(p1.y - p2.y) < 0.1

    def test_sequential_solve_idempotent(self, doc):
        """连续求解两次，第二次不应改变结果。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(3, 4)
        _add(doc, p1, p2)
        doc.constraints.append(DistanceConstraint(p1, p2, "5"))
        doc.solve_constraints(quick=False)
        x1, y1 = p1.x, p1.y
        x2, y2 = p2.x, p2.y
        doc.solve_constraints(quick=False)
        assert p1.x == pytest.approx(x1, abs=1e-9)
        assert p1.y == pytest.approx(y1, abs=1e-9)
        assert p2.x == pytest.approx(x2, abs=1e-9)
        assert p2.y == pytest.approx(y2, abs=1e-9)

    def test_solve_returns_true_when_converged(self, doc):
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(3, 4)
        _add(doc, p1, p2)
        doc.constraints.append(DistanceConstraint(p1, p2, "5"))
        assert doc.solve_constraints(quick=False) is True

    def test_solve_returns_true_no_constraints(self, doc):
        from geo.points import FreePoint
        _add(doc, FreePoint(0, 0))
        assert doc.solve_constraints(quick=True) is True

    def test_solve_returns_true_all_pinned(self, doc):
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(3, 4)
        _add(doc, p1, p2)
        doc.constraints.append(DistanceConstraint(p1, p2, "5"))
        assert doc.solve_constraints(
            trigger_points=[p1], pinned_points=[p1, p2],
            quick=True) is True


# ═══════════════════════════════════════════════════════
#  J. 约束启用/禁用
# ═══════════════════════════════════════════════════════

class TestConstraintEnableDisable:

    def test_disabled_constraint_ignored(self, doc):
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(5, 0)
        _add(doc, p1, p2)
        c = DistanceConstraint(p1, p2, "3")
        c.enabled = False
        doc.constraints.append(c)
        doc.solve_constraints(quick=False)
        # 约束被禁用，点不应移动
        assert _dist(p1, p2) == pytest.approx(5.0, abs=1e-6)

    def test_reenable_constraint(self, doc):
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(5, 0)
        _add(doc, p1, p2)
        c = DistanceConstraint(p1, p2, "3")
        c.enabled = False
        doc.constraints.append(c)
        doc.solve_constraints(quick=False)
        assert _dist(p1, p2) == pytest.approx(5.0, abs=1e-6)
        c.enabled = True
        doc.solve_constraints(quick=False)
        assert _dist(p1, p2) == pytest.approx(3.0, abs=0.1)


# ═══════════════════════════════════════════════════════
#  K. 表达式边界
# ═══════════════════════════════════════════════════════

class TestEdgeCaseExpressions:

    def test_invalid_expr_status(self, doc):
        """无效表达式 → status 标记，残差为 0。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(1, 0)
        _add(doc, p1, p2)
        c = DistanceConstraint(p1, p2, "not_a_number_xyz")
        r = c.residual()
        assert c.status == "invalid_expr"
        assert r == [0.0]

    def test_negative_distance_expr(self, doc):
        """负距离表达式。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(5, 0)
        _add(doc, p1, p2)
        c = DistanceConstraint(p1, p2, "-3")
        r = c.residual()
        # d=5, target=-3 → residual=8
        assert len(r) == 1

    def test_angle_negative_expr(self, doc):
        """负角度 → 取绝对值。"""
        from geo.points import FreePoint
        from constraints.types.angle import AngleConstraint
        p1 = FreePoint(1, 0)
        v = FreePoint(0, 0)
        p2 = FreePoint(0, 1)
        _add(doc, p1, v, p2)
        c = AngleConstraint(p1, v, p2, "-90")
        target = c._target_rad()
        assert target == pytest.approx(math.pi / 2, abs=1e-6)

    def test_zero_distance_expr(self, doc):
        """距离为 0 → 两点重合。"""
        from geo.points import FreePoint
        from constraints.types.distance import DistanceConstraint
        p1, p2 = FreePoint(0, 0), FreePoint(1, 0)
        _add(doc, p1, p2)
        c = DistanceConstraint(p1, p2, "0")
        doc.constraints.append(c)
        doc.solve_constraints(quick=False)
        assert _dist(p1, p2) < 0.1


# ═══════════════════════════════════════════════════════
#  L. 序列化往返
# ═══════════════════════════════════════════════════════

class TestSerializationRoundTrip:

    def test_all_constraint_types_dump_build(self, doc):
        """所有约束类型的 dump/build 往返不丢数据。"""
        from geo.points import FreePoint
        from geo.circles import Circle
        from geo.segments import Segment
        from constraints.base import CONSTRAINT_REGISTRY
        from constraints.types.distance import DistanceConstraint
        from constraints.types.horizontal import HorizontalConstraint
        from constraints.types.angle import AngleConstraint
        from constraints.types.circle_constraints import (
            ConcentricConstraint, EqualRadiusConstraint,
            TangentCirclesConstraint, TangentLineCircleConstraint)

        p1, p2, p3 = FreePoint(0, 0), FreePoint(1, 0), FreePoint(0, 1)
        v = FreePoint(0, 0)
        c1c, c1t = FreePoint(5, 0), FreePoint(7, 0)
        c2c, c2t = FreePoint(10, 0), FreePoint(12, 0)
        cir1, cir2 = Circle(c1c, c1t), Circle(c2c, c2t)
        a, b = FreePoint(0, 5), FreePoint(10, 5)
        seg = Segment(a, b)
        objs = [p1, p2, p3, v, c1c, c1t, c2c, c2t, cir1, cir2, a, b, seg]
        _add(doc, *objs)
        obj_map = {o.id: o for o in doc.objects}

        constraints_to_test = [
            DistanceConstraint(p1, p2, "5"),
            HorizontalConstraint(p1, p2),
            AngleConstraint(p1, v, p2, "90"),
            ConcentricConstraint(cir1, cir2),
            EqualRadiusConstraint(cir1, cir2),
            TangentCirclesConstraint(cir1, cir2, "outer"),
            TangentLineCircleConstraint(seg, cir1),
        ]
        for c in constraints_to_test:
            params = c.dump()
            assert isinstance(params, dict), \
                f"{type(c).__name__}.dump() 应返回 dict"
            rebuilt = type(c).build(obj_map, params)
            assert rebuilt.type_name == c.type_name
            # 残差应一致
            r_orig = c.residual()
            r_new = rebuilt.residual()
            for ro, rn in zip(r_orig, r_new):
                assert ro == pytest.approx(rn, abs=1e-9), \
                    f"{type(c).__name__} 重建后残差不一致"