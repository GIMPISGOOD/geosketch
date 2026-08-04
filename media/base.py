"""媒体对象基类：位置/尺寸/拾取/拖动/缩放/编辑按钮。"""
import math

from PySide6.QtCore import QRectF, Qt

from geo.base import GeoObject


class MediaObject(GeoObject):
    """媒体对象基类。x,y 为左上角世界坐标，width/height 为世界尺寸。"""
    media = True

    def __init__(self, x=0.0, y=0.0, width=6.0, height=4.0):
        super().__init__(parents=())
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)

    def distance_to(self, x, y):
        # self.x, self.y 是左上角；
        # 高度向世界坐标下方延伸，所以底边是 self.y - self.height
        if self.x <= x <= self.x + self.width and self.y - self.height <= y <= self.y:
            return 0.0

        dx = max(self.x - x, 0.0, x - (self.x + self.width))
        dy = max((self.y - self.height) - y, 0.0, y - self.y)
        return math.hypot(dx, dy)

    def screen_rect(self, view):
        tl = view.to_screen(self.x, self.y)
        br = view.to_screen(self.x + self.width, self.y - self.height)
        return QRectF(tl, br).normalized()
    
    def edit_button_rect(self, view):
        """编辑按钮屏幕矩形（右上角）。"""
        rect = self.screen_rect(view)
        s = 22
        return QRectF(rect.right() - s - 3, rect.top() + 3, s, s)

    def resize_handle_rect(self, view):
        """缩放手柄屏幕矩形（右下角）。"""
        rect = self.screen_rect(view)
        s = 12
        return QRectF(rect.right() - s / 2 - 1, rect.bottom() - s / 2 - 1, s, s)

    def resize_to(self, wpt):
        """拖动右下角手柄到世界坐标 wpt，调整宽高。
        左上角 self.x, self.y 保持不动。
        """
        self.width = max(wpt[0] - self.x, 0.5)
        self.height = max(self.y - wpt[1], 0.5)

    def dump(self):
        return {"x": self.x, "y": self.y,
                "width": self.width, "height": self.height}

    def edit(self, canvas):
        """编辑（子类覆盖，由编辑按钮触发）。"""
        pass


def draw_media_decorations(p, obj, view):
    """选中时统一绘制：边框 + ✎编辑按钮 + 缩放手柄。"""
    if not obj.selected:
        return
    from ui import theme
    rect = obj.screen_rect(view)
    # 选中边框
    p.setPen(theme.pen(theme.SELECTED, 1.5))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRect(rect)
    # 编辑按钮（右上角）
    eb = obj.edit_button_rect(view)
    p.setBrush(theme.brush(theme.PANEL_BG))
    p.setPen(theme.pen(theme.ACCENT, 1.5))
    p.drawRoundedRect(eb, 4, 4)
    p.setPen(theme.pen(theme.INK, 1))
    f = p.font(); f.setPixelSize(13); p.setFont(f)
    p.drawText(eb, Qt.AlignmentFlag.AlignCenter, "✎")
    # 缩放手柄（右下角）
    rh = obj.resize_handle_rect(view)
    p.setBrush(theme.brush(theme.ACCENT))
    p.setPen(theme.pen(theme.SELECTED, 1))
    p.drawRect(rh)