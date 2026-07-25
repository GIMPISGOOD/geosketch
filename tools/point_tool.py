# tools/point_tool.py
from core.registry import register_tool
from tools.base import Tool, point_or_snap
from ui.icons import icon_point


@register_tool(name="点", shortcut="P", order=1, icon=icon_point,
               hint="空白处点击生成自由点；点在线段上生成吸附点")
class PointTool(Tool):
    def press(self, canvas, wpt, hit):
        point_or_snap(canvas, wpt, hit)