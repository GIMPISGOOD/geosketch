"""tests/test_constraint_drag.py

约束拖动系统回归测试。
验证核心修复：拖动 FreePoint / PointOnObject 时，
关联点实时跟随、距离/角度始终满足、吸附点不脱离曲线。

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
    圆 O(0,0) r=3  ←  吸附点 P(t=0.25)  ←dist→  自由点 Q
    返回 (O, R, circle, P, Q, constraint)
    """
    from geo.points import FreePoint, PointOnObject
    from geo.circles import Circle
    from constraints.types.distance import DistanceConstraint

    O = FreePoint(0.0, 0.0)
    R = FreePoint(3.0, 0.0)
    circle = Circle(O, R)
    P = PointOnObject(circle, t=0.25)       # 圆顶 (0, 3)
    P.recompute()
    Q = FreePoint(P.x + dist_val, P.y)      # (5, 3)

    con = DistanceConstraint(P, Q, expr=str(dist_val))
    _add(doc, O, R, circle, P, Q)
    doc.constraints.append(con)
    return O, R, circle, P, Q, con


def build_segment_scene(doc, dist_val=4.0):
    """
    线段 A(0,0)→B(10,0)  ←  吸附点 P(t=0.5)  ←dist→  自由点 Q
    返回 (A, B, seg, P, Q, constraint)
    """
    from geo.points import FreePoint, PointOnObject
    from geo.segments import Segment
    from constraints.types.distance import DistanceConstraint

    A = FreePoint(0.0, 0.0)
    B = FreePoint(10.0, 0.0)
    seg = Segment(A, B)
    P = PointOnObject(seg, t=0.5)           # 中点 (5, 0)
    P.recompute()
    Q = FreePoint(P.x, P.y + dist_val)      # (5, 4)

    con = DistanceConstraint(P, Q, expr=str(dist_val))
    _add(doc, A, B, seg, P, Q)
    doc.constraints.append(con)
    return A, B, seg, P, Q, con


# ═══════════════ 1. 拖动自由点 → 吸附点跟随 ═══════════════


class TestDragFreePoint:

    def test_circle_distance_maintained(self, doc):
        """拖动 Q → P 沿圆滑动，|P−Q| = d。"""
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)
        old = (P.x, P.y)

        Q.x, Q.y = 10.0, 8.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        assert (P.x, P.y) != old, "P 应沿圆滑动"
        assert _on_circle(P, circle), f"P 脱离圆 ({P.x:.3f},{P.y:.3f})"
        assert _dist(P, Q) == pytest.approx(5.0, abs=1e-3)

    def test_segment_distance_maintained(self, doc):
        """拖动 Q → P 沿线段滑动，|P−Q| = d。"""
        _, _, seg, P, Q, _ = build_segment_scene(doc, 4.0)
        old = (P.x, P.y)

        Q.x, Q.y = 8.0, 6.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        assert (P.x, P.y) != old, "P 应沿线段滑动"
        assert _on_segment(P, seg), f"P 脱离线段 ({P.x:.3f},{P.y:.3f})"
        assert _dist(P, Q) == pytest.approx(4.0, abs=1e-3)

    def test_pinned_point_immovable(self, doc):
        """被拖动（pin）的点坐标不被求解器篡改。"""
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)
        tx, ty = 7.0, 3.0
        Q.x, Q.y = tx, ty

        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        assert Q.x == pytest.approx(tx, abs=1e-12)
        assert Q.y == pytest.approx(ty, abs=1e-12)

    def test_multiple_drag_frames(self, doc):
        """连续 10 帧拖动，每帧 P 都在圆上且距离正确。"""
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        for i in range(10):
            Q.x = 3.0 + i * 1.2
            Q.y = 2.0 + i * 0.8
            doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                                  quick=True)
            assert _on_circle(P, circle), f"帧 {i}: P 脱离圆"
            assert _dist(P, Q) == pytest.approx(5.0, abs=0.15), \
                f"帧 {i}: 距离 {_dist(P, Q):.4f}"


# ═══════════════ 2. 拖动吸附点 → 自由点跟随 ═══════════════


class TestDragAttachedPoint:

    def test_circle_poo_drags_free_point(self, doc):
        """拖动 P 沿圆 → Q 跟随，距离保持。"""
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)
        old_q = (Q.x, Q.y)

        P.t = 0.50                          # 滑到右侧
        P.recompute()
        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=True)

        assert (Q.x, Q.y) != old_q, "Q 应跟随"
        assert _dist(P, Q) == pytest.approx(5.0, abs=1e-3)

    def test_segment_poo_drags_free_point(self, doc):
        """拖动 P 沿线段 → Q 跟随。"""
        _, _, _, P, Q, _ = build_segment_scene(doc, 4.0)
        old_q = (Q.x, Q.y)

        P.t = 0.85
        P.recompute()
        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=True)

        assert (Q.x, Q.y) != old_q, "Q 应跟随"
        assert _dist(P, Q) == pytest.approx(4.0, abs=1e-3)


# ═══════════════ 3. 投影完整性 ═══════════════


