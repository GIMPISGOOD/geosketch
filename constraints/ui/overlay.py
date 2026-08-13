"""注入 Canvas：在 paintEvent 中绘制约束标记。"""
from ui.canvas import Canvas
from ui import theme

_original_paint = Canvas.paintEvent

def _new_paint(self, ev):
    _original_paint(self, ev)
    # 在原绘制结束后，追加约束标记
    if not hasattr(self.doc, 'constraints') or not self.doc.constraints: return
    
    from PySide6.QtGui import QPainter, QPen
    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(theme.MEASURE, 1.5))
    p.setFont(theme.LABEL_FONT)
    
    for c in self.doc.constraints:
        pts = c.involved_points()
        if len(pts) >= 2:
            sp1 = self.to_screen(pts[0].x, pts[0].y)
            sp2 = self.to_screen(pts[1].x, pts[1].y)
            p.drawLine(sp1, sp2)
            mx, my = (sp1.x() + sp2.x())/2, (sp1.y() + sp2.y())/2
            p.drawText(mx + 5, my - 5, c.type_name)
    p.end()

def patch_canvas():
    setattr(Canvas, "paintEvent", _new_paint)