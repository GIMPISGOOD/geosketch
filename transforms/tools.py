"""变换工具：注册到主菜单「变换」。"""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QInputDialog

from core.registry import register_tool

from tools.base import Tool, point_or_snap

from transforms.objects import TransformDriver, IterPoint
from transforms.apply import create_transformed_copies


# ------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------

def _back_select(canvas):
    from tools.select import SelectTool
    QTimer.singleShot(0, lambda: canvas.set_tool(SelectTool()))


def _ask_depth(canvas):
    depth, ok = QInputDialog.getInt(
        canvas,
        "迭代深度",
        "副本层数（1 = 单次变换）：",
        1, 1, 200, 1
    )
    return depth if ok else None


def _ask_expr(canvas, title, label, default="0"):
    text, ok = QInputDialog.getText(canvas, title, label, text=default)
    if not ok:
        return None
    return text.strip()


def _finish(canvas, created):
    if created:
        canvas.doc.set_selection(created)
    else:
        canvas.cursor_info.emit("当前对象暂不支持该变换")
    _back_select(canvas)


def _apply_driver(canvas, driver, targets, depth):
    created = create_transformed_copies(canvas.doc, driver, targets, depth)
    _finish(canvas, created)


def _axis_points(hit):
    """从命中对象提取两个端点：线段 / 直线 / 射线。"""
    if hit is None:
        return None

    if hasattr(hit, "a") and hasattr(hit, "b") \
            and hasattr(hit.a, "x") and hasattr(hit.b, "x"):
        return hit.a, hit.b

    if hasattr(hit, "origin") and hasattr(hit, "through") \
            and hasattr(hit.origin, "x") and hasattr(hit.through, "x"):
        return hit.origin, hit.through

    return None


# ------------------------------------------------------------
# 基类
# ------------------------------------------------------------

class TransformTool(Tool):
    def __init__(self):
        self.targets = []

    def activated(self, canvas):
        self.targets = [o for o in canvas.doc.objects if o.selected]

        if not self.targets:
            canvas.cursor_info.emit("请先用选择工具选中要变换的对象")
            _back_select(canvas)
            return

        self._start(canvas)

    def _start(self, canvas):
        pass

    def deactivated(self, canvas):
        self.targets = []

    def cancel(self, canvas):
        _back_select(canvas)


# ============================================================
# 平移
# ============================================================

@register_tool(name="平移·坐标", order=301, panel="transform", icon="select",
               hint="按 dx/dy 表达式平移选中对象，可绑定变量")
class TranslateExprTool(TransformTool):
    def _start(self, canvas):
        dx = _ask_expr(canvas, "平移·坐标", "dx 表达式（可绑定变量）：", "1")
        if dx is None:
            _back_select(canvas)
            return

        dy = _ask_expr(canvas, "平移·坐标", "dy 表达式（可绑定变量）：", "0")
        if dy is None:
            _back_select(canvas)
            return

        depth = _ask_depth(canvas)
        if depth is None:
            _back_select(canvas)
            return

        driver = TransformDriver(
            "translate",
            exprs={"mode": "expr", "dx": dx, "dy": dy}
        )

        _apply_driver(canvas, driver, self.targets, depth)


@register_tool(name="平移·两点向量", order=302, panel="transform", icon="select",
               hint="先选对象，再点击两个点 A→B 作为平移向量")
class TranslateVectorTool(TransformTool):
    def _start(self, canvas):
        self.pts = []
        canvas.cursor_info.emit("点击两个点作为平移向量：A → B")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        pt = point_or_snap(canvas, wpt, hit)
        self.pts.append(pt)

        if len(self.pts) == 2:
            depth = _ask_depth(canvas)
            if depth is None:
                return

            driver = TransformDriver(
                "translate",
                points=self.pts,
                exprs={"mode": "points"}
            )

            _apply_driver(canvas, driver, self.targets, depth)

    def cancel(self, canvas):
        self.pts = []
        _back_select(canvas)


@register_tool(name="平移·标记线段", order=303, panel="transform", icon="select",
               hint="先选对象，再点击一条线段/直线/射线作为平移向量")
class TranslateSegmentTool(TransformTool):
    def _start(self, canvas):
        canvas.cursor_info.emit("点击一条线段/直线/射线作为平移向量")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        if _axis_points(hit) is None:
            canvas.cursor_info.emit("请点击一条线段/直线/射线")
            return

        depth = _ask_depth(canvas)
        if depth is None:
            return

        driver = TransformDriver(
            "translate",
            segments=[hit],
            exprs={"mode": "segment"}
        )

        _apply_driver(canvas, driver, self.targets, depth)


# ============================================================
# 旋转
# ============================================================

@register_tool(name="旋转·角度", order=311, panel="transform", icon="select",
               hint="先选对象，点击旋转中心，再输入角度表达式")
