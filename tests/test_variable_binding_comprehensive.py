"""
变量绑定系统完善测试：从 UI 到底层全路径覆盖
测试目标：
1. VariableStore 所有接口
2. Document 同步绑定机制
3. Measure/RegionMeasure 度量对象
4. UI 组件（VariableSliderPanel / VariableWizard）
5. 序列化/反序列化
6. 异常路径与边界条件
7. 集成：拖动几何对象 → 绑定变量实时更新
"""

import math
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtCore import Qt

# 确保 QApplication 存在（pytest-qt 或手动）
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ================================================================
# 一、底层：VariableStore 单元测试
# ================================================================
class TestVariableStore:
    """变量存储核心逻辑测试"""

    @pytest.fixture
    def store(self):
        from core.variables import VariableStore
        s = VariableStore()
        return s

    @pytest.fixture
    def doc(self):
        from core.document import Document
        return Document()

    # ---------- 定义变量 ----------
    def test_define_normal(self, store):
        store.define("a", 3.0, 0.0, 10.0)
        var = store.get_var("a")
        assert var is not None
        assert var.value == 3.0
        assert var.vmin == 0.0
        assert var.vmax == 10.0

    def test_define_with_binding(self, store):
        binding = {"obj_id": 1, "metric": "length"}
        store.define("L", 0.0, 0.0, 10.0, binding=binding)
        var = store.get_var("L")
        assert var.binding == binding

    def test_define_invalid_name(self, store):
        from core.variables import is_valid_name
        assert not is_valid_name("pi")       # 保留名
        assert not is_valid_name("sqrt")
        assert not is_valid_name("2a")       # 数字开头
        assert not is_valid_name("a b")      # 含空格

    def test_define_duplicate_name_overwrites(self, store):
        store.define("a", 1.0)
        store.define("a", 2.0)
        assert store.get_var("a").value == 2.0

    # ---------- set / set_expr ----------
    def test_set_normal(self, store):
        store.define("a", 1.0)
        store.set("a", 5.0)
        assert store.get_var("a").value == 5.0

    def test_set_expr_variable_blocked(self, store):
        store.define("a", expr="b*2")
        store.set("a", 99.0)
        # 从动变量不应被手动修改
        assert store.get_var("a").expr == "b*2"

    def test_set_bound_variable_blocked(self, store):
        store.define("a", binding={"obj_id": 1, "metric": "length"})
        store.set("a", 99.0)
        assert store.get_var("a").binding is not None

    def test_set_expr_clears_binding(self, store):
        store.define("a", binding={"obj_id": 1, "metric": "length"})
        store.set_expr("a", "b+1")
        assert store.get_var("a").expr == "b+1"
        assert store.get_var("a").binding is None

    # ---------- delete ----------
    def test_delete_existing(self, store):
        store.define("a", 1.0)
        store.delete("a")
        assert store.get_var("a") is None

    def test_delete_nonexistent(self, store):
        store.delete("not_exist")  # 不应抛异常

    # ---------- as_dict / evaluate ----------
    def test_as_dict_simple(self, store):
        store.define("a", 2.0)
        store.define("b", 3.0)
        d = store.as_dict()
        assert d["a"] == 2.0
        assert d["b"] == 3.0

    def test_as_dict_with_expr(self, store):
        store.define("a", 2.0)
        store.define("b", expr="a*3")
        d = store.as_dict()
        assert d["b"] == 6.0

    def test_as_dict_circular_dependency(self, store):
        store.define("a", expr="b+1")
        store.define("b", expr="a+1")
        d = store.as_dict()
        # 循环依赖不应死循环，最终可能为 0 或最后一次迭代值
        assert "a" in d and "b" in d

    def test_evaluate_valid(self, store):
        store.define("a", 5.0)
        assert store.evaluate("a*2") == 10.0

    def test_evaluate_invalid(self, store):
        assert store.evaluate("a**") is None

    # ---------- to_dict / load_dict ----------
    def test_serialization_roundtrip(self, store):
        store.define("a", 3.0, 0.0, 10.0, step=0.5,
                     binding={"obj_id": 42, "metric": "area"})
        data = store.to_dict()
        store2 = type(store)()
        store2.load_dict(data)
        var = store2.get_var("a")
        assert var.value == 3.0
        assert var.binding == {"obj_id": 42, "metric": "area"}

    # ---------- bind / unbind ----------
    def test_bind_method(self, store):
        store.define("a", 1.0)
        store.bind("a", {"obj_id": 5, "metric": "length"})
        assert store.get_var("a").binding == {"obj_id": 5, "metric": "length"}

    def test_unbind(self, store):
        store.define("a", binding={"obj_id": 5, "metric": "length"})
        store.bind("a", None)
        assert store.get_var("a").binding is None

    # ---------- update_bindings 核心 ----------
    def test_update_bindings_no_bindings(self, store, doc):
        assert store.update_bindings(doc) is False

    def test_update_bindings_object_missing(self, store, doc):
        store.define("a", binding={"obj_id": 999, "metric": "length"})
        changed = store.update_bindings(doc)
        assert changed is True
        assert store.get_var("a").binding is None

    def test_update_bindings_object_exists(self, store, doc):
        from geo.segments import Segment
        from geo.points import FreePoint
        p1 = FreePoint(0, 0)
        p2 = FreePoint(3, 4)
        seg = Segment(p1, p2)
        doc.add(p1); doc.add(p2); doc.add(seg)
        store.define("L", binding={"obj_id": seg.id, "metric": "length"})
        changed = store.update_bindings(doc)
        assert changed is True
        assert abs(store.get_var("L").value - 5.0) < 1e-6

    def test_update_bindings_metric_invalid(self, store, doc):
        from geo.points import FreePoint
        p = FreePoint(0, 0)
        doc.add(p)
        store.define("a", binding={"obj_id": p.id, "metric": "nonexistent"})
        changed = store.update_bindings(doc)
        # 无法计算 → 不更新值，但可能不解除绑定（视实现）
        assert store.get_var("a").binding is not None

    def test_update_bindings_auto_expand_range(self, store, doc):
        from geo.segments import Segment
        from geo.points import FreePoint
        p1 = FreePoint(0, 0)
        p2 = FreePoint(100, 0)
        seg = Segment(p1, p2)
        doc.add(p1); doc.add(p2); doc.add(seg)
        store.define("L", vmin=0, vmax=10,
                     binding={"obj_id": seg.id, "metric": "length"})
        store.update_bindings(doc)
        assert store.get_var("L").vmax >= 100.0


