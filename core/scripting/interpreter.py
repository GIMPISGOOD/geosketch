"""脚本解释器。"""

import sys
import time

from PySide6.QtWidgets import QApplication

from .errors import ScriptError, ScriptReturn
from .scope import Scope, UserFunction, MISSING
from .object_factory import ObjectFactory, get_object_property
from .object_destructor import ObjectDestructor
from .functions import build_global_env
from .parser import parse


class Interpreter:
    def __init__(self, doc, canvas=None, owner_id="script"):
        self.doc = doc
        self.canvas = canvas
        self.owner_id = owner_id or "script"

        self.steps = 0
        self.max_steps = 100000

        self.call_depth = 0
        self.max_call_depth = 1000

        self.special = {
            "__keep": False,
            "__allow_delete_user": False,
        }

        self.logs = []
        self.created = []
        self.error = None

        self.imported_modules = {}
        self.importing = set()

        if not hasattr(doc, "script_libs"):
            doc.script_libs = {}

        self.factory = ObjectFactory(self)
        self.destructor = ObjectDestructor(self)

        self.global_scope = Scope()

        for k, v in build_global_env(self).items():
            self.global_scope.vars[k] = v

        # 用户自定义函数可能递归较深
        sys.setrecursionlimit(max(sys.getrecursionlimit(), 5000))

    # ------------------------------------------------------------
    # 对外入口
    # ------------------------------------------------------------

    def run(self, program):
        self._var_backup = self.doc.vars.to_dict()

        self.doc.begin_action()

        try:
            self.exec_block(program.statements, self.global_scope)
            self._finalize_success()

        except ScriptReturn:
            self._finalize_success()

        except ScriptError as e:
            self.error = e
            self._rollback()

        except Exception as e:
            self.error = ScriptError(str(e))
            self._rollback()

        finally:
            self.doc.end_action()

        return self.error is None

    # ------------------------------------------------------------
    # 事务 / 回滚
    # ------------------------------------------------------------

    def add_created_object(self, obj, name=None):
        obj.script_owner = self.owner_id
        obj.script_created = True

        if name:
            obj.script_name = name

            try:
                obj.name = name
            except Exception:
                pass

        self.created.append(obj)
        self.doc.add(obj)

        return obj

    def _finalize_success(self):
        keep = self._truth(self.special.get("__keep", False))

        if not keep:
            for obj in reversed(self.created):
                if obj in self.doc.objects:
                    self.doc._remove(obj)

            self.created = []
            self.doc.changed.emit()

    def _rollback(self):
        for obj in reversed(self.created):
            if obj in self.doc.objects:
                self.doc._remove(obj)

        try:
            self.doc.vars.load_dict(self._var_backup)
        except Exception:
            pass

        self.doc.changed.emit()

    # ------------------------------------------------------------
    # 执行语句
    # ------------------------------------------------------------

    def exec_block(self, stmts, scope):
        for stmt in stmts:
            self._step(stmt)
            self.exec_stmt(stmt, scope)

    def exec_stmt(self, stmt, scope):
        from .ast_nodes import (
            Import, GlobalAssign, Assign, FuncDef, Return,
            If, Repeat, ForRange, Wait, DeleteAll, DeleteExpr, ExprStmt
        )

        if isinstance(stmt, Import):
            module = self._import_module(stmt.name, scope, stmt.line)
            scope.set_local(stmt.name, module)
            return

        if isinstance(stmt, GlobalAssign):
            value = self.eval_expr(stmt.expr, scope)
            self._assign_special(stmt.name, value)
            scope.set_global(stmt.name, value)
            self._set_store_var(stmt.name, value)
            return

        if isinstance(stmt, Assign):
            value = self.eval_expr(stmt.expr, scope)
            self._assign_special(stmt.name, value)
            scope.set_local(stmt.name, value)

            # 如果赋值的是几何对象，尝试同步对象名
            if hasattr(value, "script_name"):
                value.script_name = stmt.name

                try:
                    value.name = stmt.name
                except Exception:
                    pass

            return

        if isinstance(stmt, FuncDef):
            func = UserFunction(stmt.name, stmt.params, stmt.body, scope)
            scope.set_local(stmt.name, func)
            return

        if isinstance(stmt, Return):
            value = None

            if stmt.expr is not None:
                value = self.eval_expr(stmt.expr, scope)

            raise ScriptReturn(value)

        if isinstance(stmt, If):
            for cond, body in stmt.branches:
                if self._truth(self.eval_expr(cond, scope)):
                    self.exec_block(body, scope)
                    return

            if stmt.else_body is not None:
                self.exec_block(stmt.else_body, scope)

            return

        if isinstance(stmt, Repeat):
            count = int(self._as_number(self.eval_expr(stmt.count, scope), stmt.line))

            if count < 0:
                raise ScriptError("repeat 次数不能为负数", stmt.line)

            for _ in range(count):
                self.exec_block(stmt.body, scope)

            return

        if isinstance(stmt, ForRange):
            start = int(self._as_number(self.eval_expr(stmt.start, scope), stmt.line))
            end = int(self._as_number(self.eval_expr(stmt.end, scope), stmt.line))

            if start <= end:
                it = range(start, end + 1)
            else:
                it = range(start, end - 1, -1)

            for i in it:
                scope.set_local(stmt.var, float(i))
                self.exec_block(stmt.body, scope)

            return

        if isinstance(stmt, Wait):
            seconds = self._as_number(self.eval_expr(stmt.expr, scope), stmt.line)
            self._wait(seconds)
            return

        if isinstance(stmt, DeleteAll):
            self.destructor.delete_all(stmt.target, stmt.line)
            return

        if isinstance(stmt, DeleteExpr):
            obj = self.eval_expr(stmt.expr, scope)
            self.destructor.delete_object(obj, stmt.line)
            return

        if isinstance(stmt, ExprStmt):
            self.eval_expr(stmt.expr, scope)
            return

        raise ScriptError("未知语句", getattr(stmt, "line", None))

    # ------------------------------------------------------------
    # import
    # ------------------------------------------------------------

    def _import_module(self, name, scope, line=None):
        if name in self.imported_modules:
            return self.imported_modules[name]

        from .libraries import get_builtin_library

        lib = get_builtin_library(name, self)

        if lib is not None:
            self.imported_modules[name] = lib
            return lib

        source = getattr(self.doc, "script_libs", {}).get(name)

        if source is None:
            raise ScriptError(f"找不到库：{name}", line)

        if name in self.importing:
            raise ScriptError(f"循环导入：{name}", line)

        self.importing.add(name)

        try:
            prog = parse(source)
            module_scope = Scope(self.global_scope)

            self._load_library(prog, module_scope)

            module = {
                k: v
                for k, v in module_scope.vars.items()
                if not k.startswith("__")
            }

            self.imported_modules[name] = module
            return module

        finally:
            self.importing.discard(name)

    def _load_library(self, program, scope):
        from .ast_nodes import FuncDef, Import

        for stmt in program.statements:
            if isinstance(stmt, FuncDef):
                func = UserFunction(stmt.name, stmt.params, stmt.body, scope)
                scope.set_local(stmt.name, func)

            elif isinstance(stmt, Import):
                module = self._import_module(stmt.name, scope, stmt.line)
                scope.set_local(stmt.name, module)

            else:
                raise ScriptError("库文件只能包含 func 定义和 import", getattr(stmt, "line", None))

    # ------------------------------------------------------------
    # 表达式
    # ------------------------------------------------------------

    def eval_expr(self, node, scope):
        self._step(node)

        from .ast_nodes import (
            Num, Str, Bool, Var, Member, Call, Bin, Unary
        )

        if isinstance(node, Num):
            return float(node.value)

        if isinstance(node, Str):
            return node.value

        if isinstance(node, Bool):
            return node.value

        if isinstance(node, Var):
            return self._lookup_var(node.name, scope, node.line)

        if isinstance(node, Member):
            left = self.eval_expr(node.obj, scope)

            if isinstance(left, dict):
                if node.name in left:
                    return left[node.name]

                raise ScriptError(f"模块没有成员：{node.name}", node.line)

            if hasattr(left, "type_name"):
                return get_object_property(left, node.name, node.line)

            raise ScriptError("无法访问成员", node.line)

        if isinstance(node, Call):
            return self.eval_call(node, scope)

        if isinstance(node, Unary):
            return self.eval_unary(node, scope)

        if isinstance(node, Bin):
            return self.eval_bin(node, scope)

        raise ScriptError("未知表达式", getattr(node, "line", None))

    def _lookup_var(self, name, scope, line=None):
        value = scope.find(name)

        if value is not MISSING:
            return value

        # 文档变量
        try:
            d = self.doc.vars.as_dict()

            if name in d:
                return float(d[name])
        except Exception:
            pass

        raise ScriptError(f"未定义变量：{name}", line)

    def eval_unary(self, node, scope):
        value = self.eval_expr(node.operand, scope)

        if node.op == "not":
            return not self._truth(value)

        value = self._as_number(value, node.line)

        if node.op == "-":
            return -value

        if node.op == "+":
            return value

        raise ScriptError(f"未知一元运算符：{node.op}", node.line)

    def eval_bin(self, node, scope):
        op = node.op

        if op == "and":
            left = self.eval_expr(node.left, scope)

            if not self._truth(left):
                return False

            return self._truth(self.eval_expr(node.right, scope))

        if op == "or":
            left = self.eval_expr(node.left, scope)

            if self._truth(left):
                return True

            return self._truth(self.eval_expr(node.right, scope))

        left = self.eval_expr(node.left, scope)
        right = self.eval_expr(node.right, scope)

        # 比较
        if op in ("==", "!=", "<", "<=", ">", ">="):
            return self._compare(op, left, right, node.line)

        # 字符串拼接
        if op == "+" and (isinstance(left, str) or isinstance(right, str)):
            return self._format_value(left) + self._format_value(right)

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

    def _compare(self, op, left, right, line=None):
        # 对象比较
        if hasattr(left, "type_name") or hasattr(right, "type_name"):
            if op == "==":
                return left is right

            if op == "!=":
                return left is not right

            raise ScriptError("对象只能使用 == 或 !=", line)

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

    def eval_call(self, node, scope):
        callee = self.eval_expr(node.callee, scope)

        args = [self.eval_expr(a, scope) for a in node.args]

        if isinstance(callee, UserFunction):
            return self.call_user_function(callee, args, node.line)

        if callable(callee):
            try:
                return callee(*args)
            except ScriptError:
                raise
            except Exception as e:
                raise ScriptError(str(e), node.line)

        raise ScriptError("不可调用对象", node.line)

    def call_user_function(self, func, args, line=None):
        self.call_depth += 1

        if self.call_depth > self.max_call_depth:
            raise ScriptError(f"超过最大递归深度 {self.max_call_depth}", line)

        scope = Scope(func.closure_scope)

        if len(args) > len(func.params):
            raise ScriptError(f"函数 {func.name} 参数过多", line)

        for i, param in enumerate(func.params):
            if i < len(args):
                value = args[i]
            elif param.default is not None:
                value = self.eval_expr(param.default, scope)
            else:
                raise ScriptError(f"函数 {func.name} 缺少参数 {param.name}", line)

            scope.set_local(param.name, value)

        try:
            self.exec_block(func.body, scope)
            return None

        except ScriptReturn as r:
            return r.value

        finally:
            self.call_depth -= 1

    # ------------------------------------------------------------
    # 特殊变量 / 变量系统
    # ------------------------------------------------------------

    def _assign_special(self, name, value):
        if name == "__keep":
            self.special["__keep"] = self._truth(value)

        elif name == "__allow_delete_user":
            self.special["__allow_delete_user"] = self._truth(value)

        elif name == "__max_steps":
            try:
                v = int(self._as_number(value))
                self.max_steps = min(max(v, 1), 100000)
            except Exception:
                pass

    def _set_store_var(self, name, value):
        if name.startswith("__"):
            return

        if isinstance(value, bool):
            value = 1.0 if value else 0.0

        if not isinstance(value, (int, float)):
            return

        value = float(value)

        store = self.doc.vars

        if store.get_var(name) is not None:
            store.set(name, value)
        else:
            store.define(name, value, value - 10.0, value + 10.0)

    # ------------------------------------------------------------
    # wait
    # ------------------------------------------------------------

    def _wait(self, seconds):
        seconds = float(seconds)

        if seconds <= 0:
            return

        # 单次等待最长 60 秒，避免脚本卡死
        seconds = min(seconds, 60.0)

        app = QApplication.instance()

        if app is None:
            time.sleep(seconds)
            return

        try:
            from PySide6.QtCore import QEventLoop, QTimer

            loop = QEventLoop()
            QTimer.singleShot(int(seconds * 1000), loop.quit)
            loop.exec()

        except Exception:
            time.sleep(seconds)

    # ------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------

    def _step(self, node=None):
        self.steps += 1

        if self.steps > self.max_steps:
            raise ScriptError(f"超过最大执行步数 {self.max_steps}", getattr(node, "line", None))

    def _truth(self, value):
        if isinstance(value, bool):
            return value

        if isinstance(value, (int, float)):
            return float(value) != 0.0

        if isinstance(value, str):
            return len(value) > 0

        if value is None:
            return False

        return True

    def _as_number(self, value, line=None):
        if isinstance(value, bool):
            return 1.0 if value else 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            try:
                return float(value)
            except Exception:
                raise ScriptError(f"无法转换为数字：{value}", line)

        raise ScriptError("此处需要数字", line)

    def _format_value(self, value):
        if value is None:
            return "none"

        if isinstance(value, bool):
            return "true" if value else "false"

        if isinstance(value, float):
            if abs(value - round(value)) < 1e-9:
                return str(int(round(value)))

            return f"{value:.6g}"

        if isinstance(value, int):
            return str(value)

        if isinstance(value, str):
            return value

        if hasattr(value, "type_name"):
            name = getattr(value, "script_name", None) or getattr(value, "name", None)

            if name:
                return f"<{value.type_name}:{name}>"

            return f"<{value.type_name}>"

        return str(value)