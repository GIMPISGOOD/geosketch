"""媒体对象基类：有位置/尺寸的矩形对象，可被拾取、拖动、序列化。"""
import math

from geo.base import GeoObject


class MediaObject(GeoObject):
    """媒体对象基类。x,y 为左上角世界坐标，width/height 为世界尺寸。
    media=True 标记供选择工具识别拖动。"""
    media = True

    def __init__(self, x=0.0, y=0.0, width=6.0, height=4.0):
        super().__init__(parents=())
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)

    def distance_to(self, x, y):
        """矩形内返回 0，否则返回到矩形边缘的距离。"""
        if self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height:
            return 0.0
        dx = max(self.x - x, 0.0, x - (self.x + self.width))
        dy = max(self.y - y, 0.0, y - (self.y + self.height))
        return math.hypot(dx, dy)

    def screen_rect(self, view):
        """返回屏幕坐标矩形。"""
        from PySide6.QtCore import QRectF
        tl = view.to_screen(self.x, self.y)
        br = view.to_screen(self.x + self.width, self.y + self.height)
        return QRectF(tl, br).normalized()

    def dump(self):
        return {"x": self.x, "y": self.y,
                "width": self.width, "height": self.height}

    def edit(self, canvas):
        """双击编辑（子类覆盖）。"""
        pass