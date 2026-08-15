"""新特性综合测试：隐函数、橡皮擦、图表、图片内嵌、汉化、线程安全。
运行：pytest tests/test_new_features.py -v
"""
import os
import json
import zipfile
import pytest
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

# ─────────────── Qt 环境 ───────────────
@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app

@pytest.fixture(autouse=True)
def clean_variables():
    from core.variables import get_store
    store = get_store()
    saved_vars = dict(store._vars)
    saved_version = store.version
    yield
    store._vars = saved_vars
    store.version = saved_version

# ═══════════════ 1. 隐函数解析与采样 ═══════════════
class TestImplicitCurve:
    def test_parse_equation(self):
        from geo.implicit_curve import parse_equation
        # 测试自动移项
        assert parse_equation("x^2+y^2=1") == "(x^2+y^2)-(1)"
        assert parse_equation("x^2+y^2-1") == "x^2+y^2-1"
        assert parse_equation(" sin(x)*cos(y) = 0.5 ") == "(sin(x)*cos(y))-(0.5)"

    def test_implicit_curve_init(self):
        from geo.implicit_curve import ImplicitCurve
        c = ImplicitCurve("x^2+y^2=1")
        assert c._resolved_expr == "(x^2+y^2)-(1)"
        assert c.expr == "x^2+y^2=1"
        
    def test_marching_squares_circle(self):
        from geo.implicit_sampler import _marching_squares
        from core.variables import evaluate

        # ★ 修复：不预先调用 _preprocess，因为 evaluate 内部会自动调用
        # 直接传入原始表达式 "x^2+y^2-1"，让 evaluate 内部处理 ^ → **
        class _Eval:
            def __init__(self, e):
                self.expr = e
                self.valid = True
            def eval(self, vd):
                return evaluate(self.expr, vd)

        # 先验证 evaluate 本身能正确求值
        test_val = evaluate("x^2+y^2-1", {"x": 0.0, "y": 0.0})
        assert test_val is not None, "evaluate 无法求值 x^2+y^2-1"
        assert abs(test_val - (-1.0)) < 1e-9, f"期望 -1.0，实际 {test_val}"

        test_val2 = evaluate("x^2+y^2-1", {"x": 1.0, "y": 0.0})
        assert test_val2 is not None, "evaluate 无法求值 x^2+y^2-1 在 (1,0)"
        assert abs(test_val2 - 0.0) < 1e-9, f"期望 0.0，实际 {test_val2}"

        fast = _Eval("x^2+y^2-1")  # ★ 直接传原始表达式
        vd = {}
        segments = _marching_squares(fast, vd, -2, 2, -2, 2, 20, 20)
        assert len(segments) > 0, "圆 x²+y²=1 应产生等值线段"
        for x1, y1, x2, y2 in segments:
            assert abs(x1**2 + y1**2 - 1.0) < 0.25
            assert abs(x2**2 + y2**2 - 1.0) < 0.25

# ═══════════════ 2. 真正橡皮擦逻辑 ═══════════════
class TestInkEraser:
    def test_split_stroke(self):
        from tools.ink_tool import InkTool
        # 一条水平线 y=0, x 从 -5 到 5
        points = [(float(x), 0.0) for x in range(-5, 6)]
        # 擦除中心在 (0,0)，半径 1.5 (应擦除 x=-1, 0, 1)
        segments = InkTool._split_stroke(points, (0.0, 0.0), 1.5)
        assert len(segments) == 2
        # 第一段 [-5..-2]
        assert segments[0][0] == (-5.0, 0.0)
        assert segments[0][-1] == (-2.0, 0.0)
        # 第二段 [2..5]
        assert segments[1][0] == (2.0, 0.0)
        assert segments[1][-1] == (5.0, 0.0)

    def test_split_stroke_no_erase(self):
        from tools.ink_tool import InkTool
        points = [(float(x), 0.0) for x in range(-5, 6)]
        # 擦除圆远离笔画
        segments = InkTool._split_stroke(points, (10.0, 10.0), 1.0)
        assert len(segments) == 1
        assert len(segments[0]) == len(points)

