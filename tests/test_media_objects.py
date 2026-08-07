"""媒体对象测试：表格、饼图、柱状图、基础矩形拾取。"""

import pytest

from media.table_obj import TableObject
from media.chart_obj import PieChartObject, BarChartObject


class TestTableObject:
    def test_create(self):
        t = TableObject(0, 0, rows=2, cols=3, width=4, height=2)

        assert t.rows == 2
        assert t.cols == 3

    def test_dump_build(self):
        t = TableObject(1, 2, rows=2, cols=2, width=3, height=2)

        t2 = TableObject.build([], t.dump())

        assert abs(t2.x - 1) < 1e-9
        assert abs(t2.y - 2) < 1e-9
        assert t2.rows == 2
        assert t2.cols == 2

    def test_distance_inside(self):
        t = TableObject(0, 0, rows=2, cols=2, width=4, height=2)

        # MediaObject 左上角 (0,0)，高度向下，因此内部点 y 应为负
        assert t.distance_to(1, -1) == 0.0


class TestPieChart:
    def test_get_values_numeric(self):
        p = PieChartObject(0, 0, data=[1, 2.5, 3])

        assert p.get_values() == [1.0, 2.5, 3.0]

    def test_get_values_string(self):
        p = PieChartObject(0, 0, data=["1", "2.0"])

        assert p.get_values() == [1.0, 2.0]


class TestBarChart:
    def test_get_values(self):
        b = BarChartObject(0, 0, data=[4, 5])

        assert b.get_values() == [4.0, 5.0]


class TestMediaRenderSmoke:
    def test_render_table(self, doc, canvas):
        t = TableObject(0, 0, rows=2, cols=2, width=3, height=2)
        doc.add(t)

        img = canvas.render_to_image(fit=True, bg_mode="grid", scale=1.0)

        assert img.width() > 0
        assert img.height() > 0