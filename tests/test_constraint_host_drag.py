"""tests/test_constraint_host_drag.py

宿主端点拖动回归（约束图几何依赖闭包）。

主诉场景：线段 AB 上吸附点 P，DistanceConstraint(P, A) = d。
拖动宿主端点 B 把线段拉长：
  · 旧实现 get_affected_constraints([B]) 返回空 —— B 不在 involved_points
    里，约束整程不被激活，|P−A| = t·L 随 L 线性漂移，之后一次性偿还 → 跳动；
  · 修复后 B 的几何下游闭包含 P，约束每帧激活，滑移自由度 t（增益 L）可用，
    P 沿线段滑动、A 基本不动、|P−A| 恒等于 d。

运行：pytest tests/test_constraint_host_drag.py -v
"""

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from geo.points import FreePoint, PointOnObject
from geo.segments import Segment
from constraints import types  # noqa: F401  触发 @register_constraint
from constraints.graph import (
    expand_trigger_points,
    get_affected_constraints,
)
from constraints.types.distance import DistanceConstraint


# ═══════════════════════ 场景工厂 ═══════════════════════

def _scene(doc, length=200.0, target=5.0):
    """A(0,0) → B(length,0)，P 在 t=target/length，约束 |P−A| = target。"""
    A = FreePoint(0.0, 0.0)
    B = FreePoint(length, 0.0)
    seg = Segment(A, B)
    P = PointOnObject(seg, t=target / length)
    for o in (A, B, seg, P):
        doc.add(o)
    con = DistanceConstraint(P, A, expr=str(target))
    doc.constraints.append(con)
    return A, B, seg, P, con


# ═══════════════ 1. 依赖闭包（单元级） ═══════════════

class TestDependencyClosure:
    def test_host_endpoint_seeds_constraint(self, doc):
        """★ 核心回归：拖动不在 involved_points 里的宿主端点也要激活约束。"""
        A, B, seg, P, con = _scene(doc)
        assert get_affected_constraints([B], [con]) == [con]
        assert get_affected_constraints([A], [con]) == [con]

    def test_closure_contains_attached_point(self, doc):
        A, B, seg, P, con = _scene(doc)
        out = expand_trigger_points([B])
        assert P in out
        assert B in out

    def test_closure_stable_and_dedup(self, doc):
        A, B, seg, P, con = _scene(doc)
        out = expand_trigger_points([B, B, A])
        ids = [o.id for o in out]
        assert ids == sorted(ids), "闭包结果未按创建序稳定排序"
        assert len(out) == len({id(o) for o in out}), "闭包结果有重复"

    def test_intersect_downstream_seeds_constraint(self, doc):
        """交点同样受益于闭包：拖一条线段的端点应激活交点上的约束。"""
        from geo.intersects import IntersectPoint

        p1, p2 = FreePoint(0.0, 0.0), FreePoint(10.0, 10.0)
        p3, p4 = FreePoint(0.0, 10.0), FreePoint(10.0, 0.0)
        s1, s2 = Segment(p1, p2), Segment(p3, p4)
        ip = IntersectPoint(s1, s2, 0)
        q = FreePoint(5.0, 8.0)
        for o in (p1, p2, s1, p3, p4, s2, ip, q):
            doc.add(o)
        con = DistanceConstraint(ip, q, "2")
        doc.constraints.append(con)
        assert get_affected_constraints([p1], [con]) == [con]


# ═══════════════ 2. 长线段拉伸不跳动（集成级） ═══════════════

class TestHostStretchStability:
    def test_long_segment_stretch_no_jump(self, doc):
        """L: 200 → 3980，t: 0.025 → 0.00126。P 世界坐标应几乎不动。"""
        A, B, seg, P, con = _scene(doc, length=200.0, target=5.0)
        assert abs(con.residual()[0]) < 1e-9, "初始构型应精确满足约束"

        px_hist = []
        for i in range(1, 61):
            B.x, B.y = 200.0 + i * 63.0, 0.0
            doc.recompute_from(B)
            doc.solve_constraints(trigger_points=[B], pinned_points=[B],
                                  quick=True, drag_mode=True)

            r = con.residual()[0]
            assert math.isfinite(r), f"帧 {i}: 残差 NaN/Inf"
            assert abs(r) < 0.05, f"帧 {i}: 约束漂移 {r:.4f}"
            assert abs(P.x - 5.0) < 0.1, f"帧 {i}: P.x={P.x:.4f}（应≈5）"
            assert abs(A.x) < 1.0 and abs(A.y) < 1.0, \
                f"帧 {i}: 端点 A 被放大修正 ({A.x:.3f},{A.y:.3f})"
            assert 0.0 <= P.t <= 1.0, f"帧 {i}: t={P.t} 越界"
            assert abs(P.y) < 1e-6, f"帧 {i}: P 脱离线段 y={P.y}"
            px_hist.append(P.x)

        for k in range(1, len(px_hist)):
            assert abs(px_hist[k] - px_hist[k - 1]) < 0.5, \
                f"帧 {k}: P 单帧跳动 {abs(px_hist[k] - px_hist[k-1]):.3f}"

        # 松手级精解
        doc.solve_constraints(trigger_points=[B], pinned_points=[B],
                              quick=False)
        assert abs(con.residual()[0]) < 1e-6

    def test_short_segment_stretch_stays_feasible(self, doc):
        """短起步（t=0.5）：允许端点参与分摊，但不得爆炸 / 脱离宿主。"""
        A, B, seg, P, con = _scene(doc, length=10.0, target=5.0)
        for i in range(1, 41):
            B.x, B.y = 10.0 + i * 50.0, 0.0
            doc.recompute_from(B)
            doc.solve_constraints(trigger_points=[B], pinned_points=[B],
                                  quick=True, drag_mode=True)
            r = con.residual()[0]
            assert math.isfinite(r) and abs(r) < 0.2, f"帧 {i}: 残差 {r}"
            assert abs(P.y) < 1e-6 and 0.0 <= P.t <= 1.0
            for p in (A, B, P):
                assert math.isfinite(p.x) and math.isfinite(p.y)
        assert abs(A.x) < 10.0, f"端点 A 累计漂移过大 {A.x:.3f}"

    def test_dragged_host_endpoint_immovable(self, doc):
        """被拖动的宿主端点坐标不得被求解器篡改。"""
        A, B, seg, P, con = _scene(doc)
        tx = 500.0
        B.x, B.y = tx, 0.0
        doc.recompute_from(B)
        doc.solve_constraints(trigger_points=[B], pinned_points=[B],
                              quick=False)
        assert B.x == pytest.approx(tx, abs=1e-9)
        assert B.y == pytest.approx(0.0, abs=1e-9)