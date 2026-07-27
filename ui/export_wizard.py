"""导出向导：可视化配置导出选项，带实时预览。

选项：
  视图范围 —— 当前视图 / 适配内容并居中
  背景内容 —— 网格+坐标轴 / 仅坐标轴 / 无
  格式     —— PNG（可选分辨率）/ SVG 矢量
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (QDialog, QRadioButton, QGroupBox, QVBoxLayout,
                               QHBoxLayout, QLabel, QComboBox, QPushButton,
                               QFileDialog, QMessageBox)


class ExportWizard(QDialog):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setWindowTitle("导出向导")
        self.setModal(True)
        self.setMinimumSize(780, 540)
        self._build_ui()
        self._refresh_preview()

    # ───────────── UI 搭建 ─────────────
    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(18)

        # 左侧：实时预览
        left = QVBoxLayout()
        cap = QLabel("实时预览")
        cap.setStyleSheet("font-weight:700; font-size:13px;")
        left.addWidget(cap)
        self._preview = QLabel()
        self._preview.setFixedSize(460, 400)
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setStyleSheet(
            "border:1px solid rgba(120,140,170,0.35); border-radius:8px;"
            "background:rgba(0,0,0,0.06);")
        left.addWidget(self._preview)
        self._info = QLabel()
        self._info.setStyleSheet("color:#5a6b82; font-size:11px;")
        left.addWidget(self._info)
        left.addStretch(1)
        root.addLayout(left)

        # 右侧：选项
        right = QVBoxLayout()

        g1 = QGroupBox("视图范围")
        v1 = QVBoxLayout(g1)
        self._r_cur = QRadioButton("当前视图")
        self._r_fit = QRadioButton("适配内容并居中")
        self._r_fit.setChecked(True)
        v1.addWidget(self._r_cur)
        v1.addWidget(self._r_fit)
        right.addWidget(g1)

        g2 = QGroupBox("背景内容")
        v2 = QVBoxLayout(g2)
        self._bg_grid = QRadioButton("网格 + 坐标轴")
        self._bg_axes = QRadioButton("仅坐标轴")
        self._bg_none = QRadioButton("无（仅几何图形）")
        self._bg_grid.setChecked(True)
        v2.addWidget(self._bg_grid)
        v2.addWidget(self._bg_axes)
        v2.addWidget(self._bg_none)
        right.addWidget(g2)

        g3 = QGroupBox("格式")
        v3 = QVBoxLayout(g3)
        self._fmt_png = QRadioButton("PNG 高清位图")
        self._fmt_svg = QRadioButton("SVG 矢量图")
        self._fmt_png.setChecked(True)
        v3.addWidget(self._fmt_png)
        v3.addWidget(self._fmt_svg)
        res_row = QHBoxLayout()
        res_row.addWidget(QLabel("分辨率"))
        self._res = QComboBox()
        self._res.addItems(["1× (标准)", "2× (高清)", "3× (超清)"])
        self._res.setCurrentIndex(1)
        res_row.addWidget(self._res)
        v3.addLayout(res_row)
        right.addWidget(g3)

        right.addStretch(1)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("取消")
        cancel.clicked.connect(self.reject)
        export = QPushButton("导出…")
        export.setDefault(True)
        export.clicked.connect(self._on_export)
        btns.addWidget(cancel)
        btns.addWidget(export)
        right.addLayout(btns)

        root.addLayout(right)

        # 任一选项变化 → 立即刷新预览
        for w in (self._r_cur, self._r_fit, self._bg_grid, self._bg_axes,
                  self._bg_none, self._fmt_png, self._fmt_svg):
            w.toggled.connect(self._refresh_preview)
        self._res.currentIndexChanged.connect(self._refresh_preview)

    # ───────────── 选项读取 ─────────────
    def _bg_mode(self):
        if self._bg_grid.isChecked():
            return "grid"
        if self._bg_axes.isChecked():
            return "axes"
        return "none"

    def _png_scale(self):
        return float(self._res.currentText()[0])     # "2× (高清)" → 2.0

    # ───────────── 预览 / 导出 ─────────────
    def _refresh_preview(self):
        self._res.setEnabled(self._fmt_png.isChecked())
        img = self.canvas.render_to_image(
            fit=self._r_fit.isChecked(), bg_mode=self._bg_mode(), scale=1.0)
        pix = QPixmap.fromImage(img).scaled(
            self._preview.size() - QSize(12, 12),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation)
        self._preview.setPixmap(pix)
        scale = self._png_scale() if self._fmt_png.isChecked() else 1.0
        self._info.setText(
            f"输出尺寸：{int(self.canvas.width()*scale)} × "
            f"{int(self.canvas.height()*scale)} px"
            + ("（矢量，可无限缩放）" if self._fmt_svg.isChecked() else ""))

    def _on_export(self):
        is_svg = self._fmt_svg.isChecked()
        default, flt = ("sketch.svg", "SVG 矢量图 (*.svg)") if is_svg \
            else ("sketch.png", "PNG 图像 (*.png)")
        path, _ = QFileDialog.getSaveFileName(self, "导出图像", default, flt)
        if not path:
            return
        try:
            self.canvas.export_image(path, fit=self._r_fit.isChecked(),
                                     bg_mode=self._bg_mode(),
                                     png_scale=self._png_scale())
        except Exception as e:
            QMessageBox.warning(self, "导出失败", f"导出图像时出错：\n{e}")
        else:
            self.accept()          # 导出成功后关闭向导