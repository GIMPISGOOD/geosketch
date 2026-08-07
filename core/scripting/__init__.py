"""GeoSketch 脚本系统入口。"""

from .errors import ScriptError
from .parser import parse
from .interpreter import Interpreter


class _ParseErrorResult:
    def __init__(self, error):
        self.error = error
        self.logs = []


def register_script_library(doc, name, source):
    """注册用户脚本库。

    示例：
        register_script_library(doc, "mylib", '''
        func double(x) {
            return x * 2
        }
        ''')
    """

    if not hasattr(doc, "script_libs"):
        doc.script_libs = {}

    doc.script_libs[name] = source


def run_script(doc, script, owner_id=None, canvas=None):
    """执行一段脚本。"""

    try:
        program = parse(script)

    except ScriptError as e:
        if canvas is not None and hasattr(canvas, "cursor_info"):
            canvas.cursor_info.emit(f"脚本错误：{e}")

        return _ParseErrorResult(e)

    interp = Interpreter(doc, canvas=canvas, owner_id=owner_id)
    interp.run(program)

    if interp.error is not None:
        if canvas is not None and hasattr(canvas, "cursor_info"):
            canvas.cursor_info.emit(f"脚本错误：{interp.error}")

    else:
        if interp.logs and canvas is not None and hasattr(canvas, "cursor_info"):
            canvas.cursor_info.emit(" | ".join(interp.logs))

    return interp