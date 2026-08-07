"""脚本词法分析。"""

from .errors import ScriptError


KEYWORDS = {
    # 控制流
    "if": "if",
    "如果": "if",

    "elif": "elif",
    "否则如果": "elif",

    "else": "else",
    "否则": "else",

    "repeat": "repeat",
    "重复": "repeat",

    "for": "for",
    "遍历": "for",
    "对于": "for",

    "from": "from",
    "从": "from",

    "to": "to",
    "到": "to",

    # 函数
    "func": "func",
    "函数": "func",

    "return": "return",
    "返回": "return",

    # 导入
    "import": "import",
    "导入": "import",

    # 等待
    "wait": "wait",
    "等待": "wait",

    # 删除
    "delete": "delete",
    "删除": "delete",

    # 全局
    "global": "global",
    "全局": "global",

    # 布尔
    "true": "true",
    "真": "true",

    "false": "false",
    "假": "false",

    # 逻辑
    "and": "and",
    "并且": "and",
    "且": "and",

    "or": "or",
    "或者": "or",

    "not": "not",
    "非": "not",

    # 删除范围
    "all": "all",
    "所有": "all",

    "created_by_script": "created",
    "脚本创建": "created",
}


def tokenize(src):
    """返回 token 列表：(type, value, line)。"""

    tokens = []
    i = 0
    line = 1
    n = len(src)

    two_ops = {">=", "<=", "==", "!="}
    single_ops = set("+-*/%^<>")

    while i < n:
        ch = src[i]

        if ch == "\n":
            line += 1
            i += 1
            continue

        if ch.isspace():
            i += 1
            continue

        # 注释
        if ch == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue

        # 字符串
        if ch in ("\"", "'"):
            quote = ch
            i += 1
            buf = []

            while i < n and src[i] != quote:
                if src[i] == "\\" and i + 1 < n:
                    nxt = src[i + 1]

                    if nxt == "n":
                        buf.append("\n")
                    elif nxt == "t":
                        buf.append("\t")
                    else:
                        buf.append(nxt)

                    i += 2
                    continue

                if src[i] == "\n":
                    line += 1

                buf.append(src[i])
                i += 1

            if i >= n:
                raise ScriptError("字符串未闭合", line)

            i += 1
            tokens.append(("STR", "".join(buf), line))
            continue

        # 数字
        if ch.isdigit() or (ch == "." and i + 1 < n and src[i + 1].isdigit()):
            j = i
            dot = False

            while j < n and (src[j].isdigit() or (src[j] == "." and not dot)):
                if src[j] == ".":
                    dot = True
                j += 1

            text = src[i:j]

            try:
                value = float(text)
            except Exception:
                raise ScriptError(f"非法数字：{text}", line)

            tokens.append(("NUM", value, line))
            i = j
            continue

        # 标识符 / 关键字
        if ch.isalpha() or ch == "_":
            j = i + 1

            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1

            word = src[i:j]
            key = word.lower()

            if key in KEYWORDS:
                tokens.append(("KEY", KEYWORDS[key], line))
            else:
                tokens.append(("ID", word, line))

            i = j
            continue

        # 双字符运算符
        two = src[i:i + 2]
        if two in two_ops:
            tokens.append(("OP", two, line))
            i += 2
            continue

        # 单字符
        if ch == "{":
            tokens.append(("LBRACE", ch, line))
        elif ch == "}":
            tokens.append(("RBRACE", ch, line))
        elif ch == "(":
            tokens.append(("LPAREN", ch, line))
        elif ch == ")":
            tokens.append(("RPAREN", ch, line))
        elif ch == ",":
            tokens.append(("COMMA", ch, line))
        elif ch == ".":
            tokens.append(("DOT", ch, line))
        elif ch == "=":
            tokens.append(("ASSIGN", ch, line))
        elif ch in single_ops:
            tokens.append(("OP", ch, line))
        else:
            raise ScriptError(f"无法识别的字符：{ch}", line)

        i += 1

    tokens.append(("EOF", "", line))
    return tokens