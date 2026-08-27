"""从动点坐标对自由点坐标的解析偏导数。"""
import math
from typing import Dict, Tuple

_DerivMap = Dict[int, Tuple[float, float, float, float]]


def get_coordinate_derivatives(point) -> _DerivMap:
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


# ═══════════════════════════════════════════════════════════
#  PointOnObject
# ═══════════════════════════════════════════════════════════

def _point_on_object_derivatives(poo) -> _DerivMap:
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


# ═══════════════════════════════════════════════════════════
#  DivisionPoint
# ═══════════════════════════════════════════════════════════

def _division_point_derivatives(dp) -> _DerivMap:
    from geo.points import FreePoint
    a, b, t = dp.a, dp.b, dp.t
    result = {}
    if isinstance(a, FreePoint):
        result[id(a)] = (1.0 - t, 0.0, 0.0, 1.0 - t)
    if isinstance(b, FreePoint):
        result[id(b)] = (t, 0.0, 0.0, t)
    return result


# ═══════════════════════════════════════════════════════════
#  IntersectPoint
# ═══════════════════════════════════════════════════════════

_LINE_TYPES = frozenset({
    "Segment", "Line", "Ray", "DirectedLine",
    "PerpLine", "ParallelLine", "AngleBisector",
    "AngleDivLine", "PerpBisector",
})
_CIRCLE_TYPES = frozenset({"Circle", "ExprCircle", "ThreePointCircle"})


def _intersect_point_derivatives(ip) -> _DerivMap:
    if not getattr(ip, 'exists', False):
        return {}

    px, py = ip.x, ip.y
    obj_a, obj_b = ip.a, ip.b
    tn_a, tn_b = type(obj_a).__name__, type(obj_b).__name__

    a_line = tn_a in _LINE_TYPES
    b_line = tn_b in _LINE_TYPES
    a_circ = tn_a in _CIRCLE_TYPES
    b_circ = tn_b in _CIRCLE_TYPES

    if a_line and b_line:
        return _ll_derivs(ip, obj_a, obj_b, px, py)
    if a_line and b_circ:
        return _lc_derivs(ip, obj_a, obj_b, px, py)
    if a_circ and b_line:
        return _lc_derivs(ip, obj_b, obj_a, px, py)
    if a_circ and b_circ:
        return _cc_derivs(ip, obj_a, obj_b, px, py)

    return _numeric_fallback(ip)


# ─── 线 × 线 ──────────────────────────────────────────────

def _ll_derivs(ip, la_obj, lb_obj, px, py) -> _DerivMap:
    la = _line_params(la_obj)
    lb = _line_params(lb_obj)
    if la is None or lb is None:
        return _numeric_fallback(ip)

    ax, ay, dx1, dy1 = la
    cx, cy, dx2, dy2 = lb

    j11, j12 = dy1, -dx1
    j21, j22 = dy2, -dx2
    det = j11 * j22 - j12 * j21
    if abs(det) < 1e-12:
        return _numeric_fallback(ip)

    result: _DerivMap = {}

    for pt in _line_free_points(la_obj):
        fx, fy = _ll_dF_dq(pt, ax, ay, dx1, dy1, px, py)
        _apply_implicit(result, pt, fx, fy, 0.0, 0.0,
                        j11, j12, j21, j22, det)

    for pt in _line_free_points(lb_obj):
        fx, fy = _ll_dF_dq(pt, cx, cy, dx2, dy2, px, py)
        _apply_implicit(result, pt, 0.0, 0.0, fx, fy,
                        j11, j12, j21, j22, det)

    return result


def _ll_dF_dq(pt, ox, oy, dx, dy, px, py):
    ex, ey = ox + dx, oy + dy
    qx, qy = pt.x, pt.y

    if abs(qx - ox) < 1e-12 and abs(qy - oy) < 1e-12:
        return (py - ey, ex - px)
    if abs(qx - ex) < 1e-12 and abs(qy - ey) < 1e-12:
        return (oy - py, px - ox)
    return (0.0, 0.0)


# ─── 线 × 圆 ──────────────────────────────────────────────

def _lc_derivs(ip, line_obj, circ_obj, px, py) -> _DerivMap:
    la = _line_params(line_obj)
    cc = _circle_params(circ_obj)
    if la is None or cc is None:
        return _numeric_fallback(ip)

    ax, ay, dx1, dy1 = la
    cx, cy, r = cc

    j11, j12 = dy1, -dx1
    j21, j22 = 2.0 * (px - cx), 2.0 * (py - cy)
    det = j11 * j22 - j12 * j21
    if abs(det) < 1e-12:
        return _numeric_fallback(ip)

    result: _DerivMap = {}

    for pt in _line_free_points(line_obj):
        fx, fy = _ll_dF_dq(pt, ax, ay, dx1, dy1, px, py)
        _apply_implicit(result, pt, fx, fy, 0.0, 0.0,
                        j11, j12, j21, j22, det)

    _circle_contrib(result, circ_obj, cx, cy, r, px, py,
                    j11, j12, j21, j22, det, first=False)

    return result


# ─── 圆 × 圆 ──────────────────────────────────────────────

def _cc_derivs(ip, ca_obj, cb_obj, px, py) -> _DerivMap:
    ca = _circle_params(ca_obj)
    cb = _circle_params(cb_obj)
    if ca is None or cb is None:
        return _numeric_fallback(ip)

    x1, y1, r1 = ca
    x2, y2, r2 = cb

    j11, j12 = 2.0 * (px - x1), 2.0 * (py - y1)
    j21, j22 = 2.0 * (px - x2), 2.0 * (py - y2)
    det = j11 * j22 - j12 * j21
    if abs(det) < 1e-12:
        return _numeric_fallback(ip)

    result: _DerivMap = {}

    _circle_contrib(result, ca_obj, x1, y1, r1, px, py,
                    j11, j12, j21, j22, det, first=True)
    _circle_contrib(result, cb_obj, x2, y2, r2, px, py,
                    j11, j12, j21, j22, det, first=False)
    return result


