"""变量系统（抽离为独立模块）：安全表达式求值 + 变量存储。
表达式支持 + - * / ^（乘方）%、括号、隐式乘法（2a / 2边长）、
函数 sqrt/abs/sin/cos/tan、常量 pi/e；变量名支持任意 UTF-8 标识符（中文等）。"""
import ast
import keyword
import math
import operator
import re
from typing import Optional

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

_FUNCS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "sqrt": math.sqrt, "abs": abs, "ln": math.log, "log": math.log10,
    "exp": math.exp,
    "cot": lambda x: 1.0 / math.tan(x),
    "sec": lambda x: 1.0 / math.cos(x),
    "csc": lambda x: 1.0 / math.sin(x),
}
_FUNC_NAMES = set(_FUNCS)

_NUM = r"\d+\.?\d*|\.\d+"
_IDENT = r"[^\W\d_]\w*"
_TOKEN_RE = re.compile(rf"{_NUM}|{_IDENT}|\*\*|[+\-*/()=,]|[^\s]")


def _is_value_end(tok):
    """token 能否作为乘法左操作数：数字 / 右括号 / 非函数名标识符。"""
    if re.fullmatch(_NUM, tok) or tok == ")":
        return True
    if re.fullmatch(_IDENT, tok):
        return tok not in _FUNC_NAMES
    return False


def _is_value_start(tok):
    """token 能否作为乘法右操作数：数字 / 标识符 / 左括号。"""
    return bool(re.fullmatch(_NUM, tok) or re.fullmatch(_IDENT, tok) or tok == "(")


def _preprocess(expr):
    """词法级隐式乘法补全：2x→2*x、x(x+1)→x*(x+1)、(a)(b)→(a)*(b)，
    但 sin(x) 保持函数调用不拆。逐 token 判断，杜绝正则子串误伤。"""
    toks = _TOKEN_RE.findall(expr.replace("^", "**").replace(" ", ""))
    out = []
    for i, tok in enumerate(toks):
        out.append(tok)
        if i + 1 < len(toks):
            nxt = toks[i + 1]
            if tok in _FUNC_NAMES and nxt == "(":
                continue                        # 函数应用，不补 *
            if _is_value_end(tok) and _is_value_start(nxt):
                out.append("*")
    return "".join(out)

def _eval(node: ast.AST, vars: dict[str, float]) -> float:
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


def evaluate(expr: str, variables: dict[str, float]) -> Optional[float]:
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

    def as_dict(self) -> dict[str, float]:
        return {n: v.value for n, v in self._vars.items()}

    def evaluate(self, expr: str) -> Optional[float]:
        return evaluate(expr, self.as_dict())


_STORE = VariableStore()          # 模块级单例，避免跨层传递


def get_store():
    return _STORE


def eval_expr(expr):
    return _STORE.evaluate(expr)