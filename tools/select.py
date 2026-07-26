"""选择工具：点选/拖动单个对象；空白处拖拽框选多个对象。"""
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor

from core.registry import register_tool
from geo.points import AbstractPoint, FreePoint
from tools.base import Tool, snap_target
from ui import theme


def _collect_defining_points(obj, acc, seen):
    """递归收集对象的定义点（自身是点则收自己，否则沿 parents 往下找）。"""
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, AbstractPoint):
        acc.append(obj)
        return
    for p in obj.parents:
        _collect_defining_points(p, acc, seen)


def _object_in_rect(obj, x0, y0, x1, y1):
    """对象是否落入选框：点看坐标范围；其他对象看其定义点是否落入。"""
    if not (obj.visible and obj.exists):
        return False
    if isinstance(obj, AbstractPoint):
        return x0 <= obj.x <= x1 and y0 <= obj.y <= y1
    pts = []
    _collect_defining_points(obj, pts, set())
    return any(x0 <= p.x <= x1 and y0 <= p.y <= y1 for p in pts)


@register_tool(name="选择", shortcut="V", order=0, icon="select",
               hint="点选/拖动对象；空白处拖拽框选多个；Delete 级联删除")
class SelectTool(Tool):
    def __init__(self):
        self.dragged = None
        self.offset = (0.0, 0.0)
        self._drag_undo_begun = False
        self.box_start = None
        self.box_end = None

    def activated(self, canvas):
        self.dragged = None
        self.box_start = None

    def press(self, canvas, wpt, hit):
        target = snap_target(canvas, wpt, hit)
        self.dragged = None
        self.box_start = None
        self._drag_undo_begun = False
        if target is not None:
            canvas.doc.set_selection([target])
            if getattr(target, "draggable", False):
                self.dragged = target
                self.offset = (0.0, 0.0)
                if isinstance(target, FreePoint):
                    # 记录光标与点心的偏移：拖动时点不会"跳"到光标上
                    self.offset = (target.x - wpt[0], target.y - wpt[1])
        else:
            # 空白处：开始框选
            canvas.doc.set_selection([])
            self.box_start = wpt
            self.box_end = wpt

    def move(self, canvas, wpt, hit):
        if self.dragged is not None:
            if not self._drag_undo_begun:
                canvas.doc.begin_action()          # 首次移动才记撤销（整段拖动=1步）
                self._drag_undo_begun = True
            if isinstance(self.dragged, FreePoint):
                self.dragged.drag_to((wpt[0] + self.offset[0],
                                      wpt[1] + self.offset[1]))
            else:
                self.dragged.drag_to(wpt)
            canvas.doc.recompute_from(self.dragged)
        elif self.box_start is not None:
            self.box_end = wpt
            canvas.update()                        # 重绘选框

    def release(self, canvas, wpt, hit):
        if self.dragged is not None:
            if self._drag_undo_begun:
                canvas.doc.end_action()
            self.dragged = None
            self._drag_undo_begun = False
        elif self.box_start is not None:
            x0, x1 = sorted((self.box_start[0], self.box_end[0]))
            y0, y1 = sorted((self.box_start[1], self.box_end[1]))
            sel = [o for o in canvas.doc.objects
                   if _object_in_rect(o, x0, y0, x1, y1)]
            canvas.doc.set_selection(sel)
            self.box_start = None
            self.box_end = None

    def draw_overlay(self, p, view):
        """半透明选框"""
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