class RotateTool(TransformTool):
    def _start(self, canvas):
        canvas.cursor_info.emit("点击旋转中心")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        center = point_or_snap(canvas, wpt, hit)

        angle = _ask_expr(canvas, "旋转", "角度表达式（度，可绑定变量）：", "90")
        if angle is None:
            _back_select(canvas)
            return

        depth = _ask_depth(canvas)
        if depth is None:
            _back_select(canvas)
            return

        driver = TransformDriver(
            "rotate",
            points=[center],
            exprs={"angle": angle}
        )

        _apply_driver(canvas, driver, self.targets, depth)


# ============================================================
# 缩放
# ============================================================

@register_tool(name="缩放·比例", order=321, panel="transform", icon="select",
               hint="先选对象，点击缩放中心，再输入比例表达式")
class ScaleFactorTool(TransformTool):
    def _start(self, canvas):
        canvas.cursor_info.emit("点击缩放中心")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        center = point_or_snap(canvas, wpt, hit)

        factor = _ask_expr(canvas, "缩放", "比例表达式（可绑定变量）：", "1.2")
        if factor is None:
            _back_select(canvas)
            return

        depth = _ask_depth(canvas)
        if depth is None:
            _back_select(canvas)
            return

        driver = TransformDriver(
            "scale",
            points=[center],
            exprs={"mode": "expr", "factor": factor}
        )

        _apply_driver(canvas, driver, self.targets, depth)


@register_tool(name="缩放·线段比", order=322, panel="transform", icon="select",
               hint="先选对象，点击缩放中心，再点两条线段，比例 = 线段1/线段2")
class ScaleRatioTool(TransformTool):
    def _start(self, canvas):
        self.step = 0
        self.center = None
        self.seg1 = None
        canvas.cursor_info.emit("点击缩放中心")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        if self.step == 0:
            self.center = point_or_snap(canvas, wpt, hit)
            self.step = 1
            canvas.cursor_info.emit("点击第一条线段（分子）")

        elif self.step == 1:
            if hit is None or not hasattr(hit, "length"):
                canvas.cursor_info.emit("请点击一条线段")
                return

            self.seg1 = hit
            self.step = 2
            canvas.cursor_info.emit("点击第二条线段（分母）")

        elif self.step == 2:
            if hit is None or not hasattr(hit, "length"):
                canvas.cursor_info.emit("请点击一条线段")
                return

            seg2 = hit

            depth = _ask_depth(canvas)
            if depth is None:
                return

            driver = TransformDriver(
                "scale",
                points=[self.center],
                segments=[self.seg1, seg2],
                exprs={"mode": "ratio"}
            )

            _apply_driver(canvas, driver, self.targets, depth)

    def cancel(self, canvas):
        self.step = 0
        self.center = None
        self.seg1 = None
        _back_select(canvas)


# ============================================================
# 反射 / 中心对称
# ============================================================

@register_tool(name="反射·轴对称", order=331, panel="transform", icon="select",
               hint="先选对象，再点击对称轴：可直接点线段/直线，或点两个点")
class ReflectTool(TransformTool):
    def _start(self, canvas):
        self.axis_pts = []
        canvas.cursor_info.emit("点击对称轴：可直接点一条线段/直线，或点两个点")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        if not self.axis_pts:
            ap = _axis_points(hit)
            if ap is not None:
                self.axis_pts = list(ap)
                self._finish(canvas)
                return

            pt = point_or_snap(canvas, wpt, hit)
            self.axis_pts.append(pt)
            canvas.cursor_info.emit("再点击第二个点确定对称轴")
        else:
            pt = point_or_snap(canvas, wpt, hit)
            self.axis_pts.append(pt)

            if len(self.axis_pts) == 2:
                self._finish(canvas)

    def _finish(self, canvas):
        depth = _ask_depth(canvas)
        if depth is None:
            return

        driver = TransformDriver(
            "reflect",
            points=self.axis_pts,
            exprs={}
        )

        _apply_driver(canvas, driver, self.targets, depth)

    def cancel(self, canvas):
        self.axis_pts = []
        _back_select(canvas)


@register_tool(name="反射·中心对称", order=332, panel="transform", icon="select",
               hint="先选对象，再点击对称中心")
class CentralSymmetryTool(TransformTool):
    def _start(self, canvas):
        canvas.cursor_info.emit("点击对称中心")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        center = point_or_snap(canvas, wpt, hit)

        depth = _ask_depth(canvas)
        if depth is None:
            return

        driver = TransformDriver(
            "symmetry",
            points=[center],
            exprs={}
        )

        _apply_driver(canvas, driver, self.targets, depth)


# ============================================================
# 自定义仿射变换
# ============================================================

@register_tool(name="仿射·矩阵", order=341, panel="transform", icon="select",
               hint="输入 2×3 矩阵实现任意仿射变换")
