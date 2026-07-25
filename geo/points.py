import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme


class AbstractPoint(GeoObject):
    """点的公共基类：带坐标、可拾取。渲染器注册在它身上，两种点共用。"""
    def __init__(self, parents=()):
        super().__init__(parents)
        self.x = 0.0
        self.y = 0.0

    def distance_to(self, x, y):
        return math.hypot(self.x - x, self.y - y)


@register_geo("FreePoint")
class FreePoint(AbstractPoint):
    """自由点：平面上任意拖动。"""
    draggable = True

    def __init__(self, x, y):
        super().__init__()
        self.x, self.y = x, y

    def drag_to(self, wpt):
        self.x, self.y = wpt

    def dump(self):
        return {"x": self.x, "y": self.y}

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"])


@register_geo("PointOnObject")
class PointOnObject(AbstractPoint):
    """吸附点：钉在宿主对象上，用参数 t ∈ [0,1] 描述位置。
    只要宿主实现了 point_at / project，吸附、沿宿主拖动全部自动生效。"""
    draggable = True

    def __init__(self, host, t=0.5):
        super().__init__(parents=[host])
        self.host = host
        self.t = t
        self.recompute()

    def recompute(self):
        self.x, self.y = self.host.point_at(self.t)

    def drag_to(self, wpt):
        self.t = self.host.project(*wpt)

    def dump(self):
        return {"t": self.t}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], params["t"])


# ---------- 渲染器：注册在基类上，FreePoint / PointOnObject 经 MRO 共用 ----------
@register_renderer(AbstractPoint)
def draw_point(p, obj, view):
    qpt = view.to_screen(obj.x, obj.y)
    r = 6.0 if obj.selected else 4.0
    p.setPen(theme.pen(theme.POINT_RING, 2))
    p.setBrush(theme.brush(theme.SELECTED if obj.selected else theme.POINT_FILL))
    p.drawEllipse(qpt, r, r)
    p.setPen(theme.pen(theme.LABEL))
    p.setFont(theme.LABEL_FONT)
    p.drawText(qpt + QPointF(9, -8), f"P{obj.id}")

SNAP_PX = 18.0        # 磁吸半径：18 屏幕像素（想改手感只动这一个值）

def nearest_point(doc, scale: float, wpt):
    """磁吸半径内离光标最近的已有点；没有则返回 None。

    世界半径 = SNAP_PX / scale：屏幕上恒定 18px，
    随坐标系缩放自动换算——放大则世界半径收缩，缩小则扩张。
    """
    tol = SNAP_PX / scale
    best, best_d = None, tol
    for obj in doc.objects:
        if isinstance(obj, AbstractPoint) and obj.visible and obj.exists:
            d = math.hypot(obj.x - wpt[0], obj.y - wpt[1])
            if d < best_d:
                best, best_d = obj, d
    return best