"""框选工具：拖拽矩形框批量选择对象（从选择工具中独立出来）。"""
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor

from core.registry import register_tool
from geo.points import AbstractPoint
from tools.base import Tool
from media.base import MediaObject
from ui import theme


def _collect_defining_points(obj, acc, seen):
    """递归收集对象的定义点（自身是点则收自己，否则沿 parents 往下）。"""
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, AbstractPoint):
        acc.append(obj)
        return
    for p in obj.parents:
        _collect_defining_points(p, acc, seen)


def _object_in_rect(obj, x0, y0, x1, y1):
    """对象是否落入选框：点看坐标；媒体看矩形；其他对象看其定义点是否落入。"""
    if not (obj.visible and obj.exists):
        return False

    # 媒体对象：左上角 (x, y)，底边 y - height
    if isinstance(obj, MediaObject):
        rx0, rx1 = obj.x, obj.x + obj.width
        ry0, ry1 = obj.y - obj.height, obj.y
        return not (rx1 < x0 or rx0 > x1 or ry1 < y0 or ry0 > y1)

    if isinstance(obj, AbstractPoint):
        return x0 <= obj.x <= x1 and y0 <= obj.y <= y1

    pts = []
    _collect_defining_points(obj, pts, set())
    return any(x0 <= p.x <= x1 and y0 <= p.y <= y1 for p in pts)


@register_tool(name="框选", order=1, icon="box", panel="rail",
               hint="按住拖拽矩形框，批量选中框内的几何对象")
class BoxSelectTool(Tool):
    def __init__(self):
        self.box_start = None
        self.box_end = None

    def activated(self, canvas):
        self.box_start = None

    def deactivated(self, canvas):
        self.box_start = None

    def press(self, canvas, wpt, hit):
        canvas.doc.set_selection([])
        self.box_start = wpt
        self.box_end = wpt

    def move(self, canvas, wpt, hit):
        if self.box_start is not None:
            self.box_end = wpt
            canvas.update()

    def release(self, canvas, wpt, hit):
        if self.box_start is not None:
            x0, x1 = sorted((self.box_start[0], self.box_end[0]))
            y0, y1 = sorted((self.box_start[1], self.box_end[1]))
            sel = [o for o in canvas.doc.objects
                   if _object_in_rect(o, x0, y0, x1, y1)]
            canvas.doc.set_selection(sel)
            self.box_start = None
            self.box_end = None

    def draw_overlay(self, p, view):
        if self.box_start is None or self.box_end is None:
            return
        a = view.to_screen(*self.box_start)
        b = view.to_screen(*self.box_end)
        rect = QRectF(a, b).normalized()
        fill = QColor(theme.ACCENT)
        fill.setAlpha(28)
        p.setBrush(theme.brush(fill))
        p.setPen(theme.pen(theme.ACCENT, 1.5))
        p.drawRect(rect)