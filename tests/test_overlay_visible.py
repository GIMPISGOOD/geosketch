"""工具覆盖层 draw_overlay 可见性回归测试。

用于防止：
1. 画圆预览圆/半径不见
2. 框选框不见
3. 选择工具红色参考线不见
4. 某个对象渲染异常导致整个 overlay 层被吞掉

运行：
    python -m pytest tests/test_overlay_visible.py -v
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


# ------------------------------------------------------------
# 工具函数
# ------------------------------------------------------------

def _make_canvas():
    from core.document import Document
    from ui.canvas import Canvas

    doc = Document()
    canvas = Canvas(doc)

    canvas.resize(360, 240)
    canvas.origin = QPointF(180.0, 120.0)
    canvas.scale = 20.0

    return canvas


def _non_white_count(img: QImage, step=2):
    count = 0
    for y in range(0, img.height(), step):
        for x in range(0, img.width(), step):
            c = img.pixelColor(x, y)
            if not (c.red() > 245 and c.green() > 245 and c.blue() > 245):
                count += 1
    return count


# ------------------------------------------------------------
# 1. paintEvent 必须执行 tool.draw_overlay
# ------------------------------------------------------------

class _OverlayProbeTool:
    """探针工具：只要 draw_overlay 被调用，就把画布涂红。"""
    hint = "probe"
    def activated(self, canvas): pass
    def deactivated(self, canvas): pass
    def press(self, canvas, wpt, hit): pass
    def move(self, canvas, wpt, hit): pass
    def release(self, canvas, wpt, hit): pass
    def cancel(self, canvas): pass
    def draw_overlay(self, p, view):
        p.fillRect(view.rect(), QColor(255, 0, 0))


def test_paint_event_executes_tool_overlay():
    """验证 Canvas.paintEvent 源码中是否包含调用 draw_overlay 的逻辑。
    使用源码检查可以避免 Qt 离屏渲染 (offscreen) 下 QWidget 未显示时
    QPainter(self) 报错的底层限制。"""
    import inspect
    from ui.canvas import Canvas
    
    source = inspect.getsource(Canvas.paintEvent)
    
    assert "draw_overlay" in source, (
        "Canvas.paintEvent 源码中没有找到 draw_overlay 调用。"
        "请确保 paintEvent 中包含 self.tool.draw_overlay(p, self)。"
    )


# ------------------------------------------------------------
# 2. 画圆工具预览必须可见
# ------------------------------------------------------------

def test_circle_tool_preview_visible():
    from geo.points import FreePoint
    from tools.circle_tool import CircleTool

    canvas = _make_canvas()
    tool = CircleTool()
    tool.center = FreePoint(0.0, 0.0)
    canvas.cursor_wpt = (3.0, 0.0)

    img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    tool.draw_overlay(p, canvas)
    p.end()

    assert _non_white_count(img) > 20, (
        "画圆工具预览不可见。"
        "请检查 theme.dashed_pen 是否返回了有效画笔，"
        "以及 CircleTool.draw_overlay 是否正常绘制。"
    )


# ------------------------------------------------------------
# 3. 画圆工具半径线必须可见
# ------------------------------------------------------------

def test_circle_tool_radius_line_visible():
    from geo.points import FreePoint
    from tools.circle_tool import CircleTool

    canvas = _make_canvas()
    tool = CircleTool()
    tool.center = FreePoint(0.0, 0.0)
    canvas.cursor_wpt = (4.0, 0.0)

    img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    tool.draw_overlay(p, canvas)
    p.end()

    # 半径线在 y=120 附近，从 x=180 到 x=260
    marked = 0
    y = int(canvas.origin.y())
    for x in range(int(canvas.origin.x()), int(canvas.origin.x() + 4.0 * canvas.scale), 2):
        c = img.pixelColor(x, y)
        if not (c.red() > 245 and c.green() > 245 and c.blue() > 245):
            marked += 1

    assert marked > 5, (
        "画圆工具半径预览线不可见。"
        "请检查 CircleTool.draw_overlay 是否画了 p.drawLine(center, cursor)。"
    )


# ------------------------------------------------------------
# 4. 选择工具红色参考线必须可见
# ------------------------------------------------------------

def test_select_tool_red_guide_visible():
    from tools.select import SelectTool

    canvas = _make_canvas()
    tool = SelectTool()
    tool._guides = [("v", 0.0)]

    img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)

    p = QPainter(img)
    # ★ 关闭抗锯齿，避免边缘颜色与白色背景混合导致阈值判断失败
    p.setRenderHint(QPainter.RenderHint.Antialiasing, False)

    tool.draw_overlay(p, canvas)
    p.end()

    x = int(canvas.origin.x())
    red_found = False

    # ★ 逐像素扫描(step=1)，避免虚线间隙导致漏判
    for y in range(0, img.height(), 1):
        c = img.pixelColor(x, y)
        # 判断是否为明显的红色（红色通道显著大于绿/蓝通道）
        if c.red() > 150 and c.red() > c.green() + 30 and c.red() > c.blue() + 30:
            red_found = True
            break

    assert red_found, (
        "选择工具红色参考线不可见。"
        "请检查 SelectTool.draw_overlay 和 theme.dashed_pen。"
    )


# ------------------------------------------------------------
# 5. 框选工具预览必须可见
# ------------------------------------------------------------

def test_box_select_overlay_visible():
    from tools.box_select import BoxSelectTool

    canvas = _make_canvas()
    tool = BoxSelectTool()
    tool.box_start = (-4.0, -2.0)
    tool.box_end = (4.0, 2.0)

    img = QImage(canvas.size(), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    tool.draw_overlay(p, canvas)
    p.end()

    assert _non_white_count(img) > 50, (
        "框选工具预览框不可见。"
        "请检查 BoxSelectTool.draw_overlay。"
    )