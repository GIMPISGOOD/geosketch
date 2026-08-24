import math
import os
import random
from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPixmap, QPen, QFont
from core.registry import find_renderer
from geo.points import AbstractPoint 
from geo.function_curve import FunctionCurve
from ui import theme

def nice_step(raw: float) -> float:
    e = 10.0 ** math.floor(math.log10(raw))
    return next(m * e for m in (1.0, 2.0, 5.0, 10.0) if m * e >= raw)

def arrow_path(tip: QPointF, angle_deg: float) -> QPainterPath:
    a = math.radians(angle_deg)
    size = 9.0
    bx = tip.x() - math.cos(a) * size
    by = tip.y() + math.sin(a) * size
    px, py = -math.sin(a) * size * 0.45, -math.cos(a) * size * 0.45
    path = QPainterPath()
    path.moveTo(tip)
    path.lineTo(bx + px, by + py)
    path.lineTo(bx - px, by - py)
    path.closeSubpath()
    return path

def draw_background_cached(canvas, p: QPainter) -> None:
    key = (canvas.width(), canvas.height(),
           round(canvas.origin.x(), 2), round(canvas.origin.y(), 2),
           round(canvas.scale, 2), theme.active_name())
    if canvas._bg_cache is not None and canvas._bg_cache_key == key:
        p.drawPixmap(0, 0, canvas._bg_cache)
        return
    dpr = canvas.devicePixelRatioF()
    canvas._bg_cache = QPixmap(int(canvas.width() * dpr), int(canvas.height() * dpr))
    canvas._bg_cache.setDevicePixelRatio(dpr)
    canvas._bg_cache.fill(Qt.GlobalColor.transparent)
    bg_p = QPainter(canvas._bg_cache)
    bg_p.setRenderHint(QPainter.RenderHint.Antialiasing)
    draw_background(canvas, bg_p)
    draw_grid(canvas, bg_p)
    draw_axes(canvas, bg_p)
    bg_p.end()
    canvas._bg_cache_key = key
    p.drawPixmap(0, 0, canvas._bg_cache)

def draw_background(canvas, p: QPainter) -> None:
    g = QLinearGradient(0.0, 0.0, 0.0, float(canvas.height()))
    g.setColorAt(0.0, theme.BG_TOP)
    g.setColorAt(1.0, theme.BG_BOTTOM)
    p.fillRect(canvas.rect(), g)

def draw_grid(canvas, p: QPainter) -> None:
    w, h = canvas.width(), canvas.height()
    step = nice_step(64.0 / canvas.scale)
    major = step * 5.0
    x0, y0 = canvas.to_world(QPointF(0.0, float(h)))
    x1, y1 = canvas.to_world(QPointF(float(w), 0.0))
    eps = step * 1e-6
    for s, color in ((step, theme.GRID_MINOR), (major, theme.GRID_MAJOR)):
        p.setPen(theme.pen(color, 1.0))
        gx = math.ceil(x0 / s) * s
        while gx <= x1:
            if abs(gx) > eps:
                sx = canvas.to_screen(gx, 0.0).x()
                p.drawLine(QPointF(sx, 0.0), QPointF(sx, float(h)))
            gx += s
        gy = math.ceil(y0 / s) * s
        while gy <= y1:
            if abs(gy) > eps:
                sy = canvas.to_screen(0.0, gy).y()
                p.drawLine(QPointF(0.0, sy), QPointF(float(w), sy))
            gy += s
    ox, oy = canvas.origin.x(), canvas.origin.y()
    p.setPen(theme.pen(theme.LABEL, 1.0))
    p.setFont(theme.LABEL_FONT)
    gx = math.ceil(x0 / major) * major
    while gx <= x1:
        if abs(gx) > eps:
            sx = canvas.to_screen(gx, 0.0).x()
            ly = float(min(max(oy + 16.0, 16.0), h - 6.0))
            p.drawText(QPointF(sx + 4.0, ly), f"{gx:g}")
        gx += major
    gy = math.ceil(y0 / major) * major
    while gy <= y1:
        if abs(gy) > eps:
            sy = canvas.to_screen(0.0, gy).y()
            lx = float(min(max(ox + 6.0, 6.0), w - 34.0))
            p.drawText(QPointF(lx, sy - 5.0), f"{gy:g}")
        gy += major

