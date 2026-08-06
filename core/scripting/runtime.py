"""GeoSketch 脚本运行时。

职责：
- 执行 AST
- 管理局部变量 / 全局变量
- 管理脚本创建对象
- 处理 __keep
- 控制最大执行步数
"""

from core.variables import FUNCS, CONSTS

from .errors import ScriptError
from .parser import (
    Program, Repeat, ForRange, If, Assign, Print,
    AddPoint, AddSegment, AddLine, AddCircle, AddPolygon, AddText,
    DeleteObject, NameTemplate,
    Num, Str, Bool, Var, Bin, Unary, Call
)


class ScriptRuntime:
    MAX_STEPS = 100000

    def __init__(self, doc, canvas=None, owner_id=None):
        self.doc = doc
        self.canvas = canvas
        self.owner_id = owner_id

        self.locals = {}
        self.globals = {}

        # 脚本内对象引用表：脚本名 -> GeoObject
        self.refs = {}

        self.created = []
        self.deleted = []
        self.logs = []

        self.steps = 0
        self.keep = False
        self.allow_existing = False
        self.error = None

    # ------------------------------------------------------------
    # 执行入口
    # ------------------------------------------------------------

    def execute(self, program: Program):
        try:
            for stmt in program.statements:
                self._step(stmt)
                self.exec_stmt(stmt)

            self._finalize_success()

        except ScriptError as e:
            self.error = e
            self._finalize_error()

        except Exception as e:
            self.error = ScriptError(str(e))
            self._finalize_error()

        return self

    def _finalize_success(self):
        keep_val = self.locals.get(
            "__keep",
            self.globals.get("__keep", False)
        )

        self.keep = self._truth(keep_val)

        self._apply_globals()

        if not self.keep:
            self._remove_created()

        self.doc.changed.emit()

    def _finalize_error(self):
        # 出错时不保留临时对象
        self._remove_created()
        self.doc.changed.emit()

    # ------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------

    def _step(self, node=None):
        self.steps += 1

        if self.steps > self.MAX_STEPS:
            line = getattr(node, "line", None)
            raise ScriptError(f"超过最大执行步数 {self.MAX_STEPS}", line)

    def _truth(self, value):
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return float(value) != 0.0

        if isinstance(value, str):
            return len(value) > 0

        return bool(value)

    def _as_number(self, value, line=None):
        if isinstance(value, bool):
            return 1.0 if value else 0.0

        if isinstance(value, (int, float)):
            return float(value)

        raise ScriptError("此处需要数值", line)

    def _format_value(self, value):
        if isinstance(value, float):
            if abs(value - round(value)) < 1e-9:
                return str(int(round(value)))
            return f"{value:.6g}"

        return str(value)

    # ------------------------------------------------------------
    # 变量
    # ------------------------------------------------------------

    def lookup_var(self, name, line=None):
        if name in self.locals:
            return self.locals[name]

        if name in self.globals:
            return self.globals[name]

        # 全局变量系统
        var = self.doc.vars.get_var(name)
        if var is not None:
            return var.value

        if name in CONSTS:
            return CONSTS[name]

        raise ScriptError(f"未定义变量：{name}", line)

    def _apply_globals(self):
        store = self.doc.vars

        if not self.globals:
            return

        store.blockSignals(True)

        try:
            for name, value in self.globals.items():
                # __keep 是脚本内部特殊变量，不写入全局变量面板
                if name == "__keep":
                    continue

                if isinstance(value, bool):
                    value = 1.0 if value else 0.0

                if not isinstance(value, (int, float)):
                    continue

                value = float(value)

                if store.get_var(name) is not None:
                    store.set(name, value)
                else:
                    store.define(
                        name=name,
                        value=value,
                        vmin=value - 10.0,
                        vmax=value + 10.0,
                        expr=""
                    )
        finally:
            store.blockSignals(False)

        store.changed.emit()
    # ------------------------------------------------------------
    # 对象名模板
    # ------------------------------------------------------------

    def render_name(self, node, line=None):
        """把 NameTemplate 渲染成最终对象名。

        例如：
            P{i}
            P{i + 1}
            Point_{n}
        """
        if isinstance(node, NameTemplate):
            buf = []

            for part in node.parts:
                if isinstance(part, str):
                    buf.append(part)
                else:
                    value = self.eval_expr(part)
                    buf.append(self._format_value(value))

            name = "".join(buf).strip()

            if not name:
                raise ScriptError("对象名不能为空", getattr(node, "line", line))

            # 对象名里不允许空格，自动转下划线
            name = name.replace(" ", "_")

            return name

        if isinstance(node, str):
            return node

        raise ScriptError("非法对象名", getattr(node, "line", line))
    
    # ------------------------------------------------------------
    # 对象引用 / 创建 / 删除
    # ------------------------------------------------------------

    def resolve_ref(self, name, line=None):
        obj = self.refs.get(name)

        if obj is not None and obj in self.doc.objects:
            return obj

        names = getattr(self.doc, "names", None) or {}
        obj = names.get(name)

        if obj is None:
            raise ScriptError(f"找不到对象：{name}", line)

        return obj

    def _prepare_name(self, script_name, line=None):
        """重复运行脚本时，默认先删除上一次由本脚本创建的同名对象。"""
        old = self.refs.get(script_name)

        if old is None:
            old = self.doc.names.get(script_name)

        if old is None:
            return

        owned = getattr(old, "script_owner", None) == self.owner_id

        if owned:
            self._delete_object(old, force=True)
        else:
            # 不是本脚本创建的对象：不删除，由 Document 自动重命名新对象
            return

    def _register_created(self, obj, script_name):
        if script_name:
            obj.script_owner = self.owner_id
            obj.script_name = script_name
            obj.name = script_name

        self.doc._add(obj)

        self.created.append(obj)

        if script_name:
            self.refs[script_name] = obj

    def _delete_object(self, obj, force=False, line=None):
        if obj not in self.doc.objects:
            return

        owned = getattr(obj, "script_owner", None) == self.owner_id

        if not owned and not force and not self.allow_existing:
            raise ScriptError(
                "当前脚本不能删除已有对象。只有 __keep = true 时才允许修改/删除已有对象。",
                line
            )

        doomed = self.doc._remove(obj)

        for d in doomed:
            if d in self.created:
                self.created.remove(d)

            for k, v in list(self.refs.items()):
                if v is d:
                    del self.refs[k]

            self.deleted.append(d)

    def _remove_created(self):
        for obj in list(self.created):
            if obj in self.doc.objects:
                doomed = self.doc._remove(obj)

                for d in doomed:
                    if d in self.created:
                        self.created.remove(d)

                    for k, v in list(self.refs.items()):
                        if v is d:
                            del self.refs[k]

    # ------------------------------------------------------------
    # 语句执行
    # ------------------------------------------------------------

    def exec_stmt(self, stmt):
        if isinstance(stmt, Repeat):
            return self.exec_repeat(stmt)

        if isinstance(stmt, ForRange):
            return self.exec_for(stmt)

        if isinstance(stmt, If):
            return self.exec_if(stmt)

        if isinstance(stmt, Assign):
            return self.exec_assign(stmt)

        if isinstance(stmt, Print):
            return self.exec_print(stmt)

        if isinstance(stmt, AddPoint):
            return self.exec_add_point(stmt)

        if isinstance(stmt, AddSegment):
            return self.exec_add_segment(stmt)

        if isinstance(stmt, AddLine):
            return self.exec_add_line(stmt)

        if isinstance(stmt, AddCircle):
            return self.exec_add_circle(stmt)

        if isinstance(stmt, AddPolygon):
            return self.exec_add_polygon(stmt)

        if isinstance(stmt, AddText):
            return self.exec_add_text(stmt)

        if isinstance(stmt, DeleteObject):
            return self.exec_delete(stmt)

        raise ScriptError("未知语句", getattr(stmt, "line", None))

    def exec_block(self, block):
        for stmt in block:
            self._step(stmt)
            self.exec_stmt(stmt)

    def exec_repeat(self, stmt):
        count = self.eval_expr(stmt.count)
        count = int(self._as_number(count, stmt.line))

        if count <= 0:
            return

        for _ in range(count):
            self._step(stmt)
            self.exec_block(stmt.body)

    def exec_for(self, stmt):
        start = int(self._as_number(self.eval_expr(stmt.start), stmt.line))
        end = int(self._as_number(self.eval_expr(stmt.end), stmt.line))

        if start <= end:
            it = range(start, end + 1)
        else:
            it = range(start, end - 1, -1)

        for i in it:
            self._step(stmt)
            self.locals[stmt.var] = float(i)
            self.exec_block(stmt.body)

    def exec_if(self, stmt):
        for cond, body in stmt.branches:
            if self._truth(self.eval_expr(cond)):
                self.exec_block(body)
                return

        if stmt.else_body is not None:
            self.exec_block(stmt.else_body)

    def exec_assign(self, stmt):
        value = self.eval_expr(stmt.expr)

        if stmt.scope == "global":
            self.globals[stmt.name] = value
        else:
            self.locals[stmt.name] = value

        if stmt.name == "__keep":
            self.allow_existing = self._truth(value)

    def exec_print(self, stmt):
        if stmt.expr is None:
            self.logs.append("")
            return

        value = self.eval_expr(stmt.expr)
        text = self._format_value(value)
        self.logs.append(text)

        if self.canvas is not None and hasattr(self.canvas, "cursor_info"):
            self.canvas.cursor_info.emit(text)

    # ------------------------------------------------------------
    # 几何命令
    # ------------------------------------------------------------

    def exec_add_point(self, stmt):
        from geo.points import FreePoint

        name = self.render_name(stmt.name, stmt.line)

        x = self._as_number(self.eval_expr(stmt.x), stmt.line)
        y = self._as_number(self.eval_expr(stmt.y), stmt.line)

        self._prepare_name(name, stmt.line)

        obj = FreePoint(x, y)
        self._register_created(obj, name)

    def exec_add_segment(self, stmt):
        from geo.segments import Segment
        from geo.points import AbstractPoint

        name = self.render_name(stmt.name, stmt.line)

        a_name = self.render_name(stmt.a, stmt.line)
        b_name = self.render_name(stmt.b, stmt.line)

        a = self.resolve_ref(a_name, stmt.line)
        b = self.resolve_ref(b_name, stmt.line)

        if not isinstance(a, AbstractPoint) or not isinstance(b, AbstractPoint):
            raise ScriptError("线段两端必须是点对象", stmt.line)

        self._prepare_name(name, stmt.line)

        obj = Segment(a, b)
        self._register_created(obj, name)

    def exec_add_line(self, stmt):
        from plugins.line_tool import Line
        from geo.points import AbstractPoint

        name = self.render_name(stmt.name, stmt.line)

        a_name = self.render_name(stmt.a, stmt.line)
        b_name = self.render_name(stmt.b, stmt.line)

        a = self.resolve_ref(a_name, stmt.line)
        b = self.resolve_ref(b_name, stmt.line)

        if not isinstance(a, AbstractPoint) or not isinstance(b, AbstractPoint):
            raise ScriptError("直线需要两个点对象", stmt.line)

        self._prepare_name(name, stmt.line)

        obj = Line(a, b)
        self._register_created(obj, name)

    def exec_add_circle(self, stmt):
        from geo.constraints import ExprCircle
        from geo.points import AbstractPoint

        name = self.render_name(stmt.name, stmt.line)

        center_name = self.render_name(stmt.center, stmt.line)
        center = self.resolve_ref(center_name, stmt.line)

        if not isinstance(center, AbstractPoint):
            raise ScriptError("圆心必须是点对象", stmt.line)

        # 如果半径写成字符串，例如 radius "a+1"，则作为表达式圆处理
        if isinstance(stmt.radius, Str):
            expr = stmt.radius.value
        else:
            value = self._as_number(self.eval_expr(stmt.radius), stmt.line)
            expr = str(value)

        self._prepare_name(name, stmt.line)

        obj = ExprCircle(center, expr)
        self._register_created(obj, name)

    def exec_add_polygon(self, stmt):
        from geo.chain_fill import ChainFill, Span, FillStyle
        from geo.points import AbstractPoint

        name = self.render_name(stmt.name, stmt.line)

        if len(stmt.point_names) < 3:
            raise ScriptError("多边形至少需要 3 个点", stmt.line)

        pts = []

        for name_node in stmt.point_names:
            point_name = self.render_name(name_node, stmt.line)
            p = self.resolve_ref(point_name, stmt.line)

            if not isinstance(p, AbstractPoint):
                raise ScriptError(f"{point_name} 不是点对象", stmt.line)

            pts.append(p)

        spans = []

        for i in range(len(pts) - 1):
            spans.append(Span(pts[i], pts[i + 1], None))

        spans.append(Span(pts[-1], pts[0], None))

        self._prepare_name(name, stmt.line)

        style = FillStyle("#4dabf7", 0.35, "solid")
        obj = ChainFill(spans, style)

        self._register_created(obj, name)

    def exec_add_text(self, stmt):
        from plugins.text_tool import TextObject

        name = self.render_name(stmt.name, stmt.line)

        x = self._as_number(self.eval_expr(stmt.x), stmt.line)
        y = self._as_number(self.eval_expr(stmt.y), stmt.line)

        if isinstance(stmt.text_expr, Str):
            text = stmt.text_expr.value
        else:
            text = self._format_value(self.eval_expr(stmt.text_expr))

        self._prepare_name(name, stmt.line)

        obj = TextObject(
            text=text,
            color="#1f2937",
            size=16,
            anchor=None,
            pos=(x, y)
        )

        self._register_created(obj, name)

    def exec_delete(self, stmt):
        name = self.render_name(stmt.name, stmt.line)
        obj = self.resolve_ref(name, stmt.line)

        self._delete_object(obj, force=False, line=stmt.line)

    # ------------------------------------------------------------
    # 表达式求值
    # ------------------------------------------------------------

    def eval_expr(self, node):
        self._step(node)

        if isinstance(node, Num):
            return float(node.value)

        if isinstance(node, Str):
            return node.value

        if isinstance(node, Bool):
            return node.value

        if isinstance(node, Var):
            return self.lookup_var(node.name, node.line)

        if isinstance(node, Unary):
            return self.eval_unary(node)

        if isinstance(node, Bin):
            return self.eval_bin(node)

        if isinstance(node, Call):
            return self.eval_call(node)

        raise ScriptError("未知表达式", getattr(node, "line", None))

    def eval_unary(self, node):
        value = self.eval_expr(node.operand)

        if node.op == "not":
            return not self._truth(value)

        value = self._as_number(value, node.line)

        if node.op == "-":
            return -value

        if node.op == "+":
            return value

        raise ScriptError(f"未知一元运算符：{node.op}", node.line)

    def eval_bin(self, node):
        op = node.op

        # 逻辑短路
        if op == "and":
            left = self.eval_expr(node.left)

            if not self._truth(left):
                return False

            return self._truth(self.eval_expr(node.right))

        if op == "or":
            left = self.eval_expr(node.left)

            if self._truth(left):
                return True

            return self._truth(self.eval_expr(node.right))

        left = self.eval_expr(node.left)
        right = self.eval_expr(node.right)

        # 比较
        if op in ("==", "!=", "<", "<=", ">", ">="):
            return self.compare(op, left, right, node.line)

        # ★ 字符串拼接
        if op == "+" and (isinstance(left, str) or isinstance(right, str)):
            return self._format_value(left) + self._format_value(right)

        # 算术
        a = self._as_number(left, node.line)
        b = self._as_number(right, node.line)

        if op == "+":
            return a + b

        if op == "-":
            return a - b

        if op == "*":
            return a * b

        if op == "/":
            if abs(b) < 1e-12:
                raise ScriptError("除数为 0", node.line)
            return a / b

        if op == "%":
            if abs(b) < 1e-12:
                raise ScriptError("模运算除数为 0", node.line)
            return a % b

        if op == "^":
            return a ** b

        raise ScriptError(f"未知运算符：{op}", node.line)

    def compare(self, op, left, right, line=None):
        # 字符串比较
        if isinstance(left, str) or isinstance(right, str):
            if op == "==":
                return str(left) == str(right)
            if op == "!=":
                return str(left) != str(right)
            raise ScriptError("字符串只能使用 == 或 !=", line)

        a = self._as_number(left, line)
        b = self._as_number(right, line)

        if op == "==":
            return abs(a - b) < 1e-12

        if op == "!=":
            return abs(a - b) >= 1e-12

        if op == "<":
            return a < b

        if op == "<=":
            return a <= b

        if op == ">":
            return a > b

        if op == ">=":
            return a >= b

        raise ScriptError(f"未知比较运算符：{op}", line)

    def eval_call(self, node):
        name = node.name

        if name not in FUNCS:
            raise ScriptError(f"不支持的函数：{name}", node.line)

        args = []

        for arg in node.args:
            v = self.eval_expr(arg)
            args.append(self._as_number(v, node.line))

        try:
            return float(FUNCS[name](*args))
        except Exception as e:
            raise ScriptError(f"函数 {name} 计算失败：{e}", node.line)


