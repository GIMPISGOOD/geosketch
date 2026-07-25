"""两圆交点：一种特殊点。

身为 AbstractPoint 子类 → 磁吸、拾取、渲染、级联删除自动继承；
不可拖动（位置由两圆完全决定）；无解时 exists=False 自动隐身。
两圆有两个交点 → 按分支 0/1 各建一个对象。
"""
import math

from PySide6.QtCore import QPointF, Qt

from core.registry import register_geo, register_renderer
from geo.points import AbstractPoint
from ui import theme


@register_geo("CircleIntersect")
class CircleIntersectPoint(AbstractPoint):
    """两圆交点中的一个（branch=0 / 1）。"""

    def __init__(self, c1, c2, branch: int = 0):
        super().__init__(parents=(c1, c2))
        self.c1, self.c2 = c1, c2
        self.branch = branch
        self.recompute()

    def recompute(self) -> None:
        c1, c2 = self.c1, self.c2
        dx, dy = c2.center.x - c1.center.x, c2.center.y - c1.center.y
        d = math.hypot(dx, dy)
        # 无解：同心 / 相离 / 内含（含浮点容差）
        if d < 1e-12 or d > c1.r + c2.r + 1e-9 or d < abs(c1.r - c2.r) - 1e-9:
            self.exists = False
            return
        a = (c1.r * c1.r - c2.r * c2.r + d * d) / (2.0 * d)
        h = math.sqrt(max(c1.r * c1.r - a * a, 0.0))
        mx, my = c1.center.x + a * dx / d, c1.center.y + a * dy / d
        sign = 1.0 if self.branch == 0 else -1.0   # 固定分支 → 拖动时轨迹连续不跳变
        self.x = mx + sign * h * dy / d
        self.y = my - sign * h * dx / d
        self.exists = True

    def dump(self) -> dict:
        return {"branch": self.branch}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], params.get("branch", 0))


# 专属渲染器：MRO 查找优先于 AbstractPoint 的通用画法
@register_renderer(CircleIntersectPoint)
def draw_intersect(p, obj, view):
    """空心环 + 中心点（青蓝），与自由点的实心琥珀区分；标注 X{id}。"""
    qpt = view.to_screen(obj.x, obj.y)
    color = theme.SELECTED if obj.selected else theme.INTERSECT
    r = 5.5 if obj.selected else 4.5
    p.setPen(theme.pen(color, 2.0))
    p.setBrush(theme.brush(theme.BG_TOP))      # 填背景色 → 空心观感
    p.drawEllipse(qpt, r, r)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(qpt, 1.8, 1.8)
    p.setPen(theme.pen(theme.LABEL))
    p.setFont(theme.LABEL_FONT)
    p.drawText(qpt + QPointF(9, -8), f"X{obj.id}")