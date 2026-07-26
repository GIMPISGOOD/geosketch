"""扩展插件库：把新功能写成本目录下的一个 .py 文件即可。

文件内的几何对象、渲染器、工具（panel="top"）会在导入时自动注册，
顶部工具栏与主窗口无需任何改动。下面的循环负责自动发现与导入。
"""
import importlib
import pkgutil

for _m in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_m.name}")