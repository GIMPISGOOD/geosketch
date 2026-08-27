"""TraceCurve 插件集成测试：验证采样、级联更新、序列化。"""
import math
import pytest
from PySide6.QtWidgets import QApplication

from core.document import Document
from geo.points import FreePoint
from geo.base import GeoObject


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture
def doc(qapp):
    GeoObject.reset_ids()
    return Document()


# ═══════════════════════════════════════════════════════
#  测试 1：基本采样 —— 手动移动点 + 手动调用 recompute
# ═══════════════════════════════════════════════════════

class TestTraceBasicSampling:
    def test_initial_state(self, doc):
        """创建后应有一个初始点。"""
        from plugins.trace_tool import TraceCurve
        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        assert len(trace.points) == 1
        assert trace.points[0] == (0.0, 0.0)

    def test_large_move_records(self, doc):
        """移动距离 > min_dist → 应记录新点。"""
        from plugins.trace_tool import TraceCurve
        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        # 移动 1.0 个世界单位（远大于 min_dist=0.12）
        pt.x, pt.y = 1.0, 0.0
        trace.recompute()

        assert len(trace.points) > 1, "大位移应记录新点"
        assert trace.points[-1] == (1.0, 0.0)

    def test_small_move_skipped(self, doc):
        """移动距离 < min_dist → 不应记录。"""
        from plugins.trace_tool import TraceCurve
        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        # 移动 0.01（远小于 min_dist=0.12）
        pt.x, pt.y = 0.01, 0.0
        trace.recompute()

        assert len(trace.points) == 1, "小位移不应记录"

    def test_small_move_accumulation_problem(self, doc):
        """★ 关键测试：模拟动画帧率，每帧移动 0.02。
        如果每帧都 < min_dist，轨迹将永远不记录！
        """
        from plugins.trace_tool import TraceCurve
        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        # 模拟 100 帧动画，每帧移动 0.02
        for i in range(1, 101):
            pt.x = i * 0.02
            pt.y = 0.0
            trace.recompute()

        total_moved = 100 * 0.02  # = 2.0 世界单位
        print(f"\n  总移动距离: {total_moved}")
        print(f"  min_dist: {trace.min_dist}")
        print(f"  记录点数: {len(trace.points)}")
        print(f"  每帧移动: 0.02 < min_dist={trace.min_dist} → 永远不记录!")

        # ★ 这个断言会失败，暴露 bug
        assert len(trace.points) > 1, (
            f"移动了 {total_moved} 个单位但只记录了 "
            f"{len(trace.points)} 个点！min_dist 过大。"
        )


# ═══════════════════════════════════════════════════════
#  测试 2：级联更新 —— 通过 Document.recompute_from 触发
# ═══════════════════════════════════════════════════════

class TestTraceCascade:
    def test_recompute_from_triggers_trace(self, doc):
        """doc.recompute_from([point]) 应触发 TraceCurve.recompute()。"""
        from plugins.trace_tool import TraceCurve
        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        assert trace in pt.children, "TraceCurve 应在 point.children 中"

        # 大位移
        pt.x, pt.y = 5.0, 5.0
        doc.recompute_from([pt])

        assert len(trace.points) > 1, "recompute_from 应触发轨迹记录"
        assert abs(trace.points[-1][0] - 5.0) < 1e-6

    def test_recompute_silent_triggers_trace(self, doc):
        """doc.recompute_silent([point]) 也应触发。"""
        from plugins.trace_tool import TraceCurve
        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        pt.x, pt.y = 3.0, 0.0
        doc.recompute_silent([pt])

        assert len(trace.points) > 1

    def test_trace_not_triggered_for_other_points(self, doc):
        """移动其他点不应影响此轨迹。"""
        from plugins.trace_tool import TraceCurve
        pt_a = doc.add(FreePoint(0, 0))
        pt_b = doc.add(FreePoint(10, 10))
        trace = TraceCurve(pt_a)
        doc.add(trace)

        pt_b.x, pt_b.y = 20.0, 20.0
        doc.recompute_from([pt_b])

        assert len(trace.points) == 1, "无关点的移动不应触发轨迹"


# ═══════════════════════════════════════════════════════
#  测试 3：工具交互 —— TraceTool.press 创建轨迹
# ═══════════════════════════════════════════════════════

