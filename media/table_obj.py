"""表格对象：可编辑的行列网格。"""
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QVBoxLayout, QDialogButtonBox

from core.registry import register_geo, register_renderer
from media.base import MediaObject
from ui import theme


@register_geo("TableObject")
class TableObject(MediaObject):
    def __init__(self, x, y, rows=3, cols=3, cells=None, width=6.0, height=4.0):
        super().__init__(x, y, width, height)
        self.rows = rows
        self.cols = cols
        self.cells = cells or [["" for _ in range(cols)] for _ in range(rows)]

    def dump(self):
        d = super().dump()
        d.update({"rows": self.rows, "cols": self.cols, "cells": self.cells})
        return d

    @classmethod
    def build(cls, parents, params):
        return cls(params["x"], params["y"], params.get("rows", 3),
                   params.get("cols", 3), params.get("cells"),
                   params.get("width", 6.0), params.get("height", 4.0))

    def edit(self, canvas):
        dlg = QDialog(canvas)
        dlg.setWindowTitle("编辑表格")
        dlg.resize(400, 300)
        layout = QVBoxLayout(dlg)
        tw = QTableWidget(self.rows, self.cols)
        for r in range(self.rows):
            for c in range(self.cols):
                txt = self.cells[r][c] if r < len(self.cells) and c < len(self.cells[r]) else ""
                tw.setItem(r, c, QTableWidgetItem(txt))
        layout.addWidget(tw)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        if dlg.exec():
            for r in range(self.rows):
                for c in range(self.cols):
                    item = tw.item(r, c)
                    self.cells[r][c] = item.text() if item else ""


@register_renderer(TableObject)
def draw_table(p, obj, view):
    rect = obj.screen_rect(view)
    rows, cols = obj.rows, obj.cols
    cell_w = rect.width() / cols
    cell_h = rect.height() / rows
    for r in range(rows):
        for c in range(cols):
            cell_rect = QRectF(rect.x() + c * cell_w, rect.y() + r * cell_h, cell_w, cell_h)
            p.setBrush(theme.brush(theme.BG_TOP))
            p.setPen(theme.pen(theme.LABEL, 1))
            p.drawRect(cell_rect)
            txt = ""
            if r < len(obj.cells) and c < len(obj.cells[r]):
                txt = obj.cells[r][c]
            p.setPen(theme.pen(theme.INK, 1))
            p.drawText(cell_rect, Qt.AlignmentFlag.AlignCenter, txt)
    if obj.selected:
        p.setPen(theme.pen(theme.SELECTED, 2))
        p.setBrush(theme.brush("transparent"))
        p.drawRect(rect)