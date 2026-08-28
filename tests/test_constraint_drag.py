"""tests/test_constraint_drag.py

约束拖动系统回归测试（修正版）。
所有测试数据均保证约束可满足。

运行：pytest tests/test_constraint_drag.py -v
"""

import math
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


# ═══════════════════════ 场景工厂 ═══════════════════════


def build_circle_scene(doc, dist_val=5.0):
    """
    圆 O(0,0) r=3，吸附点 P(t=0.25)→(0,3)，
    自由点 Q 初始在 (3,4)（|P−Q|=5 可满足范围内）。

    可达距离范围：[|Q|−r, |Q|+r]
    """
    from geo.points import FreePoint, PointOnObject
    from geo.circles import Circle
    from constraints.types.distance import DistanceConstraint

    O = FreePoint(0.0, 0.0)
    R = FreePoint(3.0, 0.0)
    circle = Circle(O, R)
    P = PointOnObject(circle, t=0.25)
    P.recompute()
    # Q 放在 P 右侧，距离 = dist_val
    Q = FreePoint(P.x + dist_val, P.y)

    con = DistanceConstraint(P, Q, expr=str(dist_val))
    _add(doc, O, R, circle, P, Q)
    doc.constraints.append(con)
    return O, R, circle, P, Q, con


def build_segment_scene(doc, dist_val=4.0):
    """
    线段 A(0,0)→B(10,0)，吸附点 P(t=0.5)→(5,0)，
    自由点 Q 在 (5, 4)。
    """
    from geo.points import FreePoint, PointOnObject
    from geo.segments import Segment
    from constraints.types.distance import DistanceConstraint

    A = FreePoint(0.0, 0.0)
    B = FreePoint(10.0, 0.0)
    seg = Segment(A, B)
    P = PointOnObject(seg, t=0.5)
    P.recompute()
    Q = FreePoint(P.x, P.y + dist_val)

    con = DistanceConstraint(P, Q, expr=str(dist_val))
    _add(doc, A, B, seg, P, Q)
    doc.constraints.append(con)
    return A, B, seg, P, Q, con


# ═══════════════ 1. 拖动自由点 → 吸附点跟随 ═══════════════


class TestDragFreePoint:

    def test_circle_distance_maintained(self, doc):
        """
        拖动 Q 到 (2, 2)。
        |Q|=2.83, 圆上可达距离=[0, 5.83], 约束 5 在范围内 ✓
        """
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)
        old = (P.x, P.y)

        # ★ 关键：Q 必须离圆足够近，使约束可满足
        # |Q| = 2.83, 可达范围 [0, 5.83] ⊃ 5 ✓
        Q.x, Q.y = 2.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        assert (P.x, P.y) != old, "P 应沿圆滑动"
        assert _on_circle(P, circle), f"P 脱离圆 ({P.x:.3f},{P.y:.3f})"
        assert _dist(P, Q) == pytest.approx(5.0, abs=0.1)

    def test_segment_distance_maintained(self, doc):
        """
        拖动 Q 到 (5, 2)。
        线段上可达距离=[0, ~5], 约束 4 在范围内 ✓
        """
        _, _, seg, P, Q, _ = build_segment_scene(doc, 4.0)
        old = (P.x, P.y)

        # Q 在线段正上方 2 单位，最近距离=2 < 4 ✓
        Q.x, Q.y = 5.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        assert (P.x, P.y) != old, "P 应沿线段滑动"
        assert _on_segment(P, seg), f"P 脱离线段 ({P.x:.3f},{P.y:.3f})"
        assert _dist(P, Q) == pytest.approx(4.0, abs=0.1)

    def test_pinned_point_immovable(self, doc):
        """被拖动（pin）的点坐标不被求解器篡改。"""
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)
        tx, ty = 2.0, 2.0
        Q.x, Q.y = tx, ty

        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        assert Q.x == pytest.approx(tx, abs=1e-9)
        assert Q.y == pytest.approx(ty, abs=1e-9)

    def test_multiple_drag_frames(self, doc):
        """
        连续 5 帧拖动，Q 始终在圆附近（可达范围内）。
        圆半径 3，约束 5 → |Q| 需 < 8
        """
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        positions = [(2, 1), (1, 2), (-1, 2), (-2, 1), (-1, -1)]
        for i, (qx, qy) in enumerate(positions):
            Q.x, Q.y = qx, qy
            doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                                  quick=True)
            assert _on_circle(P, circle), f"帧 {i}: P 脱离圆"
            # quick 模式精度较低，放宽容差
            assert _dist(P, Q) == pytest.approx(5.0, abs=0.5), \
                f"帧 {i}: 距离 {_dist(P, Q):.4f}"


