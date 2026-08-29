"""偏好设置全链路测试。

覆盖：
  1. SettingsStore 基本操作（get / set / reset / batch / version）
  2. DEFAULTS 中所有值的类型与范围合法性
  3. 序列化往返（to_dict / load_dict）
  4. 字体设置 → QFont 构建不崩溃（pointSize > 0）
  5. theme.refresh_fonts 不崩溃
  6. Document.save / load 中 settings.json 的持久化
  7. 边界值与非法输入防御
"""
from __future__ import annotations

import json
import os
import tempfile
import warnings

import pytest
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from core.settings import DEFAULTS, SettingsStore, _deep_copy, _deep_merge


# ═══════════════════════════════════════════════════════════
#  辅助
# ═══════════════════════════════════════════════════════════

def _all_leaf_keys(d: dict, prefix: str = "") -> list[tuple[str, object]]:
    """递归展开字典，返回所有叶节点的 (点号路径, 值)。"""
    items = []
    for k, v in d.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            items.extend(_all_leaf_keys(v, path))
        else:
            items.append((path, v))
    return items


def _make_doc_with_settings():
    """创建一个最小 Document（含 SettingsStore），不触发 UI。"""
    from core.document import Document
    doc = Document()
    assert hasattr(doc, "settings"), "Document 必须持有 settings 属性"
    assert isinstance(doc.settings, SettingsStore)
    return doc


# ═══════════════════════════════════════════════════════════
#  1. SettingsStore 基本操作
# ═══════════════════════════════════════════════════════════

class TestSettingsStoreBasics:

    def test_get_existing_key(self):
        s = SettingsStore()
        assert s.get("effects.panel_toggle_ms") == 200
        assert s.get("canvas.grid_visible") is True
        assert s.get("appearance.ui_font_size") == 10

    def test_get_missing_key_returns_fallback(self):
        s = SettingsStore()
        assert s.get("nonexistent.key") is None
        assert s.get("nonexistent.key", 42) == 42
        assert s.get("effects.nonexistent") is None

    def test_get_empty_string_key(self):
        s = SettingsStore()
        assert s.get("", "fallback") == "fallback"

    def test_set_and_get(self):
        s = SettingsStore()
        s.set("effects.panel_toggle_ms", 350)
        assert s.get("effects.panel_toggle_ms") == 350

    def test_set_creates_intermediate_layers(self):
        s = SettingsStore()
        s.set("new_section.new_key", 99)
        assert s.get("new_section.new_key") == 99

    def test_set_emits_changed(self, qapp):
        s = SettingsStore()
        received = []
        s.changed.connect(lambda k: received.append(k))
        s.set("effects.enabled", False)
        assert received == ["effects.enabled"]

    def test_set_does_not_emit_during_batch(self, qapp):
        s = SettingsStore()
        received = []
        s.changed.connect(lambda k: received.append(k))
        with s.batch():
            s.set("effects.enabled", False)
            s.set("effects.menu_fade", False)
        # batch 退出后应按分类合并发射
        assert received == ["effects.*"]

    def test_batch_multiple_sections(self, qapp):
        s = SettingsStore()
        received = []
        s.changed.connect(lambda k: received.append(k))
        with s.batch():
            s.set("effects.enabled", False)
            s.set("canvas.grid_visible", False)
            s.set("interaction.snap_enabled", False)
        assert "canvas.*" in received
        assert "effects.*" in received
        assert "interaction.*" in received
        assert len(received) == 3

    def test_reset(self, qapp):
        s = SettingsStore()
        s.set("effects.enabled", False)
        s.set("canvas.grid_visible", False)
        s.reset()
        assert s.get("effects.enabled") is True
        assert s.get("canvas.grid_visible") is True

    def test_reset_section(self, qapp):
        s = SettingsStore()
        s.set("effects.enabled", False)
        s.set("canvas.grid_visible", False)
        s.reset_section("effects")
        assert s.get("effects.enabled") is True
        assert s.get("canvas.grid_visible") is False  # canvas 不受影响

    def test_multiple_instances_independent(self):
        a = SettingsStore()
        b = SettingsStore()
        a.set("effects.enabled", False)
        assert b.get("effects.enabled") is True  # b 不受 a 影响


