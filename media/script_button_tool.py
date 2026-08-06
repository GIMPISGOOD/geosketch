"""插入脚本按钮工具：注册到「插入」菜单。"""

from PySide6.QtWidgets import QFileDialog  # noqa: F401  保持和其他 insert 工具一致
from core.registry import register_tool
from tools.base import Tool

from media.script_button import ScriptButtonObject


def _finish_insert(canvas, obj):
    canvas.doc.add(obj)
    canvas.doc.set_selection([obj])

    from tools.select import SelectTool
    canvas.set_tool(SelectTool())


@register_tool(
    name="插入脚本按钮",
    order=5,
    panel="insert",
    icon="insert_table",
    hint="点击画布插入脚本按钮"
)
class InsertScriptButtonTool(Tool):
    def press(self, canvas, wpt, hit):
        obj = ScriptButtonObject(
            wpt[0],
            wpt[1],
            width=4.0,
            height=1.2,
            text="运行",
            script="""# 示例脚本
set n = 3

repeat n {
    print("GeoSketch 脚本运行")
}

__keep = true
"""
        )

        _finish_insert(canvas, obj)