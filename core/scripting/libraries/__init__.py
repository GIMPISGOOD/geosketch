"""内置库入口。"""

from .math_lib import build_math_lib
from .geo_lib import build_geo_lib
from .draw_lib import build_draw_lib
from .doc_lib import build_doc_lib


def get_builtin_library(name, interp):
    if name == "math":
        return build_math_lib(interp)

    if name == "geo":
        return build_geo_lib(interp)

    if name == "draw":
        return build_draw_lib(interp)

    if name == "doc":
        return build_doc_lib(interp)

    return None