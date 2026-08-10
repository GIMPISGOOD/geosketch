"""统一对象属性面板 (v2 - 优化布局与主题适配)。"""

from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from geo.points import AbstractPoint, FreePoint, PointOnObject
from media.base import MediaObject
from ui import theme


class PropertyPanel(QWidget):
    """统一对象属性面板。"""

    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.canvas = canvas
        self.setObjectName("propertyPanel")
        self.setFixedWidth(310)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(8)

        # 标题区
        self.title = QLabel("属性")
        self.title.setObjectName("panelTitle")
        self.type_label = QLabel("")
        self.type_label.setObjectName("panelSubtitle")
        self.type_label.setWordWrap(True)

        outer.addWidget(self.title)
        outer.addWidget(self.type_label)

        # 分割线
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFixedHeight(1)
        line.setStyleSheet(f"background-color: {theme.PANEL_BORDER.name()}; border: none; margin: 4px 0;")
        outer.addWidget(line)

        # 滚动区 (修复 Pylance 报错：重命名为 scroll_area)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.content = QWidget()
        self.form = QVBoxLayout(self.content)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(10)

        self.scroll_area.setWidget(self.content)
        outer.addWidget(self.scroll_area, 1)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._do_refresh)

        canvas.doc.changed.connect(self.refresh)
        theme.bus.changed.connect(self._on_theme_changed)

        self.hide()

    def _on_theme_changed(self, *_):
        """主题切换时强制刷新样式。"""
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def refresh(self):
        self._timer.start()

    def reposition(self):
        x = max(10, self.canvas.width() - self.width() - 16)
        y = 14
        self.move(x, y)
        self.setMaximumHeight(max(240, self.canvas.height() - 110))

    def _clear_form(self):
        """安全清理表单 (修复 Pylance 空指针警告)。"""
        while self.form.count():
            item = self.form.takeAt(0)
            if item is None:
                continue
            
            # 1. 尝试获取直接子控件
            w = item.widget()
            if w is not None:
                w.deleteLater()
                continue

            # 2. 如果是嵌套布局，递归清理
            sub_layout = item.layout()
            if sub_layout is not None:
                while sub_layout.count():
                    sub_item = sub_layout.takeAt(0)
                    if sub_item is not None:
                        sub_w = sub_item.widget()
                        # ★ 修复：将结果存入局部变量再判空，消除 Pylance 警告
                        if sub_w is not None:
                            sub_w.deleteLater()

    def _add_section(self, title):
        lbl = QLabel(title)
        lbl.setStyleSheet(f"color: {theme.ACCENT.name()}; font-weight: bold; font-size: 12px; margin-top: 6px;")
        self.form.addWidget(lbl)

    def _add_row(self, label_text, widget):
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setFixedWidth(76)
        label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        label.setStyleSheet(f"color: {theme.SUBINK.name()}; font-size: 12px;")
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
        edit = QLineEdit(str(text))
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
        btn.setFixedHeight(24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        def paint():
            btn.setStyleSheet(
                f"background:{color.name()};"
                f"border:1px solid {theme.PANEL_BORDER.name()};"
                f"border-radius:4px;"
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
            "FreePoint": "自由点", "PointOnObject": "吸附点", "IntersectPoint": "交点",
            "DivisionPoint": "等分点", "Segment": "线段", "Circle": "圆",
            "ExprCircle": "表达式圆", "ExprSegment": "表达式线段", "ExprAngle": "表达式角度",
            "ExprPoint": "表达式点", "Line": "直线", "Ray": "射线", "RegularPolygon": "正多边形",
            "Ellipse": "椭圆", "CubicBezier": "贝塞尔曲线", "FunctionCurve": "函数曲线",
            "ChainFill": "链式填充", "TextObject": "文本", "ScriptButtonObject": "脚本按钮",
            "TableObject": "表格", "PieChartObject": "饼图", "BarChartObject": "柱状图",
            "ImageObject": "图片", "InkStroke": "墨迹", "Measure": "度量",
            "AngleMeasure": "角度", "RatioMeasure": "比例", "TransformPoint": "变换点",
            "IterPoint": "迭代点",
        }
        return cn.get(name, name)

    def _build_single(self, obj: Any) -> None:
        doc = self.canvas.doc
        tn = type(obj).__name__

        self._add_section("基础")
        self._add_row("名称", self._make_line(getattr(obj, "name", ""), lambda t: doc.rename_object(obj, t)))
        self._add_row("可见", self._make_check(getattr(obj, "visible", True), lambda v: self._set_visible([obj], v)))
        
        self._add_buttons([
            ("删除", lambda: doc.remove(obj)),
            ("置顶", lambda: self._reorder([obj], True)),
            ("置底", lambda: self._reorder([obj], False)),
        ])

        if isinstance(obj, FreePoint):
            self._add_section("坐标")
            self._add_row("X", self._make_spin(obj.x, -1e6, 1e6, 3, lambda v: self._set_point_coord(obj, "x", v)))
            self._add_row("Y", self._make_spin(obj.y, -1e6, 1e6, 3, lambda v: self._set_point_coord(obj, "y", v)))
        elif isinstance(obj, PointOnObject):
            self._add_section("参数")
            self._add_row("t", self._make_spin(obj.t, 0.0, 1.0, 4, lambda v: self._set_attr_and_recompute(obj, "t", v)))
        elif isinstance(obj, MediaObject):
            self._add_section("布局")
            self._add_row("X", self._make_spin(obj.x, -1e6, 1e6, 3, lambda v: self._set_attr_and_changed(obj, "x", v)))
            self._add_row("Y", self._make_spin(obj.y, -1e6, 1e6, 3, lambda v: self._set_attr_and_changed(obj, "y", v)))
            self._add_row("宽度", self._make_spin(obj.width, 0.1, 1000.0, 3, lambda v: self._set_attr_and_changed(obj, "width", v)))
            self._add_row("高度", self._make_spin(obj.height, 0.1, 1000.0, 3, lambda v: self._set_attr_and_changed(obj, "height", v)))
            if hasattr(obj, "rotation"):
                self._add_row("旋转", self._make_spin(getattr(obj, "rotation", 0.0), 0.0, 360.0, 1, lambda v: self._set_attr_and_changed(obj, "rotation", v)))

        # ★ 修复：全部使用 getattr 绕过 Pylance 对特定子类属性的误报
        if tn == "ScriptButtonObject":
            self._add_section("按钮样式")
            self._add_row("文字", self._make_line(getattr(obj, "text", ""), lambda t: self._set_attr_and_changed(obj, "text", t)))
            self._add_row("背景", self._make_color_button(QColor(getattr(obj, "color", "#1971c2")), lambda c: self._set_attr_and_changed(obj, "color", c.name())))
            self._add_row("字色", self._make_color_button(QColor(getattr(obj, "text_color", "#ffffff")), lambda c: self._set_attr_and_changed(obj, "text_color", c.name())))
            
            # 安全获取并调用方法
            run_fn = getattr(obj, "run", None)
            edit_fn = getattr(obj, "edit", None)
            btns = []
            if callable(run_fn):
                btns.append(("▶ 运行", lambda: run_fn(self.canvas)))
            if callable(edit_fn):
                btns.append(("✎ 编辑", lambda: edit_fn(self.canvas)))
            if btns:
                self._add_buttons(btns)

        elif tn == "TextObject":
            self._add_section("文本样式")
            self._add_row("内容", self._make_line(getattr(obj, "text", ""), lambda t: self._set_attr_and_changed(obj, "text", t)))
            self._add_row("颜色", self._make_color_button(QColor(getattr(obj, "color", "#1f2937")), lambda c: self._set_attr_and_changed(obj, "color", c.name())))
            self._add_row("字号", self._make_spin(getattr(obj, "size", 16), 6, 200, 0, lambda v: self._set_attr_and_changed(obj, "size", int(v))))

        elif tn == "FunctionCurve":
            self._add_section("函数")
            self._add_row("表达式", self._make_line(getattr(obj, "expr", ""), lambda t: self._set_function_curve_expr(obj, "expr", t)))
            if getattr(obj, "kind", "") == "parametric":
                self._add_row("Y 表达式", self._make_line(getattr(obj, "expr2", ""), lambda t: self._set_function_curve_expr(obj, "expr2", t)))
            self._add_row("颜色", self._make_color_button(QColor(getattr(obj, "color", "#1971c2")), lambda c: self._set_function_curve_color(obj, c)))

        elif tn in ("ExprSegment", "ExprAngle", "ExprCircle"):
            self._add_section("约束")
            self._add_row("表达式", self._make_line(getattr(obj, "expr", ""), lambda t: self._set_expr(obj, t)))

        self._add_section("依赖")
        # 使用 getattr 防止 Pylance 对 parents/children 报错
        parents = getattr(obj, "parents", [])
        children = getattr(obj, "children", [])
        self._add_row("关系", QLabel(f"{len(parents)} 父 / {len(children)} 子"))
        self._add_buttons([
            ("选父", lambda: self._select_related(obj, "parents")),
            ("选子", lambda: self._select_related(obj, "children")),
        ])

    # ================= 提交逻辑 =================
    def _set_visible(self, objs, visible):
        self._doc_action(lambda: [setattr(o, "visible", bool(visible)) for o in objs])

    def _reorder(self, objs, front):
        def doit():
            if front:
                for o in objs:
                    if o in self.canvas.doc.objects:
                        self.canvas.doc.objects.remove(o)
                        self.canvas.doc.objects.append(o)
            else:
                for o in reversed(objs):
                    if o in self.canvas.doc.objects:
                        self.canvas.doc.objects.remove(o)
                        self.canvas.doc.objects.insert(0, o)
        self._doc_action(doit)

    def _select_related(self, obj, mode):
        self.canvas.doc.set_selection(list(obj.parents) if mode == "parents" else list(obj.children))

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
        self._doc_action(lambda: setattr(obj, name, value))

    def _set_expr(self, obj, text):
        def doit():
            # ★ 修复：使用 setattr 动态设置属性，消除 Pylance 对 FreePoint 缺少 expr 属性的误报
            setattr(obj, "expr", text)
            self.canvas.doc.refresh_variables()

        self._doc_action(doit)

    def _set_function_curve_expr(self, obj, field, text):
        def doit():
            setattr(obj, field, text)
            if hasattr(obj, "invalidate_cache"): obj.invalidate_cache()
        self._doc_action(doit)

    def _set_function_curve_color(self, obj, color):
        def doit():
            obj.color = color.name()
            if hasattr(obj, "invalidate_cache"): obj.invalidate_cache()
        self._doc_action(doit)