def draw_axes(canvas, p: QPainter) -> None:
    w, h = float(canvas.width()), float(canvas.height())
    ox, oy = canvas.origin.x(), canvas.origin.y()
    p.setPen(theme.pen(theme.AXIS, 1.6))
    p.setBrush(theme.brush(theme.AXIS))
    if 0.0 <= oy <= h:
        p.drawLine(QPointF(0.0, oy), QPointF(w, oy))
        p.drawPath(arrow_path(QPointF(w - 2.0, oy), 0.0))
    if 0.0 <= ox <= w:
        p.drawLine(QPointF(ox, 0.0), QPointF(ox, h))
        p.drawPath(arrow_path(QPointF(ox, 2.0), 90.0))
    p.setPen(theme.pen(theme.LABEL, 1.0))
    p.setFont(theme.AXIS_FONT)
    if 0.0 <= oy <= h:
        p.drawText(QPointF(w - 18.0, oy - 10.0), "x")
    if 0.0 <= ox <= w:
        p.drawText(QPointF(ox + 10.0, 20.0), "y")
    if 0.0 <= ox <= w and 0.0 <= oy <= h:
        p.drawText(QPointF(ox - 18.0, oy + 20.0), "O")

def content_bbox(doc):
    xs, ys = [], []
    funcs = []
    for o in doc.objects:
        if not (o.visible and o.exists):
            continue
        if isinstance(o, FunctionCurve):
            funcs.append(o)
            continue
        if getattr(o, "media", False):
            try:
                xs.append(o.x)
                xs.append(o.x + o.width)
                ys.append(o.y)
                ys.append(o.y - o.height)
                continue
            except Exception:
                pass
        if isinstance(o, AbstractPoint):
            xs.append(o.x)
            ys.append(o.y)
            continue
        if hasattr(o, "world_pos"):
            try:
                wx, wy = o.world_pos()
                xs.append(wx)
                ys.append(wy)
                continue
            except Exception:
                pass
        if isinstance(getattr(o, "anchor", None), tuple):
            xs.append(o.anchor[0])
            ys.append(o.anchor[1])
            continue
        if isinstance(getattr(o, "label_pos", None), tuple):
            xs.append(o.label_pos[0])
            ys.append(o.label_pos[1])
            continue
        try:
            for i in range(37):
                px, py = o.point_at(i / 36)
                xs.append(px)
                ys.append(py)
        except Exception:
            pass
    if funcs:
        if xs:
            x_min, x_max = min(xs), max(xs)
            y_min, y_max = min(ys), max(ys)
            m = max(x_max - x_min, y_max - y_min) * 0.3 + 2.0
            cx0, cx1 = x_min - m, x_max + m
            cy0, cy1 = y_min - m, y_max + m
        else:
            cx0, cx1, cy0, cy1 = -10.0, 10.0, -10.0, 10.0
        for f in funcs:
            a, b = f._param_domain()
            if f.kind == "explicit":
                a = max(a, cx0)
                b = min(b, cx1)
                if a >= b:
                    a, b = cx0, cx1
                n = 199
                for i in range(n + 1):
                    u = a + (b - a) * i / n
                    p = f._eval_point(u)
                    if p is not None and cy0 <= p[1] <= cy1:
                        xs.append(p[0])
                        ys.append(p[1])
            else:
                n = 299
                for i in range(n + 1):
                    u = a + (b - a) * i / n
                    p = f._eval_point(u)
                    if p is not None and cx0 <= p[0] <= cx1 and cy0 <= p[1] <= cy1:
                        xs.append(p[0])
                        ys.append(p[1])
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)