# ═══════════════ 2. 拖动吸附点 → 自由点跟随 ═══════════════


class TestDragAttachedPoint:

    def test_circle_poo_drags_free_point(self, doc):
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)
        old_q = (Q.x, Q.y)

        P.t = 0.50
        P.recompute()
        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=True)

        assert (Q.x, Q.y) != old_q, "Q 应跟随移动"
        assert _dist(P, Q) == pytest.approx(5.0, abs=1e-3)

    def test_segment_poo_drags_free_point(self, doc):
        _, _, _, P, Q, _ = build_segment_scene(doc, 4.0)
        old_q = (Q.x, Q.y)

        P.t = 0.85
        P.recompute()
        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=True)

        assert (Q.x, Q.y) != old_q, "Q 应跟随移动"
        assert _dist(P, Q) == pytest.approx(4.0, abs=1e-3)


# ═══════════════ 3. 投影完整性 ═══════════════


class TestProjectionIntegrity:

    def test_t_xy_consistent_circle(self, doc):
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        Q.x, Q.y = 2.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        ex, ey = circle.point_at(P.t)
        assert P.x == pytest.approx(ex, abs=1e-5)
        assert P.y == pytest.approx(ey, abs=1e-5)

    def test_t_xy_consistent_segment(self, doc):
        _, _, seg, P, Q, _ = build_segment_scene(doc, 4.0)

        Q.x, Q.y = 5.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        ex, ey = seg.point_at(P.t)
        assert P.x == pytest.approx(ex, abs=1e-5)
        assert P.y == pytest.approx(ey, abs=1e-5)

    def test_t_in_valid_range(self, doc):
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)

        for dx, dy in [(2, 2), (-2, 2), (0, 4), (-2, -2)]:
            Q.x, Q.y = dx, dy
            doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                                  quick=True)
            assert 0.0 <= P.t <= 1.0, f"P.t={P.t} 越界"


# ═══════════════ 4. 松手后无弹跳 ═══════════════


class TestNoSnapBack:

    def test_release_does_not_move_pinned(self, doc):
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)

        Q.x, Q.y = 2.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)
        qx, qy = Q.x, Q.y

        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        assert Q.x == pytest.approx(qx, abs=1e-9), "松手后 Q 弹跳"
        assert Q.y == pytest.approx(qy, abs=1e-9), "松手后 Q 弹跳"

    def test_full_solve_residual_tiny(self, doc):
        """
        ★ 修正：Q=(1,2), |Q|=2.24, 可达范围[0, 5.24] ⊃ 5 ✓
        """
        _, _, _, P, Q, con = build_circle_scene(doc, 5.0)

        Q.x, Q.y = 1.0, 2.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        assert abs(con.residual()[0]) < 1e-6, \
            f"残差 {con.residual()[0]}"


# ═══════════════ 5. 多约束链 ═══════════════


class TestMultiConstraintChain:

    def test_two_hop_chain(self, doc):
        from geo.points import FreePoint, PointOnObject
        from geo.circles import Circle
        from constraints.types.distance import DistanceConstraint

        O = FreePoint(0.0, 0.0)
        R = FreePoint(3.0, 0.0)
        circle = Circle(O, R)
        P = PointOnObject(circle, t=0.0)
        P.recompute()

        A = FreePoint(P.x - 4.0, P.y)
        B = FreePoint(P.x + 6.0, P.y)
        c1 = DistanceConstraint(A, P, expr="4")
        c2 = DistanceConstraint(P, B, expr="6")

        _add(doc, O, R, circle, P, A, B)
        doc.constraints.extend([c1, c2])

        old_b = (B.x, B.y)
        # A 拖到圆附近（可达范围内）
        A.x, A.y = 1.0, 2.0

        doc.solve_constraints(trigger_points=[A], pinned_points=[A],
                              quick=True)

        assert _on_circle(P, circle), "P 脱离圆"
        assert (B.x, B.y) != old_b, "B 应跟随"
        assert _dist(A, P) == pytest.approx(4.0, abs=0.2)
        assert _dist(P, B) == pytest.approx(6.0, abs=0.2)


