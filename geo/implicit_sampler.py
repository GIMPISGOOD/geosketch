"""隐函数后台采样引擎：Marching Squares 等值线提取（唯一实现）。

所有隐函数采样统一经由本模块的 _marching_squares 完成，
主线程通过 ImplicitSamplerThread 异步提交，避免阻塞 UI。
"""

from collections import deque
from math import isfinite

from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from core.variables import evaluate


# ──────────────────────────────────────────────────────────
#  Marching Squares（唯一实现，供同步/异步共用）
# ──────────────────────────────────────────────────────────

def _marching_squares(eval_fn, var_dict, x0, x1, y0, y1, nx, ny):
    """等值线提取。

    参数
    ----
    eval_fn : callable(expr, vd) -> float | None
        表达式求值函数（通常为 core.variables.evaluate）。
    var_dict : dict
        变量快照（含 "x"、"y" 占位）。
    x0, x1, y0, y1 : float
        采样域。
    nx, ny : int
        网格分辨率。

    返回
    ----
    list[tuple[float,float,float,float]]
        线段列表 (x1, y1, x2, y2)。
    """
    dx = (x1 - x0) / nx
    dy = (y1 - y0) / ny

    # 构建标量场
    grid = [[0.0] * (nx + 1) for _ in range(ny + 1)]
    for i in range(ny + 1):
        var_dict["y"] = y0 + i * dy
        row = grid[i]
        for j in range(nx + 1):
            var_dict["x"] = x0 + j * dx
            v = eval_fn(var_dict)
            if v is None or not isfinite(v):
                row[j] = 1e18
            else:
                row[j] = v

    # 提取等值线段
    segments = []
    for i in range(ny):
        y_b = y0 + i * dy
        y_t = y_b + dy
        row0 = grid[i]
        row1 = grid[i + 1]
        for j in range(nx):
            v00 = row0[j]
            v10 = row0[j + 1]
            v11 = row1[j + 1]
            v01 = row1[j]

            if v00 > 1e17 or v10 > 1e17 or v11 > 1e17 or v01 > 1e17:
                continue

            case = 0
            if v00 > 0:
                case |= 1
            if v10 > 0:
                case |= 2
            if v11 > 0:
                case |= 4
            if v01 > 0:
                case |= 8
            if case == 0 or case == 15:
                continue

            x_l = x0 + j * dx
            x_r = x_l + dx
            pts = []

            if (v00 > 0) != (v10 > 0):
                d = v00 - v10
                t = v00 / d if abs(d) > 1e-15 else 0.5
                pts.append((x_l + t * dx, y_b))
            if (v10 > 0) != (v11 > 0):
                d = v10 - v11
                t = v10 / d if abs(d) > 1e-15 else 0.5
                pts.append((x_r, y_b + t * dy))
            if (v01 > 0) != (v11 > 0):
                d = v01 - v11
                t = v01 / d if abs(d) > 1e-15 else 0.5
                pts.append((x_l + t * dx, y_t))
            if (v00 > 0) != (v01 > 0):
                d = v00 - v01
                t = v00 / d if abs(d) > 1e-15 else 0.5
                pts.append((x_l, y_b + t * dy))

            if len(pts) == 2:
                segments.append((pts[0][0], pts[0][1],
                                 pts[1][0], pts[1][1]))
            elif len(pts) == 4:
                center = (v00 + v10 + v11 + v01) * 0.25
                if center > 0:
                    segments.append((pts[0][0], pts[0][1],
                                     pts[1][0], pts[1][1]))
                    segments.append((pts[2][0], pts[2][1],
                                     pts[3][0], pts[3][1]))
                else:
                    segments.append((pts[0][0], pts[0][1],
                                     pts[3][0], pts[3][1]))
                    segments.append((pts[1][0], pts[1][1],
                                     pts[2][0], pts[2][1]))

    return segments


def march_squares_sync(expr, var_snapshot, x0, x1, y0, y1, n):
    """同步采样（用于构造函数 / 文件加载）。"""
    vd = dict(var_snapshot)
    vd.setdefault("x", 0.0)
    vd.setdefault("y", 0.0)

    def _eval_fn(d):
        return evaluate(expr, d)

    return _marching_squares(_eval_fn, vd, x0, x1, y0, y1, n, n)


# ──────────────────────────────────────────────────────────
#  采样任务
# ──────────────────────────────────────────────────────────

class _ImplicitTask:
    __slots__ = ("curve_id", "expr", "domain", "n", "var_snapshot")

    def __init__(self, curve_id, expr, domain, n, var_snapshot):
        self.curve_id = curve_id
        self.expr = expr
        self.domain = domain
        self.n = n
        self.var_snapshot = var_snapshot


# ──────────────────────────────────────────────────────────
#  后台采样线程
# ──────────────────────────────────────────────────────────

class ImplicitSamplerThread(QThread):
    """单工作线程，按提交顺序消费任务，同 curve_id 去重（保留最新）。"""

    sampled = Signal(int, list)  # (curve_id, segments)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ImplicitSamplerThread")
        self._tasks: dict = {}
        self._queue: deque = deque()
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._running = True

    def submit(self, curve_id, expr, domain, n, var_snapshot):
        """提交采样任务。同 curve_id 重复提交时覆盖旧任务。"""
        task = _ImplicitTask(curve_id, expr, domain, n, dict(var_snapshot))
        self._mutex.lock()
        self._tasks[curve_id] = task
        if curve_id not in self._queue:
            self._queue.append(curve_id)
        self._cond.wakeOne()
        self._mutex.unlock()

    def stop(self):
        self._mutex.lock()
        self._running = False
        self._cond.wakeOne()
        self._mutex.unlock()
        if self.isRunning():
            self.wait(5000)

    def run(self):
        while True:
            self._mutex.lock()
            while self._running and not self._queue:
                self._cond.wait(self._mutex)
            if not self._running:
                self._mutex.unlock()
                break
            curve_id = self._queue.popleft()
            task = self._tasks.pop(curve_id, None)
            self._mutex.unlock()

            if task is None:
                continue

            x0, x1, y0, y1 = task.domain
            segments = march_squares_sync(
                task.expr, task.var_snapshot,
                x0, x1, y0, y1, task.n
            )
            self.sampled.emit(curve_id, segments)


# ──────────────────────────────────────────────────────────
#  全局单例（线程安全初始化）
# ──────────────────────────────────────────────────────────

_sampler: ImplicitSamplerThread | None = None
_sampler_mutex = QMutex()


def get_implicit_sampler() -> ImplicitSamplerThread:
    global _sampler
    _sampler_mutex.lock()
    try:
        if _sampler is None:
            _sampler = ImplicitSamplerThread()
            _sampler.start()
        return _sampler
    finally:
        _sampler_mutex.unlock()


def shutdown_implicit_sampler():
    global _sampler
    _sampler_mutex.lock()
    try:
        if _sampler is not None:
            _sampler.stop()
            _sampler = None
    finally:
        _sampler_mutex.unlock()