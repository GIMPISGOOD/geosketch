"""偏好设置对话框。

五页分类：外观 / 画布 / 动效 / 交互 / 工作流。
所有值从 ``SettingsStore`` 读取，写入时通过 ``set()`` 触发 ``changed`` 信号。

对外契约：
    SettingsDialog(settings: SettingsStore, parent: QWidget | None) → QDialog
"""
from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
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
    QPlainTextEdit,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

_PAGES = [
    ("🎨 ", "外观"),
    ("📐 ", "画布"),
    ("✨ ", "动效"),
    ("🖱 ", "交互"),
    ("⚙ ", "工作流"),
    ("🤖 ", "AI"),
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
        self._build_ai() 
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
    def _build_ai(self):
        f = self._new_page()

        # 总开关
        self._w_ai_enabled = QCheckBox("启用 AI 辅助")
        f.addRow(self._w_ai_enabled)

        # 提供者
        self._w_ai_provider = QComboBox()
        self._w_ai_provider.addItems(["本地模型", "远程 API"])
        self._w_ai_provider.currentIndexChanged.connect(
            self._on_ai_provider_changed)
        f.addRow("提供者", self._w_ai_provider)

        # ── 本地模型区 ──
        from PySide6.QtWidgets import QGroupBox, QLineEdit, QFileDialog
        local_box = QGroupBox("本地模型")
        lf = QFormLayout(local_box)

        dir_row = QHBoxLayout()
        self._w_ai_model_dir = QLineEdit()
        self._w_ai_model_dir.setPlaceholderText("models")
        _browse = QPushButton("浏览…")
        _browse.clicked.connect(self._on_ai_browse)
        dir_row.addWidget(self._w_ai_model_dir, 1)
        dir_row.addWidget(_browse)
        lf.addRow("模型目录", dir_row)

        self._w_ai_model_file = QComboBox()
        self._w_ai_model_file.addItem("自动选择", "")
        lf.addRow("模型文件", self._w_ai_model_file)

        self._w_ai_detect_lbl = QLabel("")
        lf.addRow("检测状态", self._w_ai_detect_lbl)

        f.addRow(local_box)
        self._ai_local_box = local_box

        # ── 远程 API 区 ──
        remote_box = QGroupBox("远程 API")
        rf = QFormLayout(remote_box)

        self._w_ai_api_url = QLineEdit()
        self._w_ai_api_url.setPlaceholderText(
            "https://api.openai.com/v1/chat/completions")
        rf.addRow("API 地址", self._w_ai_api_url)

        self._w_ai_api_key = QLineEdit()
        self._w_ai_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self._w_ai_api_key.setPlaceholderText("sk-…")
        rf.addRow("API Key", self._w_ai_api_key)

        self._w_ai_api_model = QLineEdit()
        self._w_ai_api_model.setPlaceholderText("gpt-4o-mini")
        rf.addRow("模型名称", self._w_ai_api_model)

        test_row = QHBoxLayout()
        self._w_ai_test_btn = QPushButton("测试连接")
        self._w_ai_test_btn.clicked.connect(self._on_ai_test)
        self._w_ai_test_lbl = QLabel("")
        test_row.addWidget(self._w_ai_test_btn)
        test_row.addWidget(self._w_ai_test_lbl, 1)
        rf.addRow("连接测试", test_row)

        f.addRow(remote_box)
        self._ai_remote_box = remote_box

        # ── 通用设置 ──
        self._w_ai_usage = QComboBox()
        self._w_ai_usage.addItems(["补全 + 生成", "仅补全", "仅生成"])
        f.addRow("用途", self._w_ai_usage)

        self._w_ai_prompt = QPlainTextEdit()
        self._w_ai_prompt.setMaximumHeight(60)
        f.addRow("系统提示词", self._w_ai_prompt)

        self._w_ai_max_tok = QSpinBox()
        self._w_ai_max_tok.setRange(16, 2048)
        self._w_ai_max_tok.setSingleStep(16)
        f.addRow("最大 Token", self._w_ai_max_tok)

        self._w_ai_temp = QDoubleSpinBox()
        self._w_ai_temp.setRange(0.0, 2.0)
        self._w_ai_temp.setSingleStep(0.05)
        self._w_ai_temp.setDecimals(2)
        f.addRow("采样温度", self._w_ai_temp)

        self._w_ai_timeout = QSpinBox()
        self._w_ai_timeout.setRange(1000, 30000)
        self._w_ai_timeout.setSingleStep(500)
        self._w_ai_timeout.setSuffix(" ms")
        f.addRow("超时", self._w_ai_timeout)

    # ── AI 辅助方法 ──

    def _on_ai_provider_changed(self, index):
        is_local = (index == 0)
        self._ai_local_box.setVisible(is_local)
        self._ai_remote_box.setVisible(not is_local)
        self._scan_ai_models()

    def _on_ai_browse(self):
        from PySide6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "选择模型目录")
        if d:
            self._w_ai_model_dir.setText(d)
            self._scan_ai_models()

    def _scan_ai_models(self):
        """扫描模型目录，更新检测状态和启用开关。"""
        try:
            from core.ai_service import AIService
            # 临时构造一个 AIService 仅用于扫描
            svc = AIService(self._s)
            provider_idx = self._w_ai_provider.currentIndex()

            if provider_idx == 0:  # 本地
                models = svc.discover_models()
                self._w_ai_model_file.clear()
                self._w_ai_model_file.addItem("自动选择", "")
                for m in models:
                    self._w_ai_model_file.addItem(m, m)
                if models:
                    self._w_ai_detect_lbl.setText(
                        f"✅ 找到 {len(models)} 个模型")
                    self._w_ai_detect_lbl.setStyleSheet("color: #2f9e44;")
                    self._w_ai_enabled.setEnabled(True)
                else:
                    self._w_ai_detect_lbl.setText("❌ 未找到模型文件")
                    self._w_ai_detect_lbl.setStyleSheet("color: #e03131;")
                    self._w_ai_enabled.setEnabled(False)
                    self._w_ai_enabled.setChecked(False)
            else:  # 远程
                url = self._w_ai_api_url.text().strip()
                key = self._w_ai_api_key.text().strip()
                if url and key:
                    self._w_ai_detect_lbl.setText("✅ 配置完整")
                    self._w_ai_detect_lbl.setStyleSheet("color: #2f9e44;")
                    self._w_ai_enabled.setEnabled(True)
                else:
                    self._w_ai_detect_lbl.setText("❌ 请填写 API 地址和 Key")
                    self._w_ai_detect_lbl.setStyleSheet("color: #e03131;")
                    self._w_ai_enabled.setEnabled(False)
                    self._w_ai_enabled.setChecked(False)
        except Exception:
            self._w_ai_detect_lbl.setText("❌ 检测失败")
            self._w_ai_detect_lbl.setStyleSheet("color: #e03131;")
            self._w_ai_enabled.setEnabled(False)
            self._w_ai_enabled.setChecked(False)

    def _on_ai_test(self):
        """测试远程 API 连接（后台线程）。"""
        url = self._w_ai_api_url.text().strip()
        key = self._w_ai_api_key.text().strip()
        model = self._w_ai_api_model.text().strip()
        if not url:
            self._w_ai_test_lbl.setText("❌ 请先填写 API 地址")
            self._w_ai_test_lbl.setStyleSheet("color: #e03131;")
            return
        self._w_ai_test_lbl.setText("测试中…")
        self._w_ai_test_btn.setEnabled(False)
        QApplication.processEvents()
        try:
            import requests as req
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            }
            payload = {
                "model": model or "gpt-4o-mini",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 1,
            }
            r = req.post(url, json=payload, headers=headers, timeout=5)
            r.raise_for_status()
            self._w_ai_test_lbl.setText("✅ 连接成功")
            self._w_ai_test_lbl.setStyleSheet("color: #2f9e44;")
        except ImportError:
            self._w_ai_test_lbl.setText("❌ requests 未安装")
            self._w_ai_test_lbl.setStyleSheet("color: #e03131;")
        except Exception as e:
            self._w_ai_test_lbl.setText(f"❌ {e}")
            self._w_ai_test_lbl.setStyleSheet("color: #e03131;")
        finally:
            self._w_ai_test_btn.setEnabled(True)
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
        
        # AI
        self._w_ai_enabled.setChecked(s.get("ai.enabled", False))
        provider = s.get("ai.provider", "local")
        self._w_ai_provider.setCurrentIndex(
            0 if provider == "local" else 1)
        self._w_ai_model_dir.setText(s.get("ai.model_dir", "models"))
        self._w_ai_api_url.setText(s.get("ai.api_url", ""))
        self._w_ai_api_key.setText(s.get("ai.api_key", ""))
        self._w_ai_api_model.setText(s.get("ai.api_model", ""))
        usage = s.get("ai.usage", "both")
        self._w_ai_usage.setCurrentIndex(
            {"both": 0, "complete": 1, "generate": 2}.get(usage, 0))
        self._w_ai_prompt.setPlainText(
            s.get("ai.system_prompt", ""))
        self._w_ai_max_tok.setValue(s.get("ai.max_tokens", 256))
        self._w_ai_temp.setValue(s.get("ai.temperature", 0.2))
        self._w_ai_timeout.setValue(s.get("ai.timeout_ms", 5000))
        self._on_ai_provider_changed(
            self._w_ai_provider.currentIndex())
        self._scan_ai_models()
        
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
        # AI
            s.set("ai.enabled",      self._w_ai_enabled.isChecked())
            s.set("ai.provider",
              "local" if self._w_ai_provider.currentIndex() == 0
              else "remote")
            s.set("ai.model_dir",    self._w_ai_model_dir.text())
            s.set("ai.model_file",
              self._w_ai_model_file.currentData() or "")
            s.set("ai.api_url",      self._w_ai_api_url.text())
            s.set("ai.api_key",      self._w_ai_api_key.text())
            s.set("ai.api_model",    self._w_ai_api_model.text())
            usage_map = {0: "both", 1: "complete", 2: "generate"}
            s.set("ai.usage",
              usage_map.get(self._w_ai_usage.currentIndex(), "both"))
            s.set("ai.system_prompt",
              self._w_ai_prompt.toPlainText())
            s.set("ai.max_tokens",   self._w_ai_max_tok.value())
            s.set("ai.temperature",  self._w_ai_temp.value())
            s.set("ai.timeout_ms",   self._w_ai_timeout.value())
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