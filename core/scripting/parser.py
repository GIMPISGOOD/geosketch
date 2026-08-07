"""脚本语法分析器：新语法。"""

from .errors import ScriptError
from .tokens import tokenize
from .ast_nodes import (
    Program, Import, GlobalAssign, Assign, FuncDef, Param, Return,
    If, Repeat, ForRange, Wait, DeleteAll, DeleteExpr, ExprStmt,
    Num, Str, Bool, Var, Member, Call, Bin, Unary
)


class Parser:
    def __init__(self, tokens):
        self.toks = tokens
        self.i = 0

    # ------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------

    def peek(self):
        return self.toks[self.i]

    def advance(self):
        t = self.toks[self.i]
        self.i += 1
        return t

    def at(self, ty, val=None):
        t = self.peek()

        if t[0] != ty:
            return False

        if val is not None and t[1] != val:
            return False

        return True

    def error(self, msg):
        t = self.peek()
        raise ScriptError(msg, t[2])

    def expect(self, ty, val=None):
        if not self.at(ty, val):
            t = self.peek()

            if val is None:
                self.error(f"期望 {ty}，实际得到 {t[0]}:{t[1]}")
            else:
                self.error(f"期望 {val}，实际得到 {t[1]}")

        return self.advance()

    def expect_key(self, key):
        return self.expect("KEY", key)

    # ------------------------------------------------------------
    # 入口
    # ------------------------------------------------------------

    def parse_program(self):
        stmts = []

        while not self.at("EOF"):
            stmts.append(self.parse_statement())

        return Program(stmts)

    # ------------------------------------------------------------
    # 语句
    # ------------------------------------------------------------

    def parse_statement(self):
        t = self.peek()

        if t[0] == "KEY":
            key = t[1]

            if key == "import":
                return self.parse_import()

            if key == "global":
                return self.parse_global()

            if key == "func":
                return self.parse_func()

            if key == "return":
                return self.parse_return()

            if key == "if":
                return self.parse_if()

            if key == "repeat":
                return self.parse_repeat()

            if key == "for":
                return self.parse_for()

            if key == "wait":
                return self.parse_wait()

            if key == "delete":
                return self.parse_delete()

        if t[0] == "ID":
            nxt = self.toks[self.i + 1]

            if nxt[0] == "ASSIGN":
                return self.parse_assign()

        expr = self.parse_expr()
        return ExprStmt(expr, expr.line)

    def parse_block(self):
        self.expect("LBRACE")

        stmts = []

        while not self.at("RBRACE") and not self.at("EOF"):
            stmts.append(self.parse_statement())

        self.expect("RBRACE")
        return stmts

    def parse_import(self):
        line = self.peek()[2]
        self.expect_key("import")

        name = self.expect("ID")[1]
        return Import(name, line)

    def parse_global(self):
        line = self.peek()[2]
        self.expect_key("global")

        name = self.expect("ID")[1]
        self.expect("ASSIGN")

        expr = self.parse_expr()
        return GlobalAssign(name, expr, line)

    def parse_assign(self):
        line = self.peek()[2]

        name = self.expect("ID")[1]
        self.expect("ASSIGN")

        expr = self.parse_expr()
        return Assign(name, expr, line)

    def parse_func(self):
        line = self.peek()[2]
        self.expect_key("func")

        name = self.expect("ID")[1]

        params = []

        self.expect("LPAREN")

        while not self.at("RPAREN") and not self.at("EOF"):
            pname = self.expect("ID")[1]
            default = None

            if self.at("ASSIGN"):
                self.advance()
                default = self.parse_expr()

            params.append(Param(pname, default, line))

            if self.at("COMMA"):
                self.advance()
            else:
                break

        self.expect("RPAREN")

        body = self.parse_block()

        return FuncDef(name, params, body, line)

    def parse_return(self):
        line = self.peek()[2]
        self.expect_key("return")

        if self.at("RBRACE") or self.at("EOF"):
            return Return(None, line)

        expr = self.parse_expr()
        return Return(expr, line)

    def parse_if(self):
        line = self.peek()[2]
        branches = []

        self.expect_key("if")
        cond = self.parse_expr()
        body = self.parse_block()
        branches.append((cond, body))

        else_body = None

        while True:
            if self.at("KEY", "elif"):
                self.advance()

                cond = self.parse_expr()
                body = self.parse_block()
                branches.append((cond, body))
                continue

            if self.at("KEY", "else"):
                self.advance()

                if self.at("KEY", "if"):
                    self.advance()

                    cond = self.parse_expr()
                    body = self.parse_block()
                    branches.append((cond, body))
                    continue

                else_body = self.parse_block()
                break

            break

        return If(branches, else_body, line)

    def parse_repeat(self):
        line = self.peek()[2]
        self.expect_key("repeat")

        count = self.parse_expr()
        body = self.parse_block()

        return Repeat(count, body, line)

    def parse_for(self):
        line = self.peek()[2]
        self.expect_key("for")

        var = self.expect("ID")[1]

        self.expect_key("from")
        start = self.parse_expr()

        self.expect_key("to")
        end = self.parse_expr()

        body = self.parse_block()

        return ForRange(var, start, end, body, line)

    def parse_wait(self):
        line = self.peek()[2]
        self.expect_key("wait")

        expr = self.parse_expr()
        return Wait(expr, line)

    def parse_delete(self):
        line = self.peek()[2]
        self.expect_key("delete")

        if self.at("KEY", "all"):
            self.advance()

            if self.at("ID") and self.peek()[1] in ("points", "点"):
                self.advance()
                return DeleteAll("points", line)

            if self.at("ID") and self.peek()[1] in ("circles", "圆"):
                self.advance()
                return DeleteAll("circles", line)

            return DeleteAll("all", line)

        if self.at("KEY", "created"):
            self.advance()
            return DeleteAll("created", line)

        expr = self.parse_expr()
        return DeleteExpr(expr, line)

    # ------------------------------------------------------------
    # 表达式
    # ------------------------------------------------------------

    def parse_expr(self):
        return self.parse_or()

    def parse_or(self):
        left = self.parse_and()

        while self.at("KEY", "or"):
            line = self.peek()[2]
            self.advance()

            right = self.parse_and()
            left = Bin("or", left, right, line)

        return left

    def parse_and(self):
        left = self.parse_not()

        while self.at("KEY", "and"):
            line = self.peek()[2]
            self.advance()

            right = self.parse_not()
            left = Bin("and", left, right, line)

        return left

    def parse_not(self):
        if self.at("KEY", "not"):
            line = self.peek()[2]
            self.advance()

            operand = self.parse_not()
            return Unary("not", operand, line)

        return self.parse_comparison()

    def parse_comparison(self):
        left = self.parse_add()

        while self.at("OP") and self.peek()[1] in (">", "<", ">=", "<=", "==", "!="):
            op = self.advance()[1]
            right = self.parse_add()
            left = Bin(op, left, right, left.line)

        return left

    def parse_add(self):
        left = self.parse_mul()

        while self.at("OP") and self.peek()[1] in ("+", "-"):
            op = self.advance()[1]
            right = self.parse_mul()
            left = Bin(op, left, right, left.line)

        return left

    def parse_mul(self):
        left = self.parse_power()

        while self.at("OP") and self.peek()[1] in ("*", "/", "%"):
            op = self.advance()[1]
            right = self.parse_power()
            left = Bin(op, left, right, left.line)

        return left

    def parse_power(self):
        left = self.parse_unary()

        if self.at("OP", "^"):
            line = self.peek()[2]
            self.advance()

            right = self.parse_power()
            return Bin("^", left, right, line)

        return left

    def parse_unary(self):
        if self.at("OP") and self.peek()[1] in ("+", "-"):
            op = self.advance()[1]
            operand = self.parse_unary()
            return Unary(op, operand, self.peek()[2])

        return self.parse_postfix()

    def parse_postfix(self):
        node = self.parse_primary()

        while True:
            if self.at("DOT"):
                line = self.peek()[2]
                self.advance()

                name = self.expect("ID")[1]
                node = Member(node, name, line)
                continue

            if self.at("LPAREN"):
                line = self.peek()[2]
                self.advance()

                args = []

                if not self.at("RPAREN"):
                    args.append(self.parse_expr())

                    while self.at("COMMA"):
                        self.advance()
                        args.append(self.parse_expr())

                self.expect("RPAREN")

                node = Call(node, args, line)
                continue

            break

        return node

    def parse_primary(self):
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
            self.advance()
            return Var(t[1], t[2])

        if t[0] == "LPAREN":
            self.advance()
            expr = self.parse_expr()
            self.expect("RPAREN")
            return expr

        self.error(f"非法表达式：{t[1]}")


def parse(src):
    tokens = tokenize(src)
    return Parser(tokens).parse_program()