def draw_publication(p: QPainter, obj, view):
    pen = QPen(QColor("#000000"), 2.2)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    tn = type(obj).__name__
    if isinstance(obj, AbstractPoint):
        return
    if tn == "Segment":
        p.drawLine(view.to_screen(obj.a.x, obj.a.y), view.to_screen(obj.b.x, obj.b.y))
        return
    if tn in ("Line", "Ray", "DirectedLine", "PerpLine", "ParallelLine",
              "AngleBisector", "AngleDivLine", "PerpBisector"):
        w, h = view.width(), view.height()
        ts = [obj.project(*view.to_world(QPointF(cx, cy)))
              for cx, cy in ((0, 0), (w, 0), (0, h), (w, h))]
        if tn == "Ray":
            p0 = obj.point_at(0.0)
            p1 = obj.point_at(max(ts))
        else:
            p0 = obj.point_at(min(ts))
            p1 = obj.point_at(max(ts))
        p.drawLine(view.to_screen(*p0), view.to_screen(*p1))
        return
    if tn in ("Circle", "ExprCircle", "ThreePointCircle", "InvertedCircle"):
        c = view.to_screen(obj.center.x if hasattr(obj, 'center') else obj.cx,
                           obj.center.y if hasattr(obj, 'center') else obj.cy)
        r = obj.r if hasattr(obj, 'r') else getattr(obj, 'radius', 0)
        p.drawEllipse(c, r * view.scale, r * view.scale)
        return
    if tn == "Ellipse":
        path = QPainterPath()
        for i in range(73):
            sp = view.to_screen(*obj.point_at(i / 72))
            if i == 0: path.moveTo(sp)
            else: path.lineTo(sp)
        path.closeSubpath()
        p.drawPath(path)
        return
    if tn == "RegularPolygon":
        path = QPainterPath()
        for i, v in enumerate(obj.verts):
            sp = view.to_screen(*v)
            if i == 0: path.moveTo(sp)
            else: path.lineTo(sp)
        path.closeSubpath()
        p.drawPath(path)
        return
    if tn == "CubicBezier":
        path = QPainterPath()
        for i in range(61):
            sp = view.to_screen(*obj.point_at(i / 60))
            if i == 0: path.moveTo(sp)
            else: path.lineTo(sp)
        p.drawPath(path)
        return
    if tn == "FunctionCurve":
        path = QPainterPath()
        has_path = False
        a, b = obj._param_domain()
        for i in range(401):
            u = a + (b - a) * i / 400
            pt = obj._eval_point(u)
            if pt is None:
                has_path = False
                continue
            sp = view.to_screen(*pt)
            if not has_path:
                path.moveTo(sp)
                has_path = True
            else:
                path.lineTo(sp)
        p.drawPath(path)
        return
    if tn == "AngleMeasure":
        v, p1, p2 = obj.vertex, obj.p1, obj.p2
        a1 = math.atan2(p1.y - v.y, p1.x - v.x)
        a2 = math.atan2(p2.y - v.y, p2.x - v.x)
        span = (a2 - a1 + 3 * math.pi) % (2 * math.pi) - math.pi
        r = 25.0 / view.scale
        path = QPainterPath()
        for i in range(33):
            a = a1 + span * i / 32
            sp = view.to_screen(v.x + r * math.cos(a), v.y + r * math.sin(a))
            if i == 0: path.moveTo(sp)
            else: path.lineTo(sp)
        p.drawPath(path)
        return
    if tn == "TextObject":
        font = QFont("Microsoft YaHei", obj.size)
        p.setFont(font)
        p.drawText(view.to_screen(*obj.world_pos()) + QPointF(12, 24), obj.text)
        return

