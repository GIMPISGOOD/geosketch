from core.registry import register_tool
from tools.base import Tool, point_or_snap


@register_tool(name="点", shortcut="P", order=1, icon="point",
               hint="空白处点击生成自由点；点在线段/圆上生成吸附点（均自动磁吸）")
class PointTool(Tool):
    def press(self, canvas, wpt, hit):
        point_or_snap(canvas, wpt, hit)