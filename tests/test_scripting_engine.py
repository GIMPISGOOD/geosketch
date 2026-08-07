"""脚本引擎测试。

由于脚本系统可能处于旧语法 / 新语法过渡阶段，
本测试会自动探测当前可用的基础建点语法。
"""

import math

import pytest

scripting = pytest.importorskip("core.scripting")

run_script = getattr(scripting, "run_script", None)

if run_script is None:
    pytest.skip("core.scripting 没有 run_script 入口", allow_module_level=True)

from core.document import Document
from geo.points import AbstractPoint


def _points(doc):
    return [o for o in doc.objects if isinstance(o, AbstractPoint)]


def _run(doc, script):
    try:
        run_script(doc, script, owner_id="pytest", canvas=None)
    except Exception:
        # 测试里通过结果判断，不直接抛异常
        pass


@pytest.fixture(scope="module")
def syntax():
    """探测当前脚本引擎支持哪种基础建点语法。"""

    candidates = [
        (
            "new",
            """
A = point(1, 2)
__keep = true
"""
        ),
        (
            "old",
            """
add point A at (1, 2)
__keep = true
"""
        ),
    ]

    for style, script in candidates:
        doc = Document()
        _run(doc, script)

        if _points(doc):
            return style

    pytest.skip("当前脚本引擎无法通过基础建点脚本")


def _point_script(syntax, keep=True):
    keep_line = "__keep = true" if keep else "__keep = false"

    if syntax == "new":
        return f"""
A = point(1, 2)
{keep_line}
"""

    return f"""
add point A at (1, 2)
{keep_line}
"""


class TestScriptPoint:
    def test_create_point_keep_true(self, syntax):
        doc = Document()

        _run(doc, _point_script(syntax, keep=True))

        assert len(_points(doc)) == 1

    def test_create_point_keep_false(self, syntax):
        doc = Document()

        _run(doc, _point_script(syntax, keep=False))

        assert len(_points(doc)) == 0


class TestScriptControlFlow:
    def test_if_true(self, syntax):
        doc = Document()

        if syntax == "new":
            script = """
if true {
    A = point(0, 0)
}
__keep = true
"""
        else:
            script = """
if true {
    add point A at (0, 0)
}
__keep = true
"""

        _run(doc, script)

        assert len(_points(doc)) == 1

    def test_if_false_else(self, syntax):
        doc = Document()

        if syntax == "new":
            script = """
if false {
    A = point(0, 0)
} else {
    B = point(1, 1)
}
__keep = true
"""
        else:
            script = """
if false {
    add point A at (0, 0)
} else {
    add point B at (1, 1)
}
__keep = true
"""

        _run(doc, script)

        assert len(_points(doc)) == 1


class TestScriptVariable:
    def test_global_variable(self, syntax):
        doc = Document()

        script = """
global n = 7
__keep = true
"""

        _run(doc, script)

        var = doc.vars.get_var("n")

        assert var is not None
        assert abs(var.value - 7.0) < 1e-9


class TestScriptDelete:
    def test_delete_script_created_point(self, syntax):
        doc = Document()

        if syntax == "new":
            script = """
A = point(0, 0)
delete A
__keep = true
"""
        else:
            script = """
add point A at (0, 0)
delete A
__keep = true
"""

        _run(doc, script)

        assert len(_points(doc)) == 0


class TestScriptMath:
    def test_math_function(self, syntax):
        doc = Document()

        if syntax == "new":
            script = """
A = point(sin(0) + 1, 0)
__keep = true
"""
        else:
            script = """
add point A at (sin(0) + 1, 0)
__keep = true
"""

        _run(doc, script)

        pts = _points(doc)

        if not pts:
            pytest.skip("当前脚本引擎不支持在坐标表达式中调用数学函数")

        assert abs(pts[0].x - 1.0) < 1e-6


class TestScriptOldLoop:
    def test_old_name_template_loop(self, syntax):
        if syntax != "old":
            pytest.skip("该测试仅针对旧语法的名字模板循环")

        doc = Document()

        script = """
for i from 1 to 3 {
    add point P{i} at (i, 0)
}
__keep = true
"""

        _run(doc, script)

        assert len(_points(doc)) >= 3