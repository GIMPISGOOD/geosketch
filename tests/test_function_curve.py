"""FunctionCurve 函数绘制功能的单元测试。

检测"静默失败"的 5 个根源：
1. _eval_at 返回错误类型（tuple 而非 float）
2. 表达式求值失败返回 None → 无点可画
3. 变量未定义 → evaluate 返回 None
4. 采样全部被跳过
5. 对象 visible/exists 为 False

运行：python -m pytest tests/test_function_curve.py -v
"""
import math
import pytest


# ─────────────── Qt 环境 ───────────────
@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def _ensure_qapp(qapp):
    pass


@pytest.fixture(autouse=True)
def clean_variables():
    """每个测试隔离变量状态，避免测试间污染。"""
    from core.variables import get_store
    store = get_store()
    saved_vars = dict(store._vars)
    saved_version = store.version
    yield
    store._vars = saved_vars
    store.version = saved_version


# ─────────────── 采样辅助（复现渲染逻辑，不实际绘制）───────────────
def sample_explicit(obj, x0, x1, n=200):
    """复现 _draw_explicit 的采样逻辑，返回有效 (x, y) 点列表。"""
    pts = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        y = obj._eval_at(x)
        if isinstance(y, (int, float)) and math.isfinite(y):
            pts.append((x, float(y)))
    return pts


def sample_parametric(obj, t0, t1, n=200):
    pts = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        pt = obj._eval_at(t)
        if isinstance(pt, (tuple, list)) and len(pt) == 2:
            x, y = pt
            if all(isinstance(v, (int, float)) and math.isfinite(v) for v in (x, y)):
                pts.append((float(x), float(y)))
    return pts


def sample_polar(obj, t0, t1, n=200):
    pts = []
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        r = obj._eval_at(t)
        if isinstance(r, (int, float)) and math.isfinite(r):
            pts.append((float(r) * math.cos(t), float(r) * math.sin(t)))
    return pts


