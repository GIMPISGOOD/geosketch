"""Document 核心功能测试：增删、级联删除、复制粘贴、撤销重做、增量重算。"""

from geo.points import FreePoint
from geo.segments import Segment
from geo.division import DivisionPoint


class TestDocumentBasic:
    def test_add_object(self, doc):
        p = FreePoint(0, 0)
        doc.add(p)

        assert p in doc.objects

    def test_add_emits_changed(self, doc):
        received = []

        doc.changed.connect(lambda: received.append(1))

        p = FreePoint(0, 0)
        doc.add(p)

        assert received

    def test_remove_object(self, doc):
        p = FreePoint(0, 0)
        doc.add(p)

        doc.remove(p)

        assert p not in doc.objects

    def test_remove_cascade(self, doc):
        a = FreePoint(0, 0)
        b = FreePoint(1, 0)
        seg = Segment(a, b)

        doc.add(a)
        doc.add(b)
        doc.add(seg)

        doc.remove(a)

        assert a not in doc.objects
        assert seg not in doc.objects
        assert b in doc.objects

    def test_remove_selected(self, doc):
        p = FreePoint(0, 0)
        doc.add(p)

        p.selected = True
        doc.remove_selected()

        assert p not in doc.objects

    def test_clear(self, doc):
        p = FreePoint(0, 0)
        doc.add(p)

        doc.clear()

        assert len(doc.objects) == 0

    def test_clear_undo(self, doc):
        p = FreePoint(0, 0)
        doc.add(p)

        doc.clear()
        assert len(doc.objects) == 0

        doc.undo()
        assert len(doc.objects) == 1


class TestDocumentUndoRedo:
    def test_action_undo_redo(self, doc):
        doc.begin_action()

        p = FreePoint(1, 2)
        doc.add(p)

        doc.end_action()

        assert len(doc.objects) == 1

        doc.undo()
        assert len(doc.objects) == 0

        doc.redo()
        assert len(doc.objects) == 1

    def test_remove_can_undo(self, doc):
        p = FreePoint(0, 0)
        doc.add(p)

        doc.remove(p)
        assert len(doc.objects) == 0

        doc.undo()
        assert len(doc.objects) == 1


class TestDocumentClipboard:
    def test_copy_paste_point(self, doc):
        p = FreePoint(2, 3)
        doc.add(p)

        p.selected = True
        doc.copy_selection()
        doc.paste()

        points = [o for o in doc.objects if isinstance(o, FreePoint)]

        assert len(points) == 2

    def test_cut_selection(self, doc):
        p = FreePoint(0, 0)
        doc.add(p)

        p.selected = True
        doc.cut_selection()

        assert p not in doc.objects


class TestRecompute:
    def test_recompute_from_moves_dependent(self, doc):
        a = FreePoint(0, 0)
        b = FreePoint(2, 0)
        d = DivisionPoint(a, b, 0.5)

        doc.add(a)
        doc.add(b)
        doc.add(d)

        b.x = 4.0
        doc.recompute_from(b)

        assert abs(d.x - 2.0) < 1e-9