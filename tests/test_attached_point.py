"""吸附点（PointOnObject）功能测试。
运行：pytest tests/test_attached_point.py -v
"""
import math

from geo.points import FreePoint, PointOnObject
from geo.segments import Segment
from geo.circles import Circle


# ─────────────── 吸附在线段上 ───────────────
class TestPointOnSegment:
    def setup_method(self):
        self.a = FreePoint(0, 0)
        self.b = FreePoint(4, 0)
        self.seg = Segment(self.a, self.b)
        self.p = PointOnObject(self.seg, t=0.5)

    def test_01_initial_position_is_midpoint(self):
        """t=0.5 应在线段中点"""
        assert math.isclose(self.p.x, 2.0, abs_tol=1e-9)
        assert math.isclose(self.p.y, 0.0, abs_tol=1e-9)

    def test_02_drag_projects_back_onto_segment(self):
        """拖到线段外，应投影回线段"""
        self.p.drag_to((3, 5))
        self.p.recompute()
        assert math.isclose(self.p.x, 3.0, abs_tol=1e-9)
        assert math.isclose(self.p.y, 0.0, abs_tol=1e-9)

    def test_03_drag_clamped_at_endpoints(self):
        """拖过端点应被夹在端点内"""
        self.p.drag_to((100, 0))
        self.p.recompute()
        assert math.isclose(self.p.x, 4.0, abs_tol=1e-9), "应夹在 b 端"
        self.p.drag_to((-100, 0))
        self.p.recompute()
        assert math.isclose(self.p.x, 0.0, abs_tol=1e-9), "应夹在 a 端"

    def test_04_stays_on_segment_after_many_drags(self):
        """反复拖动后点始终在线段上（y=0 且 0<=x<=4）"""
        for tx, ty in [(1, 9), (3, -7), (2, 100), (0, 0), (4, 0)]:
            self.p.drag_to((tx, ty))
            self.p.recompute()
            assert math.isclose(self.p.y, 0.0, abs_tol=1e-6), f"拖到({tx},{ty})后 y={self.p.y}"
            assert -1e-6 <= self.p.x <= 4.0 + 1e-6, f"拖到({tx},{ty})后 x={self.p.x}"

    def test_05_host_endpoint_move_updates_point(self):
        """移动线段端点，吸附点应跟随"""
        self.b.x, self.b.y = 8, 0
        self.p.recompute()
        assert math.isclose(self.p.x, 4.0, abs_tol=1e-9), "应是新中点"

    def test_06_degenerate_segment_no_crash(self):
        """退化线段（两端重合）拖动不应崩溃"""
        a = FreePoint(2, 2)
        b = FreePoint(2, 2)
        seg = Segment(a, b)
        p = PointOnObject(seg, t=0.5)
        p.drag_to((5, 5))
        p.recompute()
        assert math.isclose(p.x, 2.0, abs_tol=1e-6)
        assert math.isclose(p.y, 2.0, abs_tol=1e-6)


# ─────────────── 吸附在圆上 ───────────────
class TestPointOnCircle:
    def setup_method(self):
        self.c = FreePoint(0, 0)
        self.through = FreePoint(3, 0)
        self.circle = Circle(self.c, self.through)
        self.p = PointOnObject(self.circle, t=0.0)

    def test_01_initial_position_on_circle(self):
        """t=0 应在 (3,0)"""
        assert math.isclose(self.p.x, 3.0, abs_tol=1e-9)
        assert math.isclose(self.p.y, 0.0, abs_tol=1e-9)

    def test_02_drag_projects_onto_circle(self):
        """拖到圆外上方，应投影到圆顶 (0,3)"""
        self.p.drag_to((0, 10))
        self.p.recompute()
        assert math.isclose(self.p.x, 0.0, abs_tol=1e-6)
        assert math.isclose(self.p.y, 3.0, abs_tol=1e-6)

    def test_03_always_on_circle_after_drags(self):
        """反复拖动后点到圆心距离恒等于半径"""
        for tx, ty in [(10, 10), (-5, 3), (0, -8), (100, -100)]:
            self.p.drag_to((tx, ty))
            self.p.recompute()
            dist = math.hypot(self.p.x - self.c.x, self.p.y - self.c.y)
            assert math.isclose(dist, 3.0, abs_tol=1e-6), \
                f"拖到({tx},{ty})后到圆心距离={dist:.4f}，应为3"

    def test_04_drag_to_center_does_not_crash(self):
        """拖到圆心（方向未定义）不应崩溃，且仍在圆上"""
        self.p.drag_to((0, 0))
        self.p.recompute()
        dist = math.hypot(self.p.x - self.c.x, self.p.y - self.c.y)
        assert math.isclose(dist, 3.0, abs_tol=1e-6)

    def test_05_host_center_move_updates_point(self):
        """移动圆心，吸附点应仍在圆上（距离=当前半径）"""
        self.c.x, self.c.y = 5, 5
        self.p.recompute()
        dist = math.hypot(self.p.x - self.c.x, self.p.y - self.c.y)
        assert math.isclose(dist, self.circle.r, abs_tol=1e-6), \
            f"圆心移动后偏离，距离={dist}, 半径={self.circle.r}"


# ─────────────── 依赖传播（通过 Document.recompute_from）───────────────
class TestRecomputePropagation:
    def test_01_move_endpoint_propagates_to_attached_point(self):
        """recompute_from 移动端点，吸附点应跟随"""
        from core.document import Document
        doc = Document()
        a = FreePoint(0, 0)
        b = FreePoint(4, 0)
        seg = Segment(a, b)
        p = PointOnObject(seg, t=0.5)
        for o in (a, b, seg, p):
            doc.add(o)
        b.x, b.y = 8, 0
        doc.recompute_from(b)
        assert math.isclose(p.x, 4.0, abs_tol=1e-9), f"端点移动后 x={p.x}，应为4"

    def test_02_move_circle_center_propagates(self):
        """移动圆心，吸附点应仍在圆上"""
        from core.document import Document
        doc = Document()
        c = FreePoint(0, 0)
        through = FreePoint(3, 0)
        circle = Circle(c, through)
        p = PointOnObject(circle, t=0.0)
        for o in (c, through, circle, p):
            doc.add(o)
        c.x, c.y = 10, 10
        doc.recompute_from(c)
        dist = math.hypot(p.x - c.x, p.y - c.y)
        assert math.isclose(dist, circle.r, abs_tol=1e-6), \
            f"圆心移动后偏离，距离={dist}, 半径={circle.r}"