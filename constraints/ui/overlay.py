"""注入 Canvas：在 paintEvent 中绘制约束标记。"""
from ui.canvas import Canvas
from ui import theme
from PySide6.QtGui import QPainter, QPen, QFont

_original_paint = Canvas.paintEvent

def _new_paint(self, ev):
    _original_paint(self, ev)
    
    if not hasattr(self.doc, 'constraints') or not self.doc.constraints: 
        return
    
    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    font = QFont("Segoe UI Symbol", 12, QFont.Weight.Bold)
    p.setFont(font)
    p.setPen(QPen(theme.MEASURE, 2.0))
    
    for c in self.doc.constraints:
        pts = c.involved_points()
        if not pts: continue
        
        # 计算中心点
        cx = sum(pt.x for pt in pts) / len(pts)
        cy = sum(pt.y for pt in pts) / len(pts)
        sp = self.to_screen(cx, cy)
        
        # 根据约束类型绘制标记
        t = c.type_name
        marker = ""
        if t == "distance": marker = "↔"
        elif t == "horizontal": marker = "─"
        elif t == "vertical": marker = "│"
        elif t == "parallel": marker = "∥"
        elif t == "perpendicular": marker = "⊥"
        elif t == "angle": marker = "∠"
        elif t == "collinear": marker = "⋯"
        elif t == "fixed": marker = "📌"
        
        if marker:
            # 绘制背景白底防止看不清
            p.setPen(QPen(theme.BG_TOP, 4.0))
            p.drawText(sp.x() + 10, sp.y() - 10, marker)
            p.setPen(QPen(theme.MEASURE, 2.0))
            p.drawText(sp.x() + 10, sp.y() - 10, marker)
            
    p.end()

def patch_canvas():
    setattr(Canvas, "paintEvent", _new_paint)