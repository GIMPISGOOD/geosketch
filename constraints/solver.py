"""Levenberg-Marquardt 约束求解器（v2 数值内核，纯 NumPy）。

v2 升级（数值稳定性 + 速度）：
1. 行归一化 —— 残差/雅可比按行范数归一，消除长度/角度量纲混杂的条件数失衡；
2. Marquardt 对角阻尼 (JᵀJ + λ·diag) 带对角地板，替代旧版 λI；
3. Nielsen 增益比自适应 λ；拖动模式跨帧热启动；
4. 拒绝步复用缓存 F/J，不重算残差/雅可比（病态场景的主要提速点）；
5. 拖动模式 Tikhonov 时间连续项 μ‖x − x_prev‖²，抑制欠约束系统
   零空间漂移与帧间重新分配（三圆相切抖动主因之一）；
6. 可选步长钳制（max_step），防止单帧跳变；
7. 收敛/返回语义与旧版完全一致（原始残差范数、绝对 tol），
   保证上游测试与过约束检测行为不变。
"""
from numpy import (
    asarray,
    concatenate,
    vstack,
    float64,
    diag_indices,
    isfinite,
    sqrt as np_sqrt,
)
from numpy.linalg import (
    solve as np_solve,
    norm as np_norm,
    LinAlgError,
)
from typing import List, Any, Dict, Optional
from .base import GeometricConstraint

_LAM_MAX = 1e12      # λ 上限
_DIAG_FLOOR = 1e-4   # Marquardt 对角地板：防止零列导致奇异
_ROW_FLOOR = 1e-8    # 行范数地板：防止除零
_STALL_TOL = 1e-3    # 停滞兜底收敛阈值（与旧版一致）