# ═══════════════════════════════════════════════════════════
#  2. DEFAULTS 类型与范围合法性
# ═══════════════════════════════════════════════════════════

class TestDefaultsValidity:

    def test_defaults_json_serializable(self):
        """所有默认值必须可 JSON 序列化。"""
        text = json.dumps(DEFAULTS, ensure_ascii=False)
        restored = json.loads(text)
        assert restored == DEFAULTS

    def test_all_leaf_types_are_json_primitives(self):
        """叶节点只允许 str / int / float / bool / list。"""
        for path, val in _all_leaf_keys(DEFAULTS):
            assert isinstance(val, (str, int, float, bool, list)), \
                f"{path} 的类型 {type(val).__name__} 不是 JSON 基本类型"

    def test_appearance_font_sizes_positive(self):
        """所有字号默认值必须 > 0。"""
        s = SettingsStore()
        for key in (
            "appearance.ui_font_size",
            "appearance.label_font_size",
            "appearance.axis_font_size",
            "appearance.publication_font_size",
        ):
            val = s.get(key)
            assert isinstance(val, int) and val > 0, \
                f"{key} = {val}，必须为正整数"

    def test_appearance_font_families_nonempty(self):
        """所有字体族默认值必须非空。"""
        s = SettingsStore()
        for key in (
            "appearance.label_font_family",
            "appearance.axis_font_family",
            "appearance.publication_font_family",
        ):
            val = s.get(key)
            assert isinstance(val, str) and len(val.strip()) > 0, \
                f"{key} = {val!r}，不能为空"

    def test_ui_font_family_is_list(self):
        """ui_font_family 必须是列表（回退链）。"""
        val = DEFAULTS["appearance"]["ui_font_family"]
        assert isinstance(val, list) and len(val) > 0

    def test_canvas_numeric_ranges(self):
        s = SettingsStore()
        assert s.get("canvas.grid_base_px") > 0
        assert s.get("canvas.grid_major_ratio") >= 2.0
        assert s.get("canvas.base_scale") > 0

    def test_effects_friction_range(self):
        s = SettingsStore()
        f = s.get("effects.canvas_friction")
        assert 0.0 < f < 1.0, f"friction={f}，必须在 (0,1) 内"

    def test_interaction_zoom_speed_range(self):
        s = SettingsStore()
        z = s.get("interaction.zoom_speed")
        assert z > 1.0, f"zoom_speed={z}，必须 > 1"

    def test_interaction_snap_radius_positive(self):
        s = SettingsStore()
        assert s.get("interaction.snap_radius_px") > 0

    def test_workflow_undo_limit_positive(self):
        s = SettingsStore()
        assert s.get("workflow.undo_limit") >= 1

    def test_math_scale_positive(self):
        s = SettingsStore()
        assert s.get("appearance.math_scale") > 0

    def test_point_radii_positive_and_ordered(self):
        s = SettingsStore()
        r_def = s.get("appearance.default_point_radius")
        r_sel = s.get("appearance.selected_point_radius")
        assert r_def > 0
        assert r_sel > 0
        assert r_sel >= r_def, "选中点半径应 >= 默认点半径"


# ═══════════════════════════════════════════════════════════
#  3. 序列化往返
# ═══════════════════════════════════════════════════════════

class TestSerialization:

    def test_to_dict_returns_deep_copy(self):
        s = SettingsStore()
        d = s.to_dict()
        d["effects"]["enabled"] = False
        assert s.get("effects.enabled") is True  # 原对象不受影响

    def test_load_dict_roundtrip(self, qapp):
        s = SettingsStore()
        s.set("effects.enabled", False)
        s.set("canvas.grid_base_px", 128.0)
        saved = s.to_dict()

        s2 = SettingsStore()
        s2.load_dict(saved)
        assert s2.get("effects.enabled") is False
        assert s2.get("canvas.grid_base_px") == 128.0
        # 未修改的键保持默认
        assert s2.get("appearance.ui_font_size") == 10

    def test_load_dict_partial(self, qapp):
        """只覆盖部分键，其余保持默认。"""
        s = SettingsStore()
        s.load_dict({"effects": {"enabled": False}})
        assert s.get("effects.enabled") is False
        assert s.get("effects.menu_fade") is True  # 默认值保留
        assert s.get("canvas.grid_visible") is True

    def test_load_dict_invalid_input(self, qapp):
        s = SettingsStore()
        s.load_dict(None)       # 不崩溃
        s.load_dict("bad")      # 不崩溃
        s.load_dict(42)         # 不崩溃
        assert s.get("effects.enabled") is True  # 默认值不变

    def test_load_dict_new_keys_forward_compat(self, qapp):
        """旧版文件缺少新增键时，默认值自动补全。"""
        old_saved = {"effects": {"enabled": True}}  # 只有旧键
        s = SettingsStore()
        s.load_dict(old_saved)
        # 新增键保持默认
        assert s.get("effects.canvas_friction") == 0.825
        assert s.get("interaction.snap_enabled") is True

    def test_load_dict_emits_star(self, qapp):
        s = SettingsStore()
        received = []
        s.changed.connect(lambda k: received.append(k))
        s.load_dict({"effects": {"enabled": False}})
        assert "*" in received


