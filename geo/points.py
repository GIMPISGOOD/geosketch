"""几何点对象库：自由点、吸附点，以及磁吸查询。

分层铁律 —— 本模块位于依赖链底层：
    points ──→ base          （只向下依赖）
    ✗ base 反向导入 points    （会循环导入）

对外契约（其他文件依赖下列名字，重构不得改动）：
    AbstractPoint · FreePoint · PointOnObject · nearest_point · SNAP_PX
"""
import math

from PySide6.QtCore import QPointF

from core.registry import register_geo, register_renderer
from geo.base import GeoObject
from ui import theme
from ui.math import draw_math


class AbstractPoint(GeoObject):
    """点的公共基类：带坐标、可拾取。渲染器注册在它身上，两种点共用。"""

    x: float
    y: float

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


# ───────────────────────────── 命名 ─────────────────────────────
def _index_to_letters(n):
    """序号 → 大写字母：1→A, 2→B, …, 26→Z, 27→AA。"""
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(ord('A') + r) + s
    return s


def _index_to_subscript(n):
    """序号 → Unicode 下标：1→₁, 12→₁₂。"""
    return ''.join(chr(0x2080 + int(d)) for d in str(n))


def _point_label(obj, view):
    """点名：圆心点 → O₁/O₂…；其余点 → A/B/C…（大写）。
    序号按 id 升序在同类中动态计算，删除/撤销后自动重排。"""
    doc = view.doc
    center_ids = set()
    for o in doc.objects:
        if type(o).__name__ == 'Circle':
            c = getattr(o, 'center', None)
            if isinstance(c, AbstractPoint):
                center_ids.add(id(c))
    is_center = id(obj) in center_ids
    idx = 1
    for o in doc.objects:
        if not isinstance(o, AbstractPoint):
            continue
        if (id(o) in center_ids) != is_center:
            continue
        if o is obj:
            break
        idx += 1
    return ("O" + _index_to_subscript(idx)) if is_center else _index_to_letters(idx)


# ───────────────────────────── 渲染 ─────────────────────────────
@register_renderer(AbstractPoint)
def draw_point(p, obj, view):
    """两种点共用：选中时放大换色，标签用数学排版（斜体大写字母）。"""
    qpt = view.to_screen(obj.x, obj.y)
    r = 6.0 if obj.selected else 4.0
    p.setPen(theme.pen(theme.POINT_RING, 2))
    p.setBrush(theme.brush(theme.SELECTED if obj.selected else theme.POINT_FILL))
    p.drawEllipse(qpt, r, r)
    # ★ 优先使用对象名；没有名字时回退到旧规则
    label = getattr(obj, "name", "") or _point_label(obj, view)

    draw_math(
        p,
        qpt.x() + 9,
        qpt.y() - 8,
        label,
        13,
        theme.SELECTED if obj.selected else theme.LABEL
    )


# ───────────────────────────── 磁吸 ─────────────────────────────
SNAP_PX = 18.0        # 磁吸半径（屏幕像素）：手感恒定，世界半径 = SNAP_PX / scale


def nearest_point(doc, scale, wpt):
    """磁吸半径内离光标最近的点；无则返回 None。"""
    tol = SNAP_PX / scale
    best, best_d = None, tol
    for obj in doc.objects:
        if isinstance(obj, AbstractPoint) and obj.visible and obj.exists:
            d = obj.distance_to(*wpt)
            if d < best_d:
                best, best_d = obj, d
    return best