"""脚本 AST 节点。"""


class Node:
    line = 0


# ------------------------------------------------------------
# 程序结构
# ------------------------------------------------------------

class Program(Node):
    def __init__(self, statements):
        self.statements = statements


class Import(Node):
    def __init__(self, name, line=0):
        self.name = name
        self.line = line


class GlobalAssign(Node):
    def __init__(self, name, expr, line=0):
        self.name = name
        self.expr = expr
        self.line = line


class Assign(Node):
    def __init__(self, name, expr, line=0):
        self.name = name
        self.expr = expr
        self.line = line


class FuncDef(Node):
    def __init__(self, name, params, body, line=0):
        self.name = name
        self.params = params
        self.body = body
        self.line = line


class Param(Node):
    def __init__(self, name, default=None, line=0):
        self.name = name
        self.default = default
        self.line = line


class Return(Node):
    def __init__(self, expr=None, line=0):
        self.expr = expr
        self.line = line


class If(Node):
    def __init__(self, branches, else_body=None, line=0):
        self.branches = branches
        self.else_body = else_body
        self.line = line


class Repeat(Node):
    def __init__(self, count, body, line=0):
        self.count = count
        self.body = body
        self.line = line


class ForRange(Node):
    def __init__(self, var, start, end, body, line=0):
        self.var = var
        self.start = start
        self.end = end
        self.body = body
        self.line = line


class Wait(Node):
    def __init__(self, expr, line=0):
        self.expr = expr
        self.line = line


class DeleteAll(Node):
    """target: all / points / circles / created"""

    def __init__(self, target, line=0):
        self.target = target
        self.line = line


class DeleteExpr(Node):
    def __init__(self, expr, line=0):
        self.expr = expr
        self.line = line


class ExprStmt(Node):
    def __init__(self, expr, line=0):
        self.expr = expr
        self.line = line


# ------------------------------------------------------------
# 表达式
# ------------------------------------------------------------

class Num(Node):
    def __init__(self, value, line=0):
        self.value = value
        self.line = line


class Str(Node):
    def __init__(self, value, line=0):
        self.value = value
        self.line = line


class Bool(Node):
    def __init__(self, value, line=0):
        self.value = value
        self.line = line


class Var(Node):
    def __init__(self, name, line=0):
        self.name = name
        self.line = line


class Member(Node):
    def __init__(self, obj, name, line=0):
        self.obj = obj
        self.name = name
        self.line = line


class Call(Node):
    def __init__(self, callee, args, line=0):
        self.callee = callee
        self.args = args
        self.line = line


class Bin(Node):
    def __init__(self, op, left, right, line=0):
        self.op = op
        self.left = left
        self.right = right
        self.line = line


class Unary(Node):
    def __init__(self, op, operand, line=0):
        self.op = op
        self.operand = operand
        self.line = line