"""脚本系统单元测试。
运行方式：pytest tests/test_scripting.py -v
"""
import pytest
from core.document import Document
from core.scripting import run_script, parse
from core.scripting.errors import ScriptError
from core.variables import get_store
from geo.points import FreePoint

@pytest.fixture(autouse=True)
def clean_env():
    """每个测试前清空全局变量状态，避免测试间污染"""
    store = get_store()
    store._vars.clear()
    store.version = 0
    yield

@pytest.fixture
def doc():
    return Document()

# ═══════════════ 1. 解析器 (Parser) 测试 ═══════════════

class TestParser:
    def test_tokenize_and_parse_basic(self):
        src = """
        set a = 10
        repeat 3 {
            add point P at (a, a)
        }
        """
        prog = parse(src)
        assert len(prog.statements) == 2

    def test_parse_if_else(self):
        src = """
        if x > 5 {
            y = 1
        } else if x == 5 {
            y = 2
        } else {
            y = 3
        }
        """
        prog = parse(src)
        assert len(prog.statements) == 1
        assert len(prog.statements[0].branches) == 2
        assert prog.statements[0].else_body is not None

# ═══════════════ 2. 运行时 (Runtime) 变量与控制流 ═══════════════

class TestRuntimeVariables:
    def test_local_and_global_vars(self, doc):
        src = """
        x = 5
        global y = 10
        set z = 15
        """
        rt = run_script(doc, src)
        assert rt is not None
        assert rt.error is None
        assert rt.locals.get("x") == 5.0
        
        store = get_store()
        assert store.get_var("y").value == 10.0
        assert store.get_var("z").value == 15.0

    def test_for_loop(self, doc):
        src = """
        sum = 0
        for i from 1 to 5 {
            sum = sum + i
        }
        """
        rt = run_script(doc, src)
        assert rt.error is None
        assert rt.locals.get("sum") == 15.0

    def test_if_else_logic(self, doc):
        src = """
        a = 10
        if a > 5 {
            res = 1
        } else {
            res = 0
        }
        """
        rt = run_script(doc, src)
        assert rt.error is None
        assert rt.locals.get("res") == 1.0

    def test_math_functions(self, doc):
        src = """
        val = sqrt(16) + abs(-5)
        """
        rt = run_script(doc, src)
        assert rt.error is None
        assert rt.locals.get("val") == 9.0

# ═══════════════ 3. 几何对象创建与 __keep 机制 ═══════════════

class TestRuntimeGeometry:
    def test_add_point_keep_true(self, doc):
        src = """
        add point A at (1, 2)
        __keep = true
        """
        initial_count = len(doc.objects)
        rt = run_script(doc, src, owner_id=999)
        
        assert rt.error is None
        assert len(doc.objects) == initial_count + 1
        pt = doc.objects[-1]
        assert pt.x == 1.0 and pt.y == 2.0
        assert getattr(pt, "script_owner", None) == 999
        assert doc.names.get("A") is pt

    def test_add_point_keep_false_cleanup(self, doc):
        """测试 __keep = false 时，临时对象被自动清理"""
        src = """
        add point B at (3, 4)
        __keep = false
        """
        initial_count = len(doc.objects)
        rt = run_script(doc, src, owner_id=999)
        
        assert rt.error is None
        # 对象应该在执行结束后被移除
        assert len(doc.objects) == initial_count

    def test_add_segment(self, doc):
        src = """
        add point P1 at (0, 0)
        add point P2 at (5, 5)
        add segment S1 from P1 to P2
        __keep = true
        """
        rt = run_script(doc, src, owner_id=999)
        assert rt.error is None
        assert len(doc.objects) == 3
        assert doc.names.get("P1") is not None
        assert doc.names.get("S1") is not None

    def test_delete_script_created_object(self, doc):
        """测试删除脚本自己创建的对象"""
        src_keep = """
        add point C at (1, 1)
        __keep = true
        """
        run_script(doc, src_keep, owner_id=999)
        assert len(doc.objects) == 1
        
        src_del = """
        delete point C
        __keep = true
        """
        rt = run_script(doc, src_del, owner_id=999)
        assert rt.error is None
        assert len(doc.objects) == 0

    def test_delete_user_object_fails_without_keep(self, doc):
        """测试：如果没有 __keep=true，脚本不能删除用户手动创建的对象"""
        user_pt = FreePoint(10, 10)
        user_pt.name = "UserPt"
        doc.add(user_pt)
        
        src = """
        delete point UserPt
        """
        rt = run_script(doc, src, owner_id=999)
        # 应该报错，且对象未被删除
        assert rt.error is not None
        assert "不能删除已有对象" in str(rt.error)
        assert len(doc.objects) == 1

# ═══════════════ 4. 错误拦截与边界情况 ═══════════════

class TestRuntimeErrors:
    def test_undefined_variable(self, doc):
        src = "x = unknown_var + 1"
        rt = run_script(doc, src)
        assert rt.error is not None
        assert "未定义变量" in str(rt.error)

    def test_max_steps_exceeded(self, doc):
        """测试死循环/超大循环拦截"""
        src = """
        repeat 200000 {
            x = 1
        }
        """
        rt = run_script(doc, src)
        assert rt.error is not None
        assert "最大执行步数" in str(rt.error)

    def test_division_by_zero(self, doc):
        src = "x = 1 / 0"
        rt = run_script(doc, src)
        assert rt.error is not None
        assert "除数为 0" in str(rt.error)

    def test_syntax_error(self, doc):
        src = "if x > {"
        rt = run_script(doc, src)
        assert rt.error is not None