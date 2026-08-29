"""应用偏好设置：数据模型、默认值与运行时存取。

设计原则
────────
• 默认值硬编码在本文件的 ``DEFAULTS`` 字典中（不读外部文件）。
• 持久化由 ``Document.save`` / ``Document.load`` 负责
  （写入 ``.wgeo`` ZIP 内的 ``settings.json`` 条目）。
• 本模块 **不做任何文件 I/O**。
• 每个 ``Document`` 持有一个独立的 ``SettingsStore`` 实例。

对外契约（其他文件依赖下列名字，重构不得改动）
──────────────────────────────────────────────
DEFAULTS · SettingsStore
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Generator

from PySide6.QtCore import QObject, Signal


# ═══════════════════════════════════════════════════════════
#  默认值（硬编码，不依赖外部文件）
#  所有值必须是 JSON 可序列化的基本类型：
#  str / int / float / bool / list / dict
# ═══════════════════════════════════════════════════════════

DEFAULTS: dict = {

    # ── 外观 ──────────────────────────────────────────
    "appearance": {
        "ui_font_family": [
            "Segoe UI", "PingFang SC", "Microsoft YaHei", "sans-serif",
        ],
        "ui_font_size":              10,
        "label_font_family":         "Consolas",
        "label_font_size":           9,
        "axis_font_family":          "Georgia",
        "axis_font_size":            11,
        "math_scale":                1.0,
        "default_line_width":        2.0,
        "default_point_radius":      4.0,
        "selected_point_radius":     6.0,
        "publication_font_family":   "Times New Roman",
        "publication_font_size":     16,
    },

    # ── 画布 ──────────────────────────────────────────
    "canvas": {
        "grid_visible":       True,
        "grid_base_px":       64.0,
        "grid_major_ratio":   5.0,
        "axis_visible":       True,
        "axis_labels_visible": True,
        "base_scale":         48.0,
    },

    # ── 动效（仅 UI / 渲染层，不涉及 animation 模块）──
    "effects": {
        "enabled":             True,
        "panel_toggle_ms":     200,
        "menu_fade":           True,
        "dialog_transition":   True,
        "canvas_inertia":      True,
        "canvas_friction":     0.825,
        "hover_highlight":     True,
    },

    # ── 交互 ──────────────────────────────────────────
    "interaction": {
        "snap_enabled":       True,
        "snap_radius_px":     18.0,
        "zoom_speed":         1.15,
        "touch_hit_tol":      26.0,
        "mouse_hit_tol":      9.0,
        "long_press_ms":      500,
    },

    # ── 工作流 ────────────────────────────────────────
    "workflow": {
        "undo_limit":         100,
        "autosave_minutes":   0,       # 0 = 关闭
    },
}


# ═══════════════════════════════════════════════════════════
#  SettingsStore
# ═══════════════════════════════════════════════════════════

class SettingsStore(QObject):
    """每个 ``Document`` 持有一份。

    信号
    ----
    ``changed(str)``
        参数为点号分隔的键路径，例如 ``"effects.panel_toggle_ms"``。
        批量修改 / ``reset`` 时，按分类发射 ``"effects.*"`` 等。
        ``"*"`` 表示全部重置或全部重载。
    """

    changed = Signal(str)

    # ── 构造 ──────────────────────────────────────────

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._data: dict = _deep_copy(DEFAULTS)
        self._batch_depth: int = 0
        self._batch_dirty: set[str] = set()
        self._version: int = 0

    # ── 读取 ──────────────────────────────────────────

    def get(self, key: str, fallback: Any = None) -> Any:
        """按点号路径取值。

        Examples
        --------
        >>> s.get("effects.panel_toggle_ms")
        200
        >>> s.get("nonexistent.key", 42)
        42
        """
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return fallback
            node = node[part]
        return node

    # ── 写入 ──────────────────────────────────────────

    def set(self, key: str, value: Any) -> None:
        """按点号路径设值，自动创建缺失的中间层。"""
        parts = key.split(".")
        node = self._data
        for p in parts[:-1]:
            if p not in node or not isinstance(node[p], dict):
                node[p] = {}
            node = node[p]
        node[parts[-1]] = value

        if self._batch_depth > 0:
            self._batch_dirty.add(key)
        else:
            self._version += 1
            self.changed.emit(key)

    # ── 批量修改 ──────────────────────────────────────

    @contextmanager
    def batch(self) -> Generator[SettingsStore, None, None]:
        """上下文管理器：抑制逐条信号，退出时按分类统一发射。

        Usage::

            with doc.settings.batch():
                doc.settings.set("effects.enabled", False)
                doc.settings.set("effects.menu_fade", False)
            # 退出时仅发射一次 changed("effects.*")
        """
        self._batch_depth += 1
        try:
            yield self
        finally:
            self._batch_depth -= 1
            if self._batch_depth == 0 and self._batch_dirty:
                sections = {k.split(".")[0] for k in self._batch_dirty}
                self._batch_dirty = set()
                for sec in sorted(sections):
                    self.changed.emit(f"{sec}.*")

    # ── 序列化（由 Document.save / load 调用）────────

    def to_dict(self) -> dict:
        """返回当前设置的完整深拷贝（写入 ``.wgeo``）。"""
        return _deep_copy(self._data)

    def load_dict(self, saved: dict) -> None:
        """从 ``.wgeo`` 读取的字典 **深合并** 到当前值。

        仅覆盖文件中实际存在的键；缺失的键保持默认值。
        这保证旧版 ``.wgeo``（无 ``settings.json``）打开后行为不变。
        """
        if not isinstance(saved, dict):
            return
        _deep_merge(self._data, saved)
        self._version += 1
        self.changed.emit("*")

    # ── 重置 ──────────────────────────────────────────

    def reset(self) -> None:
        """恢复全部默认值。"""
        self._data = _deep_copy(DEFAULTS)
        self._version += 1
        self.changed.emit("*")

    def reset_section(self, section: str) -> None:
        """重置某一分类，如 ``reset_section("effects")``。"""
        if section in DEFAULTS:
            self._data[section] = _deep_copy(DEFAULTS[section])
            self._version += 1
            self.changed.emit(f"{section}.*")

    # ── 调试 ──────────────────────────────────────────
    @property
    def version(self) -> int:
        """单调递增的版本号，用于缓存失效（如背景缓存 key）。"""
        return self._version
    
    def __repr__(self) -> str:
        return f"<SettingsStore sections={list(self._data)}>"


# ═══════════════════════════════════════════════════════════
#  内部工具（模块私有，外部不得导入）
# ═══════════════════════════════════════════════════════════

def _deep_copy(d: dict) -> dict:
    """利用 JSON 往返实现深拷贝。

    所有值均为 JSON 基本类型（str/int/float/bool/list/dict），
    因此往返无损且比 ``copy.deepcopy`` 更快。
    """
    return json.loads(json.dumps(d))


def _deep_merge(base: dict, override: dict) -> None:
    """将 *override* 递归合并到 *base*（**就地修改** *base*）。

    - 两侧都是 ``dict`` → 递归合并
    - 否则 → *override* 的值直接覆盖
    - *base* 中不存在的新键 → 直接添加（前向兼容）
    """
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v

