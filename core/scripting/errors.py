class ScriptError(Exception):
    """脚本错误：带行号。"""

    def __init__(self, message, line=None):
        if line is not None:
            message = f"第 {line} 行：{message}"
        super().__init__(message)
        self.line = line