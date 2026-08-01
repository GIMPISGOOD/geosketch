"""选择工具：点选对象；拖点移动单点；点图形整体平移；多选后拖动整组移动。
吸附点（PointOnObject）优先级最高：点它就直接沿宿主图形滑动。
框选功能已独立为「框选」工具。"""
from core.registry import register_tool
from geo.points import AbstractPoint, FreePoint, PointOnObject
from tools.base import Tool, snap_target


def _free_points_of(obj, acc, seen):
    """收集对象依赖闭包中的全部自由点（整体拖动用）。
    派生点（中点/交点等）不收——它们由父对象决定，父对象移动后自动跟随。"""
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, FreePoint):
        acc.append(obj)
        return
    for p in obj.parents:
        _free_points_of(p, acc, seen)


@register_tool(name="选择", shortcut="V", order=0, icon="select",
               hint="点选对象；拖点移动，点图形整体移动；框选请用「框选」工具")
class SelectTool(Tool):
    def __init__(self):
        self._reset()

    def activated(self, canvas):
        self._reset()

    def _reset(self):
        self.drag_pts = []          # 偏移拖动的自由点（单个或一组）
        self.drag_poo = None        # 参数拖动的吸附点
        self._orig_pos = []
        self._grab_wpt = None
        self._drag_undo_begun = False

    def press(self, canvas, wpt, hit):
        self._reset()
        target = snap_target(canvas, wpt, hit)
        if target is None:
            canvas.doc.set_selection([])          # 空白处点击 = 取消选择
            return

        # ★ 吸附点优先级最高：无论是否处于多选，点它就直接沿宿主图形滑动
        if isinstance(target, PointOnObject):
            canvas.doc.set_selection([target])
            self.drag_poo = target
            self._grab_wpt = wpt
            self._orig_pos = []
            return

        selected = [o for o in canvas.doc.objects if o.selected]
        multi = (len(selected) > 1) and (target in selected)
        if multi:
            # 已框选多个对象：整体拖动其中全部自由点
            canvas.doc.set_selection(selected)
            pts, seen = [], set()
            for o in selected:
                _free_points_of(o, pts, seen)
            self.drag_pts = pts
        elif isinstance(target, FreePoint):
            canvas.doc.set_selection([target])
            self.drag_pts = [target]
        elif isinstance(target, AbstractPoint):
            # 派生点（中点/交点/等分点/顶点）：只选中，不拖动
            canvas.doc.set_selection([target])
        else:
            # 几何图形：整体平移（移动它的全部自由定义点）
            canvas.doc.set_selection([target])
            pts, seen = [], set()
            _free_points_of(target, pts, seen)
            self.drag_pts = pts
        self._grab_wpt = wpt
        self._orig_pos = [(p, p.x, p.y) for p in self.drag_pts]

    def move(self, canvas, wpt, hit):
        if self.drag_poo is None and not self.drag_pts:
            return
        if not self._drag_undo_begun:
            canvas.doc.begin_action()             # 首次移动才记撤销
            self._drag_undo_begun = True
        if self.drag_poo is not None:
            self.drag_poo.drag_to(wpt)            # 投影到宿主 → 沿图形滑动
            canvas.doc.recompute_from(self.drag_poo)
        else:
            dx = wpt[0] - self._grab_wpt[0]
            dy = wpt[1] - self._grab_wpt[1]
            for p, ox, oy in self._orig_pos:
                p.drag_to((ox + dx, oy + dy))
            canvas.doc.recompute_from([p for p, _, _ in self._orig_pos])

    def release(self, canvas, wpt, hit):
        if self._drag_undo_begun:
            canvas.doc.end_action()
        self._reset()

    def cancel(self, canvas):
        self._reset()