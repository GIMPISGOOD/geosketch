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
    _auto_label: str

    def __init__(self, parents=()):
        super().__init__(parents)
        self.x = 0.0
        self.y = 0.0
        self._auto_label = ""  # 自动标签（Document 内部使用，非用户自定义）

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


@register_renderer(AbstractPoint)
def draw_point(p, obj, view):
    """两种点共用：选中时放大换色，标签用数学排版（斜体大写字母）。"""
    qpt = view.to_screen(obj.x, obj.y)

    # ── 从设置读取点半径 ──
    s = getattr(view.doc, 'settings', None)
    if s is not None:
        r_sel = float(s.get("appearance.selected_point_radius", 6.0))
        r_def = float(s.get("appearance.default_point_radius", 4.0))
    else:
        r_sel, r_def = 6.0, 4.0
    r = r_sel if obj.selected else r_def

    p.setPen(theme.pen(theme.POINT_RING, 2))
    p.setBrush(theme.brush(theme.SELECTED if obj.selected else theme.POINT_FILL))
    p.drawEllipse(qpt, r, r)

    label = getattr(obj, "name", "") or getattr(obj, "_auto_label", "")
    if not label:
        label = f"P{obj.id}"

    # ── 标签字号受 math_scale 控制 ──
    if s is not None:
        math_scale = float(s.get("appearance.math_scale", 1.0))
    else:
        math_scale = 1.0
    label_size = int(13 * math_scale)

    draw_math(
        p,
        qpt.x() + 9,
        qpt.y() - 8,
        label,
        label_size,
        theme.SELECTED if obj.selected else theme.LABEL
    )


SNAP_PX = 18.0        # 磁吸半径默认值（屏幕像素）


def nearest_point(doc, scale, wpt, snap_px=None):
    """磁吸半径内离光标最近的点；无则返回 None。

    参数
    ----
    snap_px : float | None
        磁吸半径（屏幕像素）。为 None 时使用模块级 SNAP_PX。
    """
    if snap_px is None:
        snap_px = SNAP_PX
    tol = snap_px / scale
    best, best_d = None, tol
    for obj in doc.objects:
        if isinstance(obj, AbstractPoint) and obj.visible and obj.exists:
            d = obj.distance_to(*wpt)
            if d < best_d:
                best, best_d = obj, d
    return best