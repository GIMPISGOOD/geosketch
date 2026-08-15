"""隐函数后台采样引擎：Marching Squares 等值线提取。"""
import math
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition
from core.variables import evaluate


def _marching_squares(fast, vd, x0, x1, y0, y1, nx, ny):
    dx = (x1 - x0) / nx
    dy = (y1 - y0) / ny

    # ★ 确保网格采样正确
    grid = [[0.0] * (nx + 1) for _ in range(ny + 1)]
    for i in range(ny + 1):
        vd["y"] = y0 + i * dy          # ← 必须设置 y
        row = grid[i]
        for j in range(nx + 1):
            vd["x"] = x0 + j * dx      # ← 必须设置 x
            v = fast.eval(vd)
            row[j] = v if v is not None else 1e18

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
            if v00 > 0: case |= 1
            if v10 > 0: case |= 2
            if v11 > 0: case |= 4
            if v01 > 0: case |= 8

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
                segments.append((pts[0][0], pts[0][1], pts[1][0], pts[1][1]))
            elif len(pts) == 4:
                center = (v00 + v10 + v11 + v01) * 0.25
                if center > 0:
                    segments.append((pts[0][0], pts[0][1], pts[1][0], pts[1][1]))
                    segments.append((pts[2][0], pts[2][1], pts[3][0], pts[3][1]))
                else:
                    segments.append((pts[0][0], pts[0][1], pts[3][0], pts[3][1]))
                    segments.append((pts[1][0], pts[1][1], pts[2][0], pts[2][1]))

    return segments


class _ImplicitTask:
    __slots__ = ("curve_id", "expr", "domain", "n", "var_snapshot")

    def __init__(self, curve_id, expr, domain, n, var_snapshot):
        self.curve_id = curve_id
        self.expr = expr
        self.domain = domain
        self.n = n
        self.var_snapshot = var_snapshot


class ImplicitSamplerThread(QThread):
    sampled = Signal(int, list)  # curve_id, segments

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ImplicitSamplerThread")
        self._tasks = {}
        self._queue = []
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._running = True

    def submit(self, curve_id, expr, domain, n, var_snapshot):
        task = _ImplicitTask(curve_id, expr, domain, n, var_snapshot)
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
            curve_id = self._queue.pop(0)
            task = self._tasks.pop(curve_id, None)
            self._mutex.unlock()
            if task is None:
                continue
            x0, x1, y0, y1 = task.domain
            segments = _marching_squares(
                task.expr, task.var_snapshot,
                x0, x1, y0, y1, task.n, task.n
            )
            self.sampled.emit(curve_id, segments)


_sampler = None


def get_implicit_sampler():
    global _sampler
    if _sampler is None:
        _sampler = ImplicitSamplerThread()
        _sampler.start()
    return _sampler


def shutdown_implicit_sampler():
    global _sampler
    if _sampler is not None:
        _sampler.stop()
        _sampler = None