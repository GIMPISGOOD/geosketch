"""墨迹注释：自由手绘笔画，支持钢笔/荧光笔/铅笔。"""
import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainterPath

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme


@register_geo("InkStroke")
class InkStroke(GeoObject):
    """一条手绘笔画：世界坐标点列 + 颜色/线宽/透明度/笔型。"""
    def __init__(self, points, color="#222222", width=2.5, opacity=1.0, mode="pen"):
        super().__init__(parents=())
        self.points = list(points)      # [(x, y), ...] 世界坐标
        self.color = color
        self.width = width
        self.opacity = opacity
        self.mode = mode                # pen / highlighter / pencil

    def distance_to(self, x, y):
        best = float("inf")
        pts = self.points
        for i in range(len(pts) - 1):
            x1, y1 = pts[i]
            x2, y2 = pts[i + 1]
            dx, dy = x2 - x1, y2 - y1
            denom = dx * dx + dy * dy
            t = 0.0 if denom == 0 else max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / denom))
            best = min(best, math.hypot(x1 + t * dx - x, y1 + t * dy - y))
        return best

    def dump(self):
        return {"points": self.points, "color": self.color, "width": self.width,
                "opacity": self.opacity, "mode": self.mode}

    @classmethod
    def build(cls, parents, params):
        return cls(params["points"], params.get("color", "#222222"),
                   params.get("width", 2.5), params.get("opacity", 1.0),
                   params.get("mode", "pen"))


@register_renderer(InkStroke)
def draw_ink(p, obj, view):
    if len(obj.points) < 2:
        return
    c = QColor(obj.color)
    c.setAlphaF(obj.opacity)
    # 荧光笔：粗 + 半透明 + 圆头；铅笔：细 + 略透明；钢笔：标准
    if obj.mode == "highlighter":
        pen = theme.pen(c, obj.width * 3.5)
    elif obj.mode == "pencil":
        c2 = QColor(c); c2.setAlphaF(obj.opacity * 0.75)
        pen = theme.pen(c2, max(1.0, obj.width * 0.7))
    else:
        pen = theme.pen(c, obj.width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    path = QPainterPath()
    path.moveTo(view.to_screen(*obj.points[0]))
    for pt in obj.points[1:]:
        path.lineTo(view.to_screen(*pt))
    p.drawPath(path)