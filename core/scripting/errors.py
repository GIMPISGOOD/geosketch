"""脚本错误类型。"""


class ScriptError(Exception):
    """脚本错误：带行号。"""

    def __init__(self, message, line=None):
        if line is not None:
            message = f"第 {line} 行：{message}"

        super().__init__(message)
        self.line = line


class ScriptReturn(Exception):
    """函数 return 控制流。"""

    def __init__(self, value=None):
        super().__init__("script return")
        self.value = value