class TestTraceTool:
    def test_press_creates_trace(self, doc):
        """点击一个点应创建 TraceCurve 对象。"""
        from plugins.trace_tool import TraceTool, TraceCurve

        pt = doc.add(FreePoint(2, 3))
        tool = TraceTool()

        # 模拟 press（hit = 该点）
        class FakeCanvas:
            def __init__(self, d):
                self.doc = d
            def update(self):
                pass
            @property
            def cursor_info(self):
                class _S:
                    def emit(self, *a): pass
                return _S()

        canvas = FakeCanvas(doc)
        tool.press(canvas, (2, 3), pt)

        traces = [o for o in doc.objects if isinstance(o, TraceCurve)]
        assert len(traces) == 1, "应创建一个 TraceCurve"
        assert traces[0].point is pt

    def test_press_same_point_resets(self, doc):
        """再次点击同一点应重置轨迹而非创建新的。"""
        from plugins.trace_tool import TraceTool, TraceCurve

        pt = doc.add(FreePoint(0, 0))
        tool = TraceTool()

        class FakeCanvas:
            def __init__(self, d):
                self.doc = d
            def update(self): pass
            @property
            def cursor_info(self):
                class _S:
                    def emit(self, *a): pass
                return _S()

        canvas = FakeCanvas(doc)
        tool.press(canvas, (0, 0), pt)

        # 移动点产生轨迹
        trace = [o for o in doc.objects if isinstance(o, TraceCurve)][0]
        pt.x, pt.y = 5.0, 5.0
        doc.recompute_from([pt])
        assert len(trace.points) > 1

        # 再次点击 → 重置
        tool.press(canvas, (5, 5), pt)
        assert len(trace.points) == 1, "重置后应只有 1 个点"

    def test_press_non_point_ignored(self, doc):
        """点击非点对象不应创建轨迹。"""
        from plugins.trace_tool import TraceTool, TraceCurve
        from geo.segments import Segment

        pt_a = doc.add(FreePoint(0, 0))
        pt_b = doc.add(FreePoint(1, 1))
        seg = doc.add(Segment(pt_a, pt_b))

        tool = TraceTool()

        class FakeCanvas:
            def __init__(self, d):
                self.doc = d
            def update(self): pass
            @property
            def cursor_info(self):
                class _S:
                    def emit(self, *a): pass
                return _S()

        canvas = FakeCanvas(doc)
        tool.press(canvas, (0.5, 0.5), seg)  # 点击线段

        traces = [o for o in doc.objects if isinstance(o, TraceCurve)]
        assert len(traces) == 0, "点击非点对象不应创建轨迹"


# ═══════════════════════════════════════════════════════
#  测试 4：序列化 / 反序列化
# ═══════════════════════════════════════════════════════

class TestTraceSerialization:
    def test_dump_build_roundtrip(self, doc):
        """dump → build 应还原轨迹数据。"""
        from plugins.trace_tool import TraceCurve

        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt, color="#1971c2", width=2.5)
        doc.add(trace)

        # 模拟一些轨迹点
        trace.points = [(0, 0), (1, 1), (2, 0), (3, 1)]
        trace._last_pos = (3, 1)

        params = trace.dump()
        assert params["color"] == "#1971c2"
        assert params["width"] == 2.5
        assert len(params["points"]) == 4

        # 重建
        rebuilt = TraceCurve.build([pt], params)
        assert rebuilt.color == "#1971c2"
        assert rebuilt.width == 2.5
        assert rebuilt.points == [(0, 0), (1, 1), (2, 0), (3, 1)]
        assert rebuilt._last_pos == (3, 1)

    def test_snapshot_includes_trace(self, doc):
        """Document.snapshot() 应包含 TraceCurve。"""
        from plugins.trace_tool import TraceCurve

        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        snap = doc.snapshot()
        types = [item["type"] for item in snap if isinstance(item, dict) and "type" in item]
        assert "TraceCurve" in types


# ═══════════════════════════════════════════════════════
#  测试 5：级联删除
# ═══════════════════════════════════════════════════════

class TestTraceCascadeDelete:
    def test_delete_point_removes_trace(self, doc):
        """删除被追踪的点应级联删除轨迹。"""
        from plugins.trace_tool import TraceCurve

        pt = doc.add(FreePoint(0, 0))
        trace = TraceCurve(pt)
        doc.add(trace)

        assert trace in doc.objects

        doc.remove(pt)

        assert trace not in doc.objects, "删除点应级联删除轨迹"
        assert pt not in doc.objects


# ═══════════════════════════════════════════════════════
#  测试 6：渲染器注册
# ═══════════════════════════════════════════════════════

class TestTraceRenderer:
    def test_renderer_registered(self):
        """TraceCurve 应有注册的渲染器。"""
        from core.registry import find_renderer, RENDER_REGISTRY
        from plugins.trace_tool import TraceCurve

        # 创建临时实例检查
        pt = FreePoint(0, 0)
        trace = TraceCurve(pt)

        renderer = find_renderer(trace)
        assert renderer is not None, "TraceCurve 缺少渲染器注册"