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
    """长线段拉伸稳定性。

    ★ 断言口径说明（重要）：
    A 是距离约束的涉及点、且未被 pin，会合法参与分摊修正，
    因此 P.x ≈ d 不是不变量。正确的不变量是：

        每帧 A 位移  δ_A ≈ t·F ≈ d²·ΔL / L²
        累计漂移     Σ δ_A ≈ d² ∫_{L₀}^{∞} dL/L² = d² / L₀
                        ↑ 与拉伸总长无关，收敛

    L₀=200, d=5 → 理论上界 0.125（实测 ≈0.135，含首帧 Δ/L₀ 偏大的加成）。
    修复前该场景根本不求解，残差会线性漂移到 t·L ≈ 199。

    本测试用「漂移有界 + 漂移收敛 + 单帧位移有界」三条判据锁定
    「无 1/t 放大、无跳动」，而非要求漂移为零。
    阶段 3（广义坐标）后漂移将降到 ~1e-9，届时收紧 drift_budget。
    """

    def test_long_segment_stretch_no_jump(self, doc):
        """L: 200 → 3980，t: 0.025 → 0.00126。"""
        L0, d, step, n = 200.0, 5.0, 63.0, 60
        A, B, seg, P, con = _scene(doc, length=L0, target=d)
        assert abs(con.residual()[0]) < 1e-9, "初始构型应精确满足约束"

        # 合法漂移预算：4×理论上界 d²/L₀ = 0.5
        # 对照：B 总位移 3780 —— 相差 7500 倍，足以捕获任何 1/t 放大
        drift_budget = 4.0 * d * d / L0

        px_hist, ax_hist = [], []
        for i in range(1, n + 1):
            B.x, B.y = L0 + i * step, 0.0
            doc.recompute_from(B)
            doc.solve_constraints(trigger_points=[B], pinned_points=[B],
                                  quick=True, drag_mode=True)

            r = con.residual()[0]
            assert math.isfinite(r), f"帧 {i}: 残差 NaN/Inf"
            assert abs(r) < 0.05, f"帧 {i}: 约束漂移 {r:.4f}"

            # ① 几何口径的约束跟踪：P 相对 A 的距离恒为 d
            assert abs((P.x - A.x) - d) < 0.05, \
                f"帧 {i}: |P−A|={P.x - A.x:.4f}（应≈{d}）"

            # ② 端点漂移有界 —— 核心判据：修正未被 1/t = L/d 放大
            assert abs(A.x) < drift_budget, \
                f"帧 {i}: A 累计漂移 {A.x:.4f} 超预算 {drift_budget}"
            assert abs(A.y) < 1e-9, f"帧 {i}: A 出现轴向漂移 y={A.y}"

            # ③ P 世界坐标基本不动（跟随 A 的合法微漂移）
            assert abs(P.x - d) < drift_budget + 0.05, \
                f"帧 {i}: P.x={P.x:.4f}"

            # ④ 宿主完整性
            assert 0.0 <= P.t <= 1.0, f"帧 {i}: t={P.t} 越界"
            assert abs(P.y) < 1e-6, f"帧 {i}: P 脱离线段 y={P.y}"

            px_hist.append(P.x)
            ax_hist.append(A.x)

        # ⑤ 单帧位移有界（防跳动）
        for k in range(1, len(px_hist)):
            assert abs(px_hist[k] - px_hist[k - 1]) < 0.5, \
                f"帧 {k}: P 单帧跳动 {abs(px_hist[k] - px_hist[k-1]):.3f}"
            assert abs(ax_hist[k] - ax_hist[k - 1]) < 0.5, \
                f"帧 {k}: A 单帧跳动 {abs(ax_hist[k] - ax_hist[k-1]):.3f}"

        # ⑥ 漂移收敛 —— 区分「有界微漂移」与「线性累积」的判别式
        #    δ_A ∝ 1/L²，后半程应远小于前半程（理论 ≈7%）
        early = abs(ax_hist[n // 2 - 1] - ax_hist[0])
        late = abs(ax_hist[-1] - ax_hist[n // 2 - 1])
        assert late < 0.2 * early + 1e-9, \
            f"端点漂移未收敛：前 {n//2} 帧 {early:.4f}，后 {n//2} 帧 {late:.4f}"

        # ⑦ 松手级精解
        doc.solve_constraints(trigger_points=[B], pinned_points=[B],
                              quick=False)
        assert abs(con.residual()[0]) < 1e-6
        assert abs(A.x) < drift_budget

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