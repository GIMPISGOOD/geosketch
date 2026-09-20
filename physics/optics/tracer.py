"""几何光学追迹工具。

本版扩展：
- 平面镜单镜反射
- 多平面镜连续反射
- 射线与线段求交
- 无限延伸光线的方向与终止状态
- 折线 / 射线拾取距离

设计原则：
- 纯计算，不依赖 Document。
- 不创建 / 删除对象。
- 使用轻量浮点数学，避免过多 NumPy 数组分配。
"""
from __future__ import annotations

import math

import numpy as np

EPS = 1e-12
HIT_EPS = 1e-9
MIN_ADVANCE = 1e-7
GRAZE_EPS = 1e-8


# ════════════════════════════════════════════════════════════
# 旧版兼容接口
# ════════════════════════════════════════════════════════════

def normalize(v):
    """向量归一化；零向量返回 None。保留旧接口。"""
    v = np.asarray(v, dtype=float)
    n = float(np.linalg.norm(v))
    if n < 1e-12:
        return None
    return v / n


def reflect(d, n):
    """根据入射方向 d 和法线 n 计算反射方向。保留旧接口。"""
    d = normalize(d)
    n = normalize(n)
    if d is None or n is None:
        return None
    return d - 2.0 * float(np.dot(d, n)) * n


def mirror_normal(a, b):
    """计算平面镜 AB 的单位法线。保留旧接口。"""
    m = normalize(np.array([b[0] - a[0], b[1] - a[1]], dtype=float))
    if m is None:
        return None
    return np.array([-m[1], m[0]], dtype=float)


def ray_mirror_reflect(src, inc, a, b):
    """计算从 src 射向 inc 的光线，在平面镜 AB 上的反射方向。保留旧接口。"""
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


# ════════════════════════════════════════════════════════════
# 新增：轻量二维向量工具
# ════════════════════════════════════════════════════════════

def normalize2(x: float, y: float):
    """二维向量归一化。零向量返回 None。"""
    length = math.hypot(x, y)
    if length < EPS:
        return None
    return (x / length, y / length)


