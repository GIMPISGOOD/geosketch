"""图像对象：插入图片文件，随画布缩放。"""
from PySide6.QtGui import QPixmap

from core.registry import register_geo, register_renderer
from media.base import MediaObject
from ui import theme


@register_geo("ImageObject")
class ImageObject(MediaObject):
    def __init__(self, x, y, path, width=None, height=None):
        self.path = path
        self.pixmap = QPixmap(path)
        if width is None:
            if self.pixmap.width() > 0:
                aspect = self.pixmap.height() / self.pixmap.width()
            else:
                aspect = 0.75
            width = 8.0
            height = width * aspect
        super().__init__(x, y, width, height)

    def dump(self):
        d = super().dump()
        d["path"] = self.path
        return d

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"], params["path"],
                   params.get("width"), params.get("height"))


@register_renderer(ImageObject)
def draw_image(p, obj, view):
    rect = obj.screen_rect(view)
    if not obj.pixmap.isNull():
        p.drawPixmap(rect.toRect(), obj.pixmap)
    # 选中时画边框
    if obj.selected:
        p.setPen(theme.pen(theme.SELECTED, 2))
        p.setBrush(theme.brush("transparent"))
        p.drawRect(rect)