"""表达式几何创建入口：表达式圆（点圆心+输入半径表达式）、表达式点（输入 x/y 表达式）。"""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit,
                               QDialogButtonBox, QInputDialog)

from geo.constraints import ExprCircle, ExprPoint
from tools.base import Tool, point_or_snap


class ExprCircleTool(Tool):
    """表达式圆：点一下圆心，再输入半径表达式。"""
    def activated(self, canvas):
        self.center = None

    def deactivated(self, canvas):
        self.center = None

    def press(self, canvas, wpt, hit):
        center = point_or_snap(canvas, wpt, hit)
        expr, ok = QInputDialog.getText(
            canvas, "表达式圆", "半径表达式（可用变量，如 2*a+1）：", text="1")
        if ok and expr.strip():
            canvas.doc.add(ExprCircle(center, expr.strip()))


def new_expr_point(parent, doc):
    """表达式点对话框：输入 x、y 坐标表达式。"""
    dlg = QDialog(parent)
    dlg.setWindowTitle("表达式点")
    dlg.setMinimumWidth(320)
    layout = QVBoxLayout(dlg)
    layout.addWidget(QLabel("x 坐标表达式（可用变量）："))
    ex = QLineEdit("0"); layout.addWidget(ex)
    layout.addWidget(QLabel("y 坐标表达式（可用变量）："))
    ey = QLineEdit("0"); layout.addWidget(ey)
    btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                            QDialogButtonBox.StandardButton.Cancel)
    btns.accepted.connect(dlg.accept)
    btns.rejected.connect(dlg.reject)
    layout.addWidget(btns)
    if dlg.exec():
        ex_t, ey_t = ex.text().strip(), ey.text().strip()
        if ex_t and ey_t:
            doc.add(ExprPoint(ex_t, ey_t))