def dot2(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * bx + ay * by


def cross2(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def plane_mirror_normal(a, b, hatch_side: str = "right"):
    """计算平面镜反射面法线。

    这里约定：
    - hatch_side="right" 时，反射面法线为 (-uy, ux)
    - hatch_side="left"  时，反射面法线为 (uy, -ux)

    该方向与现有平面镜背面阴影线方向相反，表示反射面朝向。
    """
    dx = float(b[0]) - float(a[0])
    dy = float(b[1]) - float(a[1])
    length = math.hypot(dx, dy)
    if length < EPS:
        return None

    ux = dx / length
    uy = dy / length

    if hatch_side == "left":
        return (uy, -ux)
    return (-uy, ux)


def ray_segment_t(origin, direction, a, b):
    """射线与线段求交。

    射线：origin + t * direction，t >= 0
    线段：a + u * (b - a)，0 <= u <= 1

    返回 t；无交点返回 None。
    """
    ox, oy = float(origin[0]), float(origin[1])
    dx, dy = float(direction[0]), float(direction[1])
    ax, ay = float(a[0]), float(a[1])
    bx, by = float(b[0]), float(b[1])

    ex = bx - ax
    ey = by - ay

    denom = cross2(dx, dy, ex, ey)
    if abs(denom) < EPS:
        return None

    qx = ax - ox
    qy = ay - oy

    t = cross2(qx, qy, ex, ey) / denom
    u = cross2(qx, qy, dx, dy) / denom

    if t > HIT_EPS and (-HIT_EPS <= u <= 1.0 + HIT_EPS):
        return float(t)
    return None


def point_ray_distance(pt, origin, direction):
    """点 pt 到无限射线 origin + t * direction 的距离。

    仅当投影位于射线正向时返回距离；
    如果投影位于射线反向，则返回 None，避免反向延长线被选中。
    """
    px, py = float(pt[0]), float(pt[1])
    ox, oy = float(origin[0]), float(origin[1])

    d = normalize2(float(direction[0]), float(direction[1]))
    if d is None:
        return math.hypot(px - ox, py - oy)

    dx, dy = d
    vx = px - ox
    vy = py - oy
    t = dot2(vx, vy, dx, dy)

    if t < 0.0:
        return None

    proj_x = ox + dx * t
    proj_y = oy + dy * t
    return math.hypot(px - proj_x, py - proj_y)


# ════════════════════════════════════════════════════════════
# 新增：多镜追迹核心
# ════════════════════════════════════════════════════════════


def _reflect_with_normal(direction, normal):
    """根据单位方向和法线计算反射方向。"""
    d = normalize2(float(direction[0]), float(direction[1]))
    n = normalize2(float(normal[0]), float(normal[1]))
    if d is None or n is None:
        return None

    dx, dy = d
    nx, ny = n
    ddot = dot2(dx, dy, nx, ny)

    rx = dx - 2.0 * ddot * nx
    ry = dy - 2.0 * ddot * ny
    return normalize2(rx, ry)


def trace_light_path(
    src,
    inc,
    initial_surface,
    surfaces,
    max_reflections: int = 16,
    initial_active: bool = True,
):
    """多表面光线追迹。

    参数
    ----
    src : (float, float)
        光源点坐标。
    inc : (float, float)
        初始入射点坐标。
    initial_surface : OpticalSurface | None
        初始光学表面（如初始平面镜）。
    surfaces : list[OpticalSurface]
        当前可参与追迹的全部表面（可含 ``initial_surface``）。
    max_reflections : int
        最大交互次数（含初始表面交互）。范围 [1, 256]。
    initial_active : bool
        初始表面是否参与第一次交互。

    返回
    ----
    dict:
        {
            "points": [(x, y), ...],
            "last_dir": (dx, dy) | None,
            "infinite": bool,
            "reason": str,
            "reflections": int,
            "hit_surfaces": [OpticalSurface, ...],
        }

    注意
    ----
    ``reason`` 的取值由各表面的 ``interact()`` 决定，常见值：
    ``"open" / "reflected" / "refracted" / "absorbed" /
    "total_internal_reflection" / "max_reflections" / "degenerate"``。

    初始表面命中点不追加到 ``points`` 与 ``hit_surfaces``，
    因为 ``inc`` 已经在 ``points`` 中。
    """
    src = (float(src[0]), float(src[1]))
    inc = (float(inc[0]), float(inc[1]))

    result = {
        "points": [src, inc],
        "last_dir": None,
        "infinite": False,
        "reason": "degenerate",
        "reflections": 0,
        "hit_surfaces": [],
    }

    dx = inc[0] - src[0]
    dy = inc[1] - src[1]
    length = math.hypot(dx, dy)

    if length < EPS:
        result["points"] = [src]
        return result

    incident_dir = normalize2(dx, dy)
    if incident_dir is None:
        result["points"] = [src]
        return result

    result["last_dir"] = incident_dir
    result["infinite"] = True
    result["reason"] = "open"

    max_reflections = max(1, min(256, int(max_reflections)))

    origin = inc
    direction = incident_dir
    last_surface = initial_surface
    reflections = 0

    # ── 初始表面第一次交互 ──
    if (
        initial_active
        and initial_surface is not None
        and getattr(initial_surface, "exists", False)
        and initial_surface.is_active_for_ray(incident_dir)
    ):
        res = initial_surface.interact(inc, incident_dir)
        if (
            res["kind"] in ("reflect", "refract")
            and res["direction"] is not None
        ):
            direction = res["direction"]
            reflections = 1
            result["last_dir"] = direction
            result["reason"] = res["reason"]
            result["hit_surfaces"].append(initial_surface)
        # absorb / direction=None：跳过初始交互，继续找其他表面。

    result["reflections"] = reflections

    if reflections >= max_reflections:
        result["reason"] = "max_reflections"
        return result

    terminated_by_max = False

    # ── 后续表面追迹 ──
    while reflections < max_reflections:
        best_t = None
        best_surface = None

        for s in surfaces:
            if s is last_surface:
                continue
            if not getattr(s, "exists", False):
                continue
            if not s.is_active_for_ray(direction):
                continue

            hit = s.ray_hit(origin, direction)
            if hit is None:
                continue

            t = hit[0]
            if t <= MIN_ADVANCE:
                continue

            if (
                best_t is None
                or t < best_t - 1e-9
                or (
                    abs(t - best_t) <= 1e-9
                    and getattr(s, "id", 0) < getattr(best_surface, "id", 0)
                )
            ):
                best_t = t
                best_surface = s

        if best_surface is None:
            result["reason"] = "open"
            break

        hit_pt = (
            origin[0] + direction[0] * best_t, # pyright: ignore[reportOperatorIssue]
            origin[1] + direction[1] * best_t, # pyright: ignore[reportOperatorIssue]
        )

        res = best_surface.interact(hit_pt, direction)

        if res["kind"] == "absorb" or res["direction"] is None:
            result["reason"] = res["reason"]
            result["infinite"] = False
            break

        result["points"].append(hit_pt)
        result["hit_surfaces"].append(best_surface)

        if best_surface.consumes_interaction_budget:
            reflections += 1

        origin = hit_pt
        direction = res["direction"]
        last_surface = best_surface

        result["last_dir"] = direction
        result["reflections"] = reflections

        if reflections >= max_reflections:
            terminated_by_max = True
            break

    if terminated_by_max:
        result["reason"] = "max_reflections"

    return result