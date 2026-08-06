"""GeoSketch 脚本解析器。

支持：
- repeat N {}
- for i from A to B {}
- if cond {} else if cond {} else {}
- local/global 变量赋值
- print(...)
- add point / segment / line / circle / polygon / text
- delete point / object
"""

from typing import Any, List, Optional, Tuple, Union
from .errors import ScriptError


# ------------------------------------------------------------
# 关键字
# ------------------------------------------------------------

KEYWORDS = {
    # 控制流
    "repeat": "repeat",
    "重复": "repeat",

    "for": "for",
    "遍历": "for",

    "from": "from",
    "从": "from",

    "to": "to",
    "到": "to",

    "if": "if",
    "如果": "if",

    "elif": "elif",
    "否则如果": "elif",

    "else": "else",
    "否则": "else",

    # 变量
    "global": "global",
    "全局": "global",

    "set": "set",
    "设置": "set",

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

    # 命令
    "add": "add",
    "新增": "add",
    "添加": "add",

    "delete": "delete",
    "删除": "delete",

    "print": "print",
    "打印": "print",

    # 图元
    "point": "point",
    "点": "point",

    "segment": "segment",
    "线段": "segment",

    "line": "line",
    "直线": "line",

    "circle": "circle",
    "圆": "circle",

    "polygon": "polygon",
    "多边形": "polygon",

    "text": "text",
    "文本": "text",

    # 介词
    "at": "at",
    "在": "at",

    "center": "center",
    "圆心": "center",

    "radius": "radius",
    "半径": "radius",

    "points": "points",
    "点集": "points",

    "object": "object",
    "对象": "object",
}


# ------------------------------------------------------------
# AST 节点
# ------------------------------------------------------------

class Node:
    line: int = 0


class Program(Node):
    def __init__(self, statements: List[Node]):
        self.statements = statements


class Repeat(Node):
    def __init__(self, count: Node, body: List[Node], line: int = 0):
        self.count = count
        self.body = body
        self.line = line


class ForRange(Node):
    def __init__(self, var: str, start: Node, end: Node, body: List[Node], line: int = 0):
        self.var = var
        self.start = start
        self.end = end
        self.body = body
        self.line = line


class If(Node):
    def __init__(self, branches: List[Tuple[Node, List[Node]]], else_body: Optional[List[Node]], line: int = 0):
        self.branches = branches
        self.else_body = else_body
        self.line = line


class Assign(Node):
    def __init__(self, name: str, expr: Node, scope: str = "local", line: int = 0):
        self.name = name
        self.expr = expr
        self.scope = scope
        self.line = line


class Print(Node):
    def __init__(self, expr: Optional[Node], line: int = 0):
        self.expr = expr
        self.line = line


class AddPoint(Node):
    def __init__(self, name: str, x: Node, y: Node, line: int = 0):
        self.name = name
        self.x = x
        self.y = y
        self.line = line


class AddSegment(Node):
    def __init__(self, name: str, a: str, b: str, line: int = 0):
        self.name = name
        self.a = a
        self.b = b
        self.line = line


class AddLine(Node):
    def __init__(self, name: str, a: str, b: str, line: int = 0):
        self.name = name
        self.a = a
        self.b = b
        self.line = line


class AddCircle(Node):
    def __init__(self, name: str, center: str, radius: Node, line: int = 0):
        self.name = name
        self.center = center
        self.radius = radius
        self.line = line


class AddPolygon(Node):
    def __init__(self, name: str, point_names: List[str], line: int = 0):
        self.name = name
        self.point_names = point_names
        self.line = line


class AddText(Node):
    def __init__(self, name: str, x: Node, y: Node, text_expr: Node, line: int = 0):
        self.name = name
        self.x = x
        self.y = y
        self.text_expr = text_expr
        self.line = line


class DeleteObject(Node):
    def __init__(self, name: str, line: int = 0):
        self.name = name
        self.line = line


# 表达式节点

class Num(Node):
    def __init__(self, value: float, line: int = 0):
        self.value = value
        self.line = line


