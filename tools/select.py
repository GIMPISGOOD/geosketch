"""选择工具：点选对象；拖点移动，点图形整体移动；媒体对象可缩放/编辑。"""
from typing import Optional, Tuple

from core.registry import register_tool
from geo.points import AbstractPoint, FreePoint, PointOnObject
from media.base import MediaObject
from tools.base import Tool, snap_target


def _free_points_of(obj, acc, seen):
    """收集对象依赖闭包中的全部自由点（整体拖动用）。"""
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, FreePoint):
        acc.append(obj)
        return
    for p in obj.parents:
        _free_points_of(p, acc, seen)


@register_tool(name="选择", shortcut="V", order=0, icon="select",
               hint="点选对象；拖点移动，点图形整体移动；媒体对象可缩放/编辑")
class SelectTool(Tool):
    def __init__(self):
        self._reset()

    def activated(self, canvas):
        self._reset()

    def _reset(self):
        self.drag_pts: list[FreePoint] = []
        self.drag_poo: Optional[PointOnObject] = None
        self.drag_media: Optional[MediaObject] = None
        self.resize_media: Optional[MediaObject] = None
        self._media_orig: Tuple[float, float] = (0.0, 0.0)
        self._orig_pos: list[Tuple[FreePoint, float, float]] = []
        self._grab_wpt: Optional[Tuple[float, float]] = None
        self._drag_undo_begun = False

    def press(self, canvas, wpt, hit):
        self._reset()
        target = snap_target(canvas, wpt, hit)
        if target is None:
            canvas.doc.set_selection([])
            return

        # ── 媒体对象：编辑按钮 / 缩放手柄 / 移动 ──
        if isinstance(target, MediaObject):
            was_selected = target.selected
            canvas.doc.set_selection([target])
            if was_selected:
                sp = canvas.to_screen(wpt[0], wpt[1])
                # 点中右上角 ✎ 按钮 → 编辑
                if target.edit_button_rect(canvas).contains(sp):
                    target.edit(canvas)
                    self._reset()
                    return
                # 点中右下角手柄 → 缩放
                if target.resize_handle_rect(canvas).contains(sp):
                    self.resize_media = target
                    self._grab_wpt = wpt
                    return
            # 否则 → 拖动移动
            self.drag_media = target
            self._media_orig = (target.x, target.y)
            self._grab_wpt = wpt
            return

        selected = [o for o in canvas.doc.objects if o.selected]
        multi = (len(selected) > 1) and (target in selected)
        if multi:
            canvas.doc.set_selection(selected)
            pts: list[FreePoint] = []
            seen = set()
            for o in selected:
                _free_points_of(o, pts, seen)
            self.drag_pts = pts
        elif isinstance(target, PointOnObject):
            canvas.doc.set_selection([target])
            self.drag_poo = target
        elif isinstance(target, FreePoint):
            canvas.doc.set_selection([target])
            self.drag_pts = [target]
        elif isinstance(target, AbstractPoint):
            canvas.doc.set_selection([target])
        else:
            canvas.doc.set_selection([target])
            pts = []
            seen = set()
            _free_points_of(target, pts, seen)
            self.drag_pts = pts
            
        self._grab_wpt = wpt
        self._orig_pos = [(p, p.x, p.y) for p in self.drag_pts]

    def move(self, canvas, wpt, hit):
        if (self.drag_poo is None and not self.drag_pts
                and self.drag_media is None and self.resize_media is None):
            return
        if not self._drag_undo_begun:
            canvas.doc.begin_action()
            self._drag_undo_begun = True

        if self.resize_media is not None:
            self.resize_media.resize_to(wpt)
            canvas.doc.changed.emit()
        elif self.drag_media is not None and self._grab_wpt is not None:
            dx = wpt[0] - self._grab_wpt[0]
            dy = wpt[1] - self._grab_wpt[1]
            self.drag_media.x = self._media_orig[0] + dx
            self.drag_media.y = self._media_orig[1] + dy
            canvas.doc.changed.emit()
        elif self.drag_poo is not None:
            self.drag_poo.drag_to(wpt)
            canvas.doc.recompute_from(self.drag_poo)
        elif self._grab_wpt is not None:
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