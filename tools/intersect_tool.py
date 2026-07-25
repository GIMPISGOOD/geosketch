"""交点工具：依次点两个圆 → 生成两个交点。"""
from PySide6.QtCore import Qt

from core.registry import register_tool
from geo.circle_intersects import CircleIntersectPoint
from geo.circles import Circle
from tools.base import Tool
from ui import theme


@register_tool(name="交点", shortcut="X", order=4, icon="intersect", # pyright: ignore[reportArgumentType]
               hint="依次点两个圆求交点（无解自动消失，交点可被磁吸）；Esc 取消")
class IntersectTool(Tool):
    def __init__(self):
        self.first = None

    def activated(self, canvas):
        self.first = None

    def deactivated(self, canvas):
        self.first = None

    def press(self, canvas, wpt, hit):
        if not isinstance(hit, Circle):
            return                                   # 只接受圆
        if self.first is None:
            self.first = hit
            canvas.doc.set_selection([hit])          # 高亮第一个圆
        else:
            if hit is not self.first:
                canvas.doc.add(CircleIntersectPoint(self.first, hit, 0))
                canvas.doc.add(CircleIntersectPoint(self.first, hit, 1))
            self.first = None
            canvas.doc.set_selection([])

    def cancel(self, canvas):
        self.first = None
        canvas.doc.set_selection([])
        canvas.update()

    def draw_overlay(self, p, view):
        """虚线高亮已选中的第一个圆"""
        if self.first is None:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 2.0))
        p.setBrush(Qt.BrushStyle.NoBrush)
        c = view.to_screen(self.first.center.x, self.first.center.y)
        r = self.first.r * view.scale
        p.drawEllipse(c, r, r)