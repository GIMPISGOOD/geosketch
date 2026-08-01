"""迷你数学排版器：词法/语法分析，输出 AST。
支持：斜体变量、数字、上下标(x^2 / a_1 / x²)、堆叠分式(\\frac{}{} 或 a/b)、
根号(\\sqrt{})、上划线(\\overline{})、希腊字母、∠ ⊥ ∥ ° 等几何符号、中文变量名。"""

# ───────── AST 节点 ─────────
class Ord:      # 普通符号
    def __init__(self, text, kind):     # kind: var/num/func/text/sym
        self.text, self.kind = text, kind

class Bin:      # 二元运算符（自带左右留白）
    def __init__(self, op, space=0.18):
        self.op, self.space = op, space

class Sup:
    def __init__(self, base, script): self.base, self.script = base, script
class Sub:
    def __init__(self, base, script): self.base, self.script = base, script
class SubSup:
    def __init__(self, base, sub, sup): self.base, self.sub, self.sup = sub and sub, sup
class Frac:
    def __init__(self, num, den): self.num, self.den = num, den
class Sqrt:
    def __init__(self, content): self.content = content
class Over:
    def __init__(self, content): self.content = content
class Row:
    def __init__(self, children): self.children = children


FUNCS = {"sin", "cos", "tan", "cot", "sqrt", "log", "ln", "abs", "exp",
         "lim", "max", "min", "arcsin", "arccos", "arctan"}

GREEK = {"alpha":"α","beta":"β","gamma":"γ","delta":"δ","epsilon":"ε","zeta":"ζ",
         "eta":"η","theta":"θ","iota":"ι","kappa":"κ","lambda":"λ","mu":"μ",
         "nu":"ν","xi":"ξ","pi":"π","rho":"ρ","sigma":"σ","tau":"τ",
         "upsilon":"υ","phi":"φ","chi":"χ","psi":"ψ","omega":"ω",
         "Gamma":"Γ","Delta":"Δ","Theta":"Θ","Lambda":"Λ","Xi":"Ξ","Pi":"Π",
         "Sigma":"Σ","Phi":"Φ","Psi":"Ψ","Omega":"Ω"}

SYMBOLS = {"angle":"∠","perp":"⊥","parallel":"∥","degree":"°","circ":"°",
           "cdot":"·","times":"×","div":"÷","pm":"±","infty":"∞","partial":"∂",
           "le":"≤","ge":"≥","ne":"≠","approx":"≈","equiv":"≡","sim":"∼",
           "rightarrow":"→","leftarrow":"←","in":"∈","subset":"⊂","cup":"∪",
           "cap":"∩","forall":"∀","exists":"∃","therefore":"∴","because":"∵"}

_SUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹", "0123456789")
_SUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉", "0123456789")


def is_cjk(ch):
    o = ord(ch)
    return (0x4E00 <= o <= 0x9FFF or 0x3400 <= o <= 0x4DBF or
            0xF900 <= o <= 0xFAFF or 0x3040 <= o <= 0x30FF)


# ───────── 词法 ─────────
def tokenize(s):
    toks, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
        elif c == "\\":
            j, name = i + 1, ""
            while j < n and s[j].isalpha():
                name += s[j]; j += 1
            toks.append(("CMD", name)); i = j
        elif c == "{": toks.append(("LB", c)); i += 1
        elif c == "}": toks.append(("RB", c)); i += 1
        elif c == "^": toks.append(("SUP", c)); i += 1
        elif c == "_": toks.append(("SUB", c)); i += 1
        elif c.isdigit() or (c == "." and i + 1 < n and s[i+1].isdigit()):
            j, num = i, ""
            while j < n and (s[j].isdigit() or s[j] == "."):
                num += s[j]; j += 1
            toks.append(("NUM", num)); i = j
        elif c in "⁰¹²³⁴⁵⁶⁷⁸⁹":
            toks.append(("SUP", "^")); toks.append(("NUM", c.translate(_SUP))); i += 1
        elif c in "₀₁₂₃₄₅₆₇₈₉":
            toks.append(("SUB", "_")); toks.append(("NUM", c.translate(_SUB))); i += 1
        elif c in "+-*/=·×÷−()°,":
            toks.append(("OP", c)); i += 1
        elif is_cjk(c):
            j, name = i, ""
            while j < n and is_cjk(s[j]):
                name += s[j]; j += 1
            toks.append(("ID", name)); i = j
        elif c.isalpha():
            j, name = i, ""
            while j < n and s[j].isalpha():
                name += s[j]; j += 1
            toks.append(("ID", name)); i = j
        else:
            toks.append(("ID", c)); i += 1
    toks.append(("EOF", ""))
    return toks


# ───────── 语法 ─────────
class _Parser:
    def __init__(self, toks):
        self.toks, self.i = toks, 0

    def peek(self): return self.toks[self.i]
    def take(self):
        t = self.toks[self.i]; self.i += 1
        return t

    def parse(self):
        return self.row(False)

    def row(self, in_group):
        nodes = []
        while True:
            ty, v = self.peek()
            if ty == "EOF" or (in_group and ty == "RB"):
                break
            node = self.atom()
            if node is None:
                self.take()
                continue
            node = self.scripts(node)
            while self.peek() == ("OP", "/"):
                self.take()
                right = self.atom()
                if right is None:
                    break
                node = Frac(node, self.scripts(right))
            nodes.append(node)
        if in_group and self.peek()[0] == "RB":
            self.take()
        if not nodes:
            return Row([])
        return nodes[0] if len(nodes) == 1 else Row(nodes)
    def scripts(self, base):
        sub = sup = None
        while self.peek()[0] in ("SUP", "SUB"):
            ty = self.take()[0]
            arg = self.group() if self.peek()[0] == "LB" else self.atom()
            if ty == "SUP": sup = arg
            else: sub = arg
        if sub and sup: return SubSup(base, sub, sup)
        if sup: return Sup(base, sup)
        if sub: return Sub(base, sub)
        return base

    def group(self):
        self.take()                     # 吃掉 {
        return self.row(True)

    def atom(self):
        ty, v = self.peek()
        if ty == "NUM":
            self.take(); return Ord(v, "num")
        if ty == "ID":
            self.take(); return self._classify(v)
        if ty == "CMD":
            self.take(); return self._cmd(v)
        if ty == "LB":
            return self.group()
        if ty == "OP":
            self.take(); return self._op(v)
        return None

    def _classify(self, v):
        if v in FUNCS:  return Ord(v, "func")
        if v in GREEK:  return Ord(GREEK[v], "var")
        if is_cjk(v[0]): return Ord(v, "text")
        if len(v) == 1: return Ord(v, "var")     # 单字母 → 斜体
        return Ord(v, "text")                     # 多字母 → 正体

    def _cmd(self, name):
        if name == "frac":
            return Frac(self._arg(), self._arg())
        if name == "sqrt":
            return Sqrt(self._arg())
        if name == "overline":
            return Over(self._arg())
        if name in GREEK:   return Ord(GREEK[name], "var")
        if name in SYMBOLS: return Ord(SYMBOLS[name], "sym")
        return Ord(name, "text")

    def _arg(self):
        return self.group() if self.peek()[0] == "LB" else self.atom()

    def _op(self, v):
        if v == "*": return Bin("·")
        if v == "-": return Bin("−")
        if v == "+": return Bin("+")
        if v in "·×÷": return Bin(v)
        if v == "=": return Bin("=", space=0.26)
        return Ord(v, "sym")              # ( ) , ° /


def parse(text):
    return _Parser(tokenize(text)).parse()