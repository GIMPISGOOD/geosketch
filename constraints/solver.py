"""Levenberg-Marquardt 约束求解器（v2.2 数值内核，纯 NumPy）。

v2 升级（数值稳定性 + 速度）：
1. 行归一化 —— 残差/雅可比按行范数归一，消除长度/角度量纲混杂的条件数失衡；
2. λI 信赖域阻尼 (JᵀJ + (λ+μ)I)：本系统通常秩亏，对角阻尼会把步长扭向
   弱耦合变量方向；λI 保证最小范数 GN 方向与恒正定；
3. Nielsen 增益比自适应 λ；拖动模式跨帧热启动；
4. 拒绝步复用缓存 F/J，不重算残差/雅可比；
5. 拖动模式 Tikhonov 时间连续项 μ‖x − x_prev‖²；
6. 可选步长钳制（max_step）；
7. 收敛/返回语义与旧版一致（原始残差范数、绝对 tol）。

v2.2 修复（pin 语义 + merit 污染 + 静默失效）：
A. pinned_points 真正生效：被 pin 的吸附点「位置冻结、参数吸收」，
   不再被 _sync_dependents 用旧 t 带走 —— 切断 ΔA = L²Δt/d 的放大链；
B. 零梯度行屏蔽：旧版 clip(1e-8) 把无信息行的残差放大 1e8 倍塞进 merit，
   使 ρ 失真。改为 scale=inf（Fs/Js 归零），原始 F 范数不变；
C. free_points 去重 + pinned 优先：重复点会让 n_vars 与雅可比列数不符，
   导致 _assemble 返回 None 而静默"求解成功"；
D. F/J 非有限值过滤：单个坏约束不再毒化整帧；
E. 拒绝步快照覆盖冻结点，避免钳制/投影造成的状态泄漏；
F. pred 修正为 0.5·δᵀAδ + (λ+0.5μ)‖δ‖²（增广目标的精确模型下降量）。
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
_ROW_FLOOR = 1e-8    # 行范数地板：低于此值视为「零梯度行」
_STALL_TOL = 1e-3    # 停滞兜底收敛阈值（与旧版一致）


def _rescale_rows(F_, J_):
    """行归一化 + 零梯度行屏蔽。

    ★ v2.2：旧版 `s.clip(min=1e-8)` 会把零梯度行（例如两点重合时
    DistanceConstraint 返回的全零雅可比）的残差放大 1e8 倍。该行对
    A=JᵀJ、g=JᵀF 贡献为 0，却把 ‖Fs‖² 抬到 1e17 量级；一旦它的残差随
    其它变量变化，ared / ρ 就被伪项支配，表现为不可解释的接受/拒绝抖动。

    零梯度行不携带任何「一步可降」的信息，正确做法是从缩放系统中剔除：
    令 scale=inf ⇒ Fs=0、Js=0。原始 F 不被修改，故 norm 与返回语义不变。
    """
    rn = np_sqrt((J_ * J_).sum(axis=1))
    s = rn.copy()
    s[rn <= _ROW_FLOOR] = float("inf")
    return s, F_ / s, J_ / s[:, None]


class ConstraintSolver:
    """LM 非线性最小二乘求解器（v2.2）。

    向后兼容：构造签名、solve(constraints, free_points, pinned_points)
    调用方式与返回语义均不变；drag_mode / max_step 为可选参数。
    """

    def __init__(self, max_iter: int = 50, tol: float = 1e-9):
        self.max_iter = max_iter
        self.tol = tol
        # ── 拖动模式参数 ──
        self.drag_tikhonov = 1e-3   # μ = drag_tikhonov × mean(diag(JᵀJ))
        self._lam_warm = 1e-3       # 跨帧热启动 λ（仅拖动模式使用）

    # ------------------------------------------------------------------
    #  依赖重算
    # ------------------------------------------------------------------
    @staticmethod
    def _collect_downstream(roots, skip_ids):
        """收集 roots 下游对象。

        ★ v2.2：skip_ids 中的对象**不重算但仍遍历其子树**。
        旧版直接剪枝，导致被冻结的吸附点的下游对象漏重算。
        对自由点而言等价（它们全是 roots，子节点已被种子化）。
        """
        seen = set()
        dirty = []
        stack = []
        for r in roots:
            stack.extend(getattr(r, "children", []))
        while stack:
            obj = stack.pop()
            oid = id(obj)
            if oid in seen:
                continue
            seen.add(oid)
            if oid not in skip_ids:
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

    @staticmethod
    def _reproject(p):
        """吸附点：位置 → 参数 → 位置（保持在宿主上的收缩映射）。"""
        try:
            p.t = p.host.project(p.x, p.y)
            p.x, p.y = p.host.point_at(p.t)
        except Exception:
            pass

    @classmethod
    def _sync_dependents(cls, free_points, frozen_points=()):
        """同步自由点下游依赖对象。

        ★ v2.2：frozen_points（被 pin 的吸附点）位置冻结 —— 不 stepping、
        不被宿主用旧 t 重算带走；步后仅做参数回投，使其在宿主运动后
        仍留在宿主上（沿宿主方向的宿主运动可精确保位）。
        """
        free_ids = {id(p) for p in free_points}
        frozen = [p for p in frozen_points if id(p) not in free_ids]
        skip = free_ids | {id(p) for p in frozen}

        cls._recompute_objects(cls._collect_downstream(free_points, skip))
        for p in free_points:
            if hasattr(p, "host") and hasattr(p, "t"):
                cls._reproject(p)
        for p in frozen:
            cls._reproject(p)
        cls._recompute_objects(cls._collect_downstream(free_points, skip))

    # ------------------------------------------------------------------
    #  组装
    # ------------------------------------------------------------------
    @staticmethod
    def _assemble(valid, vars_map, n_vars, frozen_ids=frozenset()):
        """组装原始残差 F 与原始雅可比 J。返回 (F, J, used) 或 None。

        ★ v2.2：① F/J 非有限值过滤；② 向约束传递冻结点提示
        （_frozen_ids，用完即还原，不污染外部直接调用 jacobian）。
        """
        F_parts: list = []
        J_parts: list = []
        used: list = []

        for c in valid:
            try:
                r = c.residual()
                if getattr(c, "status", "ok") == "invalid_expr":
                    continue
                if r is None:
                    continue
                r_arr = asarray(r, dtype=float64).ravel()
                if r_arr.size == 0 or not bool(isfinite(r_arr).all()):
                    continue

                prev = getattr(c, "_frozen_ids", frozenset())
                c._frozen_ids = frozen_ids
                try:
                    jac = c.jacobian(vars_map)
                finally:
                    c._frozen_ids = prev
                if jac is None:
                    continue

                J_arr = asarray(jac, dtype=float64)
                if J_arr.ndim == 1:
                    J_arr = J_arr.reshape(len(r_arr), -1)
                if J_arr.shape[0] != len(r_arr) or J_arr.shape[1] != n_vars:
                    continue
                if not bool(isfinite(J_arr).all()):
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
        """只重评估 used 约束的原始残差（不组雅可比，廉价）。"""
        parts: list = []
        for c, n in used:
            try:
                if getattr(c, "status", "ok") == "invalid_expr":
                    return None
                r = c.residual()
                if r is None:
                    return None
                arr = asarray(r, dtype=float64).ravel()
                if arr.size != n or not bool(isfinite(arr).all()):
                    return None
                parts.append(arr)
            except Exception:
                return None
        if not parts:
            return None
        return concatenate(parts)

    # ------------------------------------------------------------------
    #  主求解过程
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

        # ★ v2.2：pinned 优先 + 去重。
        #   旧版完全忽略 pinned_points；且 free_points 若含重复项，
        #   n_vars 会与雅可比列数不符 → _assemble 返回 None → 静默 True。
        pinned_ids = {id(p) for p in (pinned_points or [])}
        seen: set = set()
        fp: list = []
        for p in free_points:
            pid = id(p)
            if pid in seen or pid in pinned_ids:
                continue
            seen.add(pid)
            fp.append(p)
        free_points = fp
        if not free_points:
            return True

        # ★ v2.2：被 pin 的吸附点 = 位置冻结、参数吸收
        frozen_dep: list = []
        _fseen: set = set()
        for p in (pinned_points or []):
            pid = id(p)
            if pid in seen or pid in _fseen:
                continue
            if hasattr(p, "host") and hasattr(p, "t"):
                _fseen.add(pid)
                frozen_dep.append(p)
        frozen_ids = frozenset(_fseen)

        # 需要快照/回滚的点 = 自由点 ∪ 冻结点
        tracked = free_points + frozen_dep

        vars_map: Dict[int, int] = {
            id(p): i for i, p in enumerate(free_points)
        }
        n_vars = 2 * len(free_points)

        asm = self._assemble(valid, vars_map, n_vars, frozen_ids)
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
            for p in tracked:
                if hasattr(p, "t") and hasattr(p, "host"):
                    old.append((p.x, p.y, p.t))
                else:
                    old.append((p.x, p.y, None))
            return old

        def _restore(old):
            for i, p in enumerate(tracked):
                p.x, p.y = old[i][0], old[i][1]
                if old[i][2] is not None:
                    p.t = old[i][2]

        scales, Fs, Js = _rescale_rows(F, J)
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

            if drag_mode and xr is not None:
                mu = self.drag_tikhonov * max(
                    float(A.diagonal().mean()), 1e-12)
            else:
                mu = 0.0

            accepted = False

            for _attempt in range(16):
                if mu > 0.0:
                    dref = _cur_vec() - xr  # pyright: ignore[reportOperatorIssue]
                    rhs = -(g + mu * dref)
                else:
                    dref = None
                    rhs = -g

                M = A.copy()
                M[di] += lam + mu

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
                self._sync_dependents(free_points, frozen_dep)

                new_raw = self._eval_residual(used)
                if new_raw is None:
                    # 结构变化：拒绝本步，恢复后重组
                    _restore(old)
                    self._sync_dependents(free_points, frozen_dep)
                    asm = self._assemble(valid, vars_map, n_vars, frozen_ids)
                    if asm is None:
                        return True
                    F, J, used = asm
                    scales, Fs, Js = _rescale_rows(F, J)
                    norm = float(np_norm(F))
                    if norm < self.tol:
                        return True
                    accepted = True   # 外层循环重算 A/g
                    break

                new_Fs = new_raw / scales
                aug_new = float((new_Fs * new_Fs).sum())
                aug_old = float((Fs * Fs).sum())
                if mu > 0.0:
                    dref_new = _cur_vec() - xr  # pyright: ignore[reportOperatorIssue]
                    aug_new += mu * float(dref_new @ dref_new)
                    aug_old += mu * float(dref @ dref)  # pyright: ignore[reportOperatorIssue]

                ared = 0.5 * (aug_old - aug_new)
                # ★ v2.2：增广目标 0.5‖Fs+Jsδ‖²+0.5μ‖dref+δ‖² 的精确
                #   模型下降量 = 0.5δᵀAδ + (λ+0.5μ)‖δ‖²（旧版用 λ+μ，
                #   高估 pred → 低估 ρ → λ 过度膨胀）
                pred = (0.5 * float(delta @ (A @ delta))
                        + (lam + 0.5 * mu) * float(delta @ delta))
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

                    asm = self._assemble(valid, vars_map, n_vars, frozen_ids)
                    if asm is None:
                        return True
                    F, J, used = asm
                    scales, Fs, Js = _rescale_rows(F, J)
                    norm = float(np_norm(F))
                    if norm < self.tol:
                        self._lam_warm = min(max(lam, 1e-6), 1e2)
                        return True
                    accepted = True
                    break
                else:
                    # ── 拒绝：恢复状态、升 λ、复用缓存 F/J（不重算）──
                    _restore(old)
                    self._sync_dependents(free_points, frozen_dep)
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