# ═══════════════════════════════════════════════════════════
#  4. 版本号
# ═══════════════════════════════════════════════════════════

class TestVersion:

    def test_version_starts_at_zero(self):
        s = SettingsStore()
        assert s.version == 0

    def test_version_increments_on_set(self):
        s = SettingsStore()
        s.set("effects.enabled", False)
        assert s.version == 1
        s.set("canvas.grid_visible", False)
        assert s.version == 2

    def test_version_increments_on_load_dict(self, qapp):
        s = SettingsStore()
        s.load_dict({"effects": {"enabled": False}})
        assert s.version == 1

    def test_version_increments_on_reset(self, qapp):
        s = SettingsStore()
        s.set("effects.enabled", False)
        v_before = s.version
        s.reset()
        assert s.version == v_before + 1

    def test_version_not_incremented_during_batch(self, qapp):
        """batch 内部不逐条递增，退出时也不额外递增。"""
        s = SettingsStore()
        v0 = s.version
        with s.batch():
            s.set("effects.enabled", False)
            s.set("effects.menu_fade", False)
        # batch 内 set 不递增 _version（信号被抑制）
        # 注意：当前实现中 _version 在 set 内不递增（仅 _batch_dirty 记录）
        # 所以退出后 _version 仍为 v0
        assert s.version == v0


# ═══════════════════════════════════════════════════════════
#  5. 字体设置 → QFont 构建（核心回归测试）
# ═══════════════════════════════════════════════════════════

class TestFontConstruction:
    """确保从设置构建 QFont 时 pointSize 始终 > 0，
    不触发 'QFont::setPointSize: Point size <= 0' 警告。"""

    def test_label_font_from_defaults(self, qapp):
        s = SettingsStore()
        family = s.get("appearance.label_font_family", "Consolas")
        size = int(s.get("appearance.label_font_size", 9))
        assert size > 0
        f = QFont(family, size)
        assert f.pointSize() > 0

    def test_axis_font_from_defaults(self, qapp):
        s = SettingsStore()
        family = s.get("appearance.axis_font_family", "Georgia")
        size = int(s.get("appearance.axis_font_size", 11))
        assert size > 0
        f = QFont(family, size, QFont.Weight.DemiBold)
        f.setItalic(True)
        assert f.pointSize() > 0

    def test_ui_font_from_defaults(self, qapp):
        s = SettingsStore()
        families = s.get("appearance.ui_font_family", ["Segoe UI"])
        size = int(s.get("appearance.ui_font_size", 10))
        assert size > 0
        f = QFont()
        if isinstance(families, list):
            f.setFamilies(families)
        else:
            f.setFamilies([str(families)])
        f.setPointSize(size)
        assert f.pointSize() > 0

    def test_publication_font_from_defaults(self, qapp):
        s = SettingsStore()
        family = s.get("appearance.publication_font_family", "Times New Roman")
        size = int(s.get("appearance.publication_font_size", 16))
        assert size > 0
        f = QFont(family, size)
        assert f.pointSize() > 0

    def test_font_size_never_negative_after_set(self, qapp):
        """模拟设置对话框写入后，字号仍 > 0。"""
        s = SettingsStore()
        for val in (1, 6, 10, 24, 100):
            s.set("appearance.label_font_size", val)
            size = int(s.get("appearance.label_font_size"))
            assert size > 0

    def test_font_size_clamped_to_minimum_1(self, qapp):
        """即使意外写入 0 或负数，构建 QFont 时用 max(1,...) 兜底。"""
        s = SettingsStore()
        s.set("appearance.label_font_size", 0)
        size = max(1, int(s.get("appearance.label_font_size", 9)))
        f = QFont("Consolas", size)
        assert f.pointSize() >= 1

    def test_fontcombobox_setfont_requires_pointsize(self, qapp):
        """QFontComboBox.setCurrentFont 传入的 QFont 必须 pointSize > 0。
        这是导致 'Point size <= 0 (-1)' 警告的直接原因。"""
        from PySide6.QtWidgets import QFontComboBox
        combo = QFontComboBox()
        # 正确方式：同时指定 family 和 pointSize
        f = QFont("Consolas")
        f.setPointSize(9)
        combo.setCurrentFont(f)
        assert combo.currentFont().family() == "Consolas"
        # 错误方式（会触发警告）：
        # combo.setCurrentFont(QFont("Consolas"))  ← pointSize == -1


