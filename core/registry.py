"""三个注册表 + 工具面板归属。所有扩展都经过这里。"""
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
    for klass in type(obj).__mro__:
        if klass in RENDER_REGISTRY:
            return RENDER_REGISTRY[klass]
    return None


def register_tool(name: str, shortcut: Optional[str] = None, order: int = 100,
                  hint: str = "", icon: Optional[str] = None, panel: str = "rail"):
    """注册工具。
    panel="rail" → 左侧工具栏（核心工具）；
    panel="menu" → 菜单栏「工具」下拉菜单（plugins/ 插件工具）。"""
    def deco(cls):
        cls.tool_name = name
        cls.shortcut = shortcut
        cls.hint = hint
        cls.panel = panel
        TOOL_REGISTRY.append({"name": name, "shortcut": shortcut, "order": order,
                              "hint": hint, "icon": icon, "panel": panel, "cls": cls})
        TOOL_REGISTRY.sort(key=lambda d: d["order"])
        return cls
    return deco