# ------------------------------------------------------------
# 对外入口
# ------------------------------------------------------------

def run_script(doc, script, owner_id=None, canvas=None):
    """执行一段脚本。返回 ScriptRuntime。"""
    from .parser import parse

    # ------------------------------------------------------------
    # 1. 解析脚本
    # ------------------------------------------------------------
    try:
        program = parse(script)

    except ScriptError as e:
        # ★ 修复：语法错误也返回 runtime，方便测试和 UI 读取 error
        rt = ScriptRuntime(doc, canvas=canvas, owner_id=owner_id)
        rt.error = e

        if canvas is not None and hasattr(canvas, "cursor_info"):
            canvas.cursor_info.emit(f"脚本错误：{e}")

        return rt

    except Exception as e:
        rt = ScriptRuntime(doc, canvas=canvas, owner_id=owner_id)
        rt.error = ScriptError(str(e))

        if canvas is not None and hasattr(canvas, "cursor_info"):
            canvas.cursor_info.emit(f"脚本错误：{e}")

        return rt

    # ------------------------------------------------------------
    # 2. 执行脚本
    # ------------------------------------------------------------
    rt = ScriptRuntime(doc, canvas=canvas, owner_id=owner_id)

    doc.begin_action()

    try:
        rt.execute(program)
    finally:
        doc.end_action()

    # ------------------------------------------------------------
    # 3. 输出结果
    # ------------------------------------------------------------
    if rt.error is not None:
        if canvas is not None and hasattr(canvas, "cursor_info"):
            canvas.cursor_info.emit(f"脚本错误：{rt.error}")
    else:
        if rt.logs and canvas is not None and hasattr(canvas, "cursor_info"):
            canvas.cursor_info.emit(" | ".join(rt.logs))

    return rt