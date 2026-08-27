"""轨迹追踪插件 —— 独立于动画系统。

核心改进：
  1. 自适应弧长采样：点每移动 min_dist 就记录，帧间大位移自动插值
  2. Catmull-Rom 样条渲染：彻底消除折线感
  3. 不依赖动画播放：拖动、脚本、约束求解均能触发记录
  4. 作为标准几何对象参与序列化 / 撤销 / 级联删除
"""
import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainterPath

from core.registry import register_geo, register_renderer, register_tool
from geo.base import GeoObject
from geo.points import AbstractPoint
from tools.base import Tool
from ui import theme


# ═══════════════════════════════════════════════════════
#  几何对象
# ═══════════════════════════════════════════════════════

@register_geo("TraceCurve")
class TraceCurve(GeoObject):
    """轨迹曲线：追踪父点的运动路径，自适应弧长采样。"""

    def __init__(self, point, color="#e03131", width=1.8):
        super().__init__(parents=[point])
        self.point = point
        self.color = color
        self.width = width
        self.min_dist = 0.12          # 最小采样步长（世界坐标）
        self.max_points = 6000        # 最大点数（防止内存膨胀）
        self.points: list[tuple] = [(point.x, point.y)]
        self._last_pos = (point.x, point.y)

    # ── 核心：父点移动时自动记录 ──────────────────────

    def recompute(self):
        """级联更新时调用。弧长超过阈值 → 记录（含帧间插值）。"""
        if not self.point.exists:
            return
        x, y = self.point.x, self.point.y
        dx = x - self._last_pos[0]
        dy = y - self._last_pos[1]
        dist = math.hypot(dx, dy)
        if dist < self.min_dist:
            return
        # 帧间大位移 → 线性插值补点，保证采样密度
        n_steps = max(1, int(dist / self.min_dist))
        for i in range(1, n_steps + 1):
            t = i / n_steps
            self.points.append((
                self._last_pos[0] + dx * t,
                self._last_pos[1] + dy * t,
            ))
        self._last_pos = (x, y)
        # 限制总点数
        if len(self.points) > self.max_points:
            self.points = self.points[-self.max_points:]

    def clear(self):
        """清除历史，从当前位置重新开始。"""
        if self.point.exists:
            self.points = [(self.point.x, self.point.y)]
            self._last_pos = (self.point.x, self.point.y)
        else:
            self.points = []

    # ── 拾取 ──────────────────────────────────────────

    def distance_to(self, x, y):
        if len(self.points) < 2:
            return None
        best = float('inf')
        for i in range(len(self.points) - 1):
            x1, y1 = self.points[i]
            x2, y2 = self.points[i + 1]
            d = _pt_seg_dist(x, y, x1, y1, x2, y2)
            if d < best:
                best = d
        return best

    # ── 序列化 ────────────────────────────────────────

    def dump(self):
        return {
            "color": self.color,
            "width": self.width,
            "min_dist": self.min_dist,
            "max_points": self.max_points,
            "points": self.points,
        }

    @classmethod
    def build(cls, parents, params):
        obj = cls(parents[0],
                  color=params.get("color", "#e03131"),
                  width=params.get("width", 1.8))
        obj.min_dist = params.get("min_dist", 0.12)
        obj.max_points = params.get("max_points", 6000)
        obj.points = [tuple(p) for p in params.get("points", [])]
        if obj.points:
            obj._last_pos = obj.points[-1]
        return obj


# ═══════════════════════════════════════════════════════
#  渲染器（Catmull-Rom 样条 → 光滑曲线）
# ═══════════════════════════════════════════════════════

@register_renderer(TraceCurve)
def draw_trace(p, obj, view):
    pts = obj.points
    if len(pts) < 2:
        return

    color = QColor(obj.color) if isinstance(obj.color, str) else obj.color
    selected = getattr(obj, 'selected', False)
    pen_color = theme.SELECTED if selected else color
    p.setPen(theme.pen(pen_color, obj.width))
    p.setBrush(Qt.BrushStyle.NoBrush)

    path = _catmull_rom_path(pts, view)
    p.drawPath(path)

    # 终点圆点
    last = view.to_screen(pts[-1][0], pts[-1][1])
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(theme.brush(color))
    p.drawEllipse(last, 3.0, 3.0)


def _catmull_rom_path(pts, view, tension=1.0):
    """Catmull-Rom → Cubic Bézier，输出 QPainterPath。"""
    n = len(pts)
    path = QPainterPath()
    s0 = view.to_screen(pts[0][0], pts[0][1])
    path.moveTo(s0)

    if n == 2:
        s1 = view.to_screen(pts[1][0], pts[1][1])
        path.lineTo(s1)
        return path

    for i in range(n - 1):
        p0 = pts[max(i - 1, 0)]
        p1 = pts[i]
        p2 = pts[i + 1]
        p3 = pts[min(i + 2, n - 1)]

        # Catmull-Rom 切线 → Bézier 控制点
        t6 = 6.0 * tension
        c1x = p1[0] + (p2[0] - p0[0]) / t6
        c1y = p1[1] + (p2[1] - p0[1]) / t6
        c2x = p2[0] - (p3[0] - p1[0]) / t6
        c2y = p2[1] - (p3[1] - p1[1]) / t6

        path.cubicTo(
            view.to_screen(c1x, c1y),
            view.to_screen(c2x, c2y),
            view.to_screen(p2[0], p2[1]),
        )
    return path


def _pt_seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    denom = dx * dx + dy * dy
    if denom < 1e-12:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / denom))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


# ═══════════════════════════════════════════════════════
#  工具
# ═══════════════════════════════════════════════════════

@register_tool("轨迹追踪", shortcut=None, order=200,
               hint="点击一个点以追踪其运动轨迹（拖动/动画/脚本均可触发）",
               icon="fa5s.route", panel="menu")
class TraceTool(Tool):
    """点击一个点 → 创建 TraceCurve 追踪其运动。再次点击同一点 → 重置。"""

    def activated(self, canvas):
        canvas.cursor_info.emit("🎯 点击一个点以开始追踪轨迹")

    def press(self, canvas, wpt, hit):
        if not isinstance(hit, AbstractPoint):
            canvas.cursor_info.emit("请点击一个点")
            return

        # 若该点已有轨迹 → 清除重来
        for obj in canvas.doc.objects:
            if isinstance(obj, TraceCurve) and obj.point is hit:
                obj.clear()
                canvas.cursor_info.emit("🔄 轨迹已重置，继续追踪")
                canvas.update()
                return

        # 自动分配颜色
        palette = ["#e03131", "#1971c2", "#2f9e44",
                   "#f08c00", "#9c36b5", "#0c8599"]
        existing = [o for o in canvas.doc.objects if isinstance(o, TraceCurve)]
        color = palette[len(existing) % len(palette)]

        trace = TraceCurve(hit, color=color)
        canvas.doc.add(trace)

        name = (getattr(hit, "name", "")
                or getattr(hit, "_auto_label", "")
                or f"P{hit.id}")
        canvas.cursor_info.emit(f"✔ 正在追踪 {name}")
        canvas.update()

    def move(self, canvas, wpt, hit):
        pass

    def release(self, canvas, wpt, hit):
        pass

    def cancel(self, canvas):
        pass

    def draw_overlay(self, p, view):
        pass