"""统一对象属性面板。

选中对象后显示在画布右侧，支持常见属性的查看与编辑：
- 名称
- 可见性
- 父对象 / 子对象
- 点坐标
- 吸附点参数 t
- 媒体对象位置、宽高、旋转
- 文本对象内容、颜色、字号
- 脚本按钮文字、颜色、脚本
- 表达式约束对象表达式
- 函数曲线表达式与颜色
- 填充对象样式
- 墨迹颜色、宽度、透明度
"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from geo.points import AbstractPoint, FreePoint, PointOnObject
from media.base import MediaObject
from ui import theme


def _css_color(color: QColor) -> str:
    try:
        return color.name(QColor.NameFormat.HexArgb)
    except Exception:
        return color.name()


class PropertyPanel(QWidget):
    """统一对象属性面板。"""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setObjectName("propertyPanel")
        self.setFixedWidth(290)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 10, 12, 10)
        outer.setSpacing(8)

        self.title = QLabel("属性")
        self.type_label = QLabel("")
        self.type_label.setWordWrap(True)

        # ★ 修复：重命名为 self.scroll_area，避免与 QWidget 内置的 scroll() 方法冲突
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.form = QVBoxLayout(self.content)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(6)

        self.scroll_area.setWidget(self.content)

        outer.addWidget(self.title)
        outer.addWidget(self.type_label)
        outer.addWidget(self.scroll_area, 1)

        self.scroll_area.setStyleSheet("background:transparent;border:none;")
        self.content.setStyleSheet("background:transparent;")

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._do_refresh)

        canvas.doc.changed.connect(self.refresh)
        theme.bus.changed.connect(lambda *_: self._apply_style())

        self._apply_style()
        self.hide()

    # ================= 基础 =================

    def refresh(self):
        self._timer.start()

    def reposition(self):
        x = max(10, self.canvas.width() - self.width() - 16)
        y = 14
        self.move(x, y)
        self.setMaximumHeight(max(220, self.canvas.height() - 110))

    def _apply_style(self):
        self.setStyleSheet(
            f"""
            #propertyPanel {{
                background: {_css_color(theme.PANEL_BG)};
                border: 1px solid {_css_color(theme.PANEL_BORDER)};
                border-radius: 14px;
            }}
            #propertyPanel QLabel {{
                color: {theme.INK.name()};
                background: transparent;
            }}
            #propertyPanel QLineEdit,
            #propertyPanel QDoubleSpinBox,
            #propertyPanel QComboBox {{
                background: {_css_color(theme.WINDOW_BG)};
                color: {theme.INK.name()};
                border: 1px solid {_css_color(theme.PANEL_BORDER)};
                border-radius: 6px;
                padding: 2px 5px;
            }}
            #propertyPanel QCheckBox {{
                color: {theme.INK.name()};
                background: transparent;
            }}
            #propertyPanel QPushButton {{
                background: {theme.ACCENT.name()};
                color: #ffffff;
                border: none;
                border-radius: 7px;
                padding: 4px 8px;
                font-weight: 600;
            }}
            #propertyPanel QPushButton:hover {{
                background: {theme.SELECTED.name()};
            }}
            """
        )

    def _clear_form(self):
        while self.form.count():
            item = self.form.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _add_row(self, label_text, widget):
        row = QHBoxLayout()
        row.setSpacing(6)
        label = QLabel(label_text)
        label.setFixedWidth(72)
        row.addWidget(label)
        row.addWidget(widget, 1)
        self.form.addLayout(row)

    def _add_buttons(self, buttons):
        row = QHBoxLayout()
        row.setSpacing(6)
        for text, slot in buttons:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        self.form.addLayout(row)

    def _make_line(self, text, on_commit):
        edit = QLineEdit(text)
        edit.editingFinished.connect(lambda: on_commit(edit.text().strip()))
        return edit

    def _make_spin(self, value, vmin, vmax, decimals, on_commit):
        spin = QDoubleSpinBox()
        spin.setRange(vmin, vmax)
        spin.setDecimals(decimals)
        spin.setValue(float(value))
        spin.setKeyboardTracking(False)
        spin.editingFinished.connect(lambda: on_commit(spin.value()))
        return spin

    def _make_check(self, checked, on_toggle):
        check = QCheckBox()
        check.setChecked(bool(checked))
        check.toggled.connect(on_toggle)
        return check

    def _make_combo(self, items, current, on_change):
        combo = QComboBox()
        combo.addItems(items)
        if current in items:
            combo.setCurrentText(current)
        combo.currentTextChanged.connect(on_change)
        return combo

    def _make_color_button(self, color, on_commit):
        btn = QPushButton()
        btn.setFixedHeight(22)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def paint():
            btn.setStyleSheet(
                f"background:{color.name()};"
                f"border:1px solid rgba(0,0,0,0.30);"
                f"border-radius:5px;"
            )

        def pick():
            nonlocal color
            c = QColorDialog.getColor(color, self, "选择颜色")
            if c.isValid():
                color = c
                paint()
                on_commit(c)

        btn.clicked.connect(pick)
        paint()
        return btn

    def _doc_action(self, fn):
        doc = self.canvas.doc
        doc.begin_action()
        try:
            fn()
        finally:
            doc.end_action()
        doc.changed.emit()

    # ================= 刷新 =================

    def _do_refresh(self):
        doc = self.canvas.doc
        selected = [o for o in doc.objects if o.selected and o in doc.objects]

        if not selected:
            self.hide()
            return

        self._clear_form()

        if len(selected) == 1:
            obj = selected[0]
            self.title.setText(getattr(obj, "name", "") or self._type_label(obj))
            self.type_label.setText(self._type_label(obj))
            self._build_single(obj)
        else:
            self.title.setText(f"已选 {len(selected)} 个对象")
            self.type_label.setText("批量操作")
            self._build_multi(selected)

        self.form.addStretch(1)
        self.reposition()
        self.show()
        self.raise_()

    def _type_label(self, obj):
        name = type(obj).__name__
        cn = {
            "FreePoint": "自由点",
            "PointOnObject": "吸附点",
            "IntersectPoint": "交点",
            "DivisionPoint": "等分点",
            "Segment": "线段",
            "Circle": "圆",
            "ExprCircle": "表达式圆",
            "ExprSegment": "表达式线段",
            "ExprAngle": "表达式角度",
            "ExprPoint": "表达式点",
            "Line": "直线",
            "Ray": "射线",
            "RegularPolygon": "正多边形",
            "Ellipse": "椭圆",
            "CubicBezier": "贝塞尔曲线",
            "FunctionCurve": "函数曲线",
            "ChainFill": "链式填充",
            "TextObject": "文本",
            "ScriptButtonObject": "脚本按钮",
            "TableObject": "表格",
            "PieChartObject": "饼图",
            "BarChartObject": "柱状图",
            "ImageObject": "图片",
            "InkStroke": "墨迹",
            "Measure": "度量",
            "AngleMeasure": "角度",
            "RatioMeasure": "比例",
            "TransformPoint": "变换点",
            "IterPoint": "迭代点",
        }
        return cn.get(name, name)

    # ================= 多选 =================

    def _build_multi(self, objs):
        self._add_row(
            "数量",
            QLabel(str(len(objs))),
        )

        visible_all = all(getattr(o, "visible", True) for o in objs)

        self._add_buttons(
            [
                ("隐藏" if visible_all else "显示",
                 lambda: self._set_visible(objs, not visible_all)),
                ("删除", self.canvas.doc.remove_selected),
            ]
        )

        self._add_buttons(
            [
                ("置顶", lambda: self._reorder(objs, True)),
                ("置底", lambda: self._reorder(objs, False)),
            ]
        )

        self._add_buttons(
            [
                ("复制", self.canvas.doc.copy_selection),
                ("剪切", self.canvas.doc.cut_selection),
                ("复制一份", self._duplicate_selected),
            ]
        )

    # ================= 单选 =================

    def _build_single(self, obj):
        doc = self.canvas.doc

        # ---------- 通用属性 ----------
        self._add_row(
            "名称",
            self._make_line(
                getattr(obj, "name", "") or "",
                lambda text: doc.rename_object(obj, text),
            ),
        )

        self._add_row(
            "可见",
            self._make_check(
                getattr(obj, "visible", True),
                lambda v: self._set_visible([obj], v),
            ),
        )

        self._add_buttons(
            [
                ("删除", lambda: doc.remove(obj)),
                ("置顶", lambda: self._reorder([obj], True)),
                ("置底", lambda: self._reorder([obj], False)),
            ]
        )

        # ---------- 几何专属 ----------
        tn = type(obj).__name__

        if isinstance(obj, FreePoint):
            self._add_row(
                "x",
                self._make_spin(
                    obj.x, -1e6, 1e6, 3,
                    lambda v: self._set_point_coord(obj, "x", v),
                ),
            )
            self._add_row(
                "y",
                self._make_spin(
                    obj.y, -1e6, 1e6, 3,
                    lambda v: self._set_point_coord(obj, "y", v),
                ),
            )

        elif isinstance(obj, PointOnObject):
            self._add_row(
                "参数 t",
                self._make_spin(
                    obj.t, 0.0, 1.0, 4,
                    lambda v: self._set_attr_and_recompute(obj, "t", v),
                ),
            )

        elif isinstance(obj, AbstractPoint):
            if hasattr(obj, "x") and hasattr(obj, "y"):
                self._add_row("x", QLabel(f"{obj.x:.3f}"))
                self._add_row("y", QLabel(f"{obj.y:.3f}"))

        if isinstance(obj, MediaObject):
            self._build_media(obj)

        if tn == "ScriptButtonObject":
            self._build_script_button(obj)

        if tn == "TextObject":
            self._build_text_object(obj)

        if tn == "FunctionCurve":
            self._build_function_curve(obj)

        if tn in ("ExprSegment", "ExprAngle", "ExprCircle"):
            self._add_row(
                "表达式",
                self._make_line(
                    getattr(obj, "expr", ""),
                    lambda text: self._set_expr(obj, text),
                ),
            )

        if tn == "ExprPoint":
            self._add_row(
                "x 表达式",
                self._make_line(
                    getattr(obj, "expr_x", ""),
                    lambda text: self._set_attr_and_refresh_variables(obj, "expr_x", text),
                ),
            )
            self._add_row(
                "y 表达式",
                self._make_line(
                    getattr(obj, "expr_y", ""),
                    lambda text: self._set_attr_and_refresh_variables(obj, "expr_y", text),
                ),
            )

        if tn == "ChainFill":
            self._build_chain_fill(obj)

        if tn == "InkStroke":
            self._build_ink_stroke(obj)

        # ---------- 依赖关系 ----------
        self._add_row(
            "依赖",
            QLabel(f"{len(obj.parents)} 个父对象，{len(obj.children)} 个子对象"),
        )

        self._add_buttons(
            [
                ("选择父对象", lambda: self._select_related(obj, "parents")),
                ("选择子对象", lambda: self._select_related(obj, "children")),
            ]
        )

    # ================= 媒体对象 =================

    def _build_media(self, obj):
        self._add_row(
            "x",
            self._make_spin(
                obj.x, -1e6, 1e6, 3,
                lambda v: self._set_attr_and_changed(obj, "x", v),
            ),
        )
        self._add_row(
            "y",
            self._make_spin(
                obj.y, -1e6, 1e6, 3,
                lambda v: self._set_attr_and_changed(obj, "y", v),
            ),
        )
        self._add_row(
            "宽度",
            self._make_spin(
                obj.width, 0.1, 1000.0, 3,
                lambda v: self._set_attr_and_changed(obj, "width", v),
            ),
        )
        self._add_row(
            "高度",
            self._make_spin(
                obj.height, 0.1, 1000.0, 3,
                lambda v: self._set_attr_and_changed(obj, "height", v),
            ),
        )

        if getattr(obj, "rotatable", False) or hasattr(obj, "rotation"):
            self._add_row(
                "旋转角",
                self._make_spin(
                    getattr(obj, "rotation", 0.0), 0.0, 360.0, 1,
                    lambda v: self._set_attr_and_changed(obj, "rotation", v),
                ),
            )

        if hasattr(obj, "edit") and callable(obj.edit):
            self._add_buttons([("编辑对象", lambda: obj.edit(self.canvas))])

    # ================= 脚本按钮 =================

    def _build_script_button(self, obj):
        self._add_row(
            "按钮文字",
            self._make_line(
                getattr(obj, "text", ""),
                lambda text: self._set_attr_and_changed(obj, "text", text),
            ),
        )

        self._add_row(
            "背景色",
            self._make_color_button(
                QColor(getattr(obj, "color", "#1971c2")),
                lambda c: self._set_attr_and_changed(obj, "color", c.name()),
            ),
        )

        self._add_row(
            "文字颜色",
            self._make_color_button(
                QColor(getattr(obj, "text_color", "#ffffff")),
                lambda c: self._set_attr_and_changed(obj, "text_color", c.name()),
            ),
        )

        self._add_buttons(
            [
                ("运行", lambda: obj.run(self.canvas)),
                ("简单编辑", lambda: self._simple_edit_script_button(obj)),
                ("高级编辑", lambda: obj.edit(self.canvas)),
            ]
        )

    def _simple_edit_script_button(self, obj):
        from media.script_button_wizard import ScriptButtonWizard

        dlg = ScriptButtonWizard(self.canvas, obj, parent=self.canvas)
        if dlg.exec():
            def doit():
                dlg.apply_to(obj)

            self._doc_action(doit)

    # ================= 文本对象 =================

    def _build_text_object(self, obj):
        self._add_row(
            "文本",
            self._make_line(
                getattr(obj, "text", ""),
                lambda text: self._set_attr_and_changed(obj, "text", text),
            ),
        )

        self._add_row(
            "颜色",
            self._make_color_button(
                QColor(getattr(obj, "color", "#1f2937")),
                lambda c: self._set_attr_and_changed(obj, "color", c.name()),
            ),
        )

        self._add_row(
            "字号",
            self._make_spin(
                getattr(obj, "size", 16), 6, 200, 0,
                lambda v: self._set_attr_and_changed(obj, "size", int(v)),
            ),
        )

    # ================= 函数曲线 =================

    def _build_function_curve(self, obj):
        self._add_row("类型", QLabel(getattr(obj, "kind", "explicit")))

        self._add_row(
            "表达式",
            self._make_line(
                getattr(obj, "expr", ""),
                lambda text: self._set_function_curve_expr(obj, "expr", text),
            ),
        )

        if getattr(obj, "kind", "") == "parametric":
            self._add_row(
                "表达式 2",
                self._make_line(
                    getattr(obj, "expr2", ""),
                    lambda text: self._set_function_curve_expr(obj, "expr2", text),
                ),
            )

        self._add_row(
            "颜色",
            self._make_color_button(
                QColor(getattr(obj, "color", "#1971c2")),
                lambda c: self._set_function_curve_color(obj, c),
            ),
        )

    def _set_function_curve_expr(self, obj, field, text):
        def doit():
            setattr(obj, field, text)
            if hasattr(obj, "invalidate_cache"):
                obj.invalidate_cache()

        self._doc_action(doit)

    def _set_function_curve_color(self, obj, color):
        def doit():
            obj.color = color.name()
            if hasattr(obj, "invalidate_cache"):
                obj.invalidate_cache()

        self._doc_action(doit)

    # ================= 链式填充 =================

    def _build_chain_fill(self, obj):
        style = getattr(obj, "style", None)
        if style is None:
            return

        self._add_row(
            "颜色",
            self._make_color_button(
                QColor(style.color),
                lambda c: self._set_fill_style(obj, color=c),
            ),
        )

        self._add_row(
            "透明度",
            self._make_spin(
                style.opacity * 100.0, 0.0, 100.0, 0,
                lambda v: self._set_fill_style(obj, opacity=v / 100.0),
            ),
        )

        self._add_row(
            "样式",
            self._make_combo(
                ["solid", "gradient", "hatch", "crosshatch"],
                style.kind,
                lambda text: self._set_fill_style(obj, kind=text),
            ),
        )

        self._add_row(
            "填充规则",
            self._make_combo(
                ["evenodd", "winding"],
                getattr(style, "fill_rule", "evenodd"),
                lambda text: self._set_fill_style(obj, fill_rule=text),
            ),
        )

    def _set_fill_style(self, obj, **kwargs):
        def doit():
            style = getattr(obj, "style", None)
            if style is None:
                return
            for k, v in kwargs.items():
                setattr(style, k, v)

        self._doc_action(doit)

    # ================= 墨迹 =================

    def _build_ink_stroke(self, obj):
        self._add_row(
            "颜色",
            self._make_color_button(
                QColor(getattr(obj, "color", "#222222")),
                lambda c: self._set_attr_and_changed(obj, "color", c.name()),
            ),
        )

        self._add_row(
            "宽度",
            self._make_spin(
                getattr(obj, "width", 2.5), 0.5, 50.0, 1,
                lambda v: self._set_attr_and_changed(obj, "width", v),
            ),
        )

        self._add_row(
            "透明度",
            self._make_spin(
                getattr(obj, "opacity", 1.0) * 100.0, 0.0, 100.0, 0,
                lambda v: self._set_attr_and_changed(obj, "opacity", v / 100.0),
            ),
        )

        self._add_row(
            "笔型",
            self._make_combo(
                ["pen", "highlighter", "pencil"],
                getattr(obj, "mode", "pen"),
                lambda text: self._set_attr_and_changed(obj, "mode", text),
            ),
        )

    # ================= 通用提交 =================

    def _set_visible(self, objs, visible):
        def doit():
            for o in objs:
                o.visible = bool(visible)

        self._doc_action(doit)

    def _reorder(self, objs, front):
        def doit():
            doc = self.canvas.doc
            if front:
                for o in objs:
                    if o in doc.objects:
                        doc.objects.remove(o)
                        doc.objects.append(o)
            else:
                for o in reversed(objs):
                    if o in doc.objects:
                        doc.objects.remove(o)
                        doc.objects.insert(0, o)

        self._doc_action(doit)

    def _duplicate_selected(self):
        self.canvas.doc.copy_selection()
        self.canvas.doc.paste()

    def _select_related(self, obj, mode):
        related = []
        if mode == "parents":
            related = list(obj.parents)
        else:
            related = list(obj.children)
        self.canvas.doc.set_selection(related)

    def _set_point_coord(self, obj, axis, value):
        def doit():
            setattr(obj, axis, float(value))
            self.canvas.doc.recompute_from(obj)

        self._doc_action(doit)

    def _set_attr_and_recompute(self, obj, name, value):
        def doit():
            setattr(obj, name, value)
            self.canvas.doc.recompute_from(obj)

        self._doc_action(doit)

    def _set_attr_and_changed(self, obj, name, value):
        def doit():
            setattr(obj, name, value)

        self._doc_action(doit)

    def _set_expr(self, obj, text):
        def doit():
            obj.expr = text
            self.canvas.doc.refresh_variables()

        self._doc_action(doit)

    def _set_attr_and_refresh_variables(self, obj, name, text):
        def doit():
            setattr(obj, name, text)
            self.canvas.doc.refresh_variables()

        self._doc_action(doit)