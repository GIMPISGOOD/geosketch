"""变量系统（抽离为独立模块）：安全表达式求值 + 变量存储。
表达式支持 + - * / ^（乘方）%、括号、隐式乘法（2a / 2边长）、
函数 sqrt/abs/sin/cos/tan、常量 pi/e；变量名支持任意 UTF-8 标识符（中文等）。"""
import ast
import keyword
import math
import operator
import re

from PySide6.QtCore import QObject, Signal

_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}
FUNCS = {"sqrt": math.sqrt, "abs": abs, "sin": math.sin,
         "cos": math.cos, "tan": math.tan}
CONSTS = {"pi": math.pi, "e": math.e}
RESERVED = set(FUNCS) | set(CONSTS)


def is_valid_name(name):
    """变量名校验：任意 UTF-8 标识符（中文/希腊字母等），
    但不能含空格/运算符，且不能是关键字或 pi/e/sqrt 等保留名。"""
    name = name.strip()
    return (bool(name) and name.isidentifier()
            and not keyword.iskeyword(name) and name not in RESERVED)


def _preprocess(expr):
    s = expr.replace("^", "**")
    s = re.sub(r"(\d)([^\W\d_])", r"\1*\2", s)   # 2a / 2边长 → 2*a / 2*边长
    s = re.sub(r"(\d)\(", r"\1*(", s)             # 2( → 2*(
    s = re.sub(r"\)(\d)", r")*\1", s)             # )2 → )*2
    s = re.sub(r"\)\(", r")*(", s)                # )( → )*(
    s = re.sub(r"\)([^\W\d_])", r")*\1", s)       # )a → )*a
    return s


def _eval(node, vars):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in vars:
            return float(vars[node.id])
        if node.id in CONSTS:
            return CONSTS[node.id]
        raise ValueError(f"未定义变量: {node.id}")
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.left, vars), _eval(node.right, vars))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _OPS:
        return _OPS[type(node.op)](_eval(node.operand, vars))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
            and node.func.id in FUNCS:
        return FUNCS[node.func.id](*[_eval(a, vars) for a in node.args])
    raise ValueError("不支持的语法")


def evaluate(expr, variables):
    """安全求值（AST 白名单，绝不执行任意代码）；非法返回 None。"""
    try:
        return _eval(ast.parse(_preprocess(expr), mode="eval").body, variables)
    except Exception:
        return None


class Variable:
    __slots__ = ("name", "value", "vmin", "vmax")

    def __init__(self, name, value=1.0, vmin=0.0, vmax=10.0):
        self.name = name
        self.value = float(value)
        self.vmin = float(vmin)
        self.vmax = float(vmax)


class VariableStore(QObject):
    changed = Signal()

    def __init__(self):
        super().__init__()
        self._vars = {}
        self.version = 0

    def names(self):
        return sorted(self._vars)

    def get_var(self, name):
        return self._vars.get(name)

    def define(self, name, value, vmin, vmax):
        self._vars[name] = Variable(name, value, vmin, vmax)
        self.version += 1
        self.changed.emit()

    def set(self, name, value):
        v = self._vars.get(name)
        if v and v.value != float(value):
            v.value = float(value)
            self.version += 1
            self.changed.emit()

    def set_range(self, name, vmin, vmax):
        """修改变量的滑杆范围，并把当前值收敛回新范围。"""
        v = self._vars.get(name)
        if v is None:
            return
        v.vmin, v.vmax = float(vmin), float(vmax)
        v.value = min(max(v.value, v.vmin), v.vmax)   # 防止当前值越界
        self.version += 1
        self.changed.emit()

    def delete(self, name):
        if name in self._vars:
            del self._vars[name]
            self.version += 1
            self.changed.emit()

    def as_dict(self):
        return {n: v.value for n, v in self._vars.items()}

    def evaluate(self, expr):
        return evaluate(expr, self.as_dict())


_STORE = VariableStore()          # 模块级单例，避免跨层传递


def get_store():
    return _STORE


def eval_expr(expr):
    return _STORE.evaluate(expr)