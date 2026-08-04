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
_FUNCS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "arcsin": math.asin,
    "arccos": math.acos,
    "arctan": math.atan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "sqrt": math.sqrt,
    "abs": abs,
    "ln": math.log,
    "log": math.log10,
    "exp": math.exp,
    "cot": lambda x: 1.0 / math.tan(x),
    "sec": lambda x: 1.0 / math.cos(x),
    "csc": lambda x: 1.0 / math.sin(x),
}

FUNCS = dict(_FUNCS)
CONSTS = {"pi": math.pi, "π": math.pi, "e": math.e}
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
    __slots__ = ("name", "value", "vmin", "vmax", "expr")

    def __init__(self, name, value=1.0, vmin=0.0, vmax=10.0, expr=""):
        self.name = name
        self.value = float(value)
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        self.expr = expr          # ★ 从动表达式（非空则为从动变量）

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

    def define(self, name, value, vmin, vmax, expr=""):
        self._vars[name] = Variable(name, value, vmin, vmax, expr)
        self.version += 1
        self.changed.emit()

    def set(self, name, value):
        v = self._vars.get(name)
        if v and not v.expr and v.value != float(value):  # 从动变量不可手动改值
            v.value = float(value)
            self.version += 1
            self.changed.emit()

    def set_expr(self, name, expr):
        v = self._vars.get(name)
        if v:
            v.expr = expr
            self.version += 1
            self.changed.emit()

    def delete(self, name):
        if name in self._vars:
            del self._vars[name]
            self.version += 1
            self.changed.emit()

    def as_dict(self):
        """返回所有变量的当前值（自动计算从动变量）。"""
        d = {}
        # 1. 先收集独立变量
        for n, v in self._vars.items():
            if not v.expr:
                d[n] = v.value
        
        # 2. 迭代计算从动变量（支持多级依赖，如 c=b*2, b=a+1）
        changed = True
        max_iter = 10
        while changed and max_iter > 0:
            changed = False
            max_iter -= 1
            for n, v in self._vars.items():
                if v.expr:
                    val = evaluate(v.expr, d)
                    if val is not None and d.get(n) != val:
                        d[n] = val
                        changed = True
        return d

    def evaluate(self, expr):
        return evaluate(expr, self.as_dict())
    
    def set_range(self, name, vmin, vmax):
        """修改变量滑杆范围，并把当前值夹回合法区间。"""
        v = self._vars.get(name)
        if not v:
            return

        vmin = float(vmin)
        vmax = float(vmax)
        if vmin > vmax:
            vmin, vmax = vmax, vmin

        v.vmin = vmin
        v.vmax = vmax
        v.value = min(max(v.value, v.vmin), v.vmax)

        self.version += 1
        self.changed.emit()

    def to_dict(self):
        """序列化变量，便于保存到 .wgeo 文件。"""
        return {
            name: {
                "value": v.value,
                "vmin": v.vmin,
                "vmax": v.vmax,
                "expr": v.expr,
            }
            for name, v in self._vars.items()
        }

    def load_dict(self, data):
        """从字典恢复变量。会清空当前变量。"""
        self._vars.clear()

        for name, d in data.items():
            self._vars[name] = Variable(
                name,
                d.get("value", 0.0),
                d.get("vmin", 0.0),
                d.get("vmax", 10.0),
                d.get("expr", ""),
            )

        self.version += 1
        self.changed.emit()


_STORE = VariableStore()          # 模块级单例，避免跨层传递


def get_store():
    return _STORE


def eval_expr(expr):
    return _STORE.evaluate(expr)

def render_template(text: str) -> str:
    """把文本中的 {表达式} 替换为表达式求值结果。

    例如：
        "(a的值为{a})"

    如果 a = 3，则返回：
        "(a的值为3)"

    求值失败时保留原样。
    """
    if not isinstance(text, str):
        return str(text)

    if "{" not in text or "}" not in text:
        return text

    def _fmt(v: float) -> str:
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.3f}"

    def _replace(m):
        expr = m.group(1).strip()
        if not expr:
            return m.group(0)

        val = eval_expr(expr)
        if val is None:
            return m.group(0)

        return _fmt(val)

    return re.sub(r"\{([^{}]+)\}", _replace, text)