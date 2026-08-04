"""插入工具：图像 / 表格 / 饼图 / 柱状图。注册到「插入」菜单（panel="insert"）。"""

from PySide6.QtWidgets import QFileDialog

from core.registry import register_tool
from tools.base import Tool

from media.image_obj import ImageObject
from media.table_obj import TableObject
from media.chart_obj import PieChartObject, BarChartObject


def _finish_insert(canvas, obj):
    """统一完成插入：加入文档、选中、切回选择工具。"""
    canvas.doc.add(obj)
    canvas.doc.set_selection([obj])

    # ★ 延迟导入，避免 media.insert_tools ↔ tools.select 循环导入
    from tools.select import SelectTool
    canvas.set_tool(SelectTool())


@register_tool(name="插入图像", order=1, panel="insert", icon="insert_image",
               hint="点击画布插入图片")
class InsertImageTool(Tool):
    def press(self, canvas, wpt, hit):
        path, _ = QFileDialog.getOpenFileName(
            canvas, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            obj = ImageObject(wpt[0], wpt[1], path)
            _finish_insert(canvas, obj)


@register_tool(name="插入表格", order=2, panel="insert", icon="insert_table",
               hint="点击画布插入表格（向导设置行列/数值/颜色）")
class InsertTableTool(Tool):
    def press(self, canvas, wpt, hit):
        from media.table_wizard import InsertTableWizard

        wiz = InsertTableWizard(canvas)
        if wiz.exec():
            rows, cols, cells, cell_colors = wiz.get_table_data()
            width = max(cols * 1.6, 3.0)
            height = max(rows * 1.1, 2.0)
            obj = TableObject(wpt[0], wpt[1], rows, cols, cells, cell_colors,
                              width, height)
            _finish_insert(canvas, obj)


@register_tool(name="插入饼图", order=3, panel="insert", icon="insert_pie",
               hint="点击画布插入饼状图（点 ✎ 编辑数据）")
class InsertPieTool(Tool):
    def press(self, canvas, wpt, hit):
        obj = PieChartObject(wpt[0], wpt[1])
        _finish_insert(canvas, obj)


@register_tool(name="插入柱状图", order=4, panel="insert", icon="insert_bar",
               hint="点击画布插入柱状图（点 ✎ 编辑数据）")
class InsertBarTool(Tool):
    def press(self, canvas, wpt, hit):
        obj = BarChartObject(wpt[0], wpt[1])
        _finish_insert(canvas, obj)