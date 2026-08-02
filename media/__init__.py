"""媒体对象包：图像 / 表格 / 图表。自动扫描子模块触发注册。"""
import pkgutil
import os

_pkg_dir = os.path.dirname(__file__)
for _info in pkgutil.iter_modules([_pkg_dir]):
    __import__(f"{__name__}.{_info.name}")