# ═══════════════ 1. _eval_at 类型安全（静默失败核心）═══════════════
class TestEvalAtTypes:

    def test_explicit_returns_float(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x^2")
        y = f._eval_at(2.0)
        assert isinstance(y, float), f"explicit 应返回 float，实际 {type(y).__name__}"
        assert y == pytest.approx(4.0)

    def test_explicit_never_returns_tuple(self):
        """回归：之前 _eval_at 对 explicit 误返回 tuple 导致 math.isfinite 崩溃。"""
        from geo.function_curve import FunctionCurve
        for expr in ["x", "x^2", "sin(x)", "x^2 + tan(x)", "2*x + 1", "sqrt(abs(x))"]:
            f = FunctionCurve(kind="explicit", expr=expr)
            y = f._eval_at(1.0)
            assert not isinstance(y, tuple), f"expr={expr!r} 返回了 tuple: {y}"

    def test_parametric_returns_2tuple(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="parametric", expr="cos(t)", expr2="sin(t)")
        pt = f._eval_at(0.0)
        assert isinstance(pt, (tuple, list)), f"parametric 应返回 tuple，实际 {type(pt).__name__}"
        assert len(pt) == 2

    def test_polar_returns_float(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="polar", expr="1 + cos(t)")
        r = f._eval_at(0.0)
        assert isinstance(r, float), f"polar 应返回 float，实际 {type(r).__name__}"


# ═══════════════ 2. 表达式求值正确性 ═══════════════
class TestExpressionEvaluation:

    def test_polynomial(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x^2 + 2*x + 1")
        assert f._eval_at(0.0) == pytest.approx(1.0)
        assert f._eval_at(1.0) == pytest.approx(4.0)
        assert f._eval_at(-1.0) == pytest.approx(0.0)

    def test_trig(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="sin(x)")
        assert f._eval_at(0.0) == pytest.approx(0.0)
        assert f._eval_at(math.pi / 2) == pytest.approx(1.0)

    def test_tan_composite(self):
        """用户报告的 x^2 + tan(x) 场景。"""
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x^2 + tan(x)")
        y = f._eval_at(1.0)
        assert isinstance(y, float)
        assert y == pytest.approx(1.0 + math.tan(1.0))

    def test_empty_expr_returns_none(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="")
        assert f._eval_at(0.0) is None

    def test_invalid_expr_no_crash(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x +*+ bad")
        result = f._eval_at(1.0)  # 不应抛异常
        assert result is None or isinstance(result, float)


# ═══════════════ 3. 变量联动 ═══════════════
class TestVariableLinkage:

    def test_variable_in_expr(self):
        from geo.function_curve import FunctionCurve
        from core.variables import get_store
        get_store().define("a", 2.0, 0.0, 10.0)
        f = FunctionCurve(kind="explicit", expr="a*x")
        assert f._eval_at(3.0) == pytest.approx(6.0)

    def test_variable_change_updates(self):
        from geo.function_curve import FunctionCurve
        from core.variables import get_store
        store = get_store()
        store.define("a", 2.0, 0.0, 10.0)
        f = FunctionCurve(kind="explicit", expr="a*x")
        assert f._eval_at(3.0) == pytest.approx(6.0)
        store.set("a", 5.0)
        assert f._eval_at(3.0) == pytest.approx(15.0)

    def test_undefined_variable_returns_none(self):
        """未定义变量 → evaluate 返回 None（静默失败根源之一）。"""
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="no_such_var * x")
        assert f._eval_at(1.0) is None


# ═══════════════ 4. 采样逻辑 ═══════════════
class TestSampling:

    def test_explicit_produces_points(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x^2")
        pts = sample_explicit(f, -5, 5, n=100)
        assert len(pts) > 50, f"采样点过少: {len(pts)}"

    def test_tan_has_valid_points(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="tan(x)")
        pts = sample_explicit(f, -2.0, 2.0, n=400)
        assert len(pts) > 0, "tan(x) 采样不应为空"
        assert all(math.isfinite(y) for _, y in pts)

    def test_parametric_unit_circle(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="parametric", expr="cos(t)", expr2="sin(t)")
        pts = sample_parametric(f, 0, 2 * math.pi, n=100)
        assert len(pts) > 50
        for x, y in pts:
            assert math.hypot(x, y) == pytest.approx(1.0, abs=1e-6)

    def test_polar_circle(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="polar", expr="1")
        pts = sample_polar(f, 0, 2 * math.pi, n=100)
        assert len(pts) > 50
        for x, y in pts:
            assert math.hypot(x, y) == pytest.approx(1.0, abs=1e-6)

    def test_empty_expr_no_points(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="")
        assert sample_explicit(f, -5, 5) == []


# ═══════════════ 5. 序列化 ═══════════════
class TestSerialization:

    def test_explicit_roundtrip(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x^2 + 1", domain=(-3, 3), color="#ff0000")
        f2 = FunctionCurve.build([], f.dump())
        assert f2.kind == "explicit"
        assert f2.expr == "x^2 + 1"
        assert f2.domain == (-3, 3)

    def test_parametric_roundtrip(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="parametric", expr="cos(t)", expr2="sin(t)")
        f2 = FunctionCurve.build([], f.dump())
        assert f2.kind == "parametric"
        assert f2.expr == "cos(t)"
        assert f2.expr2 == "sin(t)"


# ═══════════════ 6. 边界情况 ═══════════════
class TestEdgeCases:

    def test_division_by_zero(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="1/x")
        result = f._eval_at(0.0)  # 不应抛异常
        assert result is None or not math.isfinite(result) or isinstance(result, float)

    def test_sqrt_negative(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="sqrt(x)")
        result = f._eval_at(-1.0)  # 不应抛异常
        assert result is None or isinstance(result, float)

    def test_domain_stored(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x", domain=(0, 1))
        assert f.domain == (0, 1)

    def test_default_domain(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x")
        assert f.domain is None or isinstance(f.domain, tuple)


# ═══════════════ 7. 对象状态 ═══════════════
class TestObjectState:

    def test_visible_by_default(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x^2")
        assert getattr(f, "visible", True) is True

    def test_exists_by_default(self):
        from geo.function_curve import FunctionCurve
        f = FunctionCurve(kind="explicit", expr="x^2")
        assert getattr(f, "exists", True) is True