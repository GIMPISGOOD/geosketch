from core.registry import register_tool
from geo.points import FreePoint
from tools.base import Tool, snap_target
from ui.icons import icon_select


@register_tool(name="选择", shortcut="V", order=0, icon=icon_select,
               hint="拖动点移动整幅图（靠近点自动磁吸抓取）；Delete 级联删除")
class SelectTool(Tool):
    def __init__(self):
        self.dragged = None
        self.offset = (0.0, 0.0)

    def activated(self, canvas):
        self.dragged = None

    def press(self, canvas, wpt, hit):
        target = snap_target(canvas, wpt, hit)     # 磁吸：优先抓附近的点
        canvas.doc.set_selection([target] if target else [])
        self.dragged = target if getattr(target, "draggable", False) else None
        self.offset = (0.0, 0.0)
        if isinstance(self.dragged, FreePoint):
            # 记录光标与点心的偏移：拖动时点不会"跳"到光标上
            self.offset = (self.dragged.x - wpt[0], self.dragged.y - wpt[1])

    def move(self, canvas, wpt, hit):
        if self.dragged is None:
            return
        if isinstance(self.dragged, FreePoint):
            self.dragged.drag_to((wpt[0] + self.offset[0],
                                  wpt[1] + self.offset[1]))
        else:                                       # 吸附点：投影到宿主，无偏移概念
            self.dragged.drag_to(wpt) # pyright: ignore[reportAttributeAccessIssue]
        canvas.doc.recompute_from(self.dragged)

    def release(self, canvas, wpt, hit):
        self.dragged = None