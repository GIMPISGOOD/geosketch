"""变量系统测试：定义、修改、从动变量、表达式求值、模板渲染。"""

import pytest

from core.variables import (
    get_store,
    evaluate,
    render_template,
    is_valid_name,
)


class TestVariableStore:
    def test_define_and_get(self):
        store = get_store()

        store.define("a", 3.0, 0.0, 10.0)

        var = store.get_var("a")

        assert var is not None
        assert var.value == 3.0

    def test_set_value(self):
        store = get_store()

        store.define("a", 1.0, 0.0, 10.0)
        store.set("a", 5.0)

        assert store.get_var("a").value == 5.0

    def test_delete_variable(self):
        store = get_store()

        store.define("a", 1.0, 0.0, 10.0)
        store.delete("a")

        assert store.get_var("a") is None

    def test_set_range_clamps_value(self):
        store = get_store()

        store.define("a", 20.0, 0.0, 10.0)
        store.set_range("a", 0.0, 5.0)

        var = store.get_var("a")

        assert var.vmin == 0.0
        assert var.vmax == 5.0
        assert var.value == 5.0


class TestDependentVariable:
    def test_dependent_variable_eval(self):
        store = get_store()

        store.define("a", 2.0, 0.0, 10.0)
        store.define("b", 0.0, 0.0, 10.0, expr="a * 2")

        d = store.as_dict()

        assert d["a"] == 2.0
        assert d["b"] == 4.0

    def test_dependent_variable_cannot_be_set_manually(self):
        store = get_store()

        store.define("a", 2.0, 0.0, 10.0)
        store.define("b", 0.0, 0.0, 10.0, expr="a * 2")

        store.set("b", 100.0)

        d = store.as_dict()
        assert d["b"] == 4.0

    def test_multi_level_dependency(self):
        store = get_store()

        store.define("a", 1.0, 0.0, 10.0)
        store.define("b", 0.0, 0.0, 10.0, expr="a + 1")
        store.define("c", 0.0, 0.0, 10.0, expr="b * 2")

        d = store.as_dict()

        assert d["b"] == 2.0
        assert d["c"] == 4.0


class TestEvaluate:
    def test_basic_expression(self):
        assert evaluate("2*x + 1", {"x": 3}) == 7

    def test_power_expression(self):
        assert evaluate("x^2", {"x": 4}) == 16

    def test_function_expression(self):
        val = evaluate("sqrt(x)", {"x": 9})
        assert abs(val - 3.0) < 1e-9

    def test_undefined_variable_returns_none(self):
        assert evaluate("no_such_var + 1", {}) is None

    def test_invalid_expression_returns_none(self):
        assert evaluate("x +*+ 1", {"x": 1}) is None


class TestTemplateName:
    def test_valid_name(self):
        assert is_valid_name("边长")
        assert is_valid_name("a")
        assert is_valid_name("alpha")

    def test_invalid_name(self):
        assert not is_valid_name("")
        assert not is_valid_name("a b")
        assert not is_valid_name("pi")
        assert not is_valid_name("sqrt")


class TestRenderTemplate:
    def test_render_variable(self):
        store = get_store()
        store.define("a", 3.0, 0.0, 10.0)

        assert render_template("{a}") == "3"

    def test_render_expression(self):
        store = get_store()
        store.define("a", 3.0, 0.0, 10.0)

        assert render_template("{a + 1}") == "4"

    def test_render_invalid_keeps_original(self):
        assert render_template("{no_such_var}") == "{no_such_var}"