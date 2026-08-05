"""布局引擎：两遍走 AST——measure 算出 (宽, 升, 降)，draw 按基线矢量绘制。

新增：
- 支持 Paren 节点
- 支持 x^(2*a)
"""

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainterPath, QPen

from . import font as mfont
from .parser import (
    Ord, Bin, Sup, Sub, SubSup, Frac, Sqrt, Over, Paren, Row, is_cjk
)


class MathLayout:
    def __init__(self, painter, size, color):
        self.p = painter
        self.size = float(size)
        self.color = QColor(color)
        self._mcache = {}

    # ── 字体与度量 ──

    def _metrics(self, size, italic, cjk):
        key = (round(size), italic, cjk)

        if key not in self._mcache:
            from PySide6.QtGui import QFontMetricsF
            self._mcache[key] = QFontMetricsF(mfont.math_font(size, italic, cjk))

        return self._mcache[key]

    def _text_dim(self, text, size, italic):
        cjk = any(is_cjk(c) for c in text)
        m = self._metrics(size, italic and not cjk, cjk)

        return (
            m.horizontalAdvance(text),
            m.ascent(),
            m.descent(),
            cjk
        )

    # ── 度量：返回 (宽, 升, 降) ──

    def measure(self, n):
        S = self.size

        if isinstance(n, Ord):
            w, a, d, _ = self._text_dim(n.text, S, n.kind == "var")
            return w, a, d

        if isinstance(n, Bin):
            w, a, d, _ = self._text_dim(n.op, S, False)
            return w + 2 * n.space * S, a, d

        if isinstance(n, Row):
            W = A = D = 0.0

            for c in n.children:
                w, a, d = self.measure(c)
                W += w
                A = max(A, a)
                D = max(D, d)

            return W, A, D

        if isinstance(n, Paren):
            lw, la, ld, _ = self._text_dim("(", S, False)
            rw, ra, rd, _ = self._text_dim(")", S, False)

            cw, ca, cd = self.measure(n.content)

            return (
                lw + cw + rw,
                max(la, ca, ra),
                max(ld, cd, rd)
            )

        if isinstance(n, Sup):
            bw, ba, bd = self.measure(n.base)
            sw, sa, sd = self._sub_measure(n.script)

            raise_h = max(0.5 * S, ba * 0.6)

            return (
                bw + sw,
                max(ba, raise_h + sa),
                bd
            )

        if isinstance(n, Sub):
            bw, ba, bd = self.measure(n.base)
            sw, sa, sd = self._sub_measure(n.script)

            drop = max(0.15 * S, bd * 0.3)

            return (
                bw + sw,
                ba,
                max(bd, drop + sd)
            )

        if isinstance(n, SubSup):
            bw, ba, bd = self.measure(n.base)

            ubw, uba, ubd = self._sub_measure(n.sub)
            upw, upa, upd = self._sub_measure(n.sup)

            return (
                bw + max(ubw, upw),
                max(ba, max(0.5 * S, ba * 0.6) + upa),
                max(bd, max(0.15 * S, bd * 0.3) + ubd)
            )

        if isinstance(n, Frac):
            axis = 0.26 * S
            bar = max(1.0, 0.05 * S)
            gap = 0.12 * S
            fs = 0.8 * S

            old = self.size
            self.size = fs

            nw, na, nd = self.measure(n.num)
            dw, da, dd = self.measure(n.den)

            self.size = old

            num_base = axis + bar / 2 + gap + nd
            den_base = axis - bar / 2 - gap - da

            return (
                max(nw, dw) + 0.24 * S,
                num_base + na,
                -den_base + dd
            )

        if isinstance(n, Sqrt):
            w, a, d = self.measure(n.content)
            over = 0.12 * S + max(1.0, 0.05 * S)
            rw = 0.6 * (a + d + over)

            return (
                rw + w + 0.1 * S,
                a + over,
                d
            )

        if isinstance(n, Over):
            w, a, d = self.measure(n.content)
            return w, a + 0.22 * S, d

        return 0.0, 0.0, 0.0

    def _sub_measure(self, n):
        old = self.size
        self.size = old * 0.7

        r = self.measure(n)

        self.size = old
        return r

    # ── 绘制：从 (x, 基线y) 开始，返回消耗宽度 ──

    def draw(self, n, x, y):
        S = self.size
        p = self.p

        if isinstance(n, Ord):
            w, a, d, cjk = self._text_dim(n.text, S, n.kind == "var")

            p.setFont(mfont.math_font(S, n.kind == "var" and not cjk, cjk))
            p.setPen(QPen(self.color, 1.0))
            p.drawText(QPointF(x, y), n.text)

            return w

        if isinstance(n, Bin):
            sp = n.space * S
            w, a, d, _ = self._text_dim(n.op, S, False)

            p.setFont(mfont.math_font(S, False, False))
            p.setPen(QPen(self.color, 1.0))
            p.drawText(QPointF(x + sp, y), n.op)

            return w + 2 * sp

        if isinstance(n, Row):
            cx = x

            for c in n.children:
                cx += self.draw(c, cx, y)

            return cx - x

        if isinstance(n, Paren):
            lw, _, _, _ = self._text_dim("(", S, False)

            p.setFont(mfont.math_font(S, False, False))
            p.setPen(QPen(self.color, 1.0))
            p.drawText(QPointF(x, y), "(")

            cw = self.draw(n.content, x + lw, y)

            rw, _, _, _ = self._text_dim(")", S, False)

            p.setFont(mfont.math_font(S, False, False))
            p.setPen(QPen(self.color, 1.0))
            p.drawText(QPointF(x + lw + cw, y), ")")

            return lw + cw + rw

        if isinstance(n, Sup):
            bw, ba, bd = self.measure(n.base)
            bw = self.draw(n.base, x, y)

            sw, sa, sd = self._sub_measure(n.script)

            raise_h = max(0.5 * S, ba * 0.6)
            sw = self._sub_draw(n.script, x + bw, y - raise_h)

            return bw + sw

        if isinstance(n, Sub):
            bw, ba, bd = self.measure(n.base)
            bw = self.draw(n.base, x, y)

            sw, sa, sd = self._sub_measure(n.script)

            drop = max(0.15 * S, bd * 0.3)
            sw = self._sub_draw(n.script, x + bw, y + drop)

            return bw + sw

        if isinstance(n, SubSup):
            bw, ba, bd = self.measure(n.base)
            bw = self.draw(n.base, x, y)

            ubw, uba, ubd = self._sub_measure(n.sub)
            upw, upa, upd = self._sub_measure(n.sup)

            self._sub_draw(n.sup, x + bw, y - max(0.5 * S, ba * 0.6))
            self._sub_draw(n.sub, x + bw, y + max(0.15 * S, bd * 0.3))

            return bw + max(ubw, upw)

        if isinstance(n, Frac):
            return self._draw_frac(n, x, y)

        if isinstance(n, Sqrt):
            return self._draw_sqrt(n, x, y)

        if isinstance(n, Over):
            w, a, d = self.measure(n.content)

            self.draw(n.content, x, y)

            p.setPen(QPen(self.color, max(1.0, 0.05 * S)))
            p.drawLine(
                QPointF(x, y - a - 0.1 * S),
                QPointF(x + w, y - a - 0.1 * S)
            )

            return w

        return 0.0

    def _sub_draw(self, n, x, y):
        old = self.size
        self.size = old * 0.7

        w = self.draw(n, x, y)

        self.size = old
        return w

    def _draw_frac(self, n, x, y):
        S = self.size

        axis = 0.26 * S
        bar = max(1.0, 0.05 * S)
        gap = 0.12 * S
        fs = 0.8 * S

        old = self.size
        self.size = fs

        nw, na, nd = self.measure(n.num)
        dw, da, dd = self.measure(n.den)

        inner = max(nw, dw)
        pad = 0.12 * S

        num_base = axis + bar / 2 + gap + nd
        den_base = axis - bar / 2 - gap - da

        self.draw(n.num, x + pad + (inner - nw) / 2, y - num_base)
        self.draw(n.den, x + pad + (inner - dw) / 2, y - den_base)

        self.size = old

        self.p.setPen(QPen(self.color, bar))
        self.p.drawLine(
            QPointF(x, y - axis),
            QPointF(x + inner + 2 * pad, y - axis)
        )

        return inner + 2 * pad

    def _draw_sqrt(self, n, x, y):
        S = self.size

        cw, ca, cd = self.measure(n.content)

        over = 0.12 * S + max(1.0, 0.05 * S)
        H = ca + cd + over
        rw = 0.6 * H

        top = y - (ca + over)
        bot = y + cd + over * 0.3

        path = QPainterPath()

        path.moveTo(x + rw * 0.05, top + (bot - top) * 0.55)
        path.lineTo(x + rw * 0.40, bot)
        path.lineTo(x + rw * 0.95, top)
        path.lineTo(x + rw + cw + 0.1 * S, top)

        self.p.setPen(QPen(self.color, max(1.0, 0.06 * S)))
        self.p.setBrush(Qt.BrushStyle.NoBrush)
        self.p.drawPath(path)

        w = self.draw(n.content, x + rw, y)

        return rw + w + 0.1 * S