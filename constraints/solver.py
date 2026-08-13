"""Levenberg-Marquardt 约束求解器。纯 Python 实现，无外部依赖。"""
import math
from typing import List, Any, Dict
from .base import GeometricConstraint

def solve_linear(A: List[List[float]], b: List[float]) -> List[float]:
    """高斯消元法（列主元）求解线性方程组 Ax = b。"""
    n = len(b)
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
    def __init__(self, max_iter=30, tol=1e-9):
        self.max_iter = max_iter
        self.tol = tol

    def solve(self, constraints: List[GeometricConstraint], 
              free_points: List[Any], pinned_points: List[Any]) -> bool:
        if not constraints or not free_points:
            return True

        # 建立变量索引映射 (每个 FreePoint 贡献 x, y 两个变量)
        vars_map = {id(p): i for i, p in enumerate(free_points)}
        n_vars = len(free_points) * 2
        
        lam = 1e-3
        lam_up, lam_down = 10.0, 0.1
        
        for _ in range(self.max_iter):
            F = []
            J = []
            for c in constraints:
                if not c.enabled: continue
                r = c.residual()
                jac = c.jacobian(vars_map)
                F.extend(r)
                J.extend(jac)
                
            if not F: return True
            
            norm = math.sqrt(sum(f * f for f in F))
            if norm < self.tol:
                return True

            # 构建法方程 (J^T J + lambda * I) delta = -J^T F
            n_eqs = len(F)
            JtJ = [[0.0] * n_vars for _ in range(n_vars)]
            JtF = [0.0] * n_vars
            
            for i in range(n_eqs):
                for j in range(n_vars):
                    JtF[j] += J[i][j] * F[i]
                    for k in range(n_vars):
                        JtJ[j][k] += J[i][j] * J[i][k]
                        
            for i in range(n_vars):
                JtJ[i][i] += lam

            delta = solve_linear(JtJ, [-f for f in JtF])
            if delta is None:
                lam *= lam_up
                continue

            # 试探步
            old_coords = [(p.x, p.y) for p in free_points]
            for i, p in enumerate(free_points):
                p.x += delta[2 * i]
                p.y += delta[2 * i + 1]

            # 计算新残差
            new_F = []
            for c in constraints:
                if c.enabled: new_F.extend(c.residual())
            new_norm = math.sqrt(sum(f * f for f in new_F))

            if new_norm < norm:
                lam = max(lam * lam_down, 1e-12)
                if new_norm < self.tol: return True
            else:
                # 回退
                for i, p in enumerate(free_points):
                    p.x, p.y = old_coords[i]
                lam *= lam_up
                
        return False