# ═══════════════════════════════════════════════════════════
#  6. theme.refresh_fonts 不崩溃
# ═══════════════════════════════════════════════════════════

class TestThemeRefreshFonts:

    def test_refresh_fonts_with_defaults(self, qapp):
        from ui import theme
        s = SettingsStore()
        theme.refresh_fonts(s)
        assert theme.LABEL_FONT.pointSize() > 0
        assert theme.AXIS_FONT.pointSize() > 0

    def test_refresh_fonts_with_custom_values(self, qapp):
        from ui import theme
        s = SettingsStore()
        s.set("appearance.label_font_family", "Arial")
        s.set("appearance.label_font_size", 14)
        s.set("appearance.axis_font_family", "Verdana")
        s.set("appearance.axis_font_size", 12)
        theme.refresh_fonts(s)
        assert theme.LABEL_FONT.pointSize() == 14
        assert theme.AXIS_FONT.pointSize() == 12

    def test_refresh_fonts_with_minimum_size(self, qapp):
        from ui import theme
        s = SettingsStore()
        s.set("appearance.label_font_size", 1)
        s.set("appearance.axis_font_size", 1)
        theme.refresh_fonts(s)
        assert theme.LABEL_FONT.pointSize() >= 1
        assert theme.AXIS_FONT.pointSize() >= 1

    def test_refresh_fonts_after_reset(self, qapp):
        from ui import theme
        s = SettingsStore()
        s.set("appearance.label_font_size", 20)
        theme.refresh_fonts(s)
        assert theme.LABEL_FONT.pointSize() == 20
        s.reset()
        theme.refresh_fonts(s)
        assert theme.LABEL_FONT.pointSize() == 9  # 回到默认


# ═══════════════════════════════════════════════════════════
#  7. Document.save / load 持久化
# ═══════════════════════════════════════════════════════════