# ─── 圆的偏导数贡献（★ 核心修复）──────────────────────────

def _circle_contrib(result, obj, cx, cy, r, px, py,
                    j11, j12, j21, j22, det, first):
    from geo.points import FreePoint
    center = getattr(obj, 'center', None)
    through = getattr(obj, 'through', None)

    if center is not None and isinstance(center, FreePoint):
        if through is not None:
            fx = 2.0 * (through.x - px)
            fy = 2.0 * (through.y - py)
        else:
            fx = -2.0 * (px - cx)
            fy = -2.0 * (py - cy)
        if first:
            _apply_implicit(result, center, fx, fy, 0.0, 0.0,
                            j11, j12, j21, j22, det)
        else:
            _apply_implicit(result, center, 0.0, 0.0, fx, fy,
                            j11, j12, j21, j22, det)

    if through is not None and isinstance(through, FreePoint) and r > 1e-12:
        fx = -2.0 * (through.x - cx)
        fy = -2.0 * (through.y - cy)
        if first:
            _apply_implicit(result, through, fx, fy, 0.0, 0.0,
                            j11, j12, j21, j22, det)
        else:
            _apply_implicit(result, through, 0.0, 0.0, fx, fy,
                            j11, j12, j21, j22, det)


# ─── 隐函数定理核心（★ 符号修复）─────────────────────────

def _apply_implicit(result, fp, f1x, f1y, f2x, f2y,
                    j11, j12, j21, j22, det):
    dpx_qx = (-f1x * j22 + j12 * f2x) / det
    dpy_qx = (-j11 * f2x + f1x * j21) / det
    dpx_qy = (-f1y * j22 + j12 * f2y) / det
    dpy_qy = (-j11 * f2y + f1y * j21) / det

    key = id(fp)
    if key in result:
        o = result[key]
        result[key] = (o[0] + dpx_qx, o[1] + dpx_qy,
                       o[2] + dpy_qx, o[3] + dpy_qy)
    else:
        result[key] = (dpx_qx, dpx_qy, dpy_qx, dpy_qy)


# ─── 参数提取 ──────────────────────────────────────────────

def _line_params(obj):
    tn = type(obj).__name__
    if tn == "Segment":
        return obj.a.x, obj.a.y, obj.b.x - obj.a.x, obj.b.y - obj.a.y
    if tn == "Ray":
        return (obj.origin.x, obj.origin.y,
                obj.through.x - obj.origin.x,
                obj.through.y - obj.origin.y)
    if hasattr(obj, 'a') and hasattr(obj, 'b'):
        return obj.a.x, obj.a.y, obj.b.x - obj.a.x, obj.b.y - obj.a.y
    if hasattr(obj, 'point') and hasattr(obj, 'dx') and hasattr(obj, 'dy'):
        return obj.point.x, obj.point.y, obj.dx, obj.dy
    return None


def _circle_params(obj):
    if hasattr(obj, 'center') and hasattr(obj, 'r'):
        return obj.center.x, obj.center.y, obj.r
    if hasattr(obj, 'cx') and hasattr(obj, 'cy') and hasattr(obj, 'r'):
        return obj.cx, obj.cy, obj.r
    return None


def _line_free_points(obj):
    from geo.points import FreePoint
    tn = type(obj).__name__
    if tn == "Segment":
        pts = [obj.a, obj.b]
    elif tn == "Ray":
        pts = [obj.origin, obj.through]
    elif hasattr(obj, 'a') and hasattr(obj, 'b'):
        pts = [obj.a, obj.b]
    else:
        pts = []
    return [p for p in pts if isinstance(p, FreePoint)]


# ─── 数值回退 ──────────────────────────────────────────────

def _numeric_fallback(ip) -> _DerivMap:
    from geo.points import FreePoint
    result: _DerivMap = {}
    eps = 1e-7

    free_pts = []
    for parent in ip.parents:
        free_pts.extend(_collect_free(parent))

    for fp in free_pts:
        key = id(fp)
        if key in result:
            continue

        ox, oy = fp.x, fp.y

        fp.x = ox + eps
        ip.recompute()
        xp = (ip.x, ip.y) if ip.exists else None
        fp.x = ox - eps
        ip.recompute()
        xm = (ip.x, ip.y) if ip.exists else None
        fp.x = ox
        ip.recompute()

        fp.y = oy + eps
        ip.recompute()
        yp = (ip.x, ip.y) if ip.exists else None
        fp.y = oy - eps
        ip.recompute()
        ym = (ip.x, ip.y) if ip.exists else None
        fp.y = oy
        ip.recompute()

        if xp is None or xm is None or yp is None or ym is None:
            continue

        result[key] = (
            (xp[0] - xm[0]) / (2 * eps),
            (yp[0] - ym[0]) / (2 * eps),
            (xp[1] - xm[1]) / (2 * eps),
            (yp[1] - ym[1]) / (2 * eps),
        )
    return result


def _collect_free(obj):
    from geo.points import FreePoint
    tn = type(obj).__name__
    if tn == "Segment":
        pts = [obj.a, obj.b]
    elif tn == "Ray":
        pts = [obj.origin, obj.through]
    elif tn in _CIRCLE_TYPES:
        pts = [getattr(obj, 'center', None), getattr(obj, 'through', None)]
    elif hasattr(obj, 'a') and hasattr(obj, 'b'):
        pts = [obj.a, obj.b]
    else:
        pts = []
    return [p for p in pts if isinstance(p, FreePoint)]