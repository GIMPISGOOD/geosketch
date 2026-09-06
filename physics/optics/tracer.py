"""几何光学追迹工具。

第一版只处理：
- 平面镜反射
- 折线路径生成
- 折线拾取距离

允许使用 NumPy。
"""

from __future__ import annotations

import numpy as np


def normalize(v):
    """向量归一化；零向量返回 None。"""
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return None
    return v / n


def reflect(d, n):
    """根据入射方向 d 和法线 n 计算反射方向。"""
    d = normalize(d)
    n = normalize(n)
    if d is None or n is None:
        return None
    return d - 2.0 * float(np.dot(d, n)) * n


def mirror_normal(a, b):
    """计算平面镜 AB 的单位法线。

   法线方向取垂直于 AB 的方向。
    反射公式对法线方向正负不敏感，因此这里固定取一个方向即可。
    """
    m = normalize(np.array([b[0] - a[0], b[1] - a[1]], dtype=float))
    if m is None:
        return None
    return np.array([-m[1], m[0]], dtype=float)


def ray_mirror_reflect(src, inc, a, b):
    """计算从 src 射向 inc 的光线，在平面镜 AB 上的反射方向。"""
    d = normalize(np.array([inc[0] - src[0], inc[1] - src[1]], dtype=float))
    if d is None:
        return None

    n = mirror_normal(a, b)
    if n is None:
        return None

    r = reflect(d, n)
    if r is None:
        return None

    return normalize(r)


def point_segment_distance(pt, a, b):
    """点 pt 到线段 ab 的距离。"""
    p = np.asarray(pt, dtype=float)
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)

    ab = b - a
    denom = float(np.dot(ab, ab))
    if denom < 1e-18:
        return float(np.linalg.norm(p - a))

    t = float(np.dot(p - a, ab) / denom)
    t = max(0.0, min(1.0, t))
    proj = a + t * ab
    return float(np.linalg.norm(p - proj))


def polyline_distance(points, x, y):
    """点 (x, y) 到折线 points 的最短距离。"""
    if not points or len(points) < 2:
        return None

    best = None
    for i in range(len(points) - 1):
        d = point_segment_distance((x, y), points[i], points[i + 1])
        if best is None or d < best:
            best = d
    return best