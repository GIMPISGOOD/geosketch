"""几何对象库。
新增对象：在本目录新建 .py 文件，用 @register_geo + @register_renderer 即可，
无需修改任何其他文件——下面的循环会自动导入并触发注册。
"""
import importlib
import pkgutil

for _m in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_m.name}")