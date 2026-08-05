"""变换数学基础：表达式求值、矩阵、仿射求解。"""

import math
from core.variables import eval_expr


def eval_num(expr, default=0.0):
    """把表达式求值为 float。支持 {a}、a、2*a+1 等。"""
    if expr is None:
        return default

    if isinstance(expr, (int, float)):
        return float(expr)

    s = str(expr).strip()
    if not s:
        return default

    if s.startswith("{") and s.endswith("}"):
        s = s[1:-1].strip()

    v = eval_expr(s)
    if v is None:
        return default

    try:
        if math.isfinite(float(v)):
            return float(v)
    except Exception:
        pass

    return default


def identity():
    return (1.0, 0.0, 0.0,
            0.0, 1.0, 0.0)


def translation(dx, dy):
    return (1.0, 0.0, float(dx),
            0.0, 1.0, float(dy))


def matrix_around(a, b, d, e, cx, cy):
    """以 (cx, cy) 为中心套用线性部分 [[a,b],[d,e]]。"""
    c = cx - a * cx - b * cy
    f = cy - d * cx - e * cy
    return (a, b, c, d, e, f)


def rotation_matrix(cx, cy, angle_deg):
    ang = math.radians(angle_deg)
    a = math.cos(ang)
    b = -math.sin(ang)
    d = math.sin(ang)
    e = math.cos(ang)
    return matrix_around(a, b, d, e, cx, cy)


def scale_matrix(cx, cy, s):
    return matrix_around(s, 0.0, 0.0, s, cx, cy)


def reflect_matrix(x1, y1, x2, y2):
    """关于直线 P1P2 的反射矩阵。"""
    dx = x2 - x1
    dy = y2 - y1
    L2 = dx * dx + dy * dy

    if L2 < 1e-12:
        return None

    a = (dx * dx - dy * dy) / L2
    b = 2.0 * dx * dy / L2

    # 线性部分 [[a,b],[b,-a]]
    c = x1 - (a * x1 + b * y1)
    f = y1 - (b * x1 - a * y1)

    return (a, b, c, b, -a, f)


def apply_matrix(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + b * y + c,
            d * x + e * y + f)


def _det3(m):
    return (
        m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
        - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
        + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0])
    )


def _solve3(A, b):
    D = _det3(A)
    if abs(D) < 1e-12:
        return None

    def replace(col):
        return [
            [b[i] if j == col else A[i][j] for j in range(3)]
            for i in range(3)
        ]

    return [_det3(replace(col)) / D for col in range(3)]


def solve_affine(src, dst):
    """由三组对应点求仿射矩阵。

    src = [(x1,y1), (x2,y2), (x3,y3)]
    dst = [(X1,Y1), (X2,Y2), (X3,Y3)]

    返回 (a,b,c,d,e,f)，满足：
        X = a*x + b*y + c
        Y = d*x + e*y + f
    """
    if len(src) != 3 or len(dst) != 3:
        return None

    A = [[p[0], p[1], 1.0] for p in src]

    bx = [p[0] for p in dst]
    by = [p[1] for p in dst]

    abc = _solve3(A, bx)
    deff = _solve3(A, by)

    if abc is None or deff is None:
        return None

    a, b, c = abc
    d, e, f = deff

    return (a, b, c, d, e, f)