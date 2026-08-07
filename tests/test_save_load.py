"""保存 / 载入测试。"""

from core.document import Document
from core.variables import get_store

from geo.points import FreePoint
from geo.segments import Segment


class TestSaveLoad:
    def test_roundtrip(self, doc, tmp_path):
        store = get_store()

        store.define("a", 3.0, 0.0, 10.0)

        a = FreePoint(0, 0)
        b = FreePoint(1, 1)
        seg = Segment(a, b)

        doc.add(a)
        doc.add(b)
        doc.add(seg)

        path = tmp_path / "test.wgeo"

        doc.save(str(path))

        doc2 = Document()
        doc2.load(str(path))

        assert len(doc2.objects) == len(doc.objects)

        var = doc2.vars.get_var("a")
        assert var is not None
        assert abs(var.value - 3.0) < 1e-9