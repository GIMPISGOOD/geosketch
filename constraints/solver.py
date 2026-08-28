"""Levenberg-Marquardt 约束求解器。纯 Python，无外部依赖。"""
import math
from typing import List, Any, Dict
from .base import GeometricConstraint


def _solve_linear(A: List[List[float]], b: List[float]) -> List[float]:
    n = len(b)
    if n == 0:
        return []
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(M[r][col]))
        if abs(M[pivot][col]) < 1e-15:
            return None
        M[col], M[pivot] = M[pivot], M[col]
        for row in range(col + 1, n):
            f = M[row][col] / M[col][col]
            for j in range(col, n + 1):
                M[row][j] -= f * M[col][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        x[i] = M[i][n]
        for j in range(i + 1, n):
            x[i] -= M[i][j] * x[j]
        x[i] /= M[i][i]
    return x


class ConstraintSolver:
    """LM 求解器。"""

    def __init__(self, max_iter=50, tol=1e-9):
        self.max_iter = max_iter
        self.tol = tol

    def solve(self, constraints: List[GeometricConstraint],
              free_points: List[Any], pinned_points: List[Any]) -> bool:
        valid = [c for c in constraints if c.enabled]
        if not valid or not free_points:
            return True

        vars_map: Dict[int, int] = {id(p): i for i, p in enumerate(free_points)}
        n_vars = 2 * len(free_points)
        lam = 1e-3
        lam_up, lam_down = 10.0, 0.1
        no_improve = 0

        for _ in range(self.max_iter):
            F: List[float] = []
            J: List[List[float]] = []
            for c in valid:
                try:
                    r = c.residual()
                    jac = c.jacobian(vars_map)
                    if not isinstance(r, list) or not isinstance(jac, list):
                        continue
                    if len(r) != len(jac):
                        continue
                    if len(jac) > 0 and len(jac[0]) != n_vars:
                        continue
                    F.extend(r)
                    J.extend(jac)
                except Exception:
                    continue

            if not F:
                return True

            norm = math.sqrt(sum(f * f for f in F))
            if norm < self.tol:
                return True
            if no_improve >= 5:
                return norm < 1e-3

            JtJ = [[0.0] * n_vars for _ in range(n_vars)]
            JtF = [0.0] * n_vars
            for i in range(len(F)):
                for j in range(n_vars):
                    JtF[j] += J[i][j] * F[i]
                    for k in range(n_vars):
                        JtJ[j][k] += J[i][j] * J[i][k]

            for i in range(n_vars):
                JtJ[i][i] += lam

            delta = _solve_linear(JtJ, [-f for f in JtF])
            if delta is None:
                lam *= lam_up
                no_improve += 1
                if lam > 1e10:
                    return False
                continue

            # ★ 修复：保存旧坐标（含从动点参数 t）
            old_coords = []
            for p in free_points:
                if hasattr(p, 't'):
                    old_coords.append((p.x, p.y, p.t))
                else:
                    old_coords.append((p.x, p.y, None))

            for i, p in enumerate(free_points):
                p.x += delta[2 * i]
                p.y += delta[2 * i + 1]
                # ★ 修复：吸附点投影回宿主曲线
                if hasattr(p, 'host') and hasattr(p, 't'):
                    p.t = p.host.project(p.x, p.y)
                    p.x, p.y = p.host.point_at(p.t)

            new_F = []
            for c in valid:
                try:
                    new_F.extend(c.residual())
                except Exception:
                    continue
            new_norm = math.sqrt(sum(f * f for f in new_F)) if new_F else 0.0

            if new_norm < norm:
                lam = max(lam * lam_down, 1e-12)
                no_improve = 0
                if new_norm < self.tol:
                    return True
            else:
                # ★ 修复：回退时同时恢复 t
                for i, p in enumerate(free_points):
                    p.x, p.y = old_coords[i][0], old_coords[i][1]
                    if old_coords[i][2] is not None:
                        p.t = old_coords[i][2]
                lam *= lam_up
                no_improve += 1
                if lam > 1e10:
                    return False

        return False