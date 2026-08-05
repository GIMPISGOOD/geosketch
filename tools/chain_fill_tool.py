"""自由填充工具：点→曲线→点→曲线… 描出闭合区域并填充。

新增：
- 弧段条件：自动 / 短弧 / 长弧 / 逆时针 / 顺时针
- 填充规则：偶数 / 非零环绕
- 点击闭合曲线时，根据点击位置自动选择期望弧段
"""

import math

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QToolButton, QButtonGroup, QSlider,
    QColorDialog, QGraphicsDropShadowEffect
)

from core.registry import register_tool
from geo.chain_fill import (
    ChainFill, CurveRef, Span, FillStyle, sample_span,
    polygon_edge, hatch_lines, _point_seg_dist,
    choose_closed_arc
)
from geo.points import AbstractPoint, nearest_point
from tools.base import Tool, point_or_snap
from ui import theme


# ───────────── 样式迷你预览 ─────────────

class StylePreview(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(72, 42)
        self.style_obj = FillStyle(QColor("#4dabf7"), 0.6, "solid")

    def set_style(self, style):
        self.style_obj = style
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        path = QPainterPath()
        path.addRoundedRect(
            QRectF(2, 2, self.width() - 4, self.height() - 4),
            8,
            8
        )

        st = self.style_obj
        color = QColor(st.color)

        if st.kind == "gradient":
            from PySide6.QtGui import QLinearGradient, QBrush

            g = QLinearGradient(0, 0, self.width(), self.height())

            c1 = QColor(color)
            c1.setAlphaF(st.opacity)

            c2 = QColor(color)
            c2.setAlphaF(st.opacity * 0.12)

            g.setColorAt(0, c1)
            g.setColorAt(1, c2)

            p.setBrush(QBrush(g))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

        elif st.kind in ("hatch", "crosshatch"):
            p.save()
            p.setClipPath(path)

            hatch_lines(
                p,
                QRectF(0, 0, self.width(), self.height()),
                color,
                st.opacity,
                6,
                45
            )

            if st.kind == "crosshatch":
                hatch_lines(
                    p,
                    QRectF(0, 0, self.width(), self.height()),
                    color,
                    st.opacity,
                    6,
                    -45
                )

            p.restore()

        else:
            color.setAlphaF(st.opacity)
            p.setBrush(theme.brush(color))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)

        p.setPen(theme.pen(theme.SUBINK, 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)


# ───────────── 填充配置面板 ─────────────

class FillConfigPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("fillConfigPanel")

        self._color = QColor("#4dabf7")
        self._opacity = 0.6
        self._kind = "solid"

        # ★ 新增条件
        self._arc = "auto"
        self._fill_rule = "evenodd"

        self._build()

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("填充设置")
        title.setStyleSheet("font-weight:700;font-size:13px;")
        layout.addWidget(title)

        # 填充样式
        style_row = QHBoxLayout()
        style_group = QButtonGroup(self)
        style_group.setExclusive(True)

        for kind, label in [
            ("solid", "纯色"),
            ("gradient", "渐变"),
            ("hatch", "斜线"),
            ("crosshatch", "交叉线"),
        ]:
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)

            if kind == self._kind:
                b.setChecked(True)

            b.clicked.connect(lambda _=False, k=kind: self._set_kind(k))

            style_group.addButton(b)
            style_row.addWidget(b)

        layout.addLayout(style_row)

        # ★ 弧段条件
        arc_row = QHBoxLayout()
        arc_row.addWidget(QLabel("弧段"))

        arc_group = QButtonGroup(self)
        arc_group.setExclusive(True)

        for arc, label in [
            ("auto", "自动"),
            ("short", "短弧"),
            ("long", "长弧"),
            ("ccw", "逆时针"),
            ("cw", "顺时针"),
        ]:
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)

            if arc == self._arc:
                b.setChecked(True)

            b.clicked.connect(lambda _=False, a=arc: self._set_arc(a))

            arc_group.addButton(b)
            arc_row.addWidget(b)

        layout.addLayout(arc_row)

        # ★ 填充规则
        rule_row = QHBoxLayout()
        rule_row.addWidget(QLabel("填充规则"))

        rule_group = QButtonGroup(self)
        rule_group.setExclusive(True)

        for rule, label in [
            ("evenodd", "偶数"),
            ("winding", "非零环绕"),
        ]:
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)

            if rule == self._fill_rule:
                b.setChecked(True)

            b.clicked.connect(lambda _=False, r=rule: self._set_fill_rule(r))

            rule_group.addButton(b)
            rule_row.addWidget(b)

        layout.addLayout(rule_row)

        # 颜色 / 透明度
        row2 = QHBoxLayout()

        self._color_btn = QPushButton()
        self._color_btn.setFixedSize(38, 24)
        self._color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._color_btn.setToolTip("选择填充颜色")
        self._color_btn.clicked.connect(self._pick_color)
        self._update_color_btn()
        row2.addWidget(self._color_btn)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setRange(5, 100)
        self._slider.setValue(60)
        self._slider.valueChanged.connect(self._on_opacity)
        row2.addWidget(self._slider, 1)

        self._opacity_lbl = QLabel("60%")
        self._opacity_lbl.setFixedWidth(36)
        row2.addWidget(self._opacity_lbl)

        layout.addLayout(row2)

        self._preview = StylePreview()
        layout.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignCenter)

        self._hint = QLabel("")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("font-size:11px;")
        layout.addWidget(self._hint)

        self._sync_preview()

    def set_hint(self, text):
        self._hint.setText(text)
        self._hint.setStyleSheet(f"color:{theme.SUBINK.name()};font-size:11px;")

    def _set_kind(self, kind):
        self._kind = kind
        self._sync_preview()

    def _set_arc(self, arc):
        self._arc = arc
        self._sync_preview()

    def _set_fill_rule(self, rule):
        self._fill_rule = rule
        self._sync_preview()

    def get_arc(self):
        return self._arc

    def get_fill_rule(self):
        return self._fill_rule

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "选择填充颜色")
        if c.isValid():
            self._color = c
            self._update_color_btn()
            self._sync_preview()

    def _update_color_btn(self):
        self._color_btn.setStyleSheet(
            f"background:{self._color.name()};"
            f"border:1px solid rgba(0,0,0,0.3);"
            f"border-radius:5px;"
        )

    def _on_opacity(self, v):
        self._opacity = v / 100
        self._opacity_lbl.setText(f"{v}%")
        self._sync_preview()

    def _sync_preview(self):
        self._preview.set_style(
            FillStyle(
                self._color,
                self._opacity,
                self._kind,
                self._fill_rule
            )
        )

    def get_style(self):
        return FillStyle(
            QColor(self._color),
            self._opacity,
            self._kind,
            self._fill_rule
        )


