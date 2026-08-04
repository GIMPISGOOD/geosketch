"""选择工具：点选/拖动/缩放/编辑；支持智能参考线（对齐吸附+红色虚线）。"""
from typing import Optional, Tuple, List
from PySide6.QtGui import QColor

from core.registry import register_tool
from geo.points import AbstractPoint, FreePoint, PointOnObject
from media.base import MediaObject
from tools.base import Tool, snap_target
from ui import theme


def _free_points_of(obj, acc, seen):
    if id(obj) in seen:
        return
    seen.add(id(obj))
    if isinstance(obj, FreePoint):
        acc.append(obj)
        return
    for p in obj.parents:
        _free_points_of(p, acc, seen)


@register_tool(name="选择", shortcut="V", order=0, icon="select",
               hint="点选对象；拖点/图形移动；靠近轴线或其他点时自动吸附对齐")
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
        self._guides: List[Tuple[str, float]] = []   # ★ 智能参考线

    def _detect_snap(self, canvas, x, y) -> Tuple[float, float, List[Tuple[str, float]]]:
        """检测对齐吸附：坐标轴 / 其他点。返回 (吸附后x, 吸附后y, 参考线列表)。"""
        THRESHOLD_PX = 12.0
        thresh_w = THRESHOLD_PX / canvas.scale
        
        best_dx, best_dy = thresh_w, thresh_w
        snap_x, snap_y = None, None
        guides = []
        
        # 1. 坐标轴吸附
        if abs(x) < best_dx:
            best_dx = abs(x)
            snap_x = 0.0
        if abs(y) < best_dy:
            best_dy = abs(y)
            snap_y = 0.0
            
        # 2. 其他点对齐
        for obj in canvas.doc.objects:
            if isinstance(obj, AbstractPoint) and obj.visible and obj.exists:
                if obj in self.drag_pts:
                    continue
                dx = abs(x - obj.x)
                if dx < best_dx:
                    best_dx = dx
                    snap_x = obj.x
                dy = abs(y - obj.y)
                if dy < best_dy:
                    best_dy = dy
                    snap_y = obj.y
                    
        if snap_x is not None:
            guides.append(('v', snap_x))
        if snap_y is not None:
            guides.append(('h', snap_y))
            
        return (snap_x if snap_x is not None else x,
                snap_y if snap_y is not None else y,
                guides)

    def press(self, canvas, wpt, hit):
        self._reset()
        target = snap_target(canvas, wpt, hit)
        if target is None:
            canvas.doc.set_selection([])
            return

        if isinstance(target, MediaObject):
            was_selected = target.selected
            canvas.doc.set_selection([target])
            if was_selected:
                sp = canvas.to_screen(wpt[0], wpt[1])
                if target.edit_button_rect(canvas).contains(sp):
                    target.edit(canvas)
                    self._reset()
                    return
                if target.resize_handle_rect(canvas).contains(sp):
                    self.resize_media = target
                    self._grab_wpt = wpt
                    return
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

        self._guides = []  # 每次移动清空参考线

        if self.resize_media is not None:
            self.resize_media.resize_to(wpt)
            canvas.doc.changed.emit()
            
        elif self.drag_media is not None and self._grab_wpt is not None:
            dx = wpt[0] - self._grab_wpt[0]
            dy = wpt[1] - self._grab_wpt[1]
            nx = self._media_orig[0] + dx
            ny = self._media_orig[1] + dy
            # ★ 媒体对象左上角吸附
            nx, ny, self._guides = self._detect_snap(canvas, nx, ny)
            self.drag_media.x = nx
            self.drag_media.y = ny
            canvas.doc.changed.emit()
            
        elif self.drag_poo is not None:
            self.drag_poo.drag_to(wpt)
            canvas.doc.recompute_from(self.drag_poo)
            
        elif self._grab_wpt is not None and self.drag_pts:
            dx = wpt[0] - self._grab_wpt[0]
            dy = wpt[1] - self._grab_wpt[1]
            base_p, base_ox, base_oy = self._orig_pos[0]
            nx = base_ox + dx
            ny = base_oy + dy
            # ★ 自由点吸附
            nx, ny, self._guides = self._detect_snap(canvas, nx, ny)
            actual_dx = nx - base_ox
            actual_dy = ny - base_oy
            for p, ox, oy in self._orig_pos:
                p.drag_to((ox + actual_dx, oy + actual_dy))
            canvas.doc.recompute_from([p for p, _, _ in self._orig_pos])

    def release(self, canvas, wpt, hit):
        if self._drag_undo_begun:
            canvas.doc.end_action()
        self._reset()

    def cancel(self, canvas):
        self._reset()

    def draw_overlay(self, p, view):
        # ★ 绘制智能参考线（红色虚线）
        if self._guides:
            p.setPen(theme.dashed_pen(QColor("#e03131"), 1.5))
            for g_type, val in self._guides:
                if g_type == 'v':  # 垂直线 (x = val)
                    p.drawLine(view.to_screen(val, -1000), view.to_screen(val, 1000))
                elif g_type == 'h':  # 水平线 (y = val)
                    p.drawLine(view.to_screen(-1000, val), view.to_screen(1000, val))