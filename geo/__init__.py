# geo/__init__.py
"""几何对象库。
新增对象：在本目录新建 .py 文件，用 @register_geo + @register_renderer 即可，
无需修改任何其他文件——下面会自动导入并触发注册。
"""
import importlib
import pkgutil

from geo import base          # noqa: F401  显式先行，确保基类永远最先就绪

for _m in pkgutil.iter_modules(__path__):
    if _m.name != "base":     # 跳过已导入的 base
        importlib.import_module(f"{__name__}.{_m.name}")