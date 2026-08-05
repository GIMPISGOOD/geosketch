"""把 TransformDriver 应用到选中对象，并支持深度迭代。"""

from geo.points import AbstractPoint
from geo.segments import Segment
from geo.circles import Circle

from plugins.line_tool import Line
from plugins.ray_tool import Ray
from plugins.ellipse_tool import Ellipse
from plugins.polygon import RegularPolygon

from transforms.objects import TransformPoint, CircleAxisPoint, InvertedCircle


def create_transformed_copies(doc, driver, targets, depth=1):
    """对 targets 应用 driver，depth 表示迭代层数。"""
    depth = max(1, int(depth))
    created = []

    doc.begin_action()
    try:
        if driver not in doc.objects:
            doc.add(driver)

        for src in targets:
            created.extend(_iterate_one(doc, driver, src, depth))
    finally:
        doc.end_action()

    doc.changed.emit()
    return created


# ------------------------------------------------------------
# 单一对象迭代
# ------------------------------------------------------------

def _iterate_one(doc, driver, src, depth):
    created = []

    # ---------------- 点 ----------------
    if isinstance(src, AbstractPoint):
        cur = src
        for _ in range(depth):
            p = TransformPoint(driver, cur)
            doc.add(p)
            created.append(p)
            cur = p
        return created

    # ---------------- 反演：只支持点/圆 ----------------
    if driver.kind == "invert":
        if isinstance(src, Circle) or isinstance(src, InvertedCircle):
            cur = src
            for _ in range(depth):
                ic = InvertedCircle(driver, cur)
                doc.add(ic)
                created.append(ic)
                cur = ic
            return created

        # 线段/直线/射线等暂不支持反演
        return []

    # ---------------- 线段 ----------------
    if isinstance(src, Segment):
        a, b = src.a, src.b

        for _ in range(depth):
            ta = TransformPoint(driver, a)
            tb = TransformPoint(driver, b)

            doc.add(ta)
            doc.add(tb)

            seg = Segment(ta, tb)
            doc.add(seg)

            created.append(seg)
            a, b = ta, tb

        return created

    # ---------------- 直线 ----------------
    if isinstance(src, Line):
        a, b = src.a, src.b

        for _ in range(depth):
            ta = TransformPoint(driver, a)
            tb = TransformPoint(driver, b)

            doc.add(ta)
            doc.add(tb)

            line = Line(ta, tb)
            doc.add(line)

            created.append(line)
            a, b = ta, tb

        return created

    # ---------------- 射线 ----------------
    if isinstance(src, Ray):
        a, b = src.origin, src.through

        for _ in range(depth):
            ta = TransformPoint(driver, a)
            tb = TransformPoint(driver, b)

            doc.add(ta)
            doc.add(tb)

            ray = Ray(ta, tb)
            doc.add(ray)

            created.append(ray)
            a, b = ta, tb

        return created

    # ---------------- 圆 ----------------
    if isinstance(src, Circle):
        # 相似变换：圆仍映射为圆
        if driver.similarity:
            center = src.center
            through = src.through

            for _ in range(depth):
                tc = TransformPoint(driver, center)
                tt = TransformPoint(driver, through)

                doc.add(tc)
                doc.add(tt)

                cir = Circle(tc, tt)
                doc.add(cir)

                created.append(cir)
                center, through = tc, tt

            return created

        # 仿射变换：圆映射为椭圆
        ax = CircleAxisPoint(src, 0)
        ay = CircleAxisPoint(src, 1)

        doc.add(ax)
        doc.add(ay)

        return _iterate_ellipse(doc, driver, src.center, ax, ay, depth)

    # ---------------- 椭圆 ----------------
    if isinstance(src, Ellipse):
        return _iterate_ellipse(doc, driver, src.center, src.axis_a, src.axis_b, depth)

    # ---------------- 正多边形 ----------------
    if isinstance(src, RegularPolygon):
        # 一般仿射会把正多边形变成非正多边形，这里只在相似变换下支持
        if driver.similarity:
            center = src.center
            vertex = src.vertex

            for _ in range(depth):
                tc = TransformPoint(driver, center)
                tv = TransformPoint(driver, vertex)

                doc.add(tc)
                doc.add(tv)

                poly = RegularPolygon(tc, tv, src.n)
                doc.add(poly)

                created.append(poly)
                center, vertex = tc, tv

            return created

        return []

    return created


# ------------------------------------------------------------
# 椭圆迭代
# ------------------------------------------------------------

def _iterate_ellipse(doc, driver, center, axis_a, axis_b, depth):
    created = []

    c = center
    a = axis_a
    b = axis_b

    for _ in range(depth):
        tc = TransformPoint(driver, c)
        ta = TransformPoint(driver, a)
        tb = TransformPoint(driver, b)

        doc.add(tc)
        doc.add(ta)
        doc.add(tb)

        ell = Ellipse(tc, ta, tb)
        doc.add(ell)

        created.append(ell)

        c, a, b = tc, ta, tb

    return created