class ConstraintSolver:
    """LM 非线性最小二乘求解器（v2）。

    向后兼容：构造签名、solve(constraints, free_points, pinned_points)
    调用方式与返回语义均不变；drag_mode / max_step 为新增可选参数。
    """

    def __init__(self, max_iter: int = 50, tol: float = 1e-9):
        self.max_iter = max_iter
        self.tol = tol
        # ── 拖动模式参数 ──
        self.drag_tikhonov = 1e-3   # μ = drag_tikhonov × mean(diag(JᵀJ))
        self._lam_warm = 1e-3       # 跨帧热启动 λ（仅拖动模式使用）

    # ------------------------------------------------------------------
    # 依赖重算（沿用 v1，行为不变）
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
        cls._recompute_objects(
            cls._collect_downstream(free_points, free_ids)
        )
        for p in free_points:
            if hasattr(p, "host") and hasattr(p, "t"):
                try:
                    p.t = p.host.project(p.x, p.y)
                    p.x, p.y = p.host.point_at(p.t)
                except Exception:
                    pass
        cls._recompute_objects(
            cls._collect_downstream(free_points, free_ids)
        )

    # ------------------------------------------------------------------
    # 组装
    # ------------------------------------------------------------------
    @staticmethod
    def _assemble(valid, vars_map, n_vars):
        """组装原始残差 F 与原始雅可比 J。
        返回 (F, J, used)；无有效约束返回 None。
        used: 成功贡献的 (约束, 残差维数) 列表，供廉价重评估。
        """
        F_parts: list = []
        J_parts: list = []
        used: list = []
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
                used.append((c, r_arr.size))
            except Exception:
                continue
        if not F_parts:
            return None
        return concatenate(F_parts), vstack(J_parts), used

    @staticmethod
    def _eval_residual(used):
        """只重评估 used 约束的原始残差（不组雅可比，廉价）。
        任何结构变化（异常/维数变化）返回 None → 走安全的拒绝+重组路径。
        """
        parts: list = []
        for c, n in used:
            try:
                if getattr(c, "status", "ok") == "invalid_expr":
                    return None
                r = c.residual()
                if r is None:
                    return None
                arr = asarray(r, dtype=float64).ravel()
                if arr.size != n:
                    return None
                parts.append(arr)
            except Exception:
                return None
        if not parts:
            return None
        return concatenate(parts)

    # ------------------------------------------------------------------
    # 主求解过程
    # ------------------------------------------------------------------
    def solve(
        self,
        constraints: List[GeometricConstraint],
        free_points: List[Any],
        pinned_points: List[Any],
        drag_mode: bool = False,
        max_step: Optional[float] = None,
    ) -> bool:
        valid = [c for c in constraints if getattr(c, "enabled", True)]
        if not valid or not free_points:
            return True

        vars_map: Dict[int, int] = {
            id(p): i for i, p in enumerate(free_points)
        }
        n_vars = 2 * len(free_points)

        asm = self._assemble(valid, vars_map, n_vars)
        if asm is None:
            return True
        F, J, used = asm

        # ── 拖动模式：Tikhonov 参考 = 本次求解开始时的坐标 ──
        xr = None
        if drag_mode:
            ref = []
            for p in free_points:
                ref.append(p.x)
                ref.append(p.y)
            xr = asarray(ref, dtype=float64)

        def _cur_vec():
            v = []
            for p in free_points:
                v.append(p.x)
                v.append(p.y)
            return asarray(v, dtype=float64)

        def _save_old():
            old = []
            for p in free_points:
                if hasattr(p, "t") and hasattr(p, "host"):
                    old.append((p.x, p.y, p.t))
                else:
                    old.append((p.x, p.y, None))
            return old

        def _restore(old):
            for i, p in enumerate(free_points):
                p.x, p.y = old[i][0], old[i][1]
                if old[i][2] is not None:
                    p.t = old[i][2]

        def _rescale(F_, J_):
            s = np_sqrt((J_ * J_).sum(axis=1))
            s = s.clip(min=_ROW_FLOOR)
            return s, F_ / s, J_ / s[:, None]

        scales, Fs, Js = _rescale(F, J)
        norm = float(np_norm(F))
        if norm < self.tol:
            return True

        lam = self._lam_warm if drag_mode else 1e-3
        nu = 2.0
        rejects = 0
        di = diag_indices(n_vars)
        mu = 0.0

        for _ in range(self.max_iter):
            A = Js.T @ Js
            g = Js.T @ Fs
            diag = A.diagonal().copy()
            diag[diag < _DIAG_FLOOR] = _DIAG_FLOOR
            if drag_mode and xr is not None:
                mu = self.drag_tikhonov * max(float(diag.mean()), 1e-12)
            else:
                mu = 0.0

            accepted = False
            for _attempt in range(16):
                if mu > 0.0:
                    dref = _cur_vec() - xr
                    rhs = -(g + mu * dref)
                else:
                    dref = None
                    rhs = -g
                M = A.copy()
                M[di] += lam * diag + mu
                try:
                    delta = np_solve(M, rhs)
                except LinAlgError:
                    lam = min(lam * nu, _LAM_MAX)
                    nu *= 2.0
                    if lam >= _LAM_MAX:
                        break
                    continue
                if not bool(isfinite(delta).all()):
                    lam = min(lam * nu, _LAM_MAX)
                    nu *= 2.0
                    if lam >= _LAM_MAX:
                        break
                    continue
                # ★ 步长钳制（拖动模式由调用方提供）
                if max_step is not None and max_step > 0.0:
                    dn = float(np_norm(delta))
                    if dn > max_step:
                        delta = delta * (max_step / dn)

                old = _save_old()
                for i, p in enumerate(free_points):
                    p.x += float(delta[2 * i])
                    p.y += float(delta[2 * i + 1])
                self._sync_dependents(free_points)

                new_raw = self._eval_residual(used)
                if new_raw is None:
                    # 结构变化：拒绝本步，恢复后重组
                    _restore(old)
                    self._sync_dependents(free_points)
                    asm = self._assemble(valid, vars_map, n_vars)
                    if asm is None:
                        return True
                    F, J, used = asm
                    scales, Fs, Js = _rescale(F, J)
                    norm = float(np_norm(F))
                    if norm < self.tol:
                        return True
                    accepted = True   # 外层循环重算 A/g
                    break

                new_Fs = new_raw / scales
                aug_new = float((new_Fs * new_Fs).sum())
                aug_old = float((Fs * Fs).sum())
                if mu > 0.0:
                    dref_new = _cur_vec() - xr
                    aug_new += mu * float(dref_new @ dref_new)
                    aug_old += mu * float(dref @ dref)
                ared = 0.5 * (aug_old - aug_new)
                pred = (0.5 * float(delta @ (A @ delta))
                        + lam * float(delta @ (diag * delta))
                        + mu * float(delta @ delta))
                rho = ared / pred if pred > 1e-30 else -1.0

                if rho > 1e-9:
                    # ── 接受：Nielsen λ 更新 + 在新状态重组雅可比 ──
                    lam = max(lam * max(1.0 / 3.0,
                                        1.0 - (2.0 * rho - 1.0) ** 3),
                              1e-12)
                    nu = 2.0
                    rejects = 0
                    F = new_raw
                    norm = float(np_norm(F))
                    if norm < self.tol:
                        self._lam_warm = min(max(lam, 1e-6), 1e2)
                        return True
                    asm = self._assemble(valid, vars_map, n_vars)
                    if asm is None:
                        return True
                    F, J, used = asm
                    scales, Fs, Js = _rescale(F, J)
                    norm = float(np_norm(F))
                    if norm < self.tol:
                        self._lam_warm = min(max(lam, 1e-6), 1e2)
                        return True
                    accepted = True
                    break
                else:
                    # ── 拒绝：恢复状态、升 λ、复用缓存 F/J（不重算）──
                    _restore(old)
                    self._sync_dependents(free_points)
                    lam = min(lam * nu, _LAM_MAX)
                    nu *= 2.0
                    rejects += 1
                    if lam >= _LAM_MAX or rejects >= 12:
                        self._lam_warm = 1e-3
                        return norm < _STALL_TOL
            if not accepted:
                self._lam_warm = 1e-3
                return norm < _STALL_TOL

        self._lam_warm = min(max(lam, 1e-6), 1e2) if drag_mode else 1e-3
        return False