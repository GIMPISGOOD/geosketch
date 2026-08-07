"""宏系统测试。

如果 core.macro 不存在，或 Document 未启用宏录制信号，则自动跳过。
"""

import pytest

macro = pytest.importorskip("core.macro")

from core.document import Document
from geo.points import FreePoint


@pytest.fixture
def macro_doc():
    doc = Document()

    if not hasattr(doc, "object_added"):
        pytest.skip("Document 未启用 object_added 信号，无法测试宏录制")

    if not hasattr(doc, "macros"):
        pytest.skip("Document 未启用 macros 字段，无法测试宏系统")

    return doc


class TestMacroRecorder:
    def test_record_add_point(self, macro_doc):
        mm = macro.MacroManager(macro_doc)

        if hasattr(macro, "set_macro_manager"):
            macro.set_macro_manager(mm)

        mm.start_recording()

        p = FreePoint(0, 0)
        macro_doc.add(p)

        mm.stop_recording()

        assert macro_doc.macros
        assert macro_doc.macros[0]["commands"]

    def test_playback_creates_object(self, macro_doc):
        mm = macro.MacroManager(macro_doc)

        if hasattr(macro, "set_macro_manager"):
            macro.set_macro_manager(mm)

        mm.start_recording()

        p = FreePoint(0, 0)
        macro_doc.add(p)

        mm.stop_recording()

        if not macro_doc.macros:
            pytest.skip("宏录制未产生命令")

        before = len(macro_doc.objects)

        mm.play_last()

        assert len(macro_doc.objects) > before

    def test_playback_can_undo(self, macro_doc):
        mm = macro.MacroManager(macro_doc)

        if hasattr(macro, "set_macro_manager"):
            macro.set_macro_manager(mm)

        mm.start_recording()

        p = FreePoint(0, 0)
        macro_doc.add(p)

        mm.stop_recording()

        if not macro_doc.macros:
            pytest.skip("宏录制未产生命令")

        before = len(macro_doc.objects)

        mm.play_last()

        after = len(macro_doc.objects)
        assert after > before

        macro_doc.undo()

        assert len(macro_doc.objects) == before


class TestMacroLibrary:
    def test_register_script_library(self, macro_doc):
        if not hasattr(macro, "register_script_library"):
            pytest.skip("当前宏系统没有 register_script_library")

        macro.register_script_library(
            macro_doc,
            "mylib",
            """
func double(x) {
    return x * 2
}
"""
        )

        assert hasattr(macro_doc, "script_libs")
        assert "mylib" in macro_doc.script_libs