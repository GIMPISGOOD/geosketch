"""从动点坐标对自由点坐标的解析偏导数。

预留扩展接口：
- get_coordinate_derivatives(): 新增从动点类型时在此添加分支
- _intersect_point_derivatives(): IntersectPoint 的隐函数定理实现（待补全）
"""
import math
from typing import Dict, Tuple


def get_coordinate_derivatives(point) -> Dict[int, Tuple[float, float, float, float]]:
    """返回 {id(free_point): (∂x/∂px, ∂x/∂py, ∂y/∂px, ∂y/∂py)}"""
    from geo.points import FreePoint, PointOnObject

    if isinstance(point, FreePoint):
        return {id(point): (1.0, 0.0, 0.0, 1.0)}

    if isinstance(point, PointOnObject):
        return _point_on_object_derivatives(point)

    tn = type(point).__name__
    if tn == "DivisionPoint":
        return _division_point_derivatives(point)
    if tn == "IntersectPoint":
        return _intersect_point_derivatives(point)

    return {}


def _point_on_object_derivatives(poo) -> Dict[int, Tuple[float, float, float, float]]:
    from geo.points import FreePoint
    host = poo.host
    t = poo.t
    tn = type(host).__name__

    if tn == "Segment":
        a, b = host.a, host.b
        result = {}
        if isinstance(a, FreePoint):
            result[id(a)] = (1.0 - t, 0.0, 0.0, 1.0 - t)
        if isinstance(b, FreePoint):
            result[id(b)] = (t, 0.0, 0.0, t)
        return result

    if tn in ("Circle", "ExprCircle"):
        center = host.center
        r = host.r
        angle = 2.0 * math.pi * t
        c, s = math.cos(angle), math.sin(angle)
        result = {}
        if isinstance(center, FreePoint):
            result[id(center)] = (1.0, 0.0, 0.0, 1.0)
        through = getattr(host, 'through', None)
        if through is not None and isinstance(through, FreePoint) and r > 1e-12:
            dr_dtx = (through.x - center.x) / r
            dr_dty = (through.y - center.y) / r
            result[id(through)] = (c * dr_dtx, c * dr_dty,
                                    s * dr_dtx, s * dr_dty)
        return result

    if tn in ("Line", "Ray", "DirectedLine"):
        if hasattr(host, 'a') and hasattr(host, 'b'):
            a, b = host.a, host.b
            result = {}
            if isinstance(a, FreePoint):
                result[id(a)] = (1.0 - t, 0.0, 0.0, 1.0 - t)
            if isinstance(b, FreePoint):
                result[id(b)] = (t, 0.0, 0.0, t)
            return result

    return {}


def _division_point_derivatives(dp) -> Dict[int, Tuple[float, float, float, float]]:
    from geo.points import FreePoint
    a, b, t = dp.a, dp.b, dp.t
    result = {}
    if isinstance(a, FreePoint):
        result[id(a)] = (1.0 - t, 0.0, 0.0, 1.0 - t)
    if isinstance(b, FreePoint):
        result[id(b)] = (t, 0.0, 0.0, t)
    return result


def _intersect_point_derivatives(ip) -> Dict[int, Tuple[float, float, float, float]]:
    # 预留：IntersectPoint 需要隐函数定理，当前返回空（不影响其他约束求解）
    return {}