# ================================================================
# 二、Document 层：同步绑定机制
# ================================================================
class TestDocumentBindingSync:
    """测试 Document 是否在正确时机调用 update_bindings"""

    @pytest.fixture
    def doc_with_segment(self):
        from core.document import Document
        from geo.points import FreePoint
        from geo.segments import Segment
        doc = Document()
        p1 = FreePoint(0, 0)
        p2 = FreePoint(3, 4)
        seg = Segment(p1, p2)
        doc.add(p1); doc.add(p2); doc.add(seg)
        doc.vars.define("L", binding={"obj_id": seg.id, "metric": "length"})
        return doc, p1, p2, seg

    def test_recompute_from_updates_bindings(self, doc_with_segment):
        doc, p1, p2, seg = doc_with_segment
        doc.vars.update_bindings(doc)
        assert abs(doc.vars.get_var("L").value - 5.0) < 1e-6
        # 移动点
        p2.x, p2.y = 6, 8
        doc.recompute_from(p2)
        assert abs(doc.vars.get_var("L").value - 10.0) < 1e-6

    def test_refresh_variables_updates_bindings(self, doc_with_segment):
        doc, p1, p2, seg = doc_with_segment
        p2.x, p2.y = 6, 8
        doc.recompute_silent(p2)
        doc.refresh_variables()
        assert abs(doc.vars.get_var("L").value - 10.0) < 1e-6

    def test_remove_object_unbinds(self, doc_with_segment):
        doc, p1, p2, seg = doc_with_segment
        doc.vars.update_bindings(doc)
        doc.remove(seg)
        assert doc.vars.get_var("L").binding is None

    def test_clear_unbinds_all(self, doc_with_segment):
        doc, *_ = doc_with_segment
        doc.vars.update_bindings(doc)
        doc.clear()
        assert doc.vars.get_var("L").binding is None

    def test_undo_redo_preserves_binding(self, doc_with_segment):
        doc, p1, p2, seg = doc_with_segment
        doc.vars.update_bindings(doc)
        doc.remove(seg)
        assert doc.vars.get_var("L").binding is None
        doc.undo()
        # 撤销后对象恢复，绑定应恢复
        assert doc.vars.get_var("L").binding is not None

    def test_save_load_preserves_binding(self, doc_with_segment, tmp_path):
        doc, *_ = doc_with_segment
        doc.vars.update_bindings(doc)
        path = tmp_path / "test.wgeo"
        doc.save(str(path))
        doc2 = type(doc)()
        doc2.load(str(path))
        assert doc2.vars.get_var("L").binding is not None


