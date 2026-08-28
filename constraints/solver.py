"""Levenberg-Marquardt 约束求解器。NumPy 向量化实现。"""

from numpy import asarray, concatenate, vstack, float64, diag_indices
from numpy.linalg import solve as np_solve, norm as np_norm, LinAlgError
from typing import List, Any, Dict

from .base import GeometricConstraint


class ConstraintSolver:
    """LM 非线性最小二乘求解器（NumPy 向量化）。

    参数
    ----
    max_iter : int
        最大迭代次数（quick 模式 12，精确模式 50）。
    tol : float
        残差范数收敛阈值。
    """

    def __init__(self, max_iter: int = 50, tol: float = 1e-9):
        self.max_iter = max_iter
        self.tol = tol

    # ------------------------------------------------------------------
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
            # ── 1. 组装残差向量 F 与雅可比矩阵 J ──
            F_parts: list = []
            J_parts: list = []

            for c in valid:
                try:
                    r = c.residual()
                    jac = c.jacobian(vars_map)
                    if r is None or jac is None:
                        continue
                    r_arr = asarray(r, dtype=float64).ravel()
                    J_arr = asarray(jac, dtype=float64)
                    if J_arr.ndim == 1:
                        J_arr = J_arr.reshape(len(r_arr), -1)
                    if J_arr.shape[0] != len(r_arr) or J_arr.shape[1] != n_vars:
                        continue
                    F_parts.append(r_arr)
                    J_parts.append(J_arr)
                except Exception:
                    continue

            if not F_parts:
                return True

            F = concatenate(F_parts)       # (m,)
            J = vstack(J_parts)            # (m, n_vars)

            # ── 2. 收敛判定 ──
            norm_val = float(np_norm(F))
            if norm_val < self.tol:
                return True
            if no_improve >= 5:
                return norm_val < 1e-3

            # ── 3. 正规方程 (JᵀJ + λI)δ = −JᵀF ──
            JtJ = J.T @ J                  # (n_vars, n_vars)
            JtF = J.T @ F                  # (n_vars,)
            JtJ[diag_indices(n_vars)] += lam

            try:
                delta = np_solve(JtJ, -JtF)
            except LinAlgError:
                lam *= lam_up
                no_improve += 1
                if lam > 1e10:
                    return False
                continue

            # ── 4. 保存旧状态 & 应用步长 ──
            old_coords: list = []
            for p in free_points:
                if hasattr(p, 't') and hasattr(p, 'host'):
                    old_coords.append((p.x, p.y, p.t))
                else:
                    old_coords.append((p.x, p.y, None))

            for i, p in enumerate(free_points):
                p.x += float(delta[2 * i])
                p.y += float(delta[2 * i + 1])
                if hasattr(p, 'host') and hasattr(p, 't'):
                    p.t = p.host.project(p.x, p.y)
                    p.x, p.y = p.host.point_at(p.t)

            # ── 5. 评估新残差 ──
            new_F_parts: list = []
            for c in valid:
                try:
                    new_F_parts.extend(c.residual())
                except Exception:
                    continue

            new_norm = float(np_norm(new_F_parts)) if new_F_parts else 0.0

            # ── 6. 接受 / 拒绝 ──
            if new_norm < norm_val:
                lam = max(lam * lam_down, 1e-12)
                no_improve = 0
                if new_norm < self.tol:
                    return True
            else:
                for i, p in enumerate(free_points):
                    p.x, p.y = old_coords[i][0], old_coords[i][1]
                    if old_coords[i][2] is not None:
                        p.t = old_coords[i][2]
                lam *= lam_up
                no_improve += 1
                if lam > 1e10:
                    return False

        return False