class TestProjectionIntegrity:

    def test_t_xy_consistent_circle(self, doc):
        """求解后 P.t ↔ P.(x,y) 一致。"""
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        Q.x, Q.y = 12.0, -3.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        ex, ey = circle.point_at(P.t)
        assert P.x == pytest.approx(ex, abs=1e-5)
        assert P.y == pytest.approx(ey, abs=1e-5)

    def test_t_xy_consistent_segment(self, doc):
        _, _, seg, P, Q, _ = build_segment_scene(doc, 4.0)

        Q.x, Q.y = -2.0, 9.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        ex, ey = seg.point_at(P.t)
        assert P.x == pytest.approx(ex, abs=1e-5)
        assert P.y == pytest.approx(ey, abs=1e-5)

    def test_t_in_valid_range(self, doc):
        """P.t 应始终在 [0, 1] 内。"""
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)

        for dx, dy in [(20, 20), (-20, -20), (0, 50), (-50, 0)]:
            Q.x, Q.y = dx, dy
            doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                                  quick=True)
            assert 0.0 <= P.t <= 1.0, f"P.t={P.t} 越界"


# ═══════════════ 4. 松手后无弹跳 ═══════════════


class TestNoSnapBack:

    def test_release_does_not_move_pinned(self, doc):
        """quick→full 切换后，被 pin 的 Q 坐标不变。"""
        _, _, _, P, Q, _ = build_circle_scene(doc, 5.0)

        Q.x, Q.y = 9.0, 5.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)
        qx, qy = Q.x, Q.y

        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        assert Q.x == pytest.approx(qx, abs=1e-12), "松手后 Q 弹跳"
        assert Q.y == pytest.approx(qy, abs=1e-12), "松手后 Q 弹跳"

    def test_full_solve_residual_tiny(self, doc):
        """quick=False 后残差 < 1e-6。"""
        _, _, _, P, Q, con = build_circle_scene(doc, 5.0)

        Q.x, Q.y = -4.0, 7.0
        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=False)

        assert abs(con.residual()[0]) < 1e-6


# ═══════════════ 5. 多约束链 ═══════════════


class TestMultiConstraintChain:

    def test_two_hop_chain(self, doc):
        """A ←4→ P(圆) ←6→ B：拖 A → P 滑 → B 跟。"""
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
        A.x, A.y = 5.0, 5.0

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

    def test_extreme_position_stays_on_curve(self, doc):
        """Q 拉到极远处，P 仍不脱离曲线。"""
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)
        Q.x, Q.y = 200.0, 200.0

        doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                              quick=True)

        assert _on_circle(P, circle, tol=0.5), \
            f"极端位置 P 脱离圆 ({P.x:.1f},{P.y:.1f})"

    def test_reject_step_restores_state(self, doc):
        """LM 拒绝步后，P 的 t / x / y 保持一致。"""
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        for _ in range(3):
            Q.x += 50.0
            doc.solve_constraints(trigger_points=[Q], pinned_points=[Q],
                                  quick=True)
            ex, ey = circle.point_at(P.t)
            assert P.x == pytest.approx(ex, abs=1e-4)
            assert P.y == pytest.approx(ey, abs=1e-4)


# ═══════════════ 7. 雅可比正确性 ═══════════════


class TestJacobian:

    def test_nonzero_when_poo_in_vars(self, doc):
        """P 在 vars_map 中时雅可比非零。"""
        _, _, _, P, Q, con = build_circle_scene(doc, 5.0)
        vars_map = {id(P): 0}
        jac = con.jacobian(vars_map)

        assert len(jac) >= 1
        assert any(abs(v) > 1e-10 for v in jac[0]), \
            f"雅可比全零 {jac}"

    def test_gradient_reduces_residual(self, doc):
        """沿雅可比负方向走一步，残差应减小。"""
        _, _, circle, P, Q, con = build_circle_scene(doc, 5.0)

        Q.x += 2.0                          # 制造残差
        r0 = abs(con.residual()[0])

        vars_map = {id(P): 0}
        jac = con.jacobian(vars_map)
        step = 0.1
        P.x -= jac[0][0] * step * con.residual()[0]
        P.y -= jac[0][1] * step * con.residual()[0]
        P.t = circle.project(P.x, P.y)
        P.x, P.y = circle.point_at(P.t)

        r1 = abs(con.residual()[0])
        assert r1 < r0, f"残差未减小 {r0:.6f} → {r1:.6f}"


# ═══════════════ 8. select.py 调用模式 ═══════════════


class TestSelectToolPattern:
    """模拟 select.py 修复后的调用模式。"""

    def test_move_pattern_free_point(self, doc):
        """move(): dragged={Q}, pinned={Q}。"""
        _, _, circle, P, Q, _ = build_circle_scene(doc, 5.0)

        # 模拟 select.py move()
        Q.x, Q.y = 6.0, 7.0              # drag_to
        dragged = {Q}
        doc.solve_constraints(trigger_points=list(dragged),
                              pinned_points=list(dragged),
                              quick=True)

        assert Q.x == pytest.approx(6.0, abs=1e-12)
        assert _on_circle(P, circle if 'circle' in dir() else
                          doc.objects[2], tol=1e-3)

    def test_release_pattern_free_point(self, doc):
        """release(): 同上但 quick=False。"""
        _, _, circle, P, Q, con = build_circle_scene(doc, 5.0)

        Q.x, Q.y = 6.0, 7.0
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