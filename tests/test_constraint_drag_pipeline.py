"""tests/test_constraint_drag_pipeline.py

阶段 2 回归：pin 语义（位置冻结）+ 拖动步长预算 + merit 污染防护。

运行：pytest tests/test_constraint_drag_pipeline.py -v
"""

import math
import os
import sys
import time

import pytest
from numpy import asarray, isfinite

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from geo.points import FreePoint, PointOnObject
from geo.segments import Segment
from constraints import types  # noqa: F401  触发 @register_constraint
from constraints.base import GeometricConstraint
from constraints.solver import ConstraintSolver, _rescale_rows
from constraints.types.distance import DistanceConstraint


def _scene(doc, length=1000.0, target=5.0):
    A = FreePoint(0.0, 0.0)
    B = FreePoint(length, 0.0)
    seg = Segment(A, B)
    P = PointOnObject(seg, t=target / length)
    for o in (A, B, seg, P):
        doc.add(o)
    con = DistanceConstraint(P, A, expr=str(target))
    doc.constraints.append(con)
    return A, B, seg, P, con


# ═══════════ 1. pin 语义：位置冻结、参数吸收 ═══════════

class TestPinnedAttachedPointFrozen:
    def test_no_amplification_on_long_host(self, doc):
        """★ 核心回归：拖吸附点 1 单位，端点只应移动 ~1 单位（旧版 ~200）。"""
        A, B, seg, P, con = _scene(doc, length=1000.0, target=5.0)
        assert abs(con.residual()[0]) < 1e-9

        P.t = 0.006                 # P: (5,0) → (6,0)，残差 = 1
        P.recompute()
        assert P.x == pytest.approx(6.0, abs=1e-9)

        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=False)

        assert abs(con.residual()[0]) < 1e-6
        assert P.x == pytest.approx(6.0, abs=1e-6), "被 pin 的吸附点位置被移动"
        assert A.x == pytest.approx(1.0, abs=1e-4), f"A 位移被放大：{A.x}"
        assert A.x < 2.0, "修正量仍存在 1/t 放大"

    def test_no_amplification_extreme_host(self, doc):
        """L=5000, d=5 → 旧版放大 L²/d = 5e6。"""
        A, B, seg, P, con = _scene(doc, length=5000.0, target=5.0)
        P.t = 0.0011                # P: (5,0) → (5.5,0)
        P.recompute()
        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=False)
        assert abs(con.residual()[0]) < 1e-6
        assert P.x == pytest.approx(5.5, abs=1e-6)
        assert A.x == pytest.approx(0.5, abs=1e-4)

    def test_frozen_point_stays_on_host(self, doc):
        A, B, seg, P, con = _scene(doc)
        P.t = 0.008
        P.recompute()
        doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                              quick=False)
        ex, ey = seg.point_at(P.t)
        assert P.x == pytest.approx(ex, abs=1e-9)
        assert P.y == pytest.approx(ey, abs=1e-9)
        assert 0.0 <= P.t <= 1.0

    def test_step_clamp_does_not_leak_into_frozen_point(self, doc):
        """极小 max_step（多步/可能拒绝）下冻结点位置仍不得漂移。"""
        A, B, seg, P, con = _scene(doc)
        P.t = 0.006
        P.recompute()
        for _ in range(5):
            doc.solve_constraints(trigger_points=[P], pinned_points=[P],
                                  quick=True, drag_mode=True,
                                  max_step=1e-4)
            assert P.x == pytest.approx(6.0, abs=1e-6)
            assert P.y == pytest.approx(0.0, abs=1e-9)
            assert A.x < 0.01

    def test_pinned_free_point_still_immovable(self, doc):
        """回归护栏：普通自由点的 pin 语义不受影响。"""
        A, B, seg, P, con = _scene(doc)
        B.x, B.y = 1234.0, 0.0
        doc.recompute_from(B)
        doc.solve_constraints(trigger_points=[B], pinned_points=[B],
                              quick=False)
        assert B.x == pytest.approx(1234.0, abs=1e-9)


# ═══════════ 2. merit 污染防护 ═══════════

