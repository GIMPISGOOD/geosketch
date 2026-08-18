import math
import random
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter

def init_snow(canvas):
    w = max(canvas.width(), 800)
    h = max(canvas.height(), 600)
    canvas._snowflakes = []
    for _ in range(140):
        canvas._snowflakes.append({
            "x": random.uniform(0.0, float(w)),
            "y": random.uniform(0.0, float(h)),
            "r": random.uniform(1.2, 3.4),
            "v": random.uniform(0.6, 1.9),
            "amp": random.uniform(0.2, 0.9),
            "phase": random.uniform(0.0, 2.0 * math.pi),
        })

def tick_snow(canvas):
    if not canvas._snow_active:
        return
    w = max(canvas.width(), 1)
    h = max(canvas.height(), 1)
    for f in canvas._snowflakes:
        f["y"] += f["v"]
        f["phase"] += 0.02
        f["x"] += math.sin(f["phase"]) * f["amp"]
        if f["y"] > h + 6.0:
            f["y"] = -6.0
            f["x"] = random.uniform(0.0, float(w))
    canvas.update()

def draw_snow(canvas, p: QPainter) -> None:
    p.save()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(255, 255, 255, 190))
    for f in canvas._snowflakes:
        p.drawEllipse(QPointF(f["x"], f["y"]), f["r"], f["r"])
    p.restore()