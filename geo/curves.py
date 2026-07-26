"""参数曲线基类：椭圆、贝塞尔等参数化曲线的公共基础设施。
子类只需实现 point_at(t) 与 closed 标志，即自动获得数值投影（吸附）与拾取能力。"""
import math

from geo.base import GeoObject


def _numeric_project(point_at, x, y, closed, n=72, refine=20):
    """数值投影：先粗采样找最近参数，再在该点邻域精化。
    closed=True → t ∈ [0,1) 循环（椭圆）；否则截断到 [0,1]（贝塞尔）。"""
    best_t, best_d = 0.0, float('inf')
    count = n if closed else n + 1
    for i in range(count):
        t = i / n
        px, py = point_at(t)
        d = (px - x) ** 2 + (py - y) ** 2
        if d < best_d:
            best_t, best_d = t, d
    step = 1.0 / n
    lo, hi = best_t - step, best_t + step
    for i in range(refine):
        t = lo + (hi - lo) * i / (refine - 1)
        px, py = point_at(t)
        d = (px - x) ** 2 + (py - y) ** 2
        if d < best_d:
            best_t, best_d = t, d
    return (best_t % 1.0) if closed else max(0.0, min(1.0, best_t))


class ParamCurve(GeoObject):
    """参数曲线基类（抽象）。子类实现 point_at(t)，并设置 closed。"""
    closed = False

    def point_at(self, t):
        raise NotImplementedError

    def project(self, x, y):
        return _numeric_project(lambda t: self.point_at(t), x, y, self.closed)

    def distance_to(self, x, y):
        px, py = self.point_at(self.project(x, y))
        return math.hypot(px - x, py - y)