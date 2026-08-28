"""约束基类与注册表。雅可比统一返回 np.ndarray。"""

from numpy import asarray, zeros, float64
from typing import List, Any, Dict, Type


class GeometricConstraint:
    _next_id = 1

    def __init__(self):
        self.cid = f"c{GeometricConstraint._next_id}"
        GeometricConstraint._next_id += 1
        self.enabled = True
        self.status = "ok"

    # ── 子类必须实现 ──────────────────────────────────
    def involved_points(self) -> List[Any]:
        raise NotImplementedError

    def residual(self) -> List[float]:
        raise NotImplementedError

    # ── 雅可比入口（统一返回 np.ndarray）────────────────
    def jacobian(self, vars_map: Dict[int, int]):
        """返回 shape=(n_res, 2*len(vars_map)) 的雅可比矩阵。

        快速路径：不涉及从动点 → 解析雅可比或局部数值差分。
        慢速路径：涉及从动点 → 链式法则解析雅可比。
        """
        from geo.points import FreePoint

        pts = self.involved_points()
        has_dependent = any(not isinstance(p, FreePoint) for p in pts)

        if not has_dependent:
            analytic = getattr(self, '_jacobian_analytic', None)
            if analytic is not None:
                try:
                    return asarray(analytic(vars_map), dtype=float64)
                except Exception:
                    pass
            return self._numeric_jacobian(vars_map)

        return self._chain_rule_jacobian(vars_map)

    # ── 链式法则雅可比（含从动点）──────────────────────
    def _chain_rule_jacobian(self, vars_map: Dict[int, int]):
        from geo.points import FreePoint
        from .chain_rule import get_coordinate_derivatives

        n_cols = 2 * len(vars_map)
        pts = self.involved_points()

        try:
            r = self.residual()
            n_res = len(r)
        except Exception:
            return zeros((0, n_cols), dtype=float64)

        jac = zeros((n_res, n_cols), dtype=float64)
        eps = 1e-7

        for p in pts:
            dC_dpx = zeros(n_res, dtype=float64)
            dC_dpy = zeros(n_res, dtype=float64)
            old_x, old_y = p.x, p.y

            try:
                p.x = old_x + eps
                r_px = asarray(self.residual(), dtype=float64)
                p.x = old_x - eps
                r_mx = asarray(self.residual(), dtype=float64)
                dC_dpx = (r_px - r_mx) / (2.0 * eps)
            except Exception:
                pass
            finally:
                p.x = old_x

            try:
                p.y = old_y + eps
                r_py = asarray(self.residual(), dtype=float64)
                p.y = old_y - eps
                r_my = asarray(self.residual(), dtype=float64)
                dC_dpy = (r_py - r_my) / (2.0 * eps)
            except Exception:
                pass
            finally:
                p.y = old_y

            # 三级分发
            if isinstance(p, FreePoint) and id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[:, idx * 2] = dC_dpx
                jac[:, idx * 2 + 1] = dC_dpy

            elif id(p) in vars_map:
                idx = vars_map[id(p)]
                jac[:, idx * 2] = dC_dpx
                jac[:, idx * 2 + 1] = dC_dpy

            else:
                derivs = get_coordinate_derivatives(p)
                if not derivs:
                    fallback = _numeric_chain_fallback(
                        self, p, vars_map, n_res)
                    for fp_id, d_arr in fallback.items():
                        if fp_id in vars_map:
                            idx = vars_map[fp_id]
                            n = min(n_res, len(d_arr) // 2)
                            jac[:n, idx * 2] += d_arr[:2 * n:2]
                            jac[:n, idx * 2 + 1] += d_arr[1:2 * n:2]
                else:
                    for fp_id, dm in derivs.items():
                        if fp_id in vars_map:
                            idx = vars_map[fp_id]
                            jac[:, idx * 2] += dC_dpx * dm[0] + dC_dpy * dm[2]
                            jac[:, idx * 2 + 1] += dC_dpx * dm[1] + dC_dpy * dm[3]

        return jac

    # ── 纯数值差分雅可比（无从动点，无解析式）──────────
    def _numeric_jacobian(self, vars_map: Dict[int, int]):
        eps = 1e-7
        pts = self.involved_points()
        n_res = len(self.residual())
        n_cols = 2 * len(vars_map)
        jac = zeros((n_res, n_cols), dtype=float64)

        for p in pts:
            if id(p) not in vars_map:
                continue
            idx = vars_map[id(p)]
            for axis in range(2):
                old = p.x if axis == 0 else p.y
                try:
                    if axis == 0:
                        p.x = old + eps
                    else:
                        p.y = old + eps
                    r_plus = asarray(self.residual(), dtype=float64)

                    if axis == 0:
                        p.x = old - eps
                    else:
                        p.y = old - eps
                    r_minus = asarray(self.residual(), dtype=float64)
                finally:
                    if axis == 0:
                        p.x = old
                    else:
                        p.y = old

                n = min(n_res, len(r_plus), len(r_minus))
                jac[:n, idx * 2 + axis] = (r_plus[:n] - r_minus[:n]) / (2.0 * eps)

        return jac

    # ── 序列化 ──────────────────────────────────────
    def dump(self) -> dict:
        raise NotImplementedError

    @classmethod
    def build(cls, point_map: dict, params: dict) -> 'GeometricConstraint':
        raise NotImplementedError


# ── 注册表 ──────────────────────────────────────────
CONSTRAINT_REGISTRY: Dict[str, Type[GeometricConstraint]] = {}


def register_constraint(name: str):
    def deco(cls):
        cls.type_name = name
        CONSTRAINT_REGISTRY[name] = cls
        return cls
    return deco


# ── 数值链式法则回退 ────────────────────────────────
def _numeric_chain_fallback(constraint, dep_point, vars_map, n_res):
    """直接扰动自由点，观察从动点引起的残差变化。

    返回 {fp_id: ndarray(2*n_res)}，
    布局 [dr0_dx, dr0_dy, dr1_dx, dr1_dy, ...]。
    """
    from geo.points import FreePoint

    result: Dict[int, Any] = {}
    eps = 1e-7
    free_ids = set(vars_map.keys())

    for parent in dep_point.parents:
        for fp in _collect_free_from(parent):
            if id(fp) in free_ids and id(fp) not in result:
                result[id(fp)] = zeros(2 * n_res, dtype=float64)

    for fp_id, acc in result.items():
        fp = None
        for parent in dep_point.parents:
            for p in _collect_free_from(parent):
                if id(p) == fp_id:
                    fp = p
                    break
        if fp is None:
            continue

        old_x, old_y = fp.x, fp.y

        fp.x = old_x + eps
        try:
            dep_point.recompute()
            r_px = asarray(constraint.residual(), dtype=float64)
        except Exception:
            r_px = zeros(n_res, dtype=float64)

        fp.x = old_x - eps
        try:
            dep_point.recompute()
            r_mx = asarray(constraint.residual(), dtype=float64)
        except Exception:
            r_mx = zeros(n_res, dtype=float64)

        fp.x = old_x
        fp.y = old_y + eps
        try:
            dep_point.recompute()
            r_py = asarray(constraint.residual(), dtype=float64)
        except Exception:
            r_py = zeros(n_res, dtype=float64)

        fp.y = old_y - eps
        try:
            dep_point.recompute()
            r_my = asarray(constraint.residual(), dtype=float64)
        except Exception:
            r_my = zeros(n_res, dtype=float64)

        fp.y = old_y
        try:
            dep_point.recompute()
        except Exception:
            pass

        n = min(n_res, len(r_px), len(r_mx), len(r_py), len(r_my))
        acc[:n] = (r_px[:n] - r_mx[:n]) / (2.0 * eps)
        acc[n:2 * n] = (r_py[:n] - r_my[:n]) / (2.0 * eps)

    return result


def _collect_free_from(obj):
    """从几何对象中收集自由点。"""
    from geo.points import FreePoint
    pts = []
    if isinstance(obj, FreePoint):
        pts.append(obj)
    elif hasattr(obj, 'a') and hasattr(obj, 'b'):
        for attr in ('a', 'b'):
            p = getattr(obj, attr)
            if isinstance(p, FreePoint):
                pts.append(p)
    elif hasattr(obj, 'center'):
        c = obj.center
        if isinstance(c, FreePoint):
            pts.append(c)
        t = getattr(obj, 'through', None)
        if t is not None and isinstance(t, FreePoint):
            pts.append(t)
    elif hasattr(obj, 'origin') and hasattr(obj, 'through'):
        for attr in ('origin', 'through'):
            p = getattr(obj, attr)
            if isinstance(p, FreePoint):
                pts.append(p)
    return pts