class TestMeritIntegrity:
    def test_zero_gradient_row_is_masked_not_amplified(self):
        """★ 零梯度行不得被放大 1e8 倍塞进 merit。"""
        F = asarray([5.0, 1.0])
        J = asarray([[0.0, 0.0], [1.0, 0.0]])
        scales, Fs, Js = _rescale_rows(F, J)
        assert Fs[0] == 0.0, f"零梯度行残差未被屏蔽：{Fs[0]}"
        assert Js[0][0] == 0.0 and Js[0][1] == 0.0
        assert Fs[1] == pytest.approx(1.0, abs=1e-12)
        assert float((Fs * Fs).sum()) == pytest.approx(1.0, abs=1e-12)

    def test_live_rows_unchanged(self):
        """正常行的归一化行为与旧版完全一致。"""
        F = asarray([6.0, 2.0])
        J = asarray([[3.0, 4.0], [0.0, 2.0]])
        _, Fs, Js = _rescale_rows(F, J)
        assert Fs[0] == pytest.approx(6.0 / 5.0, abs=1e-12)
        assert Js[0][0] == pytest.approx(3.0 / 5.0, abs=1e-12)
        assert Fs[1] == pytest.approx(1.0, abs=1e-12)

    def test_nan_constraint_is_isolated(self, doc):
        """坏约束（NaN 残差）不得毒化同帧的其它约束。"""
        p1, p2 = FreePoint(0.0, 0.0), FreePoint(1.0, 0.0)
        p3, p4 = FreePoint(10.0, 0.0), FreePoint(11.0, 0.0)
        for o in (p1, p2, p3, p4):
            doc.add(o)

        class _Bad(GeometricConstraint):
            def involved_points(self):
                return [p1, p2]

            def residual(self):
                return [float("nan")]

            def _jacobian_analytic(self, vars_map):
                return [[0.0] * (2 * len(vars_map))]

        good = DistanceConstraint(p3, p4, "5")
        doc.constraints.extend([_Bad(), good])
        doc.solve_constraints(quick=False)

        for p in (p1, p2, p3, p4):
            assert math.isfinite(p.x) and math.isfinite(p.y)
        assert abs(good.residual()[0]) < 1e-6, "好约束被坏约束拖垮"

    def test_duplicate_free_points_dedup(self, doc):
        """★ free_points 重复不得导致静默无解。"""
        A, B, seg, P, con = _scene(doc)
        P.t = 0.006
        P.recompute()
        solver = ConstraintSolver(max_iter=50, tol=1e-9)
        solver.solve([con], [A, A], [P])       # 故意重复
        assert abs(con.residual()[0]) < 1e-6


# ═══════════ 3. 拖动步长预算 ═══════════

class TestDragStepBudget:
    def _tool_on_B(self, doc, canvas):
        from tools.select import SelectTool
        A, B, seg, P, con = _scene(doc, length=10.0, target=5.0)
        tool = SelectTool()
        tool.press(canvas, (10.0, 0.0), B)
        assert tool.drag_pts == [B]
        return tool, B

    def test_first_move_budget_measured_from_press(self, doc, canvas, monkeypatch):
        """★ 首帧 max_step 不再是 1e-3。"""
        captured = []
        monkeypatch.setattr(
            doc, "solve_constraints",
            lambda **kw: captured.append(kw.get("max_step")) or True)
        tool, B = self._tool_on_B(doc, canvas)
        tool.move(canvas, (12.0, 0.0), B)
        assert captured, "首次 move 未触发求解"
        assert captured[-1] == pytest.approx(4.0 * 2.0 + 1e-3, abs=1e-9)
        assert tool._drag_accum == 0.0

    def test_throttled_moves_accumulate(self, doc, canvas, monkeypatch):
        """★ 节流期间的位移必须累计，而不是被丢弃。"""
        captured = []
        monkeypatch.setattr(
            doc, "solve_constraints",
            lambda **kw: captured.append(kw.get("max_step")) or True)
        tool, B = self._tool_on_B(doc, canvas)
        tool.move(canvas, (12.0, 0.0), B)
        n_solved = len(captured)

        tool._last_solve_t = time.perf_counter()      # 强制进入节流窗口
        for k in range(1, 11):
            tool.move(canvas, (12.0 + 0.1 * k, 0.0), B)
        assert len(captured) == n_solved, "节流未生效"
        assert tool._drag_accum == pytest.approx(1.0, abs=1e-9)

        tool._last_solve_t = 0.0                      # 放开节流
        tool.move(canvas, (13.1, 0.0), B)
        assert captured[-1] == pytest.approx(4.0 * 1.1 + 1e-3, abs=1e-9)
        assert tool._drag_accum == 0.0