"""注入 SelectTool：在拖动时触发约束求解。"""
from tools.select import SelectTool

_original_move = SelectTool.move

def _new_move(self, canvas, wpt, hit):
    _original_move(self, canvas, wpt, hit)
    # 如果正在拖动 FreePoint，将其作为 pinned_points 传入求解器
    if self.drag_pts and hasattr(canvas.doc, 'solve_constraints'):
        canvas.doc.solve_constraints(
            trigger_points=self.drag_pts, 
            pinned_points=self.drag_pts
        )

def patch_select_tool():
    SelectTool.move = _new_move