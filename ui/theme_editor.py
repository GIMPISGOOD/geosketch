"""自定义主题编辑器：可视化调整所有颜色项，支持保存/导入/导出/实时应用。"""
import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                               QLabel, QLineEdit, QPushButton, QScrollArea,
                               QWidget, QColorDialog, QFileDialog, QMessageBox)

from ui import theme as _theme

# 颜色项分组（显示名 → 键列表）
GROUPS = [
    ("背景", ["BG_TOP", "BG_BOTTOM"]),
    ("网格", ["GRID_MINOR", "GRID_MAJOR"]),
    ("坐标轴", ["AXIS"]),
    ("点", ["POINT_FILL", "POINT_RING"]),
    ("线段 / 直线 / 射线", ["SEGMENT", "LINE", "RAY"]),
    ("圆", ["CIRCLE"]),
    ("多边形", ["POLYGON"]),
    ("交点", ["INTERSECT"]),
    ("测量", ["MEASURE"]),
    ("选中", ["SELECTED"]),
    ("预览", ["PREVIEW"]),
    ("标签 / 图标", ["LABEL", "ICON_INK"]),
    ("强调色", ["ACCENT"]),
    ("墨水 / 次级文字", ["INK", "SUBINK"]),
    ("面板", ["PANEL_BG", "PANEL_BORDER", "PANEL_HOVER", "PANEL_CHECKED"]),
    ("窗口 / 菜单", ["WINDOW_BG", "MENU_BG", "MENU_HOVER", "BORDER"]),
    ("椭圆", ["ELLIPSE"]),
    ("贝塞尔", ["BEZIER"]),
]

# 这些键存的是 (r,g,b,a) 元组，颜色选择器要开 Alpha 通道
ALPHA_KEYS = {"GRID_MINOR", "GRID_MAJOR", "PANEL_BG", "PANEL_BORDER",
              "PANEL_HOVER", "PANEL_CHECKED"}


class ThemeEditorDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义主题")
        self.setMinimumSize(620, 720)
        # 复制当前主题颜色作为编辑起点
        self._colors: dict[str, QColor] = {}
        current = _theme.THEMES[_theme.active_name()]
        for k, v in current.items():
            if isinstance(v, str):
                self._colors[k] = QColor(v)
            elif isinstance(v, tuple):
                self._colors[k] = QColor(*v)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(10)

        # 主题名称
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("主题名称："))
        self._name_edit = QLineEdit("我的主题")
        name_row.addWidget(self._name_edit, 1)
        root.addLayout(name_row)

        # 颜色网格（滚动区）
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setSpacing(6)
        grid.setContentsMargins(8, 8, 8, 8)

        self._color_btns: dict[str, QPushButton] = {}
        row = 0
        for group_name, keys in GROUPS:
            # 分组标题
            lbl = QLabel(f"<b>{group_name}</b>")
            grid.addWidget(lbl, row, 0, 1, 3)
            row += 1
            for key in keys:
                if key not in self._colors:
                    continue
                name_lbl = QLabel(key)
                grid.addWidget(name_lbl, row, 0)
                btn = QPushButton()
                btn.setFixedSize(70, 24)
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                self._paint_btn(btn, self._colors[key])
                btn.clicked.connect(lambda _=False, k=key, b=btn: self._pick(k, b))
                grid.addWidget(btn, row, 1)
                self._color_btns[key] = btn
                row += 1

        scroll.setWidget(grid_widget)
        root.addWidget(scroll, 1)

        # 底部按钮
        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存为新主题")
        save_btn.clicked.connect(self._save)
        import_btn = QPushButton("导入…")
        import_btn.clicked.connect(self._import)
        export_btn = QPushButton("导出…")
        export_btn.clicked.connect(self._export)
        apply_btn = QPushButton("应用")
        apply_btn.clicked.connect(self._apply)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(save_btn)
        btn_row.addWidget(import_btn)
        btn_row.addWidget(export_btn)
        btn_row.addStretch()
        btn_row.addWidget(apply_btn)
        btn_row.addWidget(cancel_btn)
        root.addLayout(btn_row)

    # ───────── 内部工具 ─────────
    def _paint_btn(self, btn, color: QColor):
        btn.setStyleSheet(
            f"background:{color.name()};border:1px solid #888;border-radius:4px;")

    def _to_dict(self) -> dict:
        """把当前编辑的颜色转成 THEMES 字典格式。"""
        d = {}
        for k, c in self._colors.items():
            if k in ALPHA_KEYS:
                d[k] = (c.red(), c.green(), c.blue(), c.alpha())
            else:
                d[k] = c.name()
        return d

    # ───────── 按钮回调 ─────────
    def _pick(self, key, btn):
        opt = QColorDialog.ColorDialogOption.ShowAlphaChannel if key in ALPHA_KEYS \
            else QColorDialog.ColorDialogOption(0)
        c = QColorDialog.getColor(self._colors[key], self, f"选择 {key} 颜色", opt)
        if c.isValid():
            self._colors[key] = c
            self._paint_btn(btn, c)

    def _save(self):
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "提示", "请输入主题名称。")
            return
        _theme.save_custom_theme(name, self._to_dict())
        QMessageBox.information(self, "保存成功",
                                f"主题「{name}」已保存，可在「主题」菜单中切换。")

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "导入主题", "", "JSON 文件 (*.json)")
        if not path:
            return
        name = _theme.import_theme(path)
        # 重新加载到编辑器
        imported = _theme.THEMES[name]
        for k, v in imported.items():
            if isinstance(v, str):
                self._colors[k] = QColor(v)
            elif isinstance(v, tuple):
                self._colors[k] = QColor(*v)
        for k, btn in self._color_btns.items():
            if k in self._colors:
                self._paint_btn(btn, self._colors[k])
        self._name_edit.setText(name)

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "导出主题", "theme.json", "JSON 文件 (*.json)")
        if path:
            Path(path).write_text(
                json.dumps(self._to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")

    def _apply(self):
        """把当前编辑的颜色作为临时主题立即应用（不永久保存）。"""
        _theme.save_custom_theme("__preview__", self._to_dict())
        _theme.set_theme("__preview__")
        self.accept()