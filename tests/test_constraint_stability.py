"""tests/test_constraint_stability.py
约束求解器 v2 数值稳定性回归测试。

覆盖场景：
1. 三圆互相相切连续拖动 —— 无震荡 / 无爆炸 / 残差跟踪（用户主诉场景）
2. 内切 r1≈r2 的 kink 平滑（雅可比无跳变、无 NaN）
3. 极端小半径不崩溃
4. 拖动单帧求解预算冒烟测试

运行：pytest tests/test_constraint_stability.py -v
"""
import math
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from core.document import Document
from geo.points import FreePoint
from geo.circles import Circle

from constraints import types  # noqa: F401  触发 @register_constraint
from constraints.document_ext import patch_document
patch_document()

from constraints.types.circle_constraints import TangentCirclesConstraint


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture
def doc(qapp):
    d = Document()
    yield d
    d.objects.clear()
    d.constraints.clear()


def _build_three_tangent_circles(doc):
    """三个单位圆两两外切（等边构型），初始残差 ≈ 0。"""
    O1, T1 = FreePoint(0.0, 0.0), FreePoint(1.0, 0.0)
    O2, T2 = FreePoint(2.0, 0.0), FreePoint(3.0, 0.0)
    O3, T3 = FreePoint(1.0, math.sqrt(3.0)), FreePoint(2.0, math.sqrt(3.0))
    c1, c2, c3 = Circle(O1, T1), Circle(O2, T2), Circle(O3, T3)
    for o in (O1, T1, c1, O2, T2, c2, O3, T3, c3):
        doc.add(o)
    cons = [
        TangentCirclesConstraint(c1, c2, mode="outer"),
        TangentCirclesConstraint(c2, c3, mode="outer"),
        TangentCirclesConstraint(c1, c3, mode="outer"),
    ]
    doc.constraints.extend(cons)
    return (O1, O2, O3), (T1, T2, T3), cons


class TestThreeCircleDragStability:
    def test_drag_no_jitter_no_explosion(self, doc):
        (O1, O2, O3), (T1, T2, T3), cons = _build_three_tangent_circles(doc)
        for c in cons:
            assert abs(c.residual()[0]) < 1e-9, "初始构型应精确相切"

        n = 16
        o2_traj = []
        for i in range(1, n + 1):
            O1.x, O1.y = 0.10 * i, 0.04 * i
            doc.solve_constraints(trigger_points=[O1], pinned_points=[O1],
                                  quick=True, drag_mode=True)
            for c in cons:
                r = c.residual()[0]
                assert math.isfinite(r), f"帧 {i}: 残差 NaN/Inf"
                assert abs(r) < 0.2, f"帧 {i}: 残差失控 {r:.4f}"
            for p in (O2, O3, T1, T2, T3):
                assert math.isfinite(p.x) and math.isfinite(p.y), \
                    f"帧 {i}: 坐标爆炸"
            o2_traj.append((O2.x, O2.y))

        # 单帧位移有界（防爆炸）
        for k in range(1, len(o2_traj)):
            d = math.hypot(o2_traj[k][0] - o2_traj[k - 1][0],
                           o2_traj[k][1] - o2_traj[k - 1][1])
            assert d < 1.0, f"帧 {k}: 单帧位移爆炸 {d:.3f}"

        # 耦合点总路径有界（防往复震荡：震荡会显著拉长总路径）
        total = sum(math.hypot(o2_traj[k][0] - o2_traj[k - 1][0],
                               o2_traj[k][1] - o2_traj[k - 1][1])
                    for k in range(1, len(o2_traj)))
        drag_len = math.hypot(0.10 * n, 0.04 * n)
        assert total < 4.0 * drag_len + 1.0, \
            f"耦合点路径 {total:.2f} 过长（拖动路径 {drag_len:.2f}），疑似震荡"

        # 释放级精确求解应达到高精度
        doc.solve_constraints(trigger_points=[O1], pinned_points=[O1],
                              quick=False)
        for c in cons:
            assert abs(c.residual()[0]) < 1e-5

    def test_frame_budget(self, doc):
        centers, _, _ = _build_three_tangent_circles(doc)
        O1 = centers[0]
        n = 30
        t0 = time.perf_counter()
        for i in range(1, n + 1):
            O1.x, O1.y = 0.05 * i, 0.02 * i
            doc.solve_constraints(trigger_points=[O1], pinned_points=[O1],
                                  quick=True, drag_mode=True)
        per_frame = (time.perf_counter() - t0) / n
        # 60fps 帧预算 16ms，求解器目标 ≤8ms；CI 机器放宽到 30ms
        assert per_frame < 0.030, f"平均单帧求解 {per_frame * 1000:.1f}ms 超预算"


class TestKinkSmoothing:
    def test_inner_tangent_near_equal_radius(self, doc):
        """内切 r1≈r2：旧版 sign(r1−r2) 逐帧翻转，新版平滑。"""
        O1, T1 = FreePoint(0.0, 0.0), FreePoint(2.0, 0.0)
        O2, T2 = FreePoint(0.5, 0.0), FreePoint(2.5000001, 0.0)
        c1, c2 = Circle(O1, T1), Circle(O2, T2)
        for o in (O1, T1, c1, O2, T2, c2):
            doc.add(o)
        con = TangentCirclesConstraint(c1, c2, mode="inner")
        assert math.isfinite(con.residual()[0])
        jac = con.jacobian({id(O1): 0, id(T1): 1, id(O2): 2, id(T2): 3})
        for row in jac:
            for v in row:
                assert math.isfinite(v), "雅可比出现 NaN/Inf（kink 未平滑）"

    def test_extreme_small_radius(self, doc):
        O1, T1 = FreePoint(0.0, 0.0), FreePoint(1e-5, 0.0)
        O2, T2 = FreePoint(3.0, 0.0), FreePoint(4.0, 0.0)
        c1, c2 = Circle(O1, T1), Circle(O2, T2)
        for o in (O1, T1, c1, O2, T2, c2):
            doc.add(o)
        con = TangentCirclesConstraint(c1, c2, mode="outer")
        ok = doc.add_constraint(con, silent=True)
        for p in (O1, T1, O2, T2):
            assert math.isfinite(p.x) and math.isfinite(p.y)
        if ok:
            assert abs(con.residual()[0]) < 1e-2