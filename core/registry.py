"""三个注册表，全部扩展都经过这里（本版新增 icon 参数）：

  GEO_REGISTRY     类型名 → 几何对象类      （存盘/读盘时按名字重建）
  RENDER_REGISTRY  几何对象类 → 绘制函数    （沿 MRO 查找，子类可复用父类画法）
  TOOL_REGISTRY    工具规格列表             （左侧工具栏按 order 自动生成）
"""
from __future__ import annotations

from typing import Any, Callable, Optional

GEO_REGISTRY: dict[str, type] = {}
RENDER_REGISTRY: dict[type, Callable] = {}
TOOL_REGISTRY: list[dict[str, Any]] = []


def register_geo(type_name: str):
    def deco(cls):
        cls.type_name = type_name
        GEO_REGISTRY[type_name] = cls
        return cls
    return deco


def register_renderer(cls):
    def deco(fn):
        RENDER_REGISTRY[cls] = fn
        return fn
    return deco


def find_renderer(obj) -> Optional[Callable]:
    """沿 MRO 查找渲染器；找不到返回 None（调用方必须判空）。"""
    for klass in type(obj).__mro__:
        if klass in RENDER_REGISTRY:
            return RENDER_REGISTRY[klass]
    return None


def register_tool(name: str, shortcut: Optional[str] = None, order: int = 100,
                  hint: str = "", icon: Optional[Callable] = None):
    """注册工具。icon 为 (QPainter, QRectF, QColor) -> None 的绘制函数。"""
    def deco(cls):
        cls.tool_name = name
        cls.shortcut = shortcut
        cls.hint = hint
        TOOL_REGISTRY.append({"name": name, "shortcut": shortcut, "order": order,
                              "hint": hint, "icon": icon, "cls": cls})
        TOOL_REGISTRY.sort(key=lambda d: d["order"])
        return cls
    return deco