class AffineMatrixTool(TransformTool):
    def _start(self, canvas):
        text, ok = QInputDialog.getMultiLineText(
            canvas,
            "仿射变换·矩阵",
            "输入 2×3 矩阵，每行三个表达式，用空格分隔：\n"
            "X = a*x + b*y + c\n"
            "Y = d*x + e*y + f\n\n"
            "例如：\n1 0 0\n0 1 0",
            "1 0 0\n0 1 0"
        )

        if not ok:
            _back_select(canvas)
            return

        rows = [r.split() for r in text.strip().splitlines() if r.strip()]

        if len(rows) < 2 or len(rows[0]) < 3 or len(rows[1]) < 3:
            canvas.cursor_info.emit("矩阵格式不正确")
            _back_select(canvas)
            return

        exprs = {
            "a": rows[0][0],
            "b": rows[0][1],
            "c": rows[0][2],
            "d": rows[1][0],
            "e": rows[1][1],
            "f": rows[1][2],
        }

        depth = _ask_depth(canvas)
        if depth is None:
            _back_select(canvas)
            return

        driver = TransformDriver("affine", exprs=exprs)
        _apply_driver(canvas, driver, self.targets, depth)


@register_tool(name="仿射·三对应点", order=342, panel="transform", icon="select",
               hint="依次点 3 个源点，再点 3 个目标点，求仿射变换")
class AffinePointsTool(TransformTool):
    def _start(self, canvas):
        self.pts = []
        canvas.cursor_info.emit("依次点 3 个源点，再点 3 个目标点")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        pt = point_or_snap(canvas, wpt, hit)
        self.pts.append(pt)

        n = len(self.pts)

        if n < 3:
            canvas.cursor_info.emit(f"源点 {n}/3")
        elif n == 3:
            canvas.cursor_info.emit("源点完成，开始点目标点 1/3")
        elif n < 6:
            canvas.cursor_info.emit(f"目标点 {n - 3}/3")

        if n == 6:
            depth = _ask_depth(canvas)
            if depth is None:
                return

            driver = TransformDriver(
                "affine_pts",
                points=self.pts,
                exprs={}
            )

            _apply_driver(canvas, driver, self.targets, depth)

    def cancel(self, canvas):
        self.pts = []
        _back_select(canvas)


# ============================================================
# 圆反演
# ============================================================

@register_tool(name="反演·圆内外翻转", order=351, panel="transform", icon="select",
               hint="先选对象，点击反演圆；或点击空白设置中心后输入半径")
class InversionTool(TransformTool):
    def _start(self, canvas):
        self.center = None
        canvas.cursor_info.emit("点击反演圆；或点击空白处设置反演中心")

    def press(self, canvas, wpt, hit):
        if not self.targets:
            return

        # 直接选择已有圆作为反演圆
        if hit is not None and type(hit).__name__ == "Circle":
            depth = _ask_depth(canvas)
            if depth is None:
                return

            driver = TransformDriver(
                "invert",
                circles=[hit],
                exprs={}
            )

            _apply_driver(canvas, driver, self.targets, depth)
            return

        # 否则：点中心 + 输入半径
        if self.center is None:
            self.center = point_or_snap(canvas, wpt, hit)

            radius = _ask_expr(canvas, "反演半径", "半径表达式（可绑定变量）：", "1")
            if radius is None:
                _back_select(canvas)
                return

            depth = _ask_depth(canvas)
            if depth is None:
                _back_select(canvas)
                return

            driver = TransformDriver(
                "invert",
                points=[self.center],
                exprs={"radius": radius}
            )

            _apply_driver(canvas, driver, self.targets, depth)

    def cancel(self, canvas):
        self.center = None
        _back_select(canvas)


# ============================================================
# 迭代点列 / 分形数列点
# ============================================================

@register_tool(name="迭代·数列点", order=361, panel="transform", icon="select",
               hint="点击起点，输入迭代公式，生成点列")
class IterationPointTool(Tool):
    def __init__(self):
        self.start = None

    def activated(self, canvas):
        self.start = None

        sel = [o for o in canvas.doc.objects if o.selected]

        from geo.points import AbstractPoint
        pts = [o for o in sel if isinstance(o, AbstractPoint)]

        if len(pts) == 1:
            self._run(canvas, pts[0])
        else:
            canvas.cursor_info.emit("点击迭代起点")

    def deactivated(self, canvas):
        self.start = None

    def press(self, canvas, wpt, hit):
        start = point_or_snap(canvas, wpt, hit)
        self._run(canvas, start)

    def _run(self, canvas, start):
        fx, ok = QInputDialog.getText(
            canvas,
            "迭代点列",
            "x_{n+1} 表达式（可用 x,y,n 和变量）：",
            text="x + 0.5"
        )
        if not ok:
            _back_select(canvas)
            return

        fy, ok = QInputDialog.getText(
            canvas,
            "迭代点列",
            "y_{n+1} 表达式（可用 x,y,n 和变量）：",
            text="y"
        )
        if not ok:
            _back_select(canvas)
            return

        depth, ok = QInputDialog.getInt(
            canvas,
            "迭代深度",
            "生成点数：",
            20, 1, 1000, 1
        )
        if not ok:
            _back_select(canvas)
            return

        doc = canvas.doc
        created = []

        doc.begin_action()
        try:
            cur = start
            for i in range(1, int(depth) + 1):
                p = IterPoint(cur, i, fx.strip(), fy.strip())
                doc.add(p)
                created.append(p)
                cur = p
        finally:
            doc.end_action()

        doc.set_selection(created)
        _back_select(canvas)

    def cancel(self, canvas):
        _back_select(canvas)