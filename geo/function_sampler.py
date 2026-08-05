"""函数曲线子线程采样引擎。

设计：
- 采样在后台线程执行，主线程只绘制缓存点
- 变量变化/表达式变化/视窗变化时触发重新采样
- 任务去重：同一曲线只保留最新任务，避免滑杆拖动时任务堆积
- 双缓冲：采样完成后原子替换缓存列表，主线程无锁读取
"""

import math
import time
from collections import defaultdict
from PySide6.QtCore import QThread, Signal, QMutex, QWaitCondition

from core.variables import get_store, evaluate


class _SampleTask:
    """一次采样任务的描述。"""
    __slots__ = ("curve_id", "kind", "expr", "expr2", "domain",
                 "n", "var_snapshot", "timestamp")

    def __init__(self, curve_id, kind, expr, expr2, domain, n, var_snapshot):
        self.curve_id = curve_id
        self.kind = kind
        self.expr = expr
        self.expr2 = expr2
        self.domain = domain
        self.n = n
        self.var_snapshot = var_snapshot
        self.timestamp = time.monotonic()


class FunctionSamplerThread(QThread):
    """后台采样线程。

    信号：
        sampled(curve_id, points)  采样完成，points 为 [(x,y)|None, ...]
    """
    sampled = Signal(int, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks: dict[int, _SampleTask] = {}   # curve_id → 最新任务（去重）
        self._queue: list[int] = []                 # 待处理 id 队列
        self._mutex = QMutex()
        self._cond = QWaitCondition()
        self._running = True

    def submit(self, curve_id, kind, expr, expr2, domain, n, var_snapshot):
        """提交采样任务。同一 curve_id 只保留最新任务。"""
        task = _SampleTask(curve_id, kind, expr, expr2, domain, n, var_snapshot)
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
        self.wait(2000)

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

            # 执行采样（纯计算，不接触任何 GUI 对象）
            points = self._sample(task)

            # 发射结果到主线程
            self.sampled.emit(curve_id, points)

    def _sample(self, task) -> list:
        """根据任务描述执行采样，返回点列表。"""
        vd = dict(task.var_snapshot)  # 快照副本，线程安全
        n = task.n
        a, b = task.domain

        points = []

        if task.kind == "explicit":
            for i in range(n + 1):
                x = a + (b - a) * i / n
                vd["x"] = x
                try:
                    y = evaluate(task.expr, vd)
                except Exception:
                    y = None
                if (y is not None and isinstance(y, (int, float))
                        and math.isfinite(y)):
                    points.append((x, float(y)))
                else:
                    points.append(None)

        elif task.kind == "parametric":
            for i in range(n + 1):
                t = a + (b - a) * i / n
                vd["t"] = t
                try:
                    x = evaluate(task.expr, vd)
                    y = evaluate(task.expr2, vd)
                except Exception:
                    x = y = None
                if (x is not None and y is not None
                        and isinstance(x, (int, float)) and math.isfinite(x)
                        and isinstance(y, (int, float)) and math.isfinite(y)):
                    points.append((float(x), float(y)))
                else:
                    points.append(None)

        elif task.kind == "polar":
            for i in range(n + 1):
                t = a + (b - a) * i / n
                vd["t"] = t
                vd["θ"] = t
                try:
                    r = evaluate(task.expr, vd)
                except Exception:
                    r = None
                if (r is not None and isinstance(r, (int, float))
                        and math.isfinite(r)):
                    points.append((float(r) * math.cos(t),
                                   float(r) * math.sin(t)))
                else:
                    points.append(None)

        return points


# ───────────── 全局采样器单例 ─────────────

_sampler: FunctionSamplerThread | None = None


def get_sampler() -> FunctionSamplerThread:
    global _sampler
    if _sampler is None:
        _sampler = FunctionSamplerThread()
        _sampler.start()
    return _sampler