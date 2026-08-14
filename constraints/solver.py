"""Levenberg-Marquardt 约束求解器（优化版）。
优化点：
1. Cholesky 分解替代高斯消元（对称正定，快约 2 倍）
2. 稀疏法方程组装（只累加约束涉及点的列）
3. 独立连通分量分组求解（减小矩阵规模）
4. λ 复用（拒绝步时不重新组装雅可比）
5. 解析雅可比优先（通过 base.py 钩子）
"""
import math
from typing import List, Any, Dict, Optional

from .base import GeometricConstraint


# ─────────────── Cholesky 分解（对称正定）───────────────

def _cholesky(A: List[List[float]]) -> Optional[List[List[float]]]:
    """对称正定矩阵 Cholesky 分解 A = L·Lᵀ。失败返回 None。"""
    n = len(A)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = 0.0
            for k in range(j):
                s += L[i][k] * L[j][k]
            if i == j:
                val = A[i][i] - s
                if val <= 1e-15:
                    return None
                L[i][j] = math.sqrt(val)
            else:
                if abs(L[j][j]) < 1e-15:
                    return None
                L[i][j] = (A[i][j] - s) / L[j][j]
    return L


def _cholesky_solve(L: List[List[float]], b: List[float]) -> List[float]:
    """前代 + 回代求解 L·Lᵀ·x = b。"""
    n = len(b)
    y = [0.0] * n
    for i in range(n):
        s = 0.0
        for k in range(i):
            s += L[i][k] * y[k]
        y[i] = (b[i] - s) / L[i][i]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = 0.0
        for k in range(i + 1, n):
            s += L[k][i] * x[k]
        x[i] = (y[i] - s) / L[i][i]
    return x


# ─────────────── 并查集分组 ───────────────

def _group_independent(constraints, free_points):
    """用并查集将共享自由点的约束分组，返回 [(constraints, points), ...]。
    不共享点的约束组互相独立，可分别求解小矩阵。"""
    if not free_points:
        return []
    fp_ids = {id(p) for p in free_points}
    parent = {pid: pid for pid in fp_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for c in constraints:
        pts = [id(p) for p in c.involved_points() if id(p) in fp_ids]
        for i in range(1, len(pts)):
            union(pts[0], pts[i])

    groups = {}
    for p in free_points:
        root = find(id(p))
        groups.setdefault(root, []).append(p)

    result = []
    for root, pts in groups.items():
        pt_set = {id(p) for p in pts}
        cs = [c for c in constraints
              if any(id(p) in pt_set for p in c.involved_points())]
        if cs:
            result.append((cs, pts))
    return result


# ─────────────── 求解器 ───────────────

class ConstraintSolver:
    """LM 求解器（优化版）。"""

    def __init__(self, max_iter=50, tol=1e-9):
        self.max_iter = max_iter
        self.tol = tol

    def solve(self, constraints, free_points, pinned_points) -> bool:
        valid = [c for c in constraints if c.enabled]
        if not valid or not free_points:
            return True
        groups = _group_independent(valid, free_points)
        if not groups:
            return True
        all_ok = True
        for group_cs, group_pts in groups:
            if not self._solve_group(group_cs, group_pts):
                all_ok = False
        return all_ok

    def _solve_group(self, constraints, free_points) -> bool:
        """对单个连通分量执行 LM 迭代。"""
        vars_map: Dict[int, int] = {id(p): i for i, p in enumerate(free_points)}
        n_vars = 2 * len(free_points)
        if n_vars == 0:
            return True

        lam = 1e-3
        lam_up, lam_down = 10.0, 0.1

        F: List[float] = []
        JtJ_base: List[List[float]] = []
        JtF: List[float] = []
        norm = float('inf')
        need_assemble = True

        for _ in range(self.max_iter):
            if need_assemble:
                F, JtJ_base, JtF, norm = self._assemble(
                    constraints, vars_map, n_vars)
                need_assemble = False
                if not F:
                    return True
                if norm < self.tol:
                    return True

            # JtJ = JtJ_base + λI（只改对角线，复用基础矩阵）
            JtJ = [row[:] for row in JtJ_base]
            for i in range(n_vars):
                JtJ[i][i] += lam

            L = _cholesky(JtJ)
            if L is None:
                lam *= lam_up
                if lam > 1e10:
                    return False
                continue

            delta = _cholesky_solve(L, [-f for f in JtF])

            old_coords = [(p.x, p.y) for p in free_points]
            for i, p in enumerate(free_points):
                p.x += delta[2 * i]
                p.y += delta[2 * i + 1]

            new_norm = self._residual_norm(constraints)
            if new_norm < norm:
                lam = max(lam * lam_down, 1e-12)
                norm = new_norm
                need_assemble = True          # 点变了，下次重新组装
                if norm < self.tol:
                    return True
            else:
                # 回退，增加 λ，不重新组装（复用 JtJ_base）
                for i, p in enumerate(free_points):
                    p.x, p.y = old_coords[i]
                lam *= lam_up
                if lam > 1e10:
                    return False
        return False

    def _assemble(self, constraints, vars_map, n_vars):
        """组装 F、JᵀJ（不含 λ）、JᵀF。稀疏累加：只遍历约束涉及点的列。"""
        F: List[float] = []
        JtJ = [[0.0] * n_vars for _ in range(n_vars)]
        JtF = [0.0] * n_vars

        for c in constraints:
            try:
                r = c.residual()
                jac = c.jacobian(vars_map)
            except Exception:
                continue

            # 该约束的非零列（涉及自由点的 x/y）
            cols = []
            for p in c.involved_points():
                if id(p) in vars_map:
                    idx = vars_map[id(p)]
                    cols.extend([idx * 2, idx * 2 + 1])
            cols = sorted(set(cols))

            for i in range(len(r)):
                fi = r[i]
                F.append(fi)
                if i >= len(jac):
                    continue
                row = jac[i]
                if len(row) != n_vars:
                    continue
                for j in cols:
                    JtF[j] += row[j] * fi
                    for k in cols:
                        JtJ[j][k] += row[j] * row[k]

        norm = math.sqrt(sum(f * f for f in F)) if F else 0.0
        return F, JtJ, JtF, norm

    @staticmethod
    def _residual_norm(constraints) -> float:
        total = 0.0
        for c in constraints:
            try:
                for f in c.residual():
                    total += f * f
            except Exception:
                pass
        return math.sqrt(total)