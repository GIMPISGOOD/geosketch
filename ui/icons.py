"""工具图标：用 QPainter 现场绘制，不依赖任何图片资源。
每个工具通过 @register_tool(icon=...) 提供自己的画法；
画布色（Off）与选中色（On）各生成一份，供按钮 checked 状态切换。
"""
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPixmap

from ui import theme

IconPainter = "callable"   # (QPainter, QRectF, QColor) -> None


def icon_select(p: QPainter, r: QRectF, color: QColor) -> None:
    """箭头光标"""
    w, h = r.width(), r.height()
    pts = [(0.22, 0.05), (0.22, 0.88), (0.43, 0.67), (0.60, 0.97),
           (0.74, 0.89), (0.57, 0.60), (0.85, 0.57)]
    path = QPainterPath()
    path.moveTo(r.x() + pts[0][0] * w, r.y() + pts[0][1] * h)
    for x, y in pts[1:]:
        path.lineTo(r.x() + x * w, r.y() + y * h)
    path.closeSubpath()
    p.setPen(theme.pen(color, 1.6))
    p.setBrush(theme.brush(color))
    p.drawPath(path)


def icon_point(p: QPainter, r: QRectF, color: QColor) -> None:
    """同心点"""
    c = r.center()
    p.setPen(theme.pen(color, 1.8))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, r.width() * 0.34, r.width() * 0.34)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(c, r.width() * 0.13, r.width() * 0.13)


def icon_segment(p: QPainter, r: QRectF, color: QColor) -> None:
    """斜线段 + 两端点"""
    a = QPointF(r.left() + r.width() * 0.14, r.bottom() - r.height() * 0.14)
    b = QPointF(r.right() - r.width() * 0.14, r.top() + r.height() * 0.14)
    pen = theme.pen(color, 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.drawLine(a, b)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(a, 3.2, 3.2)
    p.drawEllipse(b, 3.2, 3.2)

def icon_circle(p, r, color):
    """圆 + 圆心"""
    c = r.center()
    p.setPen(theme.pen(color, 1.8))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(c, r.width() * 0.36, r.width() * 0.36)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(c, r.width() * 0.08, r.width() * 0.08)
    
def build_tool_icon(spec: dict) -> QIcon:
    """从注册表规格生成 QIcon：Off=墨色，On=强调色。"""
    painter_fn = spec.get("icon")
    icon = QIcon()
    for state, color in ((QIcon.State.Off, theme.ICON_INK),
                         (QIcon.State.On, theme.ACCENT)):
        pix = QPixmap(56, 56)
        pix.fill(Qt.GlobalColor.transparent)
        qp = QPainter(pix)
        qp.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(8, 8, 40, 40)
        if painter_fn is not None:
            painter_fn(qp, rect, color)
        else:                                    # 未提供图标 → 首字占位
            qp.setPen(theme.pen(color, 2.0))
            qp.drawText(rect, Qt.AlignmentFlag.AlignCenter, spec["name"][:1])
        qp.end()
        icon.addPixmap(pix, QIcon.Mode.Normal, state)
    return icon