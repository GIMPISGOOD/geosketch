"""变换模块：平移 / 旋转 / 缩放 / 反射 / 中心对称 / 仿射 / 反演 / 迭代。

在本目录新建 .py 文件会自动导入并注册。
"""

import importlib
import pkgutil

for _m in pkgutil.iter_modules(__path__):
    importlib.import_module(f"{__name__}.{_m.name}")