# ───────────── 自由填充工具 ─────────────

@register_tool(
    name="自由填充",
    shortcut="W",
    order=9,
    icon="freefill",
    panel="rail",
    hint="点→曲线→点→曲线… 描出区域；闭合曲线可点击期望弧段；Esc 重来"
)
class ChainFillTool(Tool):
    def __init__(self):
        self.chain_points = []
        self.spans = []
        self.pending_curve = None
        self.pending_prefer = None
        self._panel = None

    def activated(self, canvas):
        self._clear()

        self._panel = FillConfigPanel(canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show()
        self._panel.raise_()

        self._update_hint()

    def deactivated(self, canvas):
        self._clear()

        if self._panel is not None:
            self._panel.hide()
            self._panel.deleteLater()

        self._panel = None

    def _clear(self):
        self.chain_points = []
        self.spans = []
        self.pending_curve = None
        self.pending_prefer = None

    # ───── 拾取 ─────

    def _pick_point(self, canvas, wpt):
        pt = nearest_point(canvas.doc, canvas.scale, wpt)

        if pt is None:
            return None, float("inf")

        return pt, math.hypot(pt.x - wpt[0], pt.y - wpt[1])

    def _pick_curve(self, canvas, wpt):
        tol = 10.0 / canvas.scale
        best, best_d = None, tol

        for o in canvas.doc.objects:
            if not (o.visible and o.exists) or isinstance(o, AbstractPoint):
                continue

            if type(o).__name__ == "RegularPolygon":
                k = polygon_edge(o, wpt[0], wpt[1])
                a = o.verts[k]
                b = o.verts[(k + 1) % o.n]

                d = _point_seg_dist(wpt[0], wpt[1], a[0], a[1], b[0], b[1])

                if d < best_d:
                    best, best_d = CurveRef(o, k), d

            elif hasattr(o, "point_at") and hasattr(o, "project"):
                d = o.distance_to(wpt[0], wpt[1])

                if d is not None and d < best_d:
                    best, best_d = CurveRef(o), d

        return best, best_d

    # ───── 弧段条件 ─────

    def _resolve_arc(self, curve, from_pt, to_pt, prefer=None):
        arc = self._panel.get_arc() if self._panel else "auto"

        if arc == "auto" and curve is not None and getattr(curve, "closed", False):
            p = prefer if prefer is not None else self.pending_prefer

            if p is not None:
                return choose_closed_arc(curve, from_pt, to_pt, p)

        return arc

    # ───── 点击分发 ─────

    def press(self, canvas, wpt, hit):
        pt, pt_d = self._pick_point(canvas, wpt)
        curve, curve_d = self._pick_curve(canvas, wpt)

        expecting_point = (self.pending_curve is not None) or (not self.chain_points)

        if expecting_point:
            self._on_point(
                canvas,
                pt if pt is not None else point_or_snap(canvas, wpt, hit)
            )
        else:
            clicking_start = (
                pt is not None
                and len(self.chain_points) >= 2
                and pt is self.chain_points[0]
            )

            if curve is not None and not clicking_start and curve_d < pt_d:
                self._on_curve(canvas, curve, wpt)
            elif pt is not None:
                self._on_point(canvas, pt)
            else:
                self._on_point(canvas, point_or_snap(canvas, wpt, hit))

        self._update_hint()
        canvas.update()

    def _on_point(self, canvas, pt):
        if pt is None:
            return

        if not self.chain_points:
            self.chain_points = [pt]
            return

        # 已有待选曲线时，点击当前点视为取消待选曲线
        if self.pending_curve is not None and pt is self.chain_points[-1]:
            self.pending_curve = None
            self.pending_prefer = None
            return

        # 没有待选曲线时，点击当前点撤销上一个顶点
        if pt is self.chain_points[-1]:
            self.chain_points.pop()

            if self.spans:
                self.spans.pop()

            return

        # 手动闭合：点回起点
        if pt is self.chain_points[0] and len(self.chain_points) >= 2:
            arc = self._resolve_arc(
                self.pending_curve,
                self.chain_points[-1],
                pt
            )

            self.spans.append(
                Span(
                    self.chain_points[-1],
                    pt,
                    self.pending_curve,
                    arc
                )
            )

            self.pending_curve = None
            self.pending_prefer = None
            self._finish(canvas)
            return

        arc = self._resolve_arc(
            self.pending_curve,
            self.chain_points[-1],
            pt
        )

        self.spans.append(
            Span(
                self.chain_points[-1],
                pt,
                self.pending_curve,
                arc
            )
        )

        self.pending_curve = None
        self.pending_prefer = None
        self.chain_points.append(pt)

    def _on_curve(self, canvas, curve, wpt=None):
        # 再点同一曲线 = 取消
        if (
            self.pending_curve is not None
            and self.pending_curve.obj is curve.obj
            and self.pending_curve.edge == curve.edge
        ):
            self.pending_curve = None
            self.pending_prefer = None
            return

        # 自动闭合：这条曲线恰好接回起点 → 直接填充
        if len(self.chain_points) >= 2:
            cur, start = self.chain_points[-1], self.chain_points[0]

            if self._curve_connects(canvas, curve, cur, start):
                arc = self._resolve_arc(curve, cur, start, wpt)

                self.spans.append(
                    Span(
                        cur,
                        start,
                        curve,
                        arc
                    )
                )

                self.pending_curve = None
                self.pending_prefer = None
                self._finish(canvas)
                return

        self.pending_curve = curve
        self.pending_prefer = wpt

    @staticmethod
    def _curve_connects(canvas, curve, pt_a, pt_b):
        """曲线的两个端点是否分别与 pt_a、pt_b 重合。"""
        obj = curve.obj
        tol = 8.0 / canvas.scale

        def near(p1, p2):
            return p1 is p2 or math.hypot(p1.x - p2.x, p1.y - p2.y) < tol

        if curve.edge is not None:
            a = obj.verts[curve.edge]
            b = obj.verts[(curve.edge + 1) % obj.n]

            def cnear(p, x, y):
                return math.hypot(p.x - x, p.y - y) < tol

            return (
                (cnear(pt_a, *a) and cnear(pt_b, *b)) or
                (cnear(pt_a, *b) and cnear(pt_b, *a))
            )

        if hasattr(obj, "a") and hasattr(obj, "b"):
            a, b = obj.a, obj.b

            return (
                (near(a, pt_a) and near(b, pt_b)) or
                (near(a, pt_b) and near(b, pt_a))
            )

        return False

    def _finish(self, canvas):
        if self.spans and len(self.chain_points) >= 2:
            style = (
                self._panel.get_style()
                if self._panel
                else FillStyle(QColor("#4dabf7"), 0.6, "solid", "evenodd")
            )

            canvas.doc.add(ChainFill(self.spans, style))

        self._clear()

    def confirm(self, canvas):
        if len(self.chain_points) >= 2:
            arc = self._resolve_arc(
                self.pending_curve,
                self.chain_points[-1],
                self.chain_points[0]
            )

            self.spans.append(
                Span(
                    self.chain_points[-1],
                    self.chain_points[0],
                    self.pending_curve,
                    arc
                )
            )

            self.pending_curve = None
            self.pending_prefer = None
            self._finish(canvas)

        self._update_hint()
        canvas.update()

    def cancel(self, canvas):
        self._clear()
        self._update_hint()
        canvas.update()

    def _update_hint(self):
        if self._panel is None:
            return

        arc_name = {
            "auto": "自动",
            "short": "短弧",
            "long": "长弧",
            "ccw": "逆时针",
            "cw": "顺时针",
        }.get(self._panel.get_arc(), "自动")

        if not self.chain_points:
            self._panel.set_hint("① 点点选起点")

        elif self.pending_curve is not None:
            self._panel.set_hint(
                f"③ 点下一个点（当前弧段：{arc_name}；点击曲线时靠近想要的弧可自动选择）"
            )

        else:
            self._panel.set_hint(
                f"② 点选线段/圆弧作为边界（当前弧段：{arc_name}；也可直接点下一点走直线）"
            )

    # ───── 覆盖层 ─────

    def draw_overlay(self, p, view):
        # 待选曲线高亮
        if self.pending_curve is not None:
            c = self.pending_curve

            p.setPen(theme.dashed_pen(theme.PREVIEW, 2.5))
            p.setBrush(Qt.BrushStyle.NoBrush)

            path = QPainterPath()
            n = 60 if c.closed else 40

            for i in range(n + 1):
                sp = view.to_screen(*c.point_at(i / n))
                path.moveTo(sp) if i == 0 else path.lineTo(sp)

            if c.closed:
                path.closeSubpath()

            p.drawPath(path)

        if not self.chain_points:
            return

        # 实时填充预览
        prev = []

        for sp in self.spans:
            prev.extend(sample_span(sp)[:-1])

        prev.append((self.chain_points[-1].x, self.chain_points[-1].y))

        if len(prev) >= 2:
            prev.append((self.chain_points[0].x, self.chain_points[0].y))

        fpath = QPainterPath()
        fpath.moveTo(view.to_screen(*prev[0]))

        for q in prev[1:]:
            fpath.lineTo(view.to_screen(*q))

        fpath.closeSubpath()

        style = (
            self._panel.get_style()
            if self._panel
            else FillStyle(QColor("#4dabf7"), 0.6, "solid", "evenodd")
        )

        fc = QColor(style.color)
        fc.setAlphaF(style.opacity * 0.35)

        p.setBrush(theme.brush(fc))
        p.setPen(theme.dashed_pen(theme.ACCENT, 1.2))
        p.drawPath(fpath)

        # 已选链 + 到光标的橡皮筋
        pts = []

        for sp in self.spans:
            pts.extend(sample_span(sp)[:-1])

        pts.append((self.chain_points[-1].x, self.chain_points[-1].y))

        lpath = QPainterPath()
        lpath.moveTo(view.to_screen(*pts[0]))

        for q in pts[1:]:
            lpath.lineTo(view.to_screen(*q))

        lpath.lineTo(view.to_screen(*view.cursor_wpt))

        p.setPen(theme.dashed_pen(theme.ACCENT, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(lpath)

        # 顶点标记
        for i, pt in enumerate(self.chain_points):
            sp = view.to_screen(pt.x, pt.y)

            p.setPen(theme.pen(theme.PREVIEW if i == 0 else theme.ACCENT, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)

            r = 7 if i == 0 else 5
            p.drawEllipse(sp, r, r)