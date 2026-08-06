"""脚本按钮对象：画布上的可点击按钮，单击运行脚本。"""

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QPainterPath

from core.registry import register_geo, register_renderer
from media.base import MediaObject, draw_media_decorations
from ui import theme


@register_geo("ScriptButtonObject")
class ScriptButtonObject(MediaObject):
    """脚本按钮。

    - x,y：左上角世界坐标
    - width/height：世界尺寸，手动调整
    - text：按钮文字
    - script：脚本内容
    - color：按钮背景色
    - text_color：文字颜色
    - readonly：预留只读属性
    """

    def __init__(
        self,
        x,
        y,
        width=4.0,
        height=1.2,
        text="运行",
        script="",
        color="#1971c2",
        text_color="#ffffff",
        readonly=False
    ):
        super().__init__(x, y, width, height)

        self.text = text
        self.script = script
        self.color = color
        self.text_color = text_color
        self.readonly = bool(readonly)

    def dump(self):
        d = super().dump()
        d.update({
            "text": self.text,
            "script": self.script,
            "color": self.color,
            "text_color": self.text_color,
            "readonly": self.readonly,
        })
        return d

    @classmethod
    def build(cls, parents, params):
        obj = cls(
            params["x"],
            params["y"],
            params.get("width", 4.0),
            params.get("height", 1.2),
            params.get("text", "运行"),
            params.get("script", ""),
            params.get("color", "#1971c2"),
            params.get("text_color", "#ffffff"),
            params.get("readonly", False),
        )
        obj.rotation = params.get("rotation", 0.0)
        return obj

    def edit(self, canvas):
        """双击 / ✎ 按钮打开脚本编辑器。"""
        from ui.script_editor import edit_script_button
        edit_script_button(canvas, self)

    def run(self, canvas):
        """单击运行脚本。"""
        from core.scripting import run_script
        run_script(
            canvas.doc,
            self.script,
            owner_id=self.id,
            canvas=canvas
        )


@register_renderer(ScriptButtonObject)
def draw_script_button(p, obj, view):
    rect = obj.screen_rect(view)

    path = QPainterPath()
    path.addRoundedRect(rect, 10, 10)

    p.save()

    p.setBrush(theme.brush(QColor(obj.color)))
    p.setPen(theme.pen(theme.SELECTED if obj.selected else theme.SUBINK, 1.2))
    p.drawPath(path)

    font = p.font()
    font.setPixelSize(max(10, int(rect.height() * 0.42)))
    font.setBold(True)
    p.setFont(font)

    p.setPen(theme.pen(QColor(obj.text_color)))
    p.drawText(rect, Qt.AlignmentFlag.AlignCenter, obj.text)

    p.restore()

    draw_media_decorations(p, obj, view)