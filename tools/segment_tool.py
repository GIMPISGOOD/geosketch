# tools/segment_tool.py
from core.registry import register_tool
from geo.segments import Segment
from tools.base import Tool, point_or_snap
from ui.icons import icon_segment
from ui import theme


@register_tool(name="线段", shortcut="S", order=2, icon=icon_segment,
               hint="点击两次确定两个端点（端点自动吸附已有对象）；Esc 取消")
class SegmentTool(Tool):
    def __init__(self):
        self.first = None

    def activated(self, canvas):
        self.first = None

    def deactivated(self, canvas):
        self.first = None

    def press(self, canvas, wpt, hit):
        pt = point_or_snap(canvas, wpt, hit)
        if self.first is None:
            self.first = pt
        else:
            if pt is not self.first:
                canvas.doc.add(Segment(self.first, pt))
            self.first = None

    def cancel(self, canvas):
        self.first = None
        canvas.update()

    def draw_overlay(self, p, view):
        if self.first is None:
            return
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.drawLine(view.to_screen(self.first.x, self.first.y),
                   view.to_screen(*view.cursor_wpt))