# ================================================================
# 三、Measure / RegionMeasure 度量对象
# ================================================================
class TestMeasureObjects:
    """测试度量对象本身的计算与异常"""

    @pytest.fixture
    def doc(self):
        from core.document import Document
        return Document()

    def _make_segment(self, doc, x1=0, y1=0, x2=3, y2=4):
        from geo.points import FreePoint
        from geo.segments import Segment
        p1 = FreePoint(x1, y1)
        p2 = FreePoint(x2, y2)
        seg = Segment(p1, p2)
        doc.add(p1); doc.add(p2); doc.add(seg)
        return seg

    def test_measure_length(self, doc):
        from plugins.measure_tools import Measure
        seg = self._make_segment(doc)
        m = Measure("length", [seg])
        doc.add(m)
        assert abs(m.value - 5.0) < 1e-6

    def test_measure_distance(self, doc):
        from plugins.measure_tools import Measure
        from geo.points import FreePoint
        p1 = FreePoint(0, 0)
        p2 = FreePoint(3, 4)
        doc.add(p1); doc.add(p2)
        m = Measure("distance", [p1, p2])
        doc.add(m)
        assert abs(m.value - 5.0) < 1e-6

    def test_measure_angle(self, doc):
        from plugins.measure_tools import Measure
        from geo.points import FreePoint
        v = FreePoint(0, 0)
        p1 = FreePoint(1, 0)
        p2 = FreePoint(0, 1)
        doc.add(v); doc.add(p1); doc.add(p2)
        m = Measure("angle", [v, p1, p2])
        doc.add(m)
        assert abs(m.value - 90.0) < 1e-6

    def test_measure_invalid_kind(self, doc):
        from plugins.measure_tools import Measure
        seg = self._make_segment(doc)
        m = Measure("invalid_kind", [seg])
        doc.add(m)
        assert m.value == 0.0

    def test_measure_target_missing(self, doc):
        from plugins.measure_tools import Measure
        m = Measure("length", [])  # 无目标
        doc.add(m)
        assert m.value == 0.0

    def test_region_measure_area_perimeter(self, doc):
        from plugins.measure_tools import RegionMeasure
        from geo.points import FreePoint
        p1 = FreePoint(0, 0)
        p2 = FreePoint(4, 0)
        p3 = FreePoint(4, 3)
        doc.add(p1); doc.add(p2); doc.add(p3)
        rm = RegionMeasure([p1, p2, p3])
        doc.add(rm)
        assert abs(rm.area - 6.0) < 1e-6
        assert abs(rm.perimeter - 12.0) < 1e-6

    def test_region_measure_less_than_3_points(self, doc):
        from plugins.measure_tools import RegionMeasure
        from geo.points import FreePoint
        p1 = FreePoint(0, 0)
        p2 = FreePoint(1, 1)
        doc.add(p1); doc.add(p2)
        rm = RegionMeasure([p1, p2])
        doc.add(rm)
        assert not rm.exists


