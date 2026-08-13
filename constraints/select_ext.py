"""SelectTool 补丁：拖动时触发约束求解。"""
from tools.select import SelectTool

_original_move = SelectTool.move
_original_release = SelectTool.release


def _new_move(self, canvas, wpt, hit):
    # 先执行原有的拖动逻辑（移动点）
    _original_move(self, canvas, wpt, hit)

    # ★ 拖动后触发约束求解
    doc = canvas.doc
    if not hasattr(doc, 'constraints') or not doc.constraints:
        return

    # 收集正在被拖动的点作为 pinned（它们跟随鼠标，不被约束移动）
    pinned = []
    if self.drag_poo is not None:
        pinned.append(self.drag_poo)
    for p in self.drag_pts:
        pinned.append(p)
    if self.drag_media is not None:
        pinned.append(self.drag_media)

    if pinned:
        try:
            doc.solve_constraints(
                trigger_points=pinned,
                pinned_points=pinned,
            )
        except Exception:
            pass  # 约束求解失败不应阻断拖动


def _new_release(self, canvas, wpt, hit):
    _original_release(self, canvas, wpt, hit)


def patch_select_tool():
    setattr(SelectTool, "move", _new_move)
    setattr(SelectTool, "release", _new_release)