class Str(Node):
    def __init__(self, value: str, line: int = 0):
        self.value = value
        self.line = line


class Bool(Node):
    def __init__(self, value: bool, line: int = 0):
        self.value = value
        self.line = line


class Var(Node):
    def __init__(self, name: str, line: int = 0):
        self.name = name
        self.line = line


class Bin(Node):
    def __init__(self, op: str, left: Node, right: Node, line: int = 0):
        self.op = op
        self.left = left
        self.right = right
        self.line = line


class Unary(Node):
    def __init__(self, op: str, operand: Node, line: int = 0):
        self.op = op
        self.operand = operand
        self.line = line


class Call(Node):
    def __init__(self, name: str, args: List[Node], line: int = 0):
        self.name = name
        self.args = args
        self.line = line


# ------------------------------------------------------------
# 词法分析
# ------------------------------------------------------------

def tokenize(src: str) -> List[Tuple[str, Any, int]]:
    tokens: List[Tuple[str, Any, int]] = []
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
                val = float(text)
            except Exception:
                raise ScriptError(f"非法数字：{text}", line)

            tokens.append(("NUM", val, line))
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
        elif ch == "=":
            tokens.append(("ASSIGN", ch, line))
        elif ch in single_ops:
            tokens.append(("OP", ch, line))
        else:
            raise ScriptError(f"无法识别的字符：{ch}", line)

        i += 1

    tokens.append(("EOF", "", line))
    return tokens


# ------------------------------------------------------------
# 语法分析
# ------------------------------------------------------------

