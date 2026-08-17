"""SelectTool 补丁：拖动时触发约束求解。"""
from tools.select import SelectTool

_original_move = SelectTool.move
_original_release = SelectTool.release


def _new_move(self, canvas, wpt, hit):
    _original_move(self, canvas, wpt, hit)
    doc = canvas.doc
    if not hasattr(doc, 'constraints') or not doc.constraints:
        return
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
                quick=True,
            )
        except Exception:
            pass


def _new_release(self, canvas, wpt, hit):
    _original_release(self, canvas, wpt, hit)
    doc = canvas.doc
    if hasattr(doc, 'constraints') and doc.constraints:
        try:
            doc.solve_constraints(quick=False)
        except Exception:
            pass


def patch_select_tool():
    setattr(SelectTool, "move", _new_move)
    setattr(SelectTool, "release", _new_release)