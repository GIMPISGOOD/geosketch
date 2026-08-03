"""插入工具：图像 / 表格 / 饼图 / 柱状图。注册到「插入」菜单（panel="insert"）。"""
from core.registry import register_tool
from tools.base import Tool
from media.image_obj import ImageObject
from media.table_obj import TableObject
from media.chart_obj import PieChartObject, BarChartObject


@register_tool(name="插入图像", order=1, panel="insert", icon="insert_image",
               hint="点击画布插入图片")
class InsertImageTool(Tool):
    def press(self, canvas, wpt, hit):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            canvas, "选择图片", "", "图片 (*.png *.jpg *.jpeg *.bmp *.gif)")
        if path:
            canvas.doc.add(ImageObject(wpt[0], wpt[1], path))


@register_tool(name="插入表格", order=2, panel="insert", icon="insert_table",
               hint="点击画布插入表格（向导设置行列/数值/颜色）")
class InsertTableTool(Tool):
    def press(self, canvas, wpt, hit):
        from media.table_wizard import InsertTableWizard
        from media.table_obj import TableObject
        wiz = InsertTableWizard(canvas)
        if wiz.exec():
            rows, cols, cells, cell_colors = wiz.get_table_data()
            width = max(cols * 1.6, 3.0)
            height = max(rows * 1.1, 2.0)
            canvas.doc.add(TableObject(wpt[0], wpt[1], rows, cols,
                                       cells, cell_colors, width, height))


@register_tool(name="插入饼图", order=3, panel="insert", icon="insert_pie",
               hint="点击画布插入饼状图（双击编辑数据）")
class InsertPieTool(Tool):
    def press(self, canvas, wpt, hit):
        canvas.doc.add(PieChartObject(wpt[0], wpt[1]))


@register_tool(name="插入柱状图", order=4, panel="insert", icon="insert_bar",
               hint="点击画布插入柱状图（双击编辑数据）")
class InsertBarTool(Tool):
    def press(self, canvas, wpt, hit):
        canvas.doc.add(BarChartObject(wpt[0], wpt[1]))