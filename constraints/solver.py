"""Levenberg-Marquardt 约束求解器。纯 Python，无外部依赖。"""
import math
from typing import List, Any, Dict
from .base import GeometricConstraint

def _solve_linear(A: List[List[float]], b: List[float]) -> List[float]:
    """高斯消元（列主元）求解 Ax = b。返回 None 表示奇异。
    ★ 必须是模块级函数，不能缩进到类内部。
    """
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

        for _ in range(self.max_iter):
            F: List[float] = []
            J: List[List[float]] = []
            
            for c in valid:
                try:
                    r = c.residual()
                    jac = c.jacobian(vars_map)
                    # ★ 修复：严格校验维度，防止 F 和 J 错位导致崩溃
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

            # 构建法方程 (JᵀJ + λI)Δ = −JᵀF
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
                if lam > 1e10: return False
                continue

            old_coords = [(p.x, p.y) for p in free_points]
            for i, p in enumerate(free_points):
                p.x += delta[2 * i]
                p.y += delta[2 * i + 1]

            new_F = []
            for c in valid:
                try: new_F.extend(c.residual())
                except: continue
            new_norm = math.sqrt(sum(f * f for f in new_F)) if new_F else 0.0

            if new_norm < norm:
                lam = max(lam * lam_down, 1e-12)
                if new_norm < self.tol: return True
            else:
                for i, p in enumerate(free_points):
                    p.x, p.y = old_coords[i]
                lam *= lam_up
                if lam > 1e10: return False
        return False