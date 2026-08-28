"""约束基类与注册表。"""
from typing import List, Any, Dict, Type


class GeometricConstraint:
    _next_id = 1

    def __init__(self):
        self.cid = f"c{GeometricConstraint._next_id}"
        GeometricConstraint._next_id += 1
        self.enabled = True
        self.status = "ok"

    def involved_points(self) -> List[Any]:
        raise NotImplementedError

    def residual(self) -> List[float]:
        raise NotImplementedError

    def jacobian(self, vars_map: Dict[int, int]) -> List[List[float]]:
        """雅可比矩阵。
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
                    return analytic(vars_map)
                except Exception:
                    pass
            return self._numeric_jacobian(vars_map)

        return self._chain_rule_jacobian(vars_map)

    def _chain_rule_jacobian(self, vars_map: Dict[int, int]) -> List[List[float]]:
        from geo.points import FreePoint
        from .chain_rule import get_coordinate_derivatives
        n_cols = 2 * len(vars_map)
        pts = self.involved_points()
        try:
            r = self.residual()
            n_res = len(r)
        except Exception:
            return []
        jac = [[0.0] * n_cols for _ in range(n_res)]
        eps = 1e-7

        for p in pts:
            dC_dpx = [0.0] * n_res
            dC_dpy = [0.0] * n_res
            old_x, old_y = p.x, p.y

            try:
                p.x = old_x + eps
                r_px = self.residual()
                p.x = old_x - eps
                r_mx = self.residual()
                for i in range(n_res):
                    dC_dpx[i] = (r_px[i] - r_mx[i]) / (2 * eps)
            except Exception:
                pass
            finally:
                p.x = old_x

            try:
                p.y = old_y + eps
                r_py = self.residual()
                p.y = old_y - eps
                r_my = self.residual()
                for i in range(n_res):
                    dC_dpy[i] = (r_py[i] - r_my[i]) / (2 * eps)
            except Exception:
                pass
            finally:
                p.y = old_y

            if isinstance(p, FreePoint):
                if id(p) in vars_map:
                    idx = vars_map[id(p)]
                    for i in range(n_res):
                        jac[i][idx * 2] = dC_dpx[i]
                        jac[i][idx * 2 + 1] = dC_dpy[i]

            elif id(p) in vars_map:
                # ★ 修复：从动点本身在优化变量中，直接使用数值偏导
                idx = vars_map[id(p)]
                for i in range(n_res):
                    jac[i][idx * 2] = dC_dpx[i]
                    jac[i][idx * 2 + 1] = dC_dpy[i]

            else:
                derivs = get_coordinate_derivatives(p)
                if not derivs:
                    for fp_id, d_matrix in _numeric_chain_fallback(
                            self, p, vars_map, n_res).items():
                        if fp_id in vars_map:
                            idx = vars_map[fp_id]
                            for i in range(n_res):
                                jac[i][idx * 2] += d_matrix[0]
                                jac[i][idx * 2 + 1] += d_matrix[1]
                else:
                    for fp_id, d_matrix in derivs.items():
                        if fp_id in vars_map:
                            idx = vars_map[fp_id]
                            for i in range(n_res):
                                jac[i][idx * 2] += dC_dpx[i] * d_matrix[0] + dC_dpy[i] * d_matrix[2]
                                jac[i][idx * 2 + 1] += dC_dpx[i] * d_matrix[1] + dC_dpy[i] * d_matrix[3]
        return jac

    def _numeric_jacobian(self, vars_map: Dict[int, int]) -> List[List[float]]:
        eps = 1e-7
        pts = self.involved_points()
        n_res = len(self.residual())
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols for _ in range(n_res)]
        for p in pts:
            if id(p) not in vars_map:
                continue
            idx = vars_map[id(p)]
            for axis in range(2):
                old = p.x if axis == 0 else p.y
                r_plus = r_minus = None
                try:
                    if axis == 0: p.x = old + eps
                    else: p.y = old + eps
                    r_plus = self.residual()
                    if axis == 0: p.x = old - eps
                    else: p.y = old - eps
                    r_minus = self.residual()
                finally:
                    if axis == 0: p.x = old
                    else: p.y = old
                if r_plus is not None and r_minus is not None:
                    for j in range(min(n_res, len(r_plus), len(r_minus))):
                        jac[j][idx * 2 + axis] = (r_plus[j] - r_minus[j]) / (2 * eps)
        return jac

    def dump(self) -> dict:
        raise NotImplementedError

    @classmethod
    def build(cls, point_map: dict, params: dict) -> 'GeometricConstraint':
        raise NotImplementedError


CONSTRAINT_REGISTRY: Dict[str, Type[GeometricConstraint]] = {}


def register_constraint(name: str):
    def deco(cls):
        cls.type_name = name
        CONSTRAINT_REGISTRY[name] = cls
        return cls
    return deco

def _numeric_chain_fallback(constraint, dep_point, vars_map, n_res):
    """数值回退：直接扰动自由点，观察残差变化。"""
    from geo.points import FreePoint
    result = {}
    eps = 1e-7

    # 找到所有相关的自由点
    free_ids = set(vars_map.keys())
    for parent in dep_point.parents:
        for fp in _collect_free_from(parent):
            if id(fp) in free_ids and id(fp) not in result:
                result[id(fp)] = [0.0] * (2 * n_res)

    for fp_id, acc in result.items():
        # 找到对应的 FreePoint 对象
        fp = None
        for parent in dep_point.parents:
            for p in _collect_free_from(parent):
                if id(p) == fp_id:
                    fp = p
                    break
        if fp is None:
            continue

        old_x, old_y = fp.x, fp.y
        # +x
        fp.x = old_x + eps
        try:
            dep_point.recompute()
            r_px = constraint.residual()
        except Exception:
            r_px = [0.0] * n_res
        # -x
        fp.x = old_x - eps
        try:
            dep_point.recompute()
            r_mx = constraint.residual()
        except Exception:
            r_mx = [0.0] * n_res
        fp.x = old_x

        # +y
        fp.y = old_y + eps
        try:
            dep_point.recompute()
            r_py = constraint.residual()
        except Exception:
            r_py = [0.0] * n_res
        # -y
        fp.y = old_y - eps
        try:
            dep_point.recompute()
            r_my = constraint.residual()
        except Exception:
            r_my = [0.0] * n_res
        fp.y = old_y

        try:
            dep_point.recompute()
        except Exception:
            pass

        for i in range(n_res):
            acc[2 * i] = (r_px[i] - r_mx[i]) / (2 * eps)
            acc[2 * i + 1] = (r_py[i] - r_my[i]) / (2 * eps)

    # 转换为元组格式
    return {k: tuple(v) for k, v in result.items()}


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