def collect_screen_segments(view):
    segments = []
    for obj in view.doc.objects:
        if not (obj.visible and obj.exists):
            continue
        tn = type(obj).__name__
        if tn == "Segment":
            sa = view.to_screen(obj.a.x, obj.a.y)
            sb = view.to_screen(obj.b.x, obj.b.y)
            segments.append((sa, sb))
        elif tn in ("Line", "Ray", "DirectedLine", "PerpLine", "ParallelLine",
                    "AngleBisector", "AngleDivLine", "PerpBisector"):
            w, h = view.width(), view.height()
            try:
                ts = [obj.project(*view.to_world(QPointF(cx, cy)))
                      for cx, cy in ((0, 0), (w, 0), (0, h), (w, h))]
                if tn == "Ray":
                    p0 = obj.point_at(0.0)
                    p1 = obj.point_at(max(ts))
                else:
                    p0 = obj.point_at(min(ts))
                    p1 = obj.point_at(max(ts))
                segments.append((view.to_screen(*p0), view.to_screen(*p1)))
            except Exception:
                pass
        elif tn in ("Circle", "ExprCircle", "ThreePointCircle"):
            try:
                n = 36
                r = obj.r if hasattr(obj, 'r') else 0
                cx = obj.center.x if hasattr(obj, 'center') else getattr(obj, 'cx', 0)
                cy = obj.center.y if hasattr(obj, 'center') else getattr(obj, 'cy', 0)
                for i in range(n):
                    a0 = 2 * math.pi * i / n
                    a1 = 2 * math.pi * (i + 1) / n
                    p0 = view.to_screen(cx + r * math.cos(a0), cy + r * math.sin(a0))
                    p1 = view.to_screen(cx + r * math.cos(a1), cy + r * math.sin(a1))
                    segments.append((p0, p1))
            except Exception:
                pass
    return segments

def segments_intersect(p1, p2, p3, p4):
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    d1 = cross(p3, p4, p1)
    d2 = cross(p3, p4, p2)
    d3 = cross(p1, p2, p3)
    d4 = cross(p1, p2, p4)
    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and \
       ((d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)):
        return True
    return False

def rect_intersects_segment(rect, seg):
    p1, p2 = seg
    if hasattr(p1, 'x') and callable(p1.x):
        x1, y1 = p1.x(), p1.y()
    else:
        x1, y1 = p1
    if hasattr(p2, 'x') and callable(p2.x):
        x2, y2 = p2.x(), p2.y()
    else:
        x2, y2 = p2
    if rect.contains(QPointF(x1, y1)) or rect.contains(QPointF(x2, y2)): # pyright: ignore[reportArgumentType]
        return True
    edges = [
        (QPointF(rect.left(), rect.top()), QPointF(rect.right(), rect.top())),
        (QPointF(rect.right(), rect.top()), QPointF(rect.right(), rect.bottom())),
        (QPointF(rect.right(), rect.bottom()), QPointF(rect.left(), rect.bottom())),
        (QPointF(rect.left(), rect.bottom()), QPointF(rect.left(), rect.top())),
    ]
    for e0, e1 in edges:
        if segments_intersect((x1, y1), (x2, y2), (e0.x(), e0.y()), (e1.x(), e1.y())):
            return True
    return False

def point_rect_dist(x, y, rect):
    dx = max(rect.left() - x, 0, x - rect.right())
    dy = max(rect.top() - y, 0, y - rect.bottom())
    return math.hypot(dx, dy)

def find_label_offset(p, sp, label, view, screen_segments):
    from PySide6.QtGui import QFontMetricsF
    from PySide6.QtCore import QRectF, QPointF, QSizeF
    fm = QFontMetricsF(p.font())
    tw = float(fm.horizontalAdvance(label))
    th = float(fm.height())
    candidates = [
        QPointF(9, -9), QPointF(9, th * 0.7), QPointF(-tw - 9, -9), QPointF(-tw - 9, th * 0.7),
        QPointF(-tw / 2, -th - 6), QPointF(-tw / 2, th + 6), QPointF(-tw - 9, -th / 2), QPointF(tw / 2 + 9, -th / 2),
    ]
    best_offset = candidates[0]
    best_score = float('inf')
    for offset in candidates:
        rect = QRectF(sp + offset, QSizeF(tw, th))
        score = 0.0
        for seg in screen_segments:
            if rect_intersects_segment(rect, seg):
                score += 10.0
            else:
                p1, p2 = seg
                if hasattr(p1, 'x') and callable(p1.x):
                    sx, sy = p1.x(), p1.y()
                    ex, ey = p2.x(), p2.y()
                else:
                    sx, sy = p1
                    ex, ey = p2
                d = min(point_rect_dist(sx, sy, rect), point_rect_dist(ex, ey, rect))
                score += 1.0 / (d + 1.0)
        if score < best_score:
            best_score = score
            best_offset = offset
    return best_offset

