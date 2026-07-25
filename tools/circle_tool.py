import math

from PySide6.QtCore import Qt

from core.registry import register_tool
from geo.circles import Circle
from tools.base import Tool, point_or_snap
from ui import theme
from ui.icons import icon_circle


@register_tool(name="圆", shortcut="C", order=3, icon=icon_circle,
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
        """橡皮筋：从圆心拉到光标的预览圆"""
        if self.center is None:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        c = view.to_screen(self.center.x, self.center.y)
        r = (math.hypot(view.cursor_wpt[0] - self.center.x,
                        view.cursor_wpt[1] - self.center.y) * view.scale)
        p.drawEllipse(c, r, r)