class TestDocumentPersistence:

    def test_save_creates_settings_json(self, qapp):
        import zipfile
        doc = _make_doc_with_settings()
        doc.settings.set("effects.enabled", False)
        doc.settings.set("canvas.grid_base_px", 100.0)

        with tempfile.NamedTemporaryFile(suffix=".wgeo", delete=False) as f:
            path = f.name
        try:
            doc.save(path)
            with zipfile.ZipFile(path, "r") as zf:
                assert "settings.json" in zf.namelist()
                saved = json.loads(zf.read("settings.json"))
                assert saved["effects"]["enabled"] is False
                assert saved["canvas"]["grid_base_px"] == 100.0
        finally:
            os.unlink(path)

    def test_load_restores_settings(self, qapp):
        import zipfile
        doc = _make_doc_with_settings()
        doc.settings.set("interaction.snap_radius_px", 25.0)
        doc.settings.set("appearance.ui_font_size", 12)

        with tempfile.NamedTemporaryFile(suffix=".wgeo", delete=False) as f:
            path = f.name
        try:
            doc.save(path)
            # 用新 Document 加载
            doc2 = _make_doc_with_settings()
            assert doc2.settings.get("interaction.snap_radius_px") == 18.0  # 默认
            doc2.load(path)
            assert doc2.settings.get("interaction.snap_radius_px") == 25.0
            assert doc2.settings.get("appearance.ui_font_size") == 12
        finally:
            os.unlink(path)

    def test_load_old_file_without_settings(self, qapp):
        """旧版 .wgeo 没有 settings.json → 保持默认值。"""
        import zipfile
        doc = _make_doc_with_settings()

        with tempfile.NamedTemporaryFile(suffix=".wgeo", delete=False) as f:
            path = f.name
        try:
            doc.save(path)
            # 手动删除 settings.json 条目（模拟旧文件）
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                data = {n: zf.read(n) for n in names}
            with zipfile.ZipFile(path, "w") as zf:
                for n in names:
                    if n != "settings.json":
                        zf.writestr(n, data[n])

            doc2 = _make_doc_with_settings()
            doc2.load(path)
            # 全部保持默认
            assert doc2.settings.get("effects.enabled") is True
            assert doc2.settings.get("canvas.grid_base_px") == 64.0
        finally:
            os.unlink(path)

    def test_load_corrupted_settings_json(self, qapp):
        """settings.json 内容损坏 → 不崩溃，保持默认。"""
        import zipfile
        doc = _make_doc_with_settings()

        with tempfile.NamedTemporaryFile(suffix=".wgeo", delete=False) as f:
            path = f.name
        try:
            doc.save(path)
            # 覆写 settings.json 为非法 JSON
            with zipfile.ZipFile(path, "r") as zf:
                names = zf.namelist()
                data = {n: zf.read(n) for n in names}
            data["settings.json"] = b"NOT VALID JSON {{{"
            with zipfile.ZipFile(path, "w") as zf:
                for n in names:
                    zf.writestr(n, data[n])

            doc2 = _make_doc_with_settings()
            doc2.load(path)  # 不应抛异常
            assert doc2.settings.get("effects.enabled") is True
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════
#  8. _deep_copy / _deep_merge 内部工具
# ═══════════════════════════════════════════════════════════

class TestInternalUtils:

    def test_deep_copy_isolation(self):
        orig = {"a": {"b": [1, 2, 3]}}
        copy = _deep_copy(orig)
        copy["a"]["b"].append(4)
        assert orig["a"]["b"] == [1, 2, 3]

    def test_deep_merge_recursive(self):
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99, "z": 100}, "c": 4}
        _deep_merge(base, override)
        assert base == {"a": {"x": 1, "y": 99, "z": 100}, "b": 3, "c": 4}

    def test_deep_merge_override_non_dict(self):
        base = {"a": {"x": 1}}
        override = {"a": "replaced"}
        _deep_merge(base, override)
        assert base["a"] == "replaced"

    def test_deep_merge_empty_override(self):
        base = {"a": 1}
        _deep_merge(base, {})
        assert base == {"a": 1}


# ═══════════════════════════════════════════════════════════
#  9. 边界值与防御
# ═══════════════════════════════════════════════════════════

class TestEdgeCases:

    def test_set_overwrites_non_dict_intermediate(self):
        """set 时中间层已存在但不是 dict → 自动覆盖为 {}。"""
        s = SettingsStore()
        s.set("effects.enabled", "not_a_dict")
        s.set("effects.enabled.sub", 42)
        assert s.get("effects.enabled.sub") == 42

    def test_get_deep_path(self):
        s = SettingsStore()
        s.set("a.b.c.d.e", "deep")
        assert s.get("a.b.c.d.e") == "deep"

    def test_repr_does_not_crash(self):
        s = SettingsStore()
        r = repr(s)
        assert "SettingsStore" in r

    def test_batch_nested(self, qapp):
        """嵌套 batch：最内层退出不发射，最外层退出时发射。"""
        s = SettingsStore()
        received = []
        s.changed.connect(lambda k: received.append(k))
        with s.batch():
            s.set("effects.enabled", False)
            with s.batch():
                s.set("canvas.grid_visible", False)
            # 内层退出，不发射
            assert received == []
        # 外层退出，发射
        assert len(received) >= 1

    def test_all_default_keys_accessible(self):
        """DEFAULTS 中每个叶节点都可通过 get 访问。"""
        s = SettingsStore()
        for path, expected in _all_leaf_keys(DEFAULTS):
            val = s.get(path)
            assert val == expected, f"{path}: 期望 {expected!r}，得到 {val!r}"