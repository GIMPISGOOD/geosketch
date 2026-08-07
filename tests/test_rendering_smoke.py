"""渲染冒烟测试：确保常见对象可以离屏渲染，不抛异常。"""

import pytest

from geo.points import FreePoint
from geo.segments import Segment
from geo.circles import Circle

from plugins.text_tool import TextObject


class TestRenderSmoke:
    def test_render_basic_objects(self, doc, canvas):
        a = FreePoint(0, 0)
        b = FreePoint(2, 1)
        seg = Segment(a, b)
        cir = Circle(a, b)
        text = TextObject("test", "#000000", 14, anchor=None, pos=(0, 1))

        for obj in (a, b, seg, cir, text):
            doc.add(obj)

        img = canvas.render_to_image(fit=False, bg_mode="grid", scale=1.0)

        assert img.width() > 0
        assert img.height() > 0

    def test_render_fit_content(self, doc, canvas):
        a = FreePoint(-1, -1)
        b = FreePoint(1, 1)
        seg = Segment(a, b)

        doc.add(a)
        doc.add(b)
        doc.add(seg)

        img = canvas.render_to_image(fit=True, bg_mode="grid", scale=1.0)

        assert img.width() > 0
        assert img.height() > 0

    def test_export_png(self, doc, canvas, tmp_path):
        p = FreePoint(0, 0)
        doc.add(p)

        path = tmp_path / "export.png"

        canvas.export_image(str(path), fit=True, bg_mode="grid", png_scale=1.0)

        assert path.exists()
        assert path.stat().st_size > 0