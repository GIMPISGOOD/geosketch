"""几何光学工具。

第一版工具：
- 点光源工具
- 平面镜工具
- 光线工具

所有工具注册到 panel="physics_optics"，
由主窗口的「物理 → 光学」菜单显示。
"""

from __future__ import annotations

from PySide6.QtCore import QPointF

from core.registry import register_tool
from geo.points import AbstractPoint, PointOnObject, nearest_point
from tools.base import Tool, point_or_snap
from ui import theme

from .objects import LightSourcePoint, PlaneMirror, LightRay


# ═══════════════════════════════════════════════════════════
# 点光源工具
# ═══════════════════════════════════════════════════════════

@register_tool(
    "点光源",
    shortcut=None,
    order=900,
    hint="创建点光源",
    icon="light_source",
    panel="physics_optics",
)
class LightSourceTool(Tool):

    def activated(self, canvas):
        self.cursor = None

    def deactivated(self, canvas):
        self.cursor = None

    def cancel(self, canvas):
        self.cursor = None
        canvas.update()

    def move(self, canvas, wpt, hit):
        self.cursor = wpt
        canvas.update()

    def release(self, canvas, wpt, hit):
        # 如果附近已有点，则不重复创建
        pt = nearest_point(canvas.doc, canvas.scale, wpt)
        if pt is not None:
            return

        with canvas.doc.action():
            canvas.doc.add(LightSourcePoint(*wpt))

    def draw_overlay(self, p, view):
        if self.cursor is None:
            return

        qpt = view.to_screen(*self.cursor)
        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.setBrush(theme.brush(theme.PREVIEW))
        p.drawEllipse(qpt, 5.0, 5.0)


# ═══════════════════════════════════════════════════════════
# 平面镜工具
# ═══════════════════════════════════════════════════════════

@register_tool(
    "平面镜",
    shortcut=None,
    order=901,
    hint="依次点击两个端点创建平面镜",
    icon="plane_mirror",
    panel="physics_optics",
)
class PlaneMirrorTool(Tool):

    def activated(self, canvas):
        self.state = 0
        self.a = None
        self.cursor = None

    def deactivated(self, canvas):
        self.cancel(canvas)

    def cancel(self, canvas):
        self.state = 0
        self.a = None
        self.cursor = None
        canvas.update()

    def move(self, canvas, wpt, hit):
        self.cursor = wpt
        canvas.update()

    def release(self, canvas, wpt, hit):
        if self.state == 0:
            with canvas.doc.action():
                self.a = point_or_snap(canvas, wpt, hit)
            self.state = 1
            canvas.update()
            return

        if self.state == 1:
            with canvas.doc.action():
                b = point_or_snap(canvas, wpt, hit)

                if b is not self.a:
                    canvas.doc.add(PlaneMirror(self.a, b))
                    self.cancel(canvas)

    def draw_overlay(self, p, view):
        if self.state != 1 or self.a is None or self.cursor is None:
            return

        pa = view.to_screen(self.a.x, self.a.y)
        pc = view.to_screen(*self.cursor)

        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.drawLine(pa, pc)

        p.setBrush(theme.brush(theme.PREVIEW))
        p.drawEllipse(pc, 4.0, 4.0)


# ═══════════════════════════════════════════════════════════
# 光线工具
# ═══════════════════════════════════════════════════════════

@register_tool(
    "光线",
    shortcut=None,
    order=902,
    hint="先点击光源，再点击平面镜上的入射位置",
    icon="light_ray",
    panel="physics_optics",
)
class LightRayTool(Tool):

    def activated(self, canvas):
        self.state = 0
        self.source = None
        self.cursor = None
        self.hover = None

    def deactivated(self, canvas):
        self.cancel(canvas)

    def cancel(self, canvas):
        self.state = 0
        self.source = None
        self.cursor = None
        self.hover = None
        canvas.update()

    def move(self, canvas, wpt, hit):
        self.cursor = wpt
        self.hover = hit
        canvas.update()

    def release(self, canvas, wpt, hit):
        # 第一步：确定光源
        if self.state == 0:
            pt = nearest_point(canvas.doc, canvas.scale, wpt)

            if isinstance(pt, AbstractPoint):
                self.source = pt
                self.state = 1
                canvas.update()
                return

            if isinstance(hit, AbstractPoint):
                self.source = hit
                self.state = 1
                canvas.update()
                return

            # 如果空白处点击，则自动创建点光源
            if hit is None or not isinstance(hit, PlaneMirror):
                with canvas.doc.action():
                    self.source = canvas.doc.add(LightSourcePoint(*wpt))
                self.state = 1
                canvas.update()
                return

            # 点击到平面镜但没有光源，仍然先创建光源
            with canvas.doc.action():
                self.source = canvas.doc.add(LightSourcePoint(*wpt))
            self.state = 1
            canvas.update()
            return

        # 第二步：点击平面镜，创建入射点和光线
        if self.state == 1:
            if isinstance(hit, PlaneMirror):
                with canvas.doc.action():
                    t = hit.project(*wpt)
                    incident = canvas.doc.add(PointOnObject(hit, t))
                    canvas.doc.add(LightRay(self.source, incident, hit))

                self.cancel(canvas)
                return

            # 允许点击另一个点来切换光源
            if isinstance(hit, AbstractPoint) and hit is not self.source:
                self.source = hit
                canvas.update()
                return

    def draw_overlay(self, p, view):
        if self.state != 1 or self.source is None or self.cursor is None:
            return

        ps = view.to_screen(self.source.x, self.source.y)
        pc = view.to_screen(*self.cursor)

        p.setPen(theme.dashed_pen(theme.PREVIEW, 1.5))
        p.drawLine(ps, pc)

        if isinstance(self.hover, PlaneMirror):
            p.setBrush(theme.brush(theme.PREVIEW))
            p.drawEllipse(pc, 4.5, 4.5)