# ================================================================
# 四、UI 层测试（VariableSliderPanel / Wizard）
# ================================================================
class TestVariableWidgets:
    """测试 UI 组件的创建、刷新、交互"""

    @pytest.fixture
    def canvas_mock(self, qapp):
        from core.document import Document
        doc = Document()
        canvas = MagicMock()
        canvas.doc = doc
        canvas.scale = 48.0
        return canvas

    @pytest.fixture
    def panel(self, canvas_mock, qapp):
        from ui.variable_widgets import VariableSliderPanel
        p = VariableSliderPanel(canvas_mock)
        return p

    def test_panel_creation(self, panel):
        assert panel is not None

    def test_refresh_empty(self, panel):
        panel.refresh()
        assert panel._rows.count() == 0

    def test_refresh_with_variables(self, panel):
        panel.canvas.doc.vars.define("a", 3.0)
        panel.refresh()
        assert panel._rows.count() == 1

    def test_make_row_normal_variable(self, panel):
        var = panel.canvas.doc.vars
        var.define("a", 3.0, 0.0, 10.0)
        row = panel._make_row("a", var.get_var("a"))
        assert row is not None

    def test_make_row_bound_variable(self, panel):
        var = panel.canvas.doc.vars
        var.define("a", binding={"obj_id": 1, "metric": "length"})
        row = panel._make_row("a", var.get_var("a"))
        assert row is not None

    def test_make_row_expr_variable(self, panel):
        var = panel.canvas.doc.vars
        var.define("a", expr="b*2")
        row = panel._make_row("a", var.get_var("a"))
        assert row is not None

    def test_on_slide_updates_variable(self, panel):
        var = panel.canvas.doc.vars
        var.define("a", 3.0, 0.0, 10.0, step=0.1)
        lbl = MagicMock()
        panel._on_slide("a", 50, lbl, 0.0, 0.1)
        assert abs(var.get_var("a").value - 5.0) < 1e-6

    def test_delete_variable(self, panel):
        var = panel.canvas.doc.vars
        var.define("a", 3.0)
        panel._delete("a")
        assert var.get_var("a") is None

    def test_wizard_valid_name(self, qapp):
        from ui.variable_widgets import VariableWizard
        wiz = VariableWizard()
        wiz._name_page.edit.setText("边长")
        assert wiz._name_page.isComplete()

    def test_wizard_invalid_name(self, qapp):
        from ui.variable_widgets import VariableWizard
        wiz = VariableWizard()
        wiz._name_page.edit.setText("pi")
        assert not wiz._name_page.isComplete()


# ================================================================
# 五、集成测试：完整工作流
# ================================================================
class TestIntegration:
    """端到端集成测试"""

    @pytest.fixture
    def full_setup(self):
        from core.document import Document
        from geo.points import FreePoint
        from geo.segments import Segment
        from plugins.measure_tools import Measure
        doc = Document()
        p1 = FreePoint(0, 0)
        p2 = FreePoint(3, 4)
        seg = Segment(p1, p2)
        doc.add(p1); doc.add(p2); doc.add(seg)
        m = Measure("length", [seg])
        doc.add(m)
        return doc, p1, p2, seg, m

    def test_bind_to_segment_then_move(self, full_setup):
        doc, p1, p2, seg, m = full_setup
        doc.vars.define("L", binding={"obj_id": seg.id, "metric": "length"})
        doc.vars.update_bindings(doc)
        assert abs(doc.vars.get_var("L").value - 5.0) < 1e-6
        p2.x, p2.y = 6, 8
        doc.recompute_from(p2)
        assert abs(doc.vars.get_var("L").value - 10.0) < 1e-6

    def test_bind_to_measure_then_move(self, full_setup):
        doc, p1, p2, seg, m = full_setup
        doc.vars.define("M", binding={"obj_id": m.id, "metric": "value"})
        doc.vars.update_bindings(doc)
        assert abs(doc.vars.get_var("M").value - 5.0) < 1e-6
        p2.x, p2.y = 6, 8
        doc.recompute_from(p2)
        assert abs(doc.vars.get_var("M").value - 10.0) < 1e-6

    def test_delete_measure_unbinds(self, full_setup):
        doc, p1, p2, seg, m = full_setup
        doc.vars.define("M", binding={"obj_id": m.id, "metric": "value"})
        doc.vars.update_bindings(doc)
        doc.remove(m)
        assert doc.vars.get_var("M").binding is None

    def test_expr_and_binding_mutual_exclusion(self, full_setup):
        doc, p1, p2, seg, m = full_setup
        doc.vars.define("a", binding={"obj_id": seg.id, "metric": "length"})
        doc.vars.set_expr("a", "b+1")
        assert doc.vars.get_var("a").expr == "b+1"
        assert doc.vars.get_var("a").binding is None


# ================================================================
# 六、压力与边界测试
# ================================================================
class TestEdgeCases:
    def test_many_variables_performance(self):
        from core.variables import VariableStore
        store = VariableStore()
        for i in range(1000):
            store.define(f"v{i}", float(i))
        assert len(store.names()) == 1000

    def test_binding_with_none_obj_id(self):
        from core.variables import VariableStore
        from core.document import Document
        store = VariableStore()
        doc = Document()
        store.define("a", binding={"obj_id": None, "metric": "length"})
        changed = store.update_bindings(doc)
        assert changed is True
        assert store.get_var("a").binding is None

    def test_binding_with_negative_obj_id(self):
        from core.variables import VariableStore
        from core.document import Document
        store = VariableStore()
        doc = Document()
        store.define("a", binding={"obj_id": -1, "metric": "length"})
        changed = store.update_bindings(doc)
        assert changed is True
        assert store.get_var("a").binding is None