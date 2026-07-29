"""数学字体加载：优先随包的 STIX Two Math，逐级回退系统数学/衬线字体。"""
import os

from PySide6.QtGui import QFont, QFontDatabase

_MATH_FAMILY = None
_CJK_FAMILY = None


def _try_load_bundled():
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.join(here, "..", "..", "resources", "fonts")
    for name in ("STIXTwoMath-Regular.otf", "STIXTwoMath-Regular.ttf",
                 "latinmodern-math.otf", "XITSMath-Regular.otf"):
        path = os.path.join(root, name)
        if os.path.exists(path):
            fid = QFontDatabase.addApplicationFont(path)
            if fid != -1:
                fams = QFontDatabase.applicationFontFamilies(fid)
                if fams:
                    return fams[0]
    return None


def _init():
    global _MATH_FAMILY, _CJK_FAMILY
    if _MATH_FAMILY is not None:
        return
    _MATH_FAMILY = _try_load_bundled()
    if _MATH_FAMILY is None:
        db = QFontDatabase()
        avail = set(db.families())
        for name in ("STIX Two Math", "Cambria Math", "XITS Math",
                     "Latin Modern Math", "Times New Roman"):
            if name in avail:
                _MATH_FAMILY = name
                break
        else:
            _MATH_FAMILY = "serif"
    _CJK_FAMILY = "Microsoft YaHei"


def math_font(size_px, italic=False, cjk=False):
    """取数学字体；CJK 字符强制正立（避免合成斜体发虚）。"""
    _init()
    f = QFont()
    if cjk:
        f.setFamilies([_CJK_FAMILY, _MATH_FAMILY])
        f.setItalic(False)
    else:
        f.setFamilies([_MATH_FAMILY, _CJK_FAMILY])
        f.setItalic(italic)
    f.setPixelSize(max(6, int(round(size_px))))
    return f


def family_name():
    _init()
    return _MATH_FAMILY