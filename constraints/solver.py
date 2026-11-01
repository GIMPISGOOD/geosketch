"""Levenberg-Marquardt 约束求解器。NumPy 向量化实现。

本次修复：
1. 每次应用步长后重算自由点下游依赖对象；
2. 吸附点在宿主重算后再投影；
3. 拒绝步后同步恢复依赖状态；
4. 跳过 invalid_expr 约束；
5. 防止 NaN / Inf 增量导致求解爆炸；
6. 空残差约束安全跳过。
"""
from numpy import (
    asarray,
    concatenate,
    vstack,
    float64,
    diag_indices,
    isfinite,
)
from numpy.linalg import (
    solve as np_solve,
    norm as np_norm,
    LinAlgError,
)
from typing import List, Any, Dict

from .base import GeometricConstraint


class ConstraintSolver:
    """LM 非线性最小二乘求解器。"""

    def __init__(self, max_iter: int = 50, tol: float = 1e-9):
        self.max_iter = max_iter
        self.tol = tol

    # ------------------------------------------------------------------
    # 依赖重算
    # ------------------------------------------------------------------

    @staticmethod
    def _collect_downstream(roots, skip_ids):
        """收集 roots 下游对象，跳过自由点本身。"""

        seen = set()
        dirty = []
        stack = []

        for r in roots:
            stack.extend(getattr(r, "children", []))

        while stack:
            obj = stack.pop()
            oid = id(obj)

            if oid in seen or oid in skip_ids:
                continue

            seen.add(oid)
            dirty.append(obj)
            stack.extend(getattr(obj, "children", []))

        # GeoObject 的 id 天然近似拓扑序：依赖先创建，id 更小
        return sorted(dirty, key=lambda o: getattr(o, "id", 0))

    @staticmethod
    def _recompute_objects(objs):
        """按给定顺序重算对象，并同步 exists。"""

        for obj in objs:
            try:
                parents = getattr(obj, "parents", [])
                obj.exists = all(
                    getattr(p, "exists", True) for p in parents
                )
                if obj.exists:
                    obj.recompute()
            except Exception:
                pass

    @classmethod
    def _sync_dependents(cls, free_points):
        """同步自由点下游依赖对象。"""

        free_ids = {id(p) for p in free_points}

        # 1. 先重算自由点下游的非自由对象
        #    例如：圆半径、交点、从动线段等
        cls._recompute_objects(
            cls._collect_downstream(free_points, free_ids)
        )

        # 2. 吸附点投影到已经更新的宿主
        for p in free_points:
            if hasattr(p, "host") and hasattr(p, "t"):
                try:
                    p.t = p.host.project(p.x, p.y)
                    p.x, p.y = p.host.point_at(p.t)
                except Exception:
                    pass

        # 3. 吸附点位置更新后，再重算其下游对象一次
        cls._recompute_objects(
            cls._collect_downstream(free_points, free_ids)
        )

    # ------------------------------------------------------------------
    # 主求解过程
    # ------------------------------------------------------------------

    def solve(
        self,
        constraints: List[GeometricConstraint],
        free_points: List[Any],
        pinned_points: List[Any]
    ) -> bool:

        valid = [c for c in constraints if getattr(c, "enabled", True)]

        if not valid or not free_points:
            return True

        vars_map: Dict[int, int] = {
            id(p): i for i, p in enumerate(free_points)
        }
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

                    if getattr(c, "status", "ok") == "invalid_expr":
                        continue

                    jac = c.jacobian(vars_map)

                    if r is None or jac is None:
                        continue

                    r_arr = asarray(r, dtype=float64).ravel()
                    if r_arr.size == 0:
                        continue

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

            F = concatenate(F_parts)
            J = vstack(J_parts)

            # ── 2. 收敛判定 ──
            norm_val = float(np_norm(F))

            if norm_val < self.tol:
                return True

            if no_improve >= 5:
                return norm_val < 1e-3

            # ── 3. 正规方程 (JᵀJ + λI)δ = −JᵀF ──
            JtJ = J.T @ J
            JtF = J.T @ F
            JtJ[diag_indices(n_vars)] += lam

            try:
                delta = np_solve(JtJ, -JtF)
            except LinAlgError:
                lam *= lam_up
                no_improve += 1
                if lam > 1e10:
                    return False
                continue

            # ★ 防止 NaN / Inf 增量导致状态污染
            if not bool(isfinite(delta).all()):
                lam *= lam_up
                no_improve += 1
                if lam > 1e10:
                    return False
                continue

            # ── 4. 保存旧状态 & 应用步长 ──
            old_coords: list = []

            for p in free_points:
                if hasattr(p, "t") and hasattr(p, "host"):
                    old_coords.append((p.x, p.y, p.t))
                else:
                    old_coords.append((p.x, p.y, None))

            for i, p in enumerate(free_points):
                p.x += float(delta[2 * i])
                p.y += float(delta[2 * i + 1])

            # ★ 先重算依赖对象，再让吸附点投影到最新宿主
            self._sync_dependents(free_points)

            # ── 5. 评估新残差 ──
            new_F_parts: list = []

            for c in valid:
                try:
                    r = c.residual()

                    if getattr(c, "status", "ok") == "invalid_expr":
                        continue

                    if r is not None:
                        new_F_parts.extend(r)

                except Exception:
                    continue

            if new_F_parts:
                new_norm = float(
                    np_norm(asarray(new_F_parts, dtype=float64).ravel())
                )
            else:
                new_norm = 0.0

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

                # ★ 拒绝步后，也必须把依赖对象恢复到旧状态
                self._sync_dependents(free_points)

                lam *= lam_up
                no_improve += 1

                if lam > 1e10:
                    return False

        return False