# ═══════════════ 3. 新媒体对象 ═══════════════
class TestChartObjects:
    def test_line_chart_dump_build(self):
        from media.chart_obj import LineChartObject
        obj = LineChartObject(1, 2, data=[10, 20], labels=["A", "B"], colors=["#ff0000"])
        d = obj.dump()
        obj2 = LineChartObject.build([], d)
        assert obj2.x == 1
        assert obj2.data == [10, 20]
        assert obj2.labels == ["A", "B"]

    def test_donut_chart_dump_build(self):
        from media.chart_obj import DonutChartObject
        obj = DonutChartObject(0, 0, data=[25, 25, 25, 25], hole=0.5)
        d = obj.dump()
        obj2 = DonutChartObject.build([], d)
        assert obj2.hole == 0.5
        assert len(obj2.data) == 4

# ═══════════════ 4. 图片内嵌序列化 ═══════════════
class TestImageEmbed:
    def test_image_embed_save_load(self, tmp_path, qapp):
        from core.document import Document
        from media.image_obj import ImageObject
        
        # 1. 创建临时图片
        img_path = tmp_path / "test_img.png"
        px = QPixmap(10, 10)
        px.save(str(img_path))
        
        # 2. 创建文档并添加图片
        doc = Document()
        img_obj = ImageObject(0, 0, str(img_path))
        doc.add(img_obj)
        
        # 3. 保存为 .wgeo
        wgeo_path = tmp_path / "test.wgeo"
        doc.save(str(wgeo_path))
        
        # 4. 验证 zip 内容
        with zipfile.ZipFile(wgeo_path, 'r') as zf:
            names = zf.namelist()
            img_files = [n for n in names if n.startswith("media/images/")]
            assert len(img_files) == 1, "图片应被内嵌到 media/images/ 目录"
            
            sketch = json.loads(zf.read("sketch.json"))
            img_data = sketch[0]["params"]
            assert "image_name" in img_data, "序列化应使用 image_name 而非绝对路径"
            assert "path" not in img_data
            
        # 5. 加载并验证
        doc2 = Document()
        doc2.load(str(wgeo_path))
        assert len(doc2.objects) == 1
        loaded_img = doc2.objects[0]
        assert isinstance(loaded_img, ImageObject)
        assert os.path.exists(loaded_img.path), "加载时应自动解压到临时目录"
        assert not loaded_img.pixmap.isNull()

# ═══════════════ 5. 属性面板汉化 ═══════════════
class TestPropertyPanelI18n:
    def test_chinese_labels(self, qapp):
        from ui.property_panel import PropertyPanel
        
        class MockDoc:
            changed = type('Signal', (), {'connect': lambda *a: None})()
        class MockCanvas:
            doc = MockDoc()
            height = 800
            width = 1200
            
        panel = PropertyPanel(MockCanvas())
        
        class DummyImplicit: pass
        DummyImplicit.__name__ = "ImplicitCurve"
        
        class DummyParallel: pass
        DummyParallel.__name__ = "ParallelLine"
        
        class DummyIncenter: pass
        DummyIncenter.__name__ = "Incenter"
        
        assert panel._get_type_label(DummyImplicit()) == "隐函数曲线"
        assert panel._get_type_label(DummyParallel()) == "平行线"
        assert panel._get_type_label(DummyIncenter()) == "内心"

# ═══════════════ 6. 线程安全退出 ═══════════════
class TestSamplerShutdown:
    def test_implicit_sampler_shutdown(self):
        from geo.implicit_sampler import get_implicit_sampler, shutdown_implicit_sampler
        sampler = get_implicit_sampler()
        assert sampler.isRunning()
        shutdown_implicit_sampler()
        # 验证线程已安全终止
        assert not sampler.isRunning()