"""选择工具：点选/拖动/缩放/编辑；支持智能参考线（对齐吸附+红色虚线）。
★ 原生集成约束求解（原 constraints/select_ext 猴子补丁已移除）。
"""
from typing import Optional, Tuple, List

from PySide6.QtGui import QColor
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from core.registry import register_tool
from geo.points import AbstractPoint, FreePoint, PointOnObject
from media.base import MediaObject
from tools.base import Tool, snap_target
from ui import theme

import math
import time


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
        self._script_timer = None

    def _reset(self):
        self.drag_pts: list[FreePoint] = []
        self.drag_poo: Optional[PointOnObject] = None
        self.drag_media: Optional[MediaObject] = None
        self.resize_media: Optional[MediaObject] = None
        self.rotate_media: Optional[MediaObject] = None
        self._media_orig: Tuple[float, float] = (0.0, 0.0)
        self._orig_pos: list[Tuple[FreePoint, float, float]] = []
        self._grab_wpt: Optional[Tuple[float, float]] = None
        self._drag_undo_begun = False
        self._guides: List[Tuple[str, float]] = []
        self._click_media = None
        self._press_wpt = None
        self._moved = False
        self._snap_mem = (None, None)      # 滞回记忆：当前吸附的 (x目标, y目标)
        self._snap_excl_ids = set()        # 吸附排除集：点的 id()
        self._last_wpt: Optional[Tuple[float, float]] = None
        self._last_solve_t: float = 0.0
        

    def cancel_pending_script(self):
        if self._script_timer is not None:
            self._script_timer.stop()
            self._script_timer = None
            
    def _build_snap_exclusion(self, canvas):
        """构建对齐吸附排除集：
        ① 被拖对象所在连通分量内的所有点（防止自吸附）；
        ② 与被拖点存在约束耦合的所有点（它们每帧被求解器移动，
           移动的吸附目标会造成反馈震荡）。
        """
        seeds = list(self.drag_pts)
        if self.drag_poo is not None:
            seeds.append(self.drag_poo)
        if not seeds:
            self._snap_excl_ids = set()
            return
        # ① 对象图双向 BFS（parents + children）
        seen = set()
        objs = []
        stack = list(seeds)
        while stack:
            o = stack.pop()
            if id(o) in seen:
                continue
            seen.add(id(o))
            objs.append(o)
            stack.extend(getattr(o, "parents", []) or [])
            stack.extend(getattr(o, "children", []) or [])
        excl = {id(o) for o in objs if isinstance(o, AbstractPoint)}
        # ② 约束耦合的点
        try:
            from constraints.graph import get_affected_constraints
            cons = getattr(canvas.doc, "constraints", None) or []
            if cons:
                for c in get_affected_constraints(seeds, cons):
                    for p in c.involved_points():
                        if isinstance(p, AbstractPoint):
                            excl.add(id(p))
        except Exception:
            pass
        self._snap_excl_ids = excl
        
    def _detect_snap(self, canvas, x, y):
        """对齐吸附（红色参考线）。
        ★ 升级版：
        ① 受设置 interaction.guide_snap_enabled 控制（默认关），
           且同时受 interaction.snap_enabled 总开关约束；
        ② 滞回：12px 吸上、16px 以外才释放，消除阈值边界高频翻转；
        ③ 排除被拖分量内与约束耦合的点（防自吸、防移动目标反馈震荡）。
        """
        s = canvas.doc.settings
        if (not s.get("interaction.guide_snap_enabled", False)
                or not s.get("interaction.snap_enabled", True)):
            self._snap_mem = (None, None)
            return x, y, []

        engage = 12.0 / canvas.scale
        release = 16.0 / canvas.scale
        excl = self._snap_excl_ids

        cand_x = [0.0]   # 坐标轴始终保留为候选
        cand_y = [0.0]
        for obj in canvas.doc.objects:
            if (isinstance(obj, AbstractPoint)
                    and obj.visible and obj.exists
                    and id(obj) not in excl):
                cand_x.append(obj.x)
                cand_y.append(obj.y)

        mem_x, mem_y = self._snap_mem

        def _pick(v, cands, mem):
            if mem is not None and abs(v - mem) < release:
                return mem
            best, best_d = None, engage
            for c in cands:
                d = abs(v - c)
                if d < best_d:
                    best, best_d = c, d
            return best

        snap_x = _pick(x, cand_x, mem_x)
        snap_y = _pick(y, cand_y, mem_y)
        self._snap_mem = (snap_x, snap_y)

        guides = []
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
        from media.script_button import ScriptButtonObject
        if isinstance(target, MediaObject):
            was_selected = target.selected
            canvas.doc.set_selection([target])
            if was_selected:
                sp = canvas.to_screen(wpt[0], wpt[1])
                if getattr(target, "rotatable", False):
                    rr = target.rotate_handle_rect(canvas)
                    if rr.width() > 0 and rr.contains(sp):
                        self.rotate_media = target
                        self._grab_wpt = wpt
                        return
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
            if isinstance(target, ScriptButtonObject):
                self._click_media = target
                self._press_wpt = wpt
                self._moved = False
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
        self._build_snap_exclusion(canvas)
        
    def move(self, canvas, wpt, hit):
        if (self.drag_poo is None and not self.drag_pts
                and self.drag_media is None and self.resize_media is None
                and self.rotate_media is None):
            return
        if self._click_media is not None and self._press_wpt is not None:
            dx = wpt[0] - self._press_wpt[0]
            dy = wpt[1] - self._press_wpt[1]
            if math.hypot(dx, dy) > 5.0 / canvas.scale:
                self._moved = True
            elif not self._moved:
                return
        if not self._drag_undo_begun:
            canvas.doc.begin_action()
            self._drag_undo_begun = True
        self._guides = []
        # 帧间位移（供步长钳制使用）
        frame_delta = 0.0
        if self._last_wpt is not None:
            frame_delta = math.hypot(wpt[0] - self._last_wpt[0],
                                     wpt[1] - self._last_wpt[1])
        self._last_wpt = wpt

        if self.rotate_media is not None:
            center = self.rotate_media.screen_rect(canvas).center()
            cur = canvas.to_screen(wpt[0], wpt[1])
            ang = math.degrees(
                math.atan2(cur.y() - center.y(), cur.x() - center.x()))
            ang += 90.0
            self.rotate_media.rotation = (ang + 360.0) % 360.0
            canvas.doc.changed.emit()
            return
        if self.resize_media is not None:
            self.resize_media.resize_to(wpt)
            canvas.doc.changed.emit()
        elif self.drag_media is not None and self._grab_wpt is not None:
            dx = wpt[0] - self._grab_wpt[0]
            dy = wpt[1] - self._grab_wpt[1]
            nx = self._media_orig[0] + dx
            ny = self._media_orig[1] + dy
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
            nx, ny, self._guides = self._detect_snap(canvas, nx, ny)
            actual_dx = nx - base_ox
            actual_dy = ny - base_oy
            for p, ox, oy in self._orig_pos:
                p.drag_to((ox + actual_dx, oy + actual_dy))
            canvas.doc.recompute_from([p for p, _, _ in self._orig_pos])

        # ★ v2：拖动约束求解（帧节流 + 拖动连续模式 + 步长钳制）
        self._solve_drag(canvas, frame_delta)

    def _solve_drag(self, canvas, frame_delta):
        """拖动时的约束求解（v2）。
        ① 帧节流：每 8ms 至多一次求解（首次 move 必解，_last_solve_t=0）；
        ② drag_mode：Tikhonov 时间连续 + λ 热启动（抑制抖动）；
        ③ max_step：单帧步长 ≤ 4×帧间拖动距离，防跳变。
        """
        doc = canvas.doc
        if not getattr(doc, "constraints", None):
            return
        dragged = set()
        if self.drag_poo is not None:
            dragged.add(self.drag_poo)
        for p in self.drag_pts:
            dragged.add(p)
        if not dragged:
            return
        now = time.perf_counter()
        if self._last_solve_t > 0.0 and now - self._last_solve_t < 0.008:
            return
        self._last_solve_t = now
        try:
            doc.solve_constraints(
                trigger_points=list(dragged),
                pinned_points=list(dragged),
                quick=True,
                drag_mode=True,
                max_step=4.0 * frame_delta + 1e-3,
            )
        except Exception:
            pass

    def release(self, canvas, wpt, hit):
        if self._click_media is not None and not self._moved:
            from media.script_button import ScriptButtonObject
            if isinstance(self._click_media, ScriptButtonObject):
                btn = self._click_media
                self.cancel_pending_script()
                self._script_timer = QTimer()
                self._script_timer.setSingleShot(True)
                interval = max(200, QApplication.doubleClickInterval())
                self._script_timer.setInterval(interval)
                self._script_timer.timeout.connect(
                    lambda: btn.run(canvas))
                self._script_timer.start()
        if self._drag_undo_begun:
            from core.macro import get_macro_manager
            mm = get_macro_manager()
            if mm is not None and mm.is_recording():
                if self.drag_poo is not None:
                    mm.recorder.record_move(self.drag_poo)
                for p in self.drag_pts:
                    mm.recorder.record_move(p)
                if self.drag_media is not None:
                    mm.recorder.record_move(self.drag_media)
                if self.resize_media is not None:
                    mm.recorder.record_move(self.resize_media)
                if self.rotate_media is not None:
                    mm.recorder.record_move(self.rotate_media)
            canvas.doc.end_action()

        doc = canvas.doc
        if hasattr(doc, 'constraints') and doc.constraints:
            dragged = set()
            if self.drag_poo is not None:
                dragged.add(self.drag_poo)
            for p in self.drag_pts:
                dragged.add(p)
            if self.drag_media is not None:
                dragged.add(self.drag_media)
            try:
                if dragged:
                    doc.solve_constraints(
                        trigger_points=list(dragged),
                        pinned_points=list(dragged),
                        quick=False,
                    )
                else:
                    doc.solve_constraints(quick=False)
            except Exception:
                pass
        self._reset()

    def activated(self, canvas):
        self.cancel_pending_script()
        self._reset()

    def deactivated(self, canvas):
        self.cancel_pending_script()
        self._reset()

    def cancel(self, canvas):
        self._reset()

    def draw_overlay(self, p, view):
        if self._guides:
            p.setPen(theme.dashed_pen(QColor("#e03131"), 1.5))
            for g_type, val in self._guides:
                if g_type == 'v':
                    p.drawLine(view.to_screen(val, -1000),
                               view.to_screen(val, 1000))
                elif g_type == 'h':
                    p.drawLine(view.to_screen(-1000, val),
                               view.to_screen(1000, val))