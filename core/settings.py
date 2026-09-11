"""应用偏好设置：数据模型、默认值与运行时存取。

设计原则
────────
• 默认值硬编码在本文件的  `DEFAULTS`  字典中（不读外部文件）。
• 持久化由  `Document.save`  /  `Document.load`  负责
  （写入  `.wgeo`  ZIP 内的  `settings.json`  条目）。
• 本模块  不做任何文件 I/O 。
• 每个  `Document`  持有一个独立的  `SettingsStore`  实例。

对外契约（其他文件依赖下列名字，重构不得改动）
──────────────────────────────────────────────
DEFAULTS · SettingsStore
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from typing import Any, Generator

from PySide6.QtCore import QObject, Signal


# ════════════════════════════════════════════════════════════
#  默认值（硬编码，不依赖外部文件）
#  所有值必须是 JSON 可序列化的基本类型：
#  str / int / float / bool / list / dict
# ════════════════════════════════════════════════════════════

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
        "autosave_minutes":   0,
    },
    # ── AI 辅助 ───────────────────────────────────────
    "ai": {
        "enabled":          False,
        "provider":         "local",
        "model_dir":        "models",
        "model_file":       "",
        "api_url":          "",
        "api_key":          "",
        "api_model":        "",
        "system_prompt":    (
            "你是 GeoSketch 几何画板的 DSL 代码生成器。"
            "严格遵守以下规则，违反任何一条都是错误：\n"
            "\n"
            "【输出格式】\n"
            "- 只输出纯 GeoSketch DSL 代码，第一行就是语句。\n"
            "- 禁止输出 ```、```geo、```python 或任何 Markdown 代码块标记。\n"
            "- 禁止输出自然语言解释、注释、引导语。\n"
            "- 禁止使用 Python 语法（import/def/class/lambda）。\n"
            "\n"
            "【DSL 语法】\n"
            "赋值：名称 = 函数(参数)\n"
            "point(x, y)  创建点\n"
            "segment(A, B)  创建线段\n"
            "line(A, B)  创建直线\n"
            "ray(A, B)  创建射线\n"
            "circle(圆心, 圆周点) 或 circle(圆心, 半径数值)  创建圆\n"
            "ellipse(中心, 轴A, 轴B)  创建椭圆\n"
            "regular_polygon(中心, 顶点, 边数)  创建正多边形\n"
            "polygon(P1, P2, P3, ...)  创建多边形填充\n"
            "midpoint(A, B)  中点\n"
            "division_point(A, B, t)  等分点(0<=t<=1)\n"
            "intersect(对象1, 对象2)  交点\n"
            "text(x, y, \"内容\")  文本\n"
            "function(\"y=f(x)\")  函数曲线\n"
            "parametric(\"x(t)\", \"y(t)\")  参数曲线\n"
            "polar(\"r(t)\")  极坐标曲线\n"
            "perp_line(参照线, 点)  垂线\n"
            "parallel_line(参照线, 点)  平行线\n"
            "angle_bisector(顶点, P1, P2)  角平分线\n"
            "perp_bisector(A, B)  中垂线\n"
            "three_point_circle(P1, P2, P3)  过三点圆\n"
            "incenter(A, B, C)  内心\n"
            "centroid(A, B, C)  重心\n"
            "cubic_bezier(P0, P1, P2, P3)  贝塞尔曲线\n"
            "angle_measure(顶点, P1, P2)  角度度量\n"
            "point_on_object(宿主, t)  吸附点(0<=t<=1)\n"
            "\n"
            "【数学函数（无需import）】\n"
            "sin cos tan sqrt abs ln log exp floor ceil round min max pi e\n"
            "\n"
            "【属性访问】\n"
            "点.x  点.y  线段.length()  圆.r\n"
            "\n"
            "【控制流】\n"
            "if 条件 { ... }\n"
            "for i from 0 to n { ... }\n"
            "func 名称(参数) { ... return 值 }\n"
            "\n"
            "【特殊标志】\n"
            "__keep = true  放在脚本开头，保留创建的对象\n"
            "\n"
            "【示例1】用户：画一个等边三角形，边长为5\n"
            "__keep = true\n"
            "A = point(0, 0)\n"
            "B = point(5, 0)\n"
            "C = point(2.5, 5 * sqrt(3) / 2)\n"
            "AB = segment(A, B)\n"
            "BC = segment(B, C)\n"
            "CA = segment(C, A)\n"
            "\n"
            "【示例2】用户：画圆心在原点半径为3的圆，再作一条切线\n"
            "__keep = true\n"
            "O = point(0, 0)\n"
            "P = point(3, 0)\n"
            "c = circle(O, P)\n"
            "T = point_on_object(c, 0)\n"
            "tangent = perp_line(c, T)\n"
        ),
        "usage":            "both",
        "max_tokens":       256,
        "temperature":      0.2,
        "context_tokens":   2048,
        "timeout_ms":       5000,
    },
    # ── 物理扩展 ─────────────────────────────────────
    "physics": {
        "optics_enabled": False,
        "optics_max_reflections": 16,
        "optics_mirror_double_sided": True,
        "optics_show_arrows": True,
    },
}


# ════════════════════════════════════════════════════════════
#  SettingsStore
# ════════════════════════════════════════════════════════════

class SettingsStore(QObject):
    """每个 `Document` 持有一份。

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
        node: Any = self._data
        for part in key.split("."):
            if not isinstance(node, dict) or part not in node:
                return fallback
            node = node[part]
        return node

    # ── 写入 ──────────────────────────────────────────
    def set(self, key: str, value: Any) -> None:
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
        return _deep_copy(self._data)

    def load_dict(self, saved: dict) -> None:
        if not isinstance(saved, dict):
            return
        _deep_merge(self._data, saved)
        self._version += 1
        self.changed.emit("*")

    # ── 重置 ──────────────────────────────────────────
    def reset(self) -> None:
        self._data = _deep_copy(DEFAULTS)
        self._version += 1
        self.changed.emit("*")

    def reset_section(self, section: str) -> None:
        if section in DEFAULTS:
            self._data[section] = _deep_copy(DEFAULTS[section])
            self._version += 1
            self.changed.emit(f"{section}.*")

    # ── 调试 ──────────────────────────────────────────
    @property
    def version(self) -> int:
        return self._version

    def __repr__(self) -> str:
        return f"<SettingsStore sections={list(self._data)}>"


# ════════════════════════════════════════════════════════════
#  内部工具（模块私有，外部不得导入）
# ════════════════════════════════════════════════════════════

def _deep_copy(d: dict) -> dict:
    return json.loads(json.dumps(d))


def _deep_merge(base: dict, override: dict) -> None:
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v