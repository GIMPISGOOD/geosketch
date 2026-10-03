"""约束参考线绘制。

★ P2-11 修复：
  ① 原实现从未被调用（__init__.py 中注释掉了）
  ② 修复 QPainter 生命周期（确保 end() 被调用）
  ③ 增加约束状态着色（满足=绿 / 违反=红）
  ④ 跳过退化约束和禁用约束
"""
from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import Qt

from ui.canvas import Canvas
from ui import theme

_original_paint = Canvas.paintEvent


def _new_paint(self, ev):
    _original_paint(self, ev)

    doc = getattr(self, 'doc', None)
    if doc is None:
        return
    if not hasattr(doc, 'constraints') or not doc.constraints:
        return

    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    for c in doc.constraints:
        if not getattr(c, 'enabled', True):
            continue

        pts = c.involved_points()
        if not pts:
            continue

        # ── 收集屏幕坐标 ──
        screen_pts = []
        for pt in pts:
            if hasattr(pt, 'x') and hasattr(pt, 'y'):
                screen_pts.append(self.to_screen(pt.x, pt.y))
        if len(screen_pts) < 2:
            continue

        # ── 根据约束状态着色 ──
        try:
            res = c.residual()
            err = sum(v * v for v in res) ** 0.5
        except Exception:
            err = 0.0

        if err < 1e-4:
            color = QColor("#2b8a3e")      # 绿：已满足
        elif err < 1e-2:
            color = QColor("#e8590c")      # 橙：近似满足
        else:
            color = QColor("#e03131")      # 红：违反

        # ── 画约束参考线（虚线）──
        p.setPen(theme.dashed_pen(color, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)

        if len(screen_pts) == 3 and c.type_name == "angle":
            p.drawLine(screen_pts[0], screen_pts[1])
            p.drawLine(screen_pts[1], screen_pts[2])
        else:
            for i in range(len(screen_pts) - 1):
                p.drawLine(screen_pts[i], screen_pts[i + 1])

        # ── 端点小圆点 ──
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(color)
        for sp in screen_pts:
            p.drawEllipse(sp, 3.0, 3.0)

    p.end()


def patch_canvas():
    """注入约束参考线绘制到 Canvas.paintEvent。"""
    setattr(Canvas, "paintEvent", _new_paint)