# ═══════════════ 6. 求解器边缘情况 ═══════════════


class TestSolverEdgeCases:

    def test_all_pinned_returns_true(self, doc):
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)
        assert doc.solve_constraints(trigger_points=[Q],
                                     pinned_points=[Q, P],
                                     quick=True) is True

    def test_no_constraints_returns_true(self, doc):
        from geo.points import FreePoint
        _add(doc, FreePoint(1, 2))
        assert doc.solve_constraints(quick=True) is True

    def test_infeasible_converges_to_best(self, doc):
        """
        ★ 新增：不可满足约束 → 应收敛到最小二乘解，不崩溃。
        Q=(10,8), 最近距离 9.81 > 约束 5
        """
        _, _, circle, P, Q, con = build_circle_scene(doc, 5.0)

        Q.x, Q.y = 10.0, 8.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        # 不崩溃，P 仍在圆上
        assert _on_circle(P, circle)
        # 残差 = 最近距离 − 5 ≈ 4.81（不可满足，但已是最优）
        assert _dist(P, Q) == pytest.approx(9.81, abs=0.1)

    def test_reject_step_restores_state(self, doc):
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        for _ in range(3):
            Q.x, Q.y = 2.0, 2.0
            doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                                  quick=True)
            ex, ey = circle.point_at(P.t)
            assert P.x == pytest.approx(ex, abs=1e-4)
            assert P.y == pytest.approx(ey, abs=1e-4)


# ═══════════════ 7. 雅可比正确性 ═══════════════


class TestJacobian:

    def test_nonzero_when_poo_in_vars(self, doc):
        _, _, _, P, Q, con = build_circle_scene(doc, 5.0)
        vars_map = {id(P): 0}
        jac = con.jacobian(vars_map)

        assert len(jac) >= 1
        assert any(abs(v) > 1e-10 for v in jac[0]), \
            f"雅可比全零 {jac}"

    def test_gradient_reduces_residual(self, doc):
        _, _, circle, P, Q, con = build_circle_scene(doc, 5.0)

        # 在可满足范围内制造残差
        Q.x, Q.y = 1.0, 2.0
        r0 = abs(con.residual()[0])
        assert r0 > 0.1, "初始残差太小，无法测试"

        vars_map = {id(P): 0}
        jac = con.jacobian(vars_map)
        step = 0.01
        P.x -= jac[0][0] * step * con.residual()[0]
        P.y -= jac[0][1] * step * con.residual()[0]
        P.t = circle.project(P.x, P.y)
        P.x, P.y = circle.point_at(P.t)

        r1 = abs(con.residual()[0])
        assert r1 < r0, f"残差未减小 {r0:.6f} → {r1:.6f}"


# ═══════════════ 8. select.py 调用模式 ═══════════════


class TestSelectToolPattern:

    def test_move_pattern_free_point(self, doc):
        """move(): dragged={Q}, pinned={Q}。"""
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        # ★ 可满足位置
        Q.x, Q.y = 2.0, 2.0
        dragged = {Q}
        doc.solve_constraints(trigger_points=list(dragged),
                              pinned_points=list(dragged),
                              quick=True)

        assert Q.x == pytest.approx(2.0, abs=1e-12)
        assert _on_circle(P, circle, tol=1e-3)

    def test_release_pattern_free_point(self, doc):
        """release(): 同上但 quick=False。"""
        _, _, circle, P, Q, con = build_circle_scene(doc, 5.0)

        # ★ 可满足位置
        Q.x, Q.y = 2.0, 2.0
        dragged = {Q}
        doc.solve_constraints(trigger_points=list(dragged),
                              pinned_points=list(dragged),
                              quick=False)

        assert abs(con.residual()[0]) < 1e-6
        assert _on_circle(P, circle)

    def test_move_pattern_poo(self, doc):
        """move(): dragged={P}, pinned={P}，Q 应被求解器移动。"""
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)
        old_q = (Q.x, Q.y)

        P.t = 0.75
        P.recompute()
        dragged = {P}
        doc.solve_constraints(trigger_points=list(dragged),
                              pinned_points=list(dragged),
                              quick=True)

        assert (Q.x, Q.y) != old_q, "Q 应被求解器移动"
        assert _dist(P, Q) == pytest.approx(5.0, abs=1e-3)