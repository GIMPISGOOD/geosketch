"""脚本系统接入约束系统的回归测试。"""

import math
import pytest

scripting = pytest.importorskip("core.scripting")
run_script = getattr(scripting, "run_script", None)

if run_script is None:
    pytest.skip(
        "core.scripting 没有 run_script 入口",
        allow_module_level=True
    )


def _run(doc, script):
    return run_script(doc, script, owner_id="pytest", canvas=None) # type: ignore


def _free_points(doc):
    return [o for o in doc.objects if type(o).__name__ == "FreePoint"]


def _dist(a, b):
    return math.hypot(a.x - b.x, a.y - b.y)


class TestScriptConstraintCreation:
    def test_distance_constraint_keep_true(self, doc):
        script = """
__keep = true
A = point(0, 0)
B = point(1, 0)
constraint_distance(A, B, 5)
"""
        rt = _run(doc, script)

        assert rt.error is None
        assert len(doc.constraints) == 1

        pts = _free_points(doc)
        assert len(pts) == 2

        d = _dist(pts[0], pts[1])
        assert abs(d - 5.0) < 1e-3

    def test_distance_constraint_from_segment(self, doc):
        script = """
__keep = true
A = point(0, 0)
B = point(1, 0)
S = segment(A, B)
constraint_distance(S, 4)
"""
        rt = _run(doc, script)

        assert rt.error is None
        assert len(doc.constraints) == 1

        segs = [o for o in doc.objects if type(o).__name__ == "Segment"]
        assert len(segs) == 1

        assert abs(segs[0].length() - 4.0) < 1e-3

    def test_horizontal_constraint(self, doc):
        script = """
__keep = true
A = point(0, 0)
B = point(2, 3)
constraint_horizontal(A, B)
"""
        rt = _run(doc, script)

        assert rt.error is None
        assert len(doc.constraints) == 1

        pts = _free_points(doc)
        assert len(pts) == 2
        assert abs(pts[0].y - pts[1].y) < 1e-3


class TestScriptConstraintLifecycle:
    def test_keep_false_removes_constraints(self, doc):
        script = """
A = point(0, 0)
B = point(1, 0)
constraint_distance(A, B, 5)
__keep = false
"""
        rt = _run(doc, script)

        assert rt.error is None
        assert len(doc.constraints) == 0
        assert len(doc.objects) == 0

    def test_runtime_error_rolls_back_constraints(self, doc):
        script = """
__keep = true
A = point(0, 0)
B = point(1, 0)
constraint_distance(A, B, 5)
undefined_function()
"""
        rt = _run(doc, script)

        assert rt.error is not None
        assert len(doc.constraints) == 0
        assert len(doc.objects) == 0

    def test_overconstraint_raises_script_error(self, doc):
        script = """
__keep = true
A = point(0, 0)
B = point(1, 0)
constraint_fixed(A)
constraint_fixed(B)
constraint_distance(A, B, 5)
"""
        rt = _run(doc, script)

        assert rt.error is not None
        assert len(doc.constraints) == 0
        assert len(doc.objects) == 0


class TestScriptConstraintDelete:
    def test_remove_constraint_function(self, doc):
        script = """
__keep = true
A = point(0, 0)
B = point(1, 0)
c = constraint_distance(A, B, 5)
remove_constraint(c)
"""
        rt = _run(doc, script)

        assert rt.error is None
        assert len(doc.constraints) == 0
        assert len(_free_points(doc)) == 2

    def test_delete_constraint_statement(self, doc):
        script = """
__keep = true
A = point(0, 0)
B = point(1, 0)
c = constraint_distance(A, B, 5)
delete c
"""
        rt = _run(doc, script)

        assert rt.error is None
        assert len(doc.constraints) == 0
        assert len(_free_points(doc)) == 2


class TestScriptConstraintVariableExpression:
    def test_variable_expression_constraint(self, doc):
        script = """
__keep = true
global d = 3
A = point(0, 0)
B = point(1, 0)
constraint_distance(A, B, "d")
global d = 5
constraint_solve()
"""
        rt = _run(doc, script)

        assert rt.error is None
        assert len(doc.constraints) == 1

        pts = _free_points(doc)
        assert len(pts) == 2

        d = _dist(pts[0], pts[1])
        assert abs(d - 5.0) < 1e-3