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
    # 基础三角
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "cot": lambda x: 1.0 / math.tan(x),
    "sec": lambda x: 1.0 / math.cos(x),
    "csc": lambda x: 1.0 / math.sin(x),
    # 反三角 (arcsin 与 asin 互为别名)
    "arcsin": math.asin, "arccos": math.acos, "arctan": math.atan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    # 双曲函数
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    # 指数与对数
    "sqrt": math.sqrt, "abs": abs, "ln": math.log, "log": math.log10, "exp": math.exp,
    # 取整与符号
    "floor": math.floor, "ceil": math.ceil, "round": round,
    "sign": lambda x: (x > 0) - (x < 0),  # 符号函数：返回 -1, 0, 1
    # 极值
    "min": min, "max": max,
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
    __slots__ = ("name", "value", "vmin", "vmax", "expr", "step", "binding")
    def __init__(self, name, value=1.0, vmin=0.0, vmax=10.0, expr="", step=0.1, binding=None):
        self.name = name
        self.value = float(value)
        self.vmin = float(vmin)
        self.vmax = float(vmax)
        self.expr = expr
        self.step = float(step) if step and step > 1e-9 else 0.1
        self.binding = binding  # {"obj_id": int, "metric": str} 或 None  
        # ★ 从动表达式（非空则为从动变量）
        
# ================= 度量绑定辅助 =================

def _finite_float(value):
    try:
        value = float(value)
    except Exception:
        return None
    if not math.isfinite(value):
        return None
    return value
def point_label(pt):
    if pt is None:
        return "?"
    label = getattr(pt, "name", "") or getattr(pt, "_auto_label", "")
    if label:
        return str(label)
    return f"P{getattr(pt, 'id', 0)}"


def object_display_name(obj):
    if obj is None:
        return "对象"

    tn = type(obj).__name__

    try:
        if tn == "Segment":
            return f"线段{point_label(obj.a)}{point_label(obj.b)}"

        if tn == "Line":
            return f"直线{point_label(obj.a)}{point_label(obj.b)}"

        if tn == "Ray":
            return f"射线{point_label(obj.origin)}{point_label(obj.through)}"

        if tn in ("Circle", "ExprCircle", "InvertedCircle"):
            c = getattr(obj, "center", None)
            if c is None:
                return "圆"
            return f"圆{point_label(c)}"

        if tn == "ThreePointCircle":
            return f"圆{point_label(obj.p1)}{point_label(obj.p2)}{point_label(obj.p3)}"

        if tn == "Ellipse":
            return f"椭圆{point_label(obj.center)}"

        if tn == "RegularPolygon":
            return f"正{obj.n}边形{point_label(obj.center)}"

        if tn == "AngleMeasure":
            return f"角{point_label(obj.p1)}{point_label(obj.vertex)}{point_label(obj.p2)}"

        if tn == "RegionMeasure":
            pts = getattr(obj, "pts", [])
            if pts:
                names = "".join(point_label(p) for p in pts[:4])
                if len(pts) > 4:
                    names += "…"
                return f"区域{names}"
            return "区域"

        if tn == "Measure":
            kind = getattr(obj, "kind", "")
            targets = getattr(obj, "targets", [])

            if kind == "angle" and len(targets) >= 3:
                v, p1, p2 = targets[0], targets[1], targets[2]
                return f"角{point_label(p1)}{point_label(v)}{point_label(p2)}"

            if kind == "distance" and len(targets) >= 2:
                return f"距离{point_label(targets[0])}{point_label(targets[1])}"

            if targets:
                return object_display_name(targets[0])

            return "度量"

        if tn == "RatioMeasure":
            return "比值"

        if tn == "ChainFill":
            return "填充"

        if tn == "FunctionCurve":
            return "函数"

        if tn == "ImplicitCurve":
            return "隐函数"

        if tn == "TextObject":
            return "文本"

        if tn == "ScriptButtonObject":
            return "按钮"

        if tn == "TableObject":
            return "表格"

        if tn in ("PieChartObject", "BarChartObject", "LineChartObject", "DonutChartObject"):
            return "图表"

        if tn == "ImageObject":
            return "图片"

        if tn == "InkStroke":
            return "墨迹"

        if tn == "InkEraser":
            return "橡皮擦"

        if tn == "TransformDriver":
            return "变换"

        if tn == "TransformPoint":
            return "变换点"

        if tn == "IterPoint":
            return "迭代点"

        if tn == "CircleAxisPoint":
            return "圆轴点"

    except Exception:
        pass

    return getattr(obj, "name", "") or tn