def draw_publication_point(p, obj, view, screen_segments):
    from PySide6.QtGui import QFont, QPen
    label = getattr(obj, "name", "") or getattr(obj, "_auto_label", "") or f"P{obj.id}"
    font = QFont("Times New Roman", 16)
    font.setItalic(True)
    p.setFont(font)
    p.setPen(QPen(QColor("#000000"), 1.0))
    sp = view.to_screen(obj.x, obj.y)
    offset = find_label_offset(p, sp, label, view, screen_segments)
    p.drawText(sp + offset, label)
    
# ============================================================
# 彩蛋补丁：[ACG] 触发后在渲染层直接绘制图片
# ============================================================
_egg_pixmap = None       # QPixmap，None 表示未激活
_egg_loading = False     # 防止重复触发


def trigger_egg(canvas):
    global _egg_loading
    if _egg_loading or _egg_pixmap is not None:
        return
    _egg_loading = True

    import threading
    import urllib.request
    from PySide6.QtCore import QMetaObject, Qt

    def _download():
        global _egg_loading
        try:
            num = random.randint(1, 512)
            url = f"https://esa-img.loliapi.cn/i/pc/img{num}.webp"
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = resp.read()

            # 将数据暂存到 canvas 对象
            canvas._egg_data = data
            # 在主线程中调用 _process_egg_data
            QMetaObject.invokeMethod(
                canvas,
                "_process_egg_data",
                Qt.ConnectionType.QueuedConnection
            )
        except Exception as e:
            print(f"[EGG] 下载失败: {e}")
        finally:
            _egg_loading = False

    threading.Thread(target=_download, daemon=True).start()

def _build_pixmap(canvas, data: bytes):
    """★ 主线程中执行：WebP 解码 → PNG 转换 → QPixmap 创建。"""
    global _egg_pixmap, _egg_loading
    try:
        from PySide6.QtGui import QImage, QPixmap
        from PySide6.QtCore import QByteArray, QBuffer

        img = QImage()
        loaded = img.loadFromData(data)
        if not loaded:
            loaded = img.loadFromData(data, "WEBP") # pyright: ignore[reportArgumentType]

        if not loaded or img.isNull():
            _egg_loading = False
            return

        # 转为 ARGB32 确保兼容
        img = img.convertToFormat(QImage.Format.Format_ARGB32)

        # 通过 QBuffer 获取 PNG 字节
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QBuffer.OpenModeFlag.WriteOnly)
        img.save(buf, "PNG") # pyright: ignore[reportCallIssue, reportArgumentType]
        buf.close()

        # 直接从内存创建 QPixmap（不写临时文件）
        pm = QPixmap()
        pm.loadFromData(ba.data(), "PNG") # pyright: ignore[reportCallIssue, reportArgumentType]

        if pm.isNull():
            _egg_loading = False
            return

        _egg_pixmap = pm

        # 触发重绘
        canvas.update()
    except Exception as e:
        import traceback
        traceback.print_exc()
        _egg_loading = False


def draw_egg_if_active(p: QPainter, canvas):
    global _egg_pixmap
    if _egg_pixmap is None or _egg_pixmap.isNull():
        return
    aspect = _egg_pixmap.height() / max(_egg_pixmap.width(), 1)
    x, y, w = 3.0, 3.0, 12.0
    h = w * aspect
    tl = canvas.to_screen(x, y)
    br = canvas.to_screen(x + w, y - h)
    rect = QRectF(tl, br).normalized()
    p.drawPixmap(rect.toRect(), _egg_pixmap)