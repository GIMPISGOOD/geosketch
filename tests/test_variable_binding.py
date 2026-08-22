import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


from core.document import Document
from core.variables import get_store
from geo.points import FreePoint
from geo.segments import Segment
from plugins.measure_tools import Measure, RegionMeasure


@pytest.fixture(autouse=True)
def clean_vars():
    store = get_store()
    store.load_dict({})
    yield store
    store.load_dict({})


def _segment_doc(x=3.0, y=4.0):
    doc = Document()

    a = FreePoint(0.0, 0.0)
    b = FreePoint(x, y)
    seg = Segment(a, b)

    doc.add(a)
    doc.add(b)
    doc.add(seg)

    return doc, a, b, seg


def test_bind_segment_length(clean_vars):
    doc, a, b, seg = _segment_doc(3.0, 4.0)

    doc.vars.define(
        name="L",
        value=0.0,
        vmin=0.0,
        vmax=10.0,
        binding={"obj_id": seg.id, "metric": "length"},
    )

    doc.vars.update_bindings(doc)
    assert abs(doc.vars.get_var("L").value - 5.0) < 1e-6

    b.x = 6.0
    b.y = 8.0
    doc.recompute_from([b])

    assert abs(doc.vars.get_var("L").value - 10.0) < 1e-6


def test_bound_variable_is_read_only(clean_vars):
    doc, a, b, seg = _segment_doc(3.0, 4.0)

    doc.vars.define(
        name="L",
        value=0.0,
        vmin=0.0,
        vmax=10.0,
        binding={"obj_id": seg.id, "metric": "length"},
    )

    doc.vars.update_bindings(doc)
    assert abs(doc.vars.get_var("L").value - 5.0) < 1e-6

    doc.vars.set("L", 999.0)
    assert abs(doc.vars.get_var("L").value - 5.0) < 1e-6


def test_delete_bound_object_unbinds(clean_vars):
    doc, a, b, seg = _segment_doc(3.0, 4.0)

    doc.vars.define(
        name="L",
        value=0.0,
        vmin=0.0,
        vmax=10.0,
        binding={"obj_id": seg.id, "metric": "length"},
    )
    doc.vars.update_bindings(doc)
    assert doc.vars.get_var("L").binding is not None

    doc.remove(seg)

    assert doc.vars.get_var("L").binding is None
    assert abs(doc.vars.get_var("L").value - 5.0) < 1e-6


def test_bind_measure_object(clean_vars):
    doc, a, b, seg = _segment_doc(3.0, 4.0)

    m = Measure("length", [seg])
    doc.add(m)

    doc.vars.define(
        name="M",
        value=0.0,
        vmin=0.0,
        vmax=10.0,
        binding={"obj_id": m.id, "metric": "value"},
    )

    doc.vars.update_bindings(doc)
    assert abs(doc.vars.get_var("M").value - 5.0) < 1e-6

    b.x = 6.0
    b.y = 8.0
    doc.recompute_from([b])

    assert abs(doc.vars.get_var("M").value - 10.0) < 1e-6


def test_bind_region_measure_area(clean_vars):
    doc = Document()

    p1 = FreePoint(0.0, 0.0)
    p2 = FreePoint(4.0, 0.0)
    p3 = FreePoint(4.0, 3.0)

    doc.add(p1)
    doc.add(p2)
    doc.add(p3)

    region = RegionMeasure([p1, p2, p3])
    doc.add(region)

    doc.vars.define(
        name="A",
        value=0.0,
        vmin=0.0,
        vmax=100.0,
        binding={"obj_id": region.id, "metric": "area"},
    )

    doc.vars.update_bindings(doc)
    assert abs(doc.vars.get_var("A").value - 6.0) < 1e-6

    p3.y = 6.0
    doc.recompute_from([p3])

    assert abs(doc.vars.get_var("A").value - 12.0) < 1e-6


def test_binding_serialization(clean_vars):
    doc, a, b, seg = _segment_doc(3.0, 4.0)

    doc.vars.define(
        name="L",
        value=0.0,
        vmin=0.0,
        vmax=10.0,
        binding={"obj_id": seg.id, "metric": "length"},
    )

    data = doc.vars.to_dict()
    assert data["L"]["binding"] == {"obj_id": seg.id, "metric": "length"}

    store = get_store()
    store.load_dict(data)

    var = store.get_var("L")
    assert var is not None
    assert var.binding == {"obj_id": seg.id, "metric": "length"}