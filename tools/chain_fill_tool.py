"""自由填充工具：顺序点击 点/曲线 围成闭合区域并填充。
交互：点→(可选曲线)→点→…→点回起点或回车闭合；再点已选元素可取消；Esc 全部重来。"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QToolButton, QButtonGroup, QSlider,
                               QColorDialog, QGraphicsDropShadowEffect)

from core.registry import register_tool
from geo.chain_fill import (ChainFill, CurveRef, Span, FillStyle, sample_span,
                            polygon_edge, hatch_lines)
from geo.points import AbstractPoint
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
        path.addRoundedRect(QRectF(2, 2, self.width() - 4, self.height() - 4), 8, 8)
        st = self.style_obj
        color = QColor(st.color)
        if st.kind == "gradient":
            from PySide6.QtGui import QLinearGradient, QBrush
            g = QLinearGradient(0, 0, self.width(), self.height())
            c1 = QColor(color); c1.setAlphaF(st.opacity)
            c2 = QColor(color); c2.setAlphaF(st.opacity * 0.12)
            g.setColorAt(0, c1); g.setColorAt(1, c2)
            p.setBrush(QBrush(g)); p.setPen(Qt.PenStyle.NoPen)
            p.drawPath(path)
        elif st.kind in ("hatch", "crosshatch"):
            p.save()
            p.setClipPath(path)
            hatch_lines(p, QRectF(0, 0, self.width(), self.height()), color, st.opacity, 6, 45)
            if st.kind == "crosshatch":
                hatch_lines(p, QRectF(0, 0, self.width(), self.height()), color, st.opacity, 6, -45)
            p.restore()
        else:
            color.setAlphaF(st.opacity)
            p.setBrush(theme.brush(color)); p.setPen(Qt.PenStyle.NoPen)
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
        self._build()
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22); shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 60))
        self.setGraphicsEffect(shadow)

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QLabel("填充设置")
        title.setStyleSheet("font-weight:700;font-size:13px;")
        layout.addWidget(title)

        # 样式四选一
        style_row = QHBoxLayout()
        group = QButtonGroup(self)
        group.setExclusive(True)
        for kind, label in [("solid", "纯色"), ("gradient", "渐变"),
                            ("hatch", "斜线"), ("crosshatch", "交叉线")]:
            b = QToolButton()
            b.setText(label)
            b.setCheckable(True)
            if kind == self._kind:
                b.setChecked(True)
            b.clicked.connect(lambda _=False, k=kind: self._set_kind(k))
            group.addButton(b)
            style_row.addWidget(b)
        layout.addLayout(style_row)

        # 颜色 + 不透明度
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

        # 实时预览
        self._preview = StylePreview()
        layout.addWidget(self._preview, 0, Qt.AlignmentFlag.AlignCenter)
        self._sync_preview()

    def _set_kind(self, kind):
        self._kind = kind
        self._sync_preview()

    def _pick_color(self):
        c = QColorDialog.getColor(self._color, self, "选择填充颜色")
        if c.isValid():
            self._color = c
            self._update_color_btn()
            self._sync_preview()

    def _update_color_btn(self):
        self._color_btn.setStyleSheet(
            f"background:{self._color.name()};border:1px solid rgba(0,0,0,0.3);border-radius:5px;")

    def _on_opacity(self, v):
        self._opacity = v / 100
        self._opacity_lbl.setText(f"{v}%")
        self._sync_preview()

    def _sync_preview(self):
        self._preview.set_style(FillStyle(self._color, self._opacity, self._kind))

    def get_style(self):
        return FillStyle(QColor(self._color), self._opacity, self._kind)


# ───────────── 自由填充工具 ─────────────
@register_tool(name="自由填充", shortcut="W", order=9, icon="freefill", panel="rail",
               hint="按顺序点 点/曲线 围成区域（点回起点或回车闭合）；再点已选元素取消；Esc 重来")
class ChainFillTool(Tool):
    def __init__(self):
        self.chain_points = []
        self.spans = []
        self.pending_curve = None
        self._panel = None

    def activated(self, canvas):
        self._clear()
        self._panel = FillConfigPanel(canvas)
        self._panel.adjustSize()
        self._panel.move((canvas.width() - self._panel.width()) // 2, 14)
        self._panel.show(); self._panel.raise_()

    def deactivated(self, canvas):
        self._clear()
        if self._panel is not None:
            self._panel.hide(); self._panel.deleteLater()
            self._panel = None

    def _clear(self):
        self.chain_points = []
        self.spans = []
        self.pending_curve = None

    def press(self, canvas, wpt, hit):
        if isinstance(hit, AbstractPoint):
            self._on_point(canvas, hit)
        else:
            curve = self._resolve_curve(hit, wpt)
            if curve is not None:
                self._on_curve(curve)
            else:
                # 空白处：新建一个顶点（磁吸生效）
                pt = point_or_snap(canvas, wpt, hit)
                if pt is not None:
                    self._on_point(canvas, pt)
        canvas.update()

    def _on_point(self, canvas, pt):
        if not self.chain_points:
            self.chain_points = [pt]
            return
        if pt is self.chain_points[-1]:
            # 取消：移除最后一个顶点（撤销上一段）
            self.chain_points.pop()
            if self.spans:
                self.spans.pop()
            return
        if pt is self.chain_points[0] and len(self.chain_points) >= 2:
            # 闭合：最后一段回到起点
            self.spans.append(Span(self.chain_points[-1], pt, self.pending_curve))
            self.pending_curve = None
            self._finish(canvas)
            return
        # 正常：从上一个顶点连一段到当前点
        self.spans.append(Span(self.chain_points[-1], pt, self.pending_curve))
        self.pending_curve = None
        self.chain_points.append(pt)

    def _on_curve(self, curve):
        # 再点一次同一曲线 = 取消选择
        if self.pending_curve is not None and self.pending_curve.obj is curve.obj \
                and self.pending_curve.edge == curve.edge:
            self.pending_curve = None
        else:
            self.pending_curve = curve

    @staticmethod
    def _resolve_curve(hit, wpt):
        if hit is None or isinstance(hit, AbstractPoint):
            return None
        if type(hit).__name__ == "RegularPolygon":
            return CurveRef(hit, polygon_edge(hit, wpt[0], wpt[1]))
        if hasattr(hit, "point_at") and hasattr(hit, "project"):
            return CurveRef(hit)
        return None

    def _finish(self, canvas):
        if self.spans and len(self.chain_points) >= 2:
            style = self._panel.get_style() if self._panel \
                else FillStyle(QColor("#4dabf7"), 0.6, "solid")
            canvas.doc.add(ChainFill(self.spans, style))
        self._clear()

    def confirm(self, canvas):                    # 回车闭合
        if len(self.chain_points) >= 2:
            self.spans.append(Span(self.chain_points[-1], self.chain_points[0],
                                   self.pending_curve))
            self.pending_curve = None
            self._finish(canvas)
            canvas.update()

    def cancel(self, canvas):
        self._clear()
        canvas.update()

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

        # 已选链 + 到光标的橡皮筋
        pts = []
        for sp in self.spans:
            pts.extend(sample_span(sp)[:-1])
        pts.append((self.chain_points[-1].x, self.chain_points[-1].y))
        path = QPainterPath()
        path.moveTo(view.to_screen(*pts[0]))
        for pt in pts[1:]:
            path.lineTo(view.to_screen(*pt))
        path.lineTo(view.to_screen(*view.cursor_wpt))
        p.setPen(theme.dashed_pen(theme.ACCENT, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

        # 顶点标记（起点用大环提示"点这里闭合"）
        for i, pt in enumerate(self.chain_points):
            sp = view.to_screen(pt.x, pt.y)
            p.setPen(theme.pen(theme.PREVIEW if i == 0 else theme.ACCENT, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            r = 7 if i == 0 else 5
            p.drawEllipse(sp, r, r)