"""工具测试：点、线段、圆、框选、选择拖动。"""

import pytest

from geo.points import FreePoint
from geo.segments import Segment
from geo.circles import Circle

from tools.point_tool import PointTool
from tools.segment_tool import SegmentTool
from tools.circle_tool import CircleTool
from tools.box_select import BoxSelectTool
from tools.select import SelectTool


class TestPointTool:
    def test_press_creates_point(self, doc, canvas):
        tool = PointTool()
        tool.activated(canvas)

        tool.press(canvas, (1.0, 1.0), None)

        points = [o for o in doc.objects if isinstance(o, FreePoint)]
        assert len(points) == 1


class TestSegmentTool:
    def test_two_presses_create_segment(self, doc, canvas):
        tool = SegmentTool()
        tool.activated(canvas)

        tool.press(canvas, (0.0, 0.0), None)
        tool.press(canvas, (2.0, 0.0), None)

        points = [o for o in doc.objects if isinstance(o, FreePoint)]
        segments = [o for o in doc.objects if isinstance(o, Segment)]

        assert len(points) == 2
        assert len(segments) == 1


class TestCircleTool:
    def test_two_presses_create_circle(self, doc, canvas):
        tool = CircleTool()
        tool.activated(canvas)

        tool.press(canvas, (0.0, 0.0), None)
        tool.press(canvas, (2.0, 0.0), None)

        circles = [o for o in doc.objects if isinstance(o, Circle)]
        assert len(circles) == 1


class TestBoxSelectTool:
    def test_box_selects_inside_points(self, doc, canvas):
        inside = FreePoint(0, 0)
        outside = FreePoint(10, 10)

        doc.add(inside)
        doc.add(outside)

        tool = BoxSelectTool()
        tool.activated(canvas)

        tool.box_start = (-1, -1)
        tool.box_end = (1, 1)

        tool.release(canvas, (1, 1), None)

        assert inside.selected
        assert not outside.selected


class TestSelectTool:
    def test_press_selects_object(self, doc, canvas):
        p = FreePoint(0, 0)
        doc.add(p)

        tool = SelectTool()
        tool.activated(canvas)

        tool.press(canvas, (0, 0), p)

        assert p.selected

    def test_drag_moves_point(self, doc, canvas):
        p = FreePoint(0, 0)
        doc.add(p)

        tool = SelectTool()
        tool.activated(canvas)

        tool.press(canvas, (0, 0), p)
        tool.move(canvas, (2, 0), None)
        tool.release(canvas, (2, 0), None)

        assert abs(p.x - 2.0) < 1e-6