"""注入 Canvas：在 paintEvent 中绘制约束参考线与锚点。"""
from ui.canvas import Canvas
from ui import theme
from PySide6.QtGui import QPainter

_original_paint = Canvas.paintEvent

def _new_paint(self, ev):
    _original_paint(self, ev)
    
    if not hasattr(self.doc, 'constraints') or not self.doc.constraints: 
        return
    
    p = QPainter(self)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    
    # 使用主题中的度量颜色画虚线
    pen = theme.dashed_pen(theme.MEASURE, 1.5)
    p.setPen(pen)
    p.setBrush(theme.brush(theme.MEASURE)) # 用于画端点小圆点
    
    for c in self.doc.constraints:
        if not getattr(c, 'enabled', True):
            continue
            
        pts = c.involved_points()
        if not pts:
            continue
            
        # 将涉及的对象转为屏幕坐标点
        screen_pts = []
        for pt in pts:
            if hasattr(pt, 'x') and hasattr(pt, 'y'):
                screen_pts.append(self.to_screen(pt.x, pt.y))
            elif hasattr(pt, 'a') and hasattr(pt, 'b'): # 兼容线段等
                mx = (pt.a.x + pt.b.x) / 2
                my = (pt.a.y + pt.b.y) / 2
                screen_pts.append(self.to_screen(mx, my))
                
        if len(screen_pts) >= 2:
            # 1. 画约束连线
            if len(screen_pts) == 3 and c.type_name == "angle":
                # 角度约束画 V 字形 (边1 -> 顶点 -> 边2)
                p.drawLine(screen_pts[0], screen_pts[1])
                p.drawLine(screen_pts[1], screen_pts[2])
            else:
                # 其他约束画首尾相连的线
                for i in range(len(screen_pts) - 1):
                    p.drawLine(screen_pts[i], screen_pts[i+1])
                
            # 2. 在涉及的关键点上画一个小实心圆，提示约束存在
            r = 3.0
            for sp in screen_pts:
                p.drawEllipse(sp, r, r)
                
    p.end()

def patch_canvas():
    setattr(Canvas, "paintEvent", _new_paint)