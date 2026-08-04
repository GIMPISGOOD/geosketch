"""图像对象：插入图片文件，随画布缩放。
支持：
- 拖动右下角手柄等比放大/缩小
- 拖动上方圆形手柄旋转
"""

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPixmap, QPainter

from core.registry import register_geo, register_renderer
from media.base import MediaObject, draw_media_decorations


@register_geo("ImageObject")
class ImageObject(MediaObject):
    rotatable = True

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

        # 记录宽高比，用于等比缩放
        self.aspect = self.height / self.width if self.width > 0 else 1.0

    def resize_to(self, wpt):
        """图片默认等比缩放。"""
        new_width = max(wpt[0] - self.x, 0.5)

        self.width = new_width
        self.height = max(new_width * self.aspect, 0.5)

    def dump(self):
        d = super().dump()
        d["path"] = self.path
        return d

    @classmethod
    def build(cls, parents, params):
        obj = cls(
            params["x"],
            params["y"],
            params["path"],
            params.get("width"),
            params.get("height")
        )

        obj.rotation = params.get("rotation", 0.0)

        if obj.width > 0:
            obj.aspect = obj.height / obj.width

        return obj


@register_renderer(ImageObject)
def draw_image(p, obj, view):
    rect = obj.screen_rect(view)

    if not obj.pixmap.isNull():
        p.save()

        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # 以图片中心为旋转中心
        p.translate(rect.center())
        p.rotate(getattr(obj, "rotation", 0.0))

        target = QRectF(
            -rect.width() / 2,
            -rect.height() / 2,
            rect.width(),
            rect.height()
        )

        p.drawPixmap(target.toRect(), obj.pixmap)

        p.restore()

    # 选中边框、编辑按钮、缩放手柄、旋转手柄
    draw_media_decorations(p, obj, view)