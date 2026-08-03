"""表格对象：可编辑的行列网格，支持每格颜色与 {表达式} 求值。"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor

from core.registry import register_geo, register_renderer
from core.variables import eval_expr
from media.base import MediaObject
from ui import theme


@register_geo("TableObject")
class TableObject(MediaObject):
    def __init__(self, x, y, rows=3, cols=3, cells=None, cell_colors=None,
                 width=6.0, height=4.0):
        super().__init__(x, y, width, height)
        self.rows = rows
        self.cols = cols
        self.cells = cells or [["" for _ in range(cols)] for _ in range(rows)]
        self.cell_colors = cell_colors or [[None for _ in range(cols)] for _ in range(rows)]

    def _eval_cell(self, text):
        """若 text 形如 {表达式}，求值并返回格式化结果；否则原样返回。"""
        if not isinstance(text, str):
            return str(text)
        text = text.strip()
        if text.startswith("{") and text.endswith("}") and len(text) > 2:
            expr = text[1:-1].strip()
            val = eval_expr(expr)
            if val is not None:
                if abs(val - round(val)) < 1e-9:
                    return str(int(round(val)))
                return f"{val:.2f}"
            return text          # 求值失败 → 显示原文
        return text

    def dump(self):
        d = super().dump()
        d.update({"rows": self.rows, "cols": self.cols,
                  "cells": self.cells, "cell_colors": self.cell_colors})
        return d

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"], params.get("rows", 3),
                   params.get("cols", 3), params.get("cells"),
                   params.get("cell_colors"),
                   params.get("width", 6.0), params.get("height", 4.0))

    def edit(self, canvas):
        """双击编辑：用同一向导预填现有数据。"""
        from media.table_wizard import InsertTableWizard
        wiz = InsertTableWizard(canvas, self.rows, self.cols, self.cells, self.cell_colors)
        if wiz.exec():
            rows, cols, cells, cell_colors = wiz.get_table_data()
            self.rows, self.cols = rows, cols
            self.cells, self.cell_colors = cells, cell_colors
            self.width = max(cols * 1.6, 3.0)
            self.height = max(rows * 1.1, 2.0)


@register_renderer(TableObject)
def draw_table(p, obj, view):
    rect = obj.screen_rect(view)
    rows, cols = obj.rows, obj.cols
    if rows <= 0 or cols <= 0:
        return
    cell_w = rect.width() / cols
    cell_h = rect.height() / rows
    for r in range(rows):
        for c in range(cols):
            cell_rect = QRectF(rect.x() + c * cell_w, rect.y() + r * cell_h,
                               cell_w, cell_h)
            # 格子背景色
            bg = None
            if r < len(obj.cell_colors) and c < len(obj.cell_colors[r]):
                bg = obj.cell_colors[r][c]
            p.setBrush(theme.brush(QColor(bg)) if bg else theme.brush(theme.BG_TOP))
            p.setPen(theme.pen(theme.LABEL, 1))
            p.drawRect(cell_rect)
            # 文本（{表达式} 自动求值）
            txt = ""
            if r < len(obj.cells) and c < len(obj.cells[r]):
                txt = obj._eval_cell(obj.cells[r][c])
            p.setPen(theme.pen(theme.INK, 1))
            p.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, txt)
    if obj.selected:
        p.setPen(theme.pen(theme.SELECTED, 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(rect)