class Parser:
    def __init__(self, tokens: List[Tuple[str, Any, int]]):
        self.toks = tokens
        self.i = 0

    # ---------- 基础 ----------

    def peek(self) -> Tuple[str, Any, int]:
        return self.toks[self.i]

    def advance(self) -> Tuple[str, Any, int]:
        t = self.toks[self.i]
        self.i += 1
        return t

    def at(self, ty: str, val: Optional[str] = None) -> bool:
        t = self.peek()
        if t[0] != ty:
            return False
        if val is not None and t[1] != val:
            return False
        return True

    def error(self, msg: str):
        t = self.peek()
        raise ScriptError(msg, t[2])

    def expect(self, ty: str, val: Optional[str] = None) -> Tuple[str, Any, int]:
        if not self.at(ty, val):
            t = self.peek()
            if val is None:
                self.error(f"期望 {ty}，实际得到 {t[0]}:{t[1]}")
            else:
                self.error(f"期望 {val}，实际得到 {t[1]}")
        return self.advance()

    def expect_key(self, key: str) -> Tuple[str, Any, int]:
        return self.expect("KEY", key)

    # ---------- 入口 ----------

    def parse_program(self) -> Program:
        stmts = []

        while not self.at("EOF"):
            stmts.append(self.parse_statement())

        return Program(stmts)

    # ---------- 语句 ----------

    def parse_statement(self) -> Node:
        t = self.peek()

        if t[0] == "KEY":
            key = t[1]

            if key == "repeat":
                return self.parse_repeat()

            if key == "for":
                return self.parse_for()

            if key == "if":
                return self.parse_if()

            if key == "global":
                return self.parse_global()

            if key == "set":
                return self.parse_set()

            if key == "print":
                return self.parse_print()

            if key == "add":
                return self.parse_add()

            if key == "delete":
                return self.parse_delete()

        if t[0] == "ID":
            nxt = self.toks[self.i + 1]
            if nxt[0] == "ASSIGN":
                return self.parse_assign(scope="local")

        self.error(f"无法识别的语句：{t[1]}")

    def parse_block(self) -> List[Node]:
        self.expect("LBRACE")
        stmts = []

        while not self.at("RBRACE") and not self.at("EOF"):
            stmts.append(self.parse_statement())

        self.expect("RBRACE")
        return stmts

    def parse_repeat(self) -> Repeat:
        line = self.peek()[2]
        self.expect_key("repeat")
        count = self.parse_expr()
        body = self.parse_block()

        return Repeat(count, body, line)

    def parse_for(self) -> ForRange:
        line = self.peek()[2]
        self.expect_key("for")

        var = self.expect("ID")[1]

        self.expect_key("from")
        start = self.parse_expr()

        self.expect_key("to")
        end = self.parse_expr()

        body = self.parse_block()

        return ForRange(var, start, end, body, line)

    def parse_if(self) -> If:
        line = self.peek()[2]
        branches = []

        self.expect_key("if")
        cond = self.parse_expr()
        body = self.parse_block()
        branches.append((cond, body))

        while self.at("KEY", "elif"):
            self.advance()
            cond = self.parse_expr()
            body = self.parse_block()
            branches.append((cond, body))

        else_body = None

        if self.at("KEY", "else"):
            self.advance()
            else_body = self.parse_block()

        return If(branches, else_body, line)

    def parse_global(self) -> Assign:
        line = self.peek()[2]
        self.expect_key("global")
        name = self.expect("ID")[1]
        self.expect("ASSIGN")
        expr = self.parse_expr()

        return Assign(name, expr, scope="global", line=line)

    def parse_set(self) -> Assign:
        line = self.peek()[2]
        self.expect_key("set")
        name = self.expect("ID")[1]
        self.expect("ASSIGN")
        expr = self.parse_expr()

        # set 也视为写全局变量
        return Assign(name, expr, scope="global", line=line)

    def parse_assign(self, scope: str = "local") -> Assign:
        line = self.peek()[2]
        name = self.expect("ID")[1]
        self.expect("ASSIGN")
        expr = self.parse_expr()

        return Assign(name, expr, scope=scope, line=line)

    def parse_print(self) -> Print:
        line = self.peek()[2]
        self.expect_key("print")

        expr = None

        if self.at("LPAREN"):
            self.advance()

            if not self.at("RPAREN"):
                expr = self.parse_expr()

            self.expect("RPAREN")
        else:
            expr = self.parse_expr()

        return Print(expr, line)

    # ---------- add 命令 ----------

    def parse_add(self) -> Node:
        line = self.peek()[2]
        self.expect_key("add")

        t = self.peek()

        if t[0] != "KEY":
            self.error("add 后需要指定对象类型：point/segment/line/circle/polygon/text")

        kind = t[1]

        if kind == "point":
            return self.parse_add_point(line)

        if kind == "segment":
            return self.parse_add_segment(line)

        if kind == "line":
            return self.parse_add_line(line)

        if kind == "circle":
            return self.parse_add_circle(line)

        if kind == "polygon":
            return self.parse_add_polygon(line)

        if kind == "text":
            return self.parse_add_text(line)

        self.error(f"暂不支持 add {kind}")

    def parse_add_point(self, line: int) -> AddPoint:
        self.expect_key("point")
        name = self.expect("ID")[1]
        self.expect_key("at")
        self.expect("LPAREN")
        x = self.parse_expr()
        self.expect("COMMA")
        y = self.parse_expr()
        self.expect("RPAREN")

        return AddPoint(name, x, y, line)

    def parse_add_segment(self, line: int) -> AddSegment:
        self.expect_key("segment")
        name = self.expect("ID")[1]
        self.expect_key("from")
        a = self.expect("ID")[1]
        self.expect_key("to")
        b = self.expect("ID")[1]

        return AddSegment(name, a, b, line)

    def parse_add_line(self, line: int) -> AddLine:
        self.expect_key("line")
        name = self.expect("ID")[1]
        self.expect_key("from")
        a = self.expect("ID")[1]
        self.expect_key("to")
        b = self.expect("ID")[1]

        return AddLine(name, a, b, line)

    def parse_add_circle(self, line: int) -> AddCircle:
        self.expect_key("circle")
        name = self.expect("ID")[1]
        self.expect_key("center")
        center = self.expect("ID")[1]
        self.expect_key("radius")
        radius = self.parse_expr()

        return AddCircle(name, center, radius, line)

    def parse_add_polygon(self, line: int) -> AddPolygon:
        self.expect_key("polygon")
        name = self.expect("ID")[1]
        self.expect_key("points")

        names = [self.expect("ID")[1]]

        while self.at("COMMA"):
            self.advance()
            names.append(self.expect("ID")[1])

        return AddPolygon(name, names, line)

    def parse_add_text(self, line: int) -> AddText:
        self.expect_key("text")
        name = self.expect("ID")[1]
        self.expect_key("at")
        self.expect("LPAREN")
        x = self.parse_expr()
        self.expect("COMMA")
        y = self.parse_expr()
        self.expect("RPAREN")

        text_expr = self.parse_expr()

        return AddText(name, x, y, text_expr, line)

    # ---------- delete ----------

    def parse_delete(self) -> DeleteObject:
        line = self.peek()[2]
        self.expect_key("delete")

        # delete point P / delete object P / delete P 都允许
        if self.at("KEY", "point") or self.at("KEY", "object"):
            self.advance()

        name = self.expect("ID")[1]

        return DeleteObject(name, line)

    # ---------- 表达式 ----------

    def parse_expr(self) -> Node:
        return self.parse_or()

    def parse_or(self) -> Node:
        left = self.parse_and()

        while self.at("KEY", "or"):
            line = self.peek()[2]
            self.advance()
            right = self.parse_and()
            left = Bin("or", left, right, line)

        return left

    def parse_and(self) -> Node:
        left = self.parse_not()

        while self.at("KEY", "and"):
            line = self.peek()[2]
            self.advance()
            right = self.parse_not()
            left = Bin("and", left, right, line)

        return left

    def parse_not(self) -> Node:
        if self.at("KEY", "not"):
            line = self.peek()[2]
            self.advance()
            return Unary("not", self.parse_not(), line)

        return self.parse_comparison()

    def parse_comparison(self) -> Node:
        left = self.parse_add()

        while self.at("OP") and self.peek()[1] in (">", "<", ">=", "<=", "==", "!="):
            op = self.advance()[1]
            right = self.parse_add()
            left = Bin(op, left, right, left.line)

        return left

    def parse_add(self) -> Node:
        left = self.parse_mul()

        while self.at("OP") and self.peek()[1] in ("+", "-"):
            op = self.advance()[1]
            right = self.parse_mul()
            left = Bin(op, left, right, left.line)

        return left

    def parse_mul(self) -> Node:
        left = self.parse_power()

        while self.at("OP") and self.peek()[1] in ("*", "/", "%"):
            op = self.advance()[1]
            right = self.parse_power()
            left = Bin(op, left, right, left.line)

        return left

    def parse_power(self) -> Node:
        left = self.parse_unary()

        if self.at("OP", "^"):
            line = self.peek()[2]
            self.advance()
            right = self.parse_power()
            return Bin("^", left, right, line)

        return left

    def parse_unary(self) -> Node:
        if self.at("OP") and self.peek()[1] in ("+", "-"):
            op = self.advance()[1]
            return Unary(op, self.parse_unary(), self.peek()[2])

        return self.parse_primary()

    def parse_primary(self) -> Node:
        t = self.peek()

        if t[0] == "NUM":
            self.advance()
            return Num(t[1], t[2])

        if t[0] == "STR":
            self.advance()
            return Str(t[1], t[2])

        if t[0] == "KEY" and t[1] == "true":
            self.advance()
            return Bool(True, t[2])

        if t[0] == "KEY" and t[1] == "false":
            self.advance()
            return Bool(False, t[2])

        if t[0] == "ID":
            name = self.advance()[1]

            # 支持 sin(x), sqrt(x) 等数学函数
            if self.at("LPAREN"):
                self.advance()
                args = []

                if not self.at("RPAREN"):
                    args.append(self.parse_expr())

                    while self.at("COMMA"):
                        self.advance()
                        args.append(self.parse_expr())

                self.expect("RPAREN")
                return Call(name, args, t[2])

            return Var(name, t[2])

        if t[0] == "LPAREN":
            self.advance()
            expr = self.parse_expr()
            self.expect("RPAREN")
            return expr

        self.error(f"非法表达式：{t[1]}")


def parse(src: str) -> Program:
    tokens = tokenize(src)
    return Parser(tokens).parse_program()