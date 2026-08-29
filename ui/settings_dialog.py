"""偏好设置对话框。

五页分类：外观 / 画布 / 动效 / 交互 / 工作流。
所有值从 ``SettingsStore`` 读取，写入时通过 ``set()`` 触发 ``changed`` 信号。

对外契约：
    SettingsDialog(settings: SettingsStore, parent: QWidget | None) → QDialog
"""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDoubleSpinBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_PAGES = [
    ("🎨", "外观"),
    ("📐", "画布"),
    ("✨", "动效"),
    ("🖱", "交互"),
    ("⚙", "工作流"),
]


class SettingsDialog(QDialog):
    """模态偏好设置对话框。

    参数
    ----
    settings : SettingsStore
        当前 ``Document.settings`` 实例。
    """

    def __init__(self, settings, parent=None):
        super().__init__(parent)
        self._s = settings
        self.setWindowTitle("偏好设置")
        self.setMinimumSize(580, 460)

        root = QHBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        # ── 左侧导航 ──
        self._nav = QListWidget()
        self._nav.setFixedWidth(100)
        for icon, title in _PAGES:
            self._nav.addItem(QListWidgetItem(f" {icon}  {title}"))
        self._nav.setCurrentRow(0)

        # ── 右侧页面 ──
        self._stack = QStackedWidget()
        self._build_appearance()
        self._build_canvas()
        self._build_effects()
        self._build_interaction()
        self._build_workflow()
        self._nav.currentRowChanged.connect(self._stack.setCurrentIndex)

        right = QVBoxLayout()
        right.addWidget(self._stack, 1)

        # ── 底部按钮 ──
        btn_row = QHBoxLayout()
        _reset = QPushButton("恢复默认")
        _reset.clicked.connect(self._on_reset)
        btn_row.addWidget(_reset)
        btn_row.addStretch(1)
        _cancel = QPushButton("取消")
        _cancel.clicked.connect(self.reject)
        btn_row.addWidget(_cancel)
        _apply = QPushButton("应用")
        _apply.clicked.connect(self._on_apply)
        btn_row.addWidget(_apply)
        _ok = QPushButton("确定")
        _ok.clicked.connect(self._on_ok)
        btn_row.addWidget(_ok)
        right.addLayout(btn_row)

        root.addWidget(self._nav)
        root.addLayout(right, 1)

        self._load()

    # ══════════════════════════════════════════════════
    #  页面构建
    # ══════════════════════════════════════════════════

    def _new_page(self) -> QFormLayout:
        w = QWidget()
        form = QFormLayout(w)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)
        form.setLabelAlignment(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.AlignmentFlag.AlignRight
        )
        self._stack.addWidget(w)
        return form

    # ── 外观 ──
    def _build_appearance(self):
        f = self._new_page()
        self._w_ui_font = QFontComboBox()
        f.addRow("UI 字体", self._w_ui_font)

        self._w_ui_size = QSpinBox()
        self._w_ui_size.setRange(6, 24)
        f.addRow("UI 字号", self._w_ui_size)

        self._w_label_font = QFontComboBox()
        f.addRow("标签字体", self._w_label_font)

        self._w_label_size = QSpinBox()
        self._w_label_size.setRange(6, 24)
        f.addRow("标签字号", self._w_label_size)

        self._w_axis_font = QFontComboBox()
        f.addRow("轴字体", self._w_axis_font)

        self._w_axis_size = QSpinBox()
        self._w_axis_size.setRange(6, 24)
        f.addRow("轴字号", self._w_axis_size)

        self._w_math_scale = QDoubleSpinBox()
        self._w_math_scale.setRange(0.5, 3.0)
        self._w_math_scale.setSingleStep(0.1)
        self._w_math_scale.setDecimals(1)
        f.addRow("数学缩放", self._w_math_scale)

        self._w_line_w = QDoubleSpinBox()
        self._w_line_w.setRange(0.5, 10.0)
        self._w_line_w.setSingleStep(0.5)
        self._w_line_w.setDecimals(1)
        f.addRow("默认线宽", self._w_line_w)

        self._w_pt_r = QDoubleSpinBox()
        self._w_pt_r.setRange(1.0, 20.0)
        self._w_pt_r.setSingleStep(0.5)
        self._w_pt_r.setDecimals(1)
        f.addRow("点半径", self._w_pt_r)

        self._w_pt_sel_r = QDoubleSpinBox()
        self._w_pt_sel_r.setRange(1.0, 20.0)
        self._w_pt_sel_r.setSingleStep(0.5)
        self._w_pt_sel_r.setDecimals(1)
        f.addRow("选中点半径", self._w_pt_sel_r)

    # ── 画布 ──
    def _build_canvas(self):
        f = self._new_page()
        self._w_grid_vis = QCheckBox("显示网格")
        f.addRow(self._w_grid_vis)

        self._w_grid_base = QDoubleSpinBox()
        self._w_grid_base.setRange(16.0, 256.0)
        self._w_grid_base.setSingleStep(8.0)
        self._w_grid_base.setDecimals(0)
        f.addRow("网格间距 (px)", self._w_grid_base)

        self._w_grid_major = QDoubleSpinBox()
        self._w_grid_major.setRange(2.0, 10.0)
        self._w_grid_major.setSingleStep(1.0)
        self._w_grid_major.setDecimals(0)
        f.addRow("主网格倍率", self._w_grid_major)

        self._w_axis_vis = QCheckBox("显示坐标轴")
        f.addRow(self._w_axis_vis)

        self._w_axis_lbl = QCheckBox("显示轴标注")
        f.addRow(self._w_axis_lbl)

        self._w_base_scale = QDoubleSpinBox()
        self._w_base_scale.setRange(8.0, 200.0)
        self._w_base_scale.setSingleStep(4.0)
        self._w_base_scale.setDecimals(0)
        f.addRow("基础缩放", self._w_base_scale)

    # ── 动效 ──
    def _build_effects(self):
        f = self._new_page()
        self._w_fx_on = QCheckBox("启用动效（总开关）")
        f.addRow(self._w_fx_on)

        self._w_panel_ms = QSpinBox()
        self._w_panel_ms.setRange(0, 1000)
        self._w_panel_ms.setSingleStep(50)
        self._w_panel_ms.setSuffix(" ms")
        f.addRow("面板动画时长", self._w_panel_ms)

        self._w_menu_fade = QCheckBox("菜单淡入")
        f.addRow(self._w_menu_fade)

        self._w_dlg_trans = QCheckBox("对话框过渡")
        f.addRow(self._w_dlg_trans)

        self._w_inertia = QCheckBox("画布惯性滑动")
        f.addRow(self._w_inertia)

        self._w_friction = QDoubleSpinBox()
        self._w_friction.setRange(0.50, 0.99)
        self._w_friction.setSingleStep(0.025)
        self._w_friction.setDecimals(3)
        f.addRow("惯性摩擦系数", self._w_friction)

        self._w_hover = QCheckBox("悬停高亮")
        f.addRow(self._w_hover)

    # ── 交互 ──
    def _build_interaction(self):
        f = self._new_page()
        self._w_snap_on = QCheckBox("启用磁吸")
        f.addRow(self._w_snap_on)

        self._w_snap_r = QDoubleSpinBox()
        self._w_snap_r.setRange(4.0, 50.0)
        self._w_snap_r.setSingleStep(1.0)
        self._w_snap_r.setDecimals(0)
        self._w_snap_r.setSuffix(" px")
        f.addRow("磁吸半径", self._w_snap_r)

        self._w_zoom_spd = QDoubleSpinBox()
        self._w_zoom_spd.setRange(1.01, 2.00)
        self._w_zoom_spd.setSingleStep(0.05)
        self._w_zoom_spd.setDecimals(2)
        f.addRow("滚轮缩放速度", self._w_zoom_spd)

        self._w_touch_tol = QDoubleSpinBox()
        self._w_touch_tol.setRange(10.0, 50.0)
        self._w_touch_tol.setSingleStep(1.0)
        self._w_touch_tol.setDecimals(0)
        self._w_touch_tol.setSuffix(" px")
        f.addRow("触屏容差", self._w_touch_tol)

        self._w_mouse_tol = QDoubleSpinBox()
        self._w_mouse_tol.setRange(3.0, 30.0)
        self._w_mouse_tol.setSingleStep(1.0)
        self._w_mouse_tol.setDecimals(0)
        self._w_mouse_tol.setSuffix(" px")
        f.addRow("鼠标容差", self._w_mouse_tol)

        self._w_long_press = QSpinBox()
        self._w_long_press.setRange(100, 2000)
        self._w_long_press.setSingleStep(50)
        self._w_long_press.setSuffix(" ms")
        f.addRow("长按时长", self._w_long_press)

    # ── 工作流 ──
    def _build_workflow(self):
        f = self._new_page()
        self._w_undo = QSpinBox()
        self._w_undo.setRange(10, 500)
        self._w_undo.setSingleStep(10)
        f.addRow("撤销步数上限", self._w_undo)

        self._w_autosave = QSpinBox()
        self._w_autosave.setRange(0, 60)
        self._w_autosave.setSingleStep(1)
        self._w_autosave.setSuffix(" 分钟")
        self._w_autosave.setSpecialValueText("关闭")
        f.addRow("自动保存", self._w_autosave)

    # ══════════════════════════════════════════════════
    #  读取 / 写入
    # ══════════════════════════════════════════════════

    def _load(self):
        s = self._s

        # 外观
        families = s.get("appearance.ui_font_family", ["Segoe UI"])
        _f = QFont(families[0] if families else "Segoe UI")
        _f.setPointSize(max(1, int(s.get("appearance.ui_font_size", 10))))
        self._w_ui_font.setCurrentFont(_f)

        self._w_ui_size.setValue(s.get("appearance.ui_font_size", 10))

        _f = QFont(s.get("appearance.label_font_family", "Consolas"))
        _f.setPointSize(max(1, int(s.get("appearance.label_font_size", 9))))
        self._w_label_font.setCurrentFont(_f)

        self._w_label_size.setValue(s.get("appearance.label_font_size", 9))

        _f = QFont(s.get("appearance.axis_font_family", "Georgia"))
        _f.setPointSize(max(1, int(s.get("appearance.axis_font_size", 11))))
        self._w_axis_font.setCurrentFont(_f)

        self._w_axis_size.setValue(s.get("appearance.axis_font_size", 11))

        self._w_math_scale.setValue(s.get("appearance.math_scale", 1.0))
        self._w_line_w.setValue(s.get("appearance.default_line_width", 2.0))
        self._w_pt_r.setValue(s.get("appearance.default_point_radius", 4.0))
        self._w_pt_sel_r.setValue(s.get("appearance.selected_point_radius", 6.0))

        # 画布
        self._w_grid_vis.setChecked(s.get("canvas.grid_visible", True))
        self._w_grid_base.setValue(s.get("canvas.grid_base_px", 64.0))
        self._w_grid_major.setValue(s.get("canvas.grid_major_ratio", 5.0))
        self._w_axis_vis.setChecked(s.get("canvas.axis_visible", True))
        self._w_axis_lbl.setChecked(s.get("canvas.axis_labels_visible", True))
        self._w_base_scale.setValue(s.get("canvas.base_scale", 48.0))

        # 动效
        self._w_fx_on.setChecked(s.get("effects.enabled", True))
        self._w_panel_ms.setValue(s.get("effects.panel_toggle_ms", 200))
        self._w_menu_fade.setChecked(s.get("effects.menu_fade", True))
        self._w_dlg_trans.setChecked(s.get("effects.dialog_transition", True))
        self._w_inertia.setChecked(s.get("effects.canvas_inertia", True))
        self._w_friction.setValue(s.get("effects.canvas_friction", 0.825))
        self._w_hover.setChecked(s.get("effects.hover_highlight", True))

        # 交互
        self._w_snap_on.setChecked(s.get("interaction.snap_enabled", True))
        self._w_snap_r.setValue(s.get("interaction.snap_radius_px", 18.0))
        self._w_zoom_spd.setValue(s.get("interaction.zoom_speed", 1.15))
        self._w_touch_tol.setValue(s.get("interaction.touch_hit_tol", 26.0))
        self._w_mouse_tol.setValue(s.get("interaction.mouse_hit_tol", 9.0))
        self._w_long_press.setValue(s.get("interaction.long_press_ms", 500))

        # 工作流
        self._w_undo.setValue(s.get("workflow.undo_limit", 100))
        self._w_autosave.setValue(s.get("workflow.autosave_minutes", 0))

    def _apply(self):
        """从控件读取值 → 批量写入 SettingsStore。"""
        s = self._s
        with s.batch():
            # 外观
            families = list(s.get("appearance.ui_font_family",
                                  ["Segoe UI", "sans-serif"]))
            if families:
                families[0] = self._w_ui_font.currentFont().family()
            s.set("appearance.ui_font_family", families)
            s.set("appearance.ui_font_size",       self._w_ui_size.value())
            s.set("appearance.label_font_family",  self._w_label_font.currentFont().family())
            s.set("appearance.label_font_size",    self._w_label_size.value())
            s.set("appearance.axis_font_family",   self._w_axis_font.currentFont().family())
            s.set("appearance.axis_font_size",     self._w_axis_size.value())
            s.set("appearance.math_scale",         self._w_math_scale.value())
            s.set("appearance.default_line_width", self._w_line_w.value())
            s.set("appearance.default_point_radius",    self._w_pt_r.value())
            s.set("appearance.selected_point_radius",   self._w_pt_sel_r.value())

            # 画布
            s.set("canvas.grid_visible",        self._w_grid_vis.isChecked())
            s.set("canvas.grid_base_px",        self._w_grid_base.value())
            s.set("canvas.grid_major_ratio",    self._w_grid_major.value())
            s.set("canvas.axis_visible",        self._w_axis_vis.isChecked())
            s.set("canvas.axis_labels_visible", self._w_axis_lbl.isChecked())
            s.set("canvas.base_scale",          self._w_base_scale.value())

            # 动效
            s.set("effects.enabled",           self._w_fx_on.isChecked())
            s.set("effects.panel_toggle_ms",    self._w_panel_ms.value())
            s.set("effects.menu_fade",          self._w_menu_fade.isChecked())
            s.set("effects.dialog_transition",  self._w_dlg_trans.isChecked())
            s.set("effects.canvas_inertia",     self._w_inertia.isChecked())
            s.set("effects.canvas_friction",    self._w_friction.value())
            s.set("effects.hover_highlight",    self._w_hover.isChecked())

            # 交互
            s.set("interaction.snap_enabled",    self._w_snap_on.isChecked())
            s.set("interaction.snap_radius_px",  self._w_snap_r.value())
            s.set("interaction.zoom_speed",      self._w_zoom_spd.value())
            s.set("interaction.touch_hit_tol",   self._w_touch_tol.value())
            s.set("interaction.mouse_hit_tol",   self._w_mouse_tol.value())
            s.set("interaction.long_press_ms",   self._w_long_press.value())

            # 工作流
            s.set("workflow.undo_limit",        self._w_undo.value())
            s.set("workflow.autosave_minutes",  self._w_autosave.value())

    # ══════════════════════════════════════════════════
    #  按钮槽
    # ══════════════════════════════════════════════════

    def _on_apply(self):
        self._apply()

    def _on_ok(self):
        self._apply()
        self.accept()

    def _on_reset(self):
        self._s.reset()          # 发射 changed("*")
        self._load()             # 刷新控件到默认值