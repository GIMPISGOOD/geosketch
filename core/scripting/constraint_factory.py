"""脚本约束工厂：把约束系统暴露给脚本。"""

from geo.base import GeoObject
from geo.points import AbstractPoint
from core.variables import eval_expr

from .errors import ScriptError

try:
    from constraints.types.fixed import FixedConstraint
    from constraints.types.distance import DistanceConstraint
    from constraints.types.angle import AngleConstraint
    from constraints.types.horizontal import HorizontalConstraint
    from constraints.types.vertical import VerticalConstraint
    from constraints.types.collinear import CollinearConstraint
    from constraints.types.parallel import ParallelConstraint
    from constraints.types.perpendicular import PerpendicularConstraint
    from constraints.types.circle_constraints import (
        ConcentricConstraint,
        EqualRadiusConstraint,
        TangentCirclesConstraint,
        TangentLineCircleConstraint,
    )
    _HAS_CONSTRAINTS = True
except Exception:
    _HAS_CONSTRAINTS = False


class ConstraintFactory:
    """脚本约束创建工厂。

    设计目标：
    - 参数可以传对象，也可以传对象名字符串；
    - 点级约束可以从线段 / 直线 / 圆等对象中自动提取点；
    - 所有约束统一通过 Interpreter.add_created_constraint 添加；
    - 脚本事务失败时可回滚。
    """

    def __init__(self, interp):
        self.interp = interp

    # ------------------------------------------------------------
    # 基础工具
    # ------------------------------------------------------------

    def _require(self):
        if not _HAS_CONSTRAINTS:
            raise ScriptError("约束系统不可用")

    def _doc(self):
        return self.interp.doc

    def _resolve_object(self, value, line=None):
        """把脚本参数解析为几何对象。"""
        if isinstance(value, GeoObject):
            return value

        if isinstance(value, str):
            name = value.strip()
            if not name:
                raise ScriptError("对象名不能为空", line)

            from .scope import MISSING

            found = self.interp.global_scope.find(name)
            if found is not MISSING and isinstance(found, GeoObject):
                return found

            for obj in self._doc().objects:
                if getattr(obj, "script_name", None) == name:
                    return obj
                if getattr(obj, "name", None) == name:
                    return obj

            obj = self._doc().names.get(name)
            if obj is not None:
                return obj

            raise ScriptError(f"找不到对象：{name}", line)

        raise ScriptError("此处需要几何对象或对象名", line)

    def _extract_points(self, obj, line=None):
        """从几何对象中提取定义点。与约束工具的智能拾取保持一致。"""
        if isinstance(obj, AbstractPoint):
            return [obj]

        if hasattr(obj, "a") and hasattr(obj, "b"):
            return [obj.a, obj.b]

        if hasattr(obj, "origin") and hasattr(obj, "through"):
            return [obj.origin, obj.through]

        if hasattr(obj, "center") and hasattr(obj, "through"):
            return [obj.center, obj.through]

        if hasattr(obj, "verts") and hasattr(obj, "n"):
            verts = [
                c for c in getattr(obj, "children", [])
                if type(c).__name__ == "PolygonVertex"
            ]
            if verts:
                return verts

        return []

    def _point_arg(self, arg, line=None):
        """要求参数最终是一个点。"""
        obj = self._resolve_object(arg, line)
        if isinstance(obj, AbstractPoint):
            return obj

        pts = self._extract_points(obj, line)
        if len(pts) == 1:
            return pts[0]

        raise ScriptError("此处需要一个点对象", line)

    def _collect_points(self, args, need, line=None):
        """从多个参数中收集恰好 need 个点。"""
        pts = []

        for arg in args:
            obj = self._resolve_object(arg, line)
            extracted = self._extract_points(obj, line)

            if not extracted:
                raise ScriptError("无法从参数中提取点", line)

            for p in extracted:
                pts.append(p)

        if len(pts) < need:
            raise ScriptError(
                f"约束需要 {need} 个点，当前只有 {len(pts)} 个",
                line
            )

        if len(pts) > need:
            raise ScriptError(
                f"约束需要 {need} 个点，但参数提供了 {len(pts)} 个点",
                line
            )

        return pts

    def _circle_arg(self, arg, need_through=True, line=None):
        obj = self._resolve_object(arg, line)

        if not hasattr(obj, "center"):
            raise ScriptError("此处需要圆对象", line)

        if need_through and not hasattr(obj, "through"):
            raise ScriptError("该约束需要带圆周点的圆对象", line)

        return obj

    def _number(self, value, line=None):
        if isinstance(value, bool):
            return 1.0 if value else 0.0

        if isinstance(value, (int, float)):
            return float(value)

        if isinstance(value, str):
            v = eval_expr(value)
            if v is not None:
                return float(v)
            try:
                return float(value)
            except Exception:
                raise ScriptError(f"无法解析数字：{value}", line)

        raise ScriptError("此处需要数字或表达式", line)

    def _expr(self, value, line=None):
        """约束表达式统一转成字符串。"""
        if isinstance(value, str):
            return value

        if isinstance(value, bool):
            return "1" if value else "0"

        if isinstance(value, (int, float)):
            return str(value)

        raise ScriptError("约束表达式需要数字或字符串", line)

    def _add(self, constraint, name=None, line=None):
        return self.interp.add_created_constraint(
            constraint,
            name=name,
            line=line
        )

    # ------------------------------------------------------------
    # 点级约束
    # ------------------------------------------------------------

    def fixed(self, p, x=None, y=None):
        """固定点。

        脚本用法：
            constraint_fixed(A)
            constraint_fixed(A, 0, 0)
            constraint_fixed(A, "a", "b")
        """
        self._require()

        pt = self._point_arg(p)

        if x is None and y is None:
            fx, fy = pt.x, pt.y
        elif x is None or y is None:
            raise ScriptError("constraint_fixed 需要同时给出 x 和 y")
        else:
            fx = self._number(x)
            fy = self._number(y)

        return self._add(FixedConstraint(pt, fx, fy))

    def distance(self, *args):
        """距离约束。

        脚本用法：
            constraint_distance(A, B, 5)
            constraint_distance(A, B, "a * 2")
            constraint_distance(S, 5)
        """
        self._require()

        if len(args) < 2:
            raise ScriptError("constraint_distance 需要点/线段和距离表达式")

        expr = self._expr(args[-1])
        pts = self._collect_points(args[:-1], 2)

        return self._add(DistanceConstraint(pts[0], pts[1], expr))

    def angle(self, *args):
        """角度约束。

        脚本用法：
            constraint_angle(A, O, B, 90)
            constraint_angle(A, O, B, "theta")
        """
        self._require()

        if len(args) < 2:
            raise ScriptError("constraint_angle 需要三个点和角度表达式")

        expr = self._expr(args[-1])
        pts = self._collect_points(args[:-1], 3)

        return self._add(AngleConstraint(pts[0], pts[1], pts[2], expr))

    def horizontal(self, *args):
        """水平约束。

        脚本用法：
            constraint_horizontal(A, B)
            constraint_horizontal(S)
        """
        self._require()
        pts = self._collect_points(args, 2)
        return self._add(HorizontalConstraint(pts[0], pts[1]))

    def vertical(self, *args):
        """竖直约束。

        脚本用法：
            constraint_vertical(A, B)
            constraint_vertical(S)
        """
        self._require()
        pts = self._collect_points(args, 2)
        return self._add(VerticalConstraint(pts[0], pts[1]))

    def collinear(self, *args):
        """共线约束。

        脚本用法：
            constraint_collinear(A, B, C)
        """
        self._require()
        pts = self._collect_points(args, 3)
        return self._add(CollinearConstraint(pts[0], pts[1], pts[2]))

    def parallel(self, *args):
        """平行约束。

        脚本用法：
            constraint_parallel(L1, L2)
            constraint_parallel(A, B, C, D)
        """
        self._require()
        pts = self._collect_points(args, 4)
        return self._add(
            ParallelConstraint(pts[0], pts[1], pts[2], pts[3])
        )

    def perpendicular(self, *args):
        """垂直约束。

        脚本用法：
            constraint_perpendicular(L1, L2)
            constraint_perpendicular(A, B, C, D)
        """
        self._require()
        pts = self._collect_points(args, 4)
        return self._add(
            PerpendicularConstraint(pts[0], pts[1], pts[2], pts[3])
        )

    # ------------------------------------------------------------
    # 对象级约束
    # ------------------------------------------------------------

    def concentric(self, a, b):
        """同心约束。"""
        self._require()

        c1 = self._circle_arg(a, need_through=False)
        c2 = self._circle_arg(b, need_through=False)

        return self._add(ConcentricConstraint(c1, c2))

    def equal_radius(self, a, b):
        """等半径约束。"""
        self._require()

        c1 = self._circle_arg(a, need_through=True)
        c2 = self._circle_arg(b, need_through=True)

        return self._add(EqualRadiusConstraint(c1, c2))

    def tangent(self, *args):
        """相切约束。

        支持：
            constraint_tangent(circle1, circle2)
            constraint_tangent(circle1, circle2, "inner")
            constraint_tangent(line, circle)
            constraint_tangent(circle, line)
        """
        self._require()

        mode = "outer"
        objs = list(args)

        if len(objs) == 3 and isinstance(objs[-1], str):
            m = objs[-1].strip().lower()
            if m in ("outer", "external", "外切"):
                mode = "outer"
                objs = objs[:2]
            elif m in ("inner", "internal", "内切"):
                mode = "inner"
                objs = objs[:2]

        if len(objs) != 2:
            raise ScriptError("constraint_tangent 需要两个对象")

        o1 = self._resolve_object(objs[0])
        o2 = self._resolve_object(objs[1])

        def is_circle(o):
            return hasattr(o, "center") and hasattr(o, "through")

        def is_line(o):
            return hasattr(o, "a") and hasattr(o, "b")

        if is_circle(o1) and is_circle(o2):
            return self._add(TangentCirclesConstraint(o1, o2, mode))

        if is_circle(o1) and is_line(o2):
            return self._add(TangentLineCircleConstraint(o2, o1))

        if is_line(o1) and is_circle(o2):
            return self._add(TangentLineCircleConstraint(o1, o2))

        raise ScriptError("相切约束需要两个圆，或一条线和一个圆")

    # ------------------------------------------------------------
    # 求解 / 删除
    # ------------------------------------------------------------

    def solve(self, quick=False):
        """主动触发约束求解。

        脚本用法：
            constraint_solve()
            constraint_solve(true)
        """
        self._require()

        doc = self._doc()
        if not hasattr(doc, "solve_constraints"):
            return True

        return bool(doc.solve_constraints(quick=bool(quick)))

    def remove(self, value):
        """删除约束。
        支持：
        remove_constraint(c)
        remove_constraint("c12")
        """
        doc = self._doc()
        target = None
        
        # 1. 解析目标约束
        if hasattr(value, "cid"):
            target = value
        elif isinstance(value, str):
            for c in doc.constraints:
                if getattr(c, "cid", None) == value:
                    target = c
                    break
                if getattr(c, "script_name", None) == value:
                    target = c
                    break
                    
        # 2. 统一校验目标是否存在于文档中
        if target is None or target not in doc.constraints:
            raise ScriptError("找不到要删除的约束")
            
        # 3. 执行删除与清理
        doc.remove_constraint(target)
        try:
            if target in self.interp.created_constraints:
                self.interp.created_constraints.remove(target)
        except Exception:
            pass
        return True