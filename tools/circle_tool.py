import math

from PySide6.QtCore import Qt

from core.registry import register_tool
from geo.circles import Circle
from tools.base import Tool, point_or_snap
from ui import theme


@register_tool(name="圆", shortcut="C", order=3, icon="circle",
               hint="第一下定圆心，第二下定圆周上的点（均自动磁吸）；Esc 取消")
class CircleTool(Tool):
    def __init__(self):
        self.center = None

    def activated(self, canvas):
        self.center = None

    def deactivated(self, canvas):
        self.center = None

    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if self.center is None:
            self.center = pt
        else:
            if pt is not self.center:
                canvas.doc.add(Circle(self.center, pt))
            self.center = None

    def cancel(self, canvas):
        self.center = None
        canvas.update()

    def draw_overlay(self, p, view):
        if self.center is None:
            return

        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)

        center_sp = view.to_screen(self.center.x, self.center.y)
        cursor_sp = view.to_screen(*view.cursor_wpt)

        r = math.hypot(
            view.cursor_wpt[0] - self.center.x,
            view.cursor_wpt[1] - self.center.y
        ) * view.scale

        # 预览圆
        p.drawEllipse(center_sp, r, r)

        # ★ 半径预览线：圆心 → 当前光标
        p.drawLine(center_sp, cursor_sp)