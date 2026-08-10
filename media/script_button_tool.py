"""插入脚本按钮工具：注册到「插入」菜单。

点击画布后打开脚本按钮向导，而不是直接插入裸脚本。
"""

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
    hint="点击画布，通过向导创建脚本按钮"
)
class InsertScriptButtonTool(Tool):
    def press(self, canvas, wpt, hit):
        from media.script_button_wizard import ScriptButtonWizard

        dlg = ScriptButtonWizard(canvas, None, parent=canvas)
        if not dlg.exec():
            return

        obj = ScriptButtonObject(
            wpt[0],
            wpt[1],
            width=4.5,
            height=1.3,
        )

        dlg.apply_to(obj)
        _finish_insert(canvas, obj)