def binding_display_name(obj, metric):
    base = object_display_name(obj)
    tn = type(obj).__name__

    if tn == "Segment" and metric == "length":
        return base

    if tn in ("Circle", "ExprCircle", "ThreePointCircle", "InvertedCircle") and metric == "radius":
        return base

    if tn == "Ellipse" and metric == "area":
        return base

    if tn == "RegularPolygon" and metric == "area":
        return base

    if tn == "AngleMeasure" and metric == "degrees":
        return base

    if tn == "Measure":
        kind = getattr(obj, "kind", "")

        if kind in ("length", "distance", "angle", "area", "radius"):
            return base

        suffix = {
            "perimeter": "周长",
            "diameter": "直径",
            "slope": "斜率",
            "ratio": "比值",
            "coord": "坐标",
        }.get(kind, "")

        if suffix:
            return f"{base}{suffix}"
        return base

    if metric == "value":
        return base

    suffix = {
        "length": "长度",
        "distance": "距离",
        "angle": "角度",
        "ratio": "比值",
        "area": "面积",
        "perimeter": "周长",
        "radius": "半径",
        "diameter": "直径",
        "slope": "斜率",
        "degrees": "角度",
    }.get(metric, metric)

    if suffix:
        return f"{base}{suffix}"

    return base

def available_metrics(obj):
    """返回对象支持的度量列表：[(metric, label), ...]"""
    if obj is None or not getattr(obj, "exists", True):
        return []

    tn = type(obj).__name__

    if tn == "Measure":
        kind = getattr(obj, "kind", "")
        if kind == "coord":
            return []
        labels = {
            "length": "长度",
            "distance": "距离",
            "angle": "角度",
            "ratio": "比值",
            "area": "面积",
            "perimeter": "周长",
            "radius": "半径",
            "diameter": "直径",
            "slope": "斜率",
        }
        return [("value", labels.get(kind, kind))]

    if tn == "RegionMeasure":
        return [
            ("area", "区域面积"),
            ("perimeter", "区域周长"),
        ]

    if tn == "Segment":
        return [
            ("length", "线段长度"),
            ("slope", "斜率"),
        ]

    if tn == "Line":
        return [
            ("slope", "斜率"),
        ]

    if tn == "AngleMeasure":
        return [
            ("degrees", "角度"),
        ]

    if tn in ("Circle", "ExprCircle", "ThreePointCircle", "InvertedCircle"):
        return [
            ("radius", "半径"),
            ("diameter", "直径"),
            ("area", "面积"),
            ("perimeter", "周长"),
        ]

    if tn == "Ellipse":
        return [
            ("area", "面积"),
            ("perimeter", "周长"),
        ]

    if tn == "RegularPolygon":
        return [
            ("radius", "外接圆半径"),
            ("area", "面积"),
            ("perimeter", "周长"),
        ]

    return []


def compute_metric(obj, metric):
    """计算对象某个度量的 float 值；失败返回 None。"""
    if obj is None or not getattr(obj, "exists", True):
        return None

    tn = type(obj).__name__

    try:
        # Measure 对象统一用 value
        if tn == "Measure":
            kind = getattr(obj, "kind", "")
            if kind == "coord":
                return None
            if metric in ("value", kind):
                return _finite_float(getattr(obj, "value", 0.0))
            return None

        # RegionMeasure
        if tn == "RegionMeasure":
            if metric == "area":
                return _finite_float(getattr(obj, "area", 0.0))
            if metric == "perimeter":
                return _finite_float(getattr(obj, "perimeter", 0.0))
            return None

        # 长度
        if metric == "length":
            if hasattr(obj, "length") and callable(obj.length):
                return _finite_float(obj.length())
            return None

        # 角度
        if metric == "degrees":
            if hasattr(obj, "degrees"):
                return _finite_float(obj.degrees)
            return None

        # 半径 / 直径
        if metric == "radius":
            if hasattr(obj, "r"):
                return _finite_float(obj.r)
            return None

        if metric == "diameter":
            if hasattr(obj, "r"):
                return _finite_float(2.0 * obj.r)
            return None

        # 斜率
        if metric == "slope":
            a = getattr(obj, "a", None)
            b = getattr(obj, "b", None)
            if a is None and hasattr(obj, "origin"):
                a = obj.origin
            if b is None and hasattr(obj, "through"):
                b = obj.through
            if a is None or b is None:
                return None
            dx = b.x - a.x
            dy = b.y - a.y
            if abs(dx) < 1e-12:
                return None
            return _finite_float(dy / dx)

        # 面积
        if metric == "area":
            if tn in ("Circle", "ExprCircle", "ThreePointCircle", "InvertedCircle"):
                if hasattr(obj, "r"):
                    return _finite_float(math.pi * obj.r * obj.r)
                return None

            if tn == "Ellipse":
                return _finite_float(math.pi * abs(obj.ux * obj.vy - obj.uy * obj.vx))

            if tn == "RegularPolygon":
                n = obj.n
                r = obj.r
                return _finite_float(0.5 * n * r * r * math.sin(2.0 * math.pi / n))

            return None

        # 周长
        if metric == "perimeter":
            if tn in ("Circle", "ExprCircle", "ThreePointCircle", "InvertedCircle"):
                if hasattr(obj, "r"):
                    return _finite_float(2.0 * math.pi * obj.r)
                return None

            if tn == "Ellipse":
                a = math.hypot(obj.ux, obj.uy)
                b = math.hypot(obj.vx, obj.vy)
                if a + b <= 0:
                    return 0.0
                h = ((a - b) ** 2) / ((a + b) ** 2)
                return _finite_float(
                    math.pi * (a + b) * (1.0 + 3.0 * h / (10.0 + math.sqrt(4.0 - 3.0 * h)))
                )

            if tn == "RegularPolygon":
                return _finite_float(obj.n * 2.0 * obj.r * math.sin(math.pi / obj.n))

            return None

    except Exception:
        return None

    return None


def available_bindings(doc):
    items = []
    for obj in getattr(doc, "objects", []):
        if not getattr(obj, "exists", True):
            continue
        if not getattr(obj, "visible", True):
            continue

        for metric, label in available_metrics(obj):
            val = compute_metric(obj, metric)
            if val is None:
                continue

            kind = getattr(obj, "kind", "")
            if metric == "degrees" or kind == "angle":
                value_text = f"{val:.1f}°"
            else:
                value_text = f"{val:.3f}"

            name = binding_display_name(obj, metric)

            items.append(
                {
                    "obj_id": obj.id,
                    "metric": metric,
                    "label": f"{name} = {value_text}",
                    "var_name": name,
                }
            )

    return items

# ================= 度量绑定辅助结束 =================

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

    def define(self, name, value=1.0, vmin=0.0, vmax=10.0, expr="", step=0.1, binding=None):
        if binding:
            expr = ""
        self._vars[name] = Variable(name, value, vmin, vmax, expr, step, binding)
        self.version += 1
        self.changed.emit()

    def set(self, name, value):
        v = self._vars.get(name)
        if v and not v.expr and not v.binding and v.value != float(value):
            v.value = float(value)
            self.version += 1
            self.changed.emit()

    def set_expr(self, name, expr):
        v = self._vars.get(name)
        if v:
            v.expr = expr
            if expr:
                v.binding = None
            self.version += 1
            self.changed.emit()
            
    def bind(self, name, binding):
        v = self._vars.get(name)
        if not v:
            return
        v.binding = binding
        if binding:
            v.expr = ""
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
        return {
            name: {
                "value": v.value,
                "vmin": v.vmin,
                "vmax": v.vmax,
                "expr": v.expr,
                "step": v.step,
                "binding": v.binding,
            }
            for name, v in self._vars.items()
        }

    def load_dict(self, data):
        self._vars.clear()
        for name, d in data.items():
            self._vars[name] = Variable(
                name,
                d.get("value", 0.0),
                d.get("vmin", 0.0),
                d.get("vmax", 10.0),
                d.get("expr", ""),
                d.get("step", 0.1),
                d.get("binding", None),
            )
        self.version += 1
        self.changed.emit()
        
    def update_bindings(self, doc):
        """更新所有绑定到几何对象度量的变量。
        返回 True 表示有绑定变量或绑定关系发生了变化。
        ★ 不触发 changed 信号，由调用方统一触发，避免无限循环。
        """
        changed = False

        if not any(v.binding for v in self._vars.values()):
            return changed

        obj_map = {o.id: o for o in doc.objects}

        for name, var in self._vars.items():
            if not var.binding:
                continue

            # 表达式变量优先，绑定不生效
            if var.expr:
                continue

            obj_id = var.binding.get("obj_id")
            metric = var.binding.get("metric")
            obj = obj_map.get(obj_id)

            if obj is None or not getattr(obj, "exists", True):
                var.binding = None
                changed = True
                continue

            new_val = compute_metric(obj, metric)
            if new_val is None:
                continue

            if abs(new_val - var.value) > 1e-9:
                step = var.step if var.step > 1e-9 else 0.1
                pad = max(step * 10.0, 1.0)

                if new_val < var.vmin:
                    var.vmin = new_val - pad
                if new_val > var.vmax:
                    var.vmax = new_val + pad

                var.value = new_val
                changed = True

        return changed

    def _compute_metric(self, obj, metric):
        """兼容旧接口。"""
        return compute_metric(obj, metric)


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