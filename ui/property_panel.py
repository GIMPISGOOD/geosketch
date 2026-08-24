"""统一对象属性面板 (v4 - 主题适配修复)。"""
from __future__ import annotations
from typing import Any, Callable
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


class PropertyPanel(QWidget):
    """统一对象属性面板，支持折叠/展开，跟随主题切换。"""

    def __init__(self, canvas: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.canvas = canvas
        self.setObjectName("propertyPanel")
        self._collapsed: bool = False
        self._expanded_width: int = 300
        self._collapsed_width: int = 36

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        # ── 展开态 ──
        self._expanded_widget = QWidget()
        self._expanded_layout = QVBoxLayout(self._expanded_widget)
        self._expanded_layout.setContentsMargins(12, 10, 12, 10)
        self._expanded_layout.setSpacing(6)

        head = QHBoxLayout()
        self.title = QLabel("属性")
        self.title.setObjectName("panelTitle")
        head.addWidget(self.title)
        head.addStretch(1)

        self._collapse_btn = QPushButton("»")
        self._collapse_btn.setObjectName("collapseBtn")
        self._collapse_btn.setFixedSize(22, 22)
        self._collapse_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._collapse_btn.setToolTip("折叠属性面板")
        self._collapse_btn.clicked.connect(self._toggle_collapse)
        head.addWidget(self._collapse_btn)
        self._expanded_layout.addLayout(head)

        self.type_label = QLabel("")
        self.type_label.setObjectName("panelSubtitle")
        self.type_label.setWordWrap(True)
        self._expanded_layout.addWidget(self.type_label)

        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._content = QWidget()
        self.form = QVBoxLayout(self._content)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setSpacing(10)
        self._scroll_area.setWidget(self._content)
        self._expanded_layout.addWidget(self._scroll_area, 1)

        # ── 折叠态 ──
        self._collapsed_widget = QWidget()
        self._collapsed_layout = QVBoxLayout(self._collapsed_widget)
        self._collapsed_layout.setContentsMargins(4, 10, 4, 10)
        self._collapsed_layout.setSpacing(8)

        self._expand_btn = QPushButton("«")
        self._expand_btn.setObjectName("expandBtn")
        self._expand_btn.setFixedSize(24, 24)
        self._expand_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._expand_btn.setToolTip("展开属性面板")
        self._expand_btn.clicked.connect(self._toggle_collapse)
        self._collapsed_layout.addWidget(
            self._expand_btn, 0, Qt.AlignmentFlag.AlignHCenter
        )

        self._collapsed_label = QLabel("属\n性")
        self._collapsed_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._collapsed_label.setStyleSheet(
            "font-size: 11px; letter-spacing: 2px; background: transparent;"
        )
        self._collapsed_layout.addWidget(self._collapsed_label)
        self._collapsed_layout.addStretch(1)

        self._outer.addWidget(self._expanded_widget)
        self._outer.addWidget(self._collapsed_widget)
        self._collapsed_widget.hide()
        self.setFixedWidth(self._expanded_width)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(80)
        self._timer.timeout.connect(self._do_refresh)
        self.canvas.doc.changed.connect(self._schedule_refresh)

        # ★ 主题切换时重新应用样式
        theme.bus.changed.connect(self._on_theme_changed)

        self.hide()

    # ──────────────────────────────────────────────────────
    #  主题切换
    # ──────────────────────────────────────────────────────
    def _on_theme_changed(self, *_: Any) -> None:
        """主题切换时：强制重新解析样式表并刷新。"""
        # 清除旧样式缓存
        self.setStyleSheet("")
        # unpolish + polish 强制重新计算
        self.style().unpolish(self)
        self.style().polish(self)
        # 递归刷新所有子控件
        for child in self.findChildren(QWidget):
            child.style().unpolish(child)
            child.style().polish(child)
        self.update()

    # ──────────────────────────────────────────────────────
    #  折叠 / 展开
    # ──────────────────────────────────────────────────────
    def _toggle_collapse(self) -> None:
        self._collapsed = not self._collapsed
        if self._collapsed:
            self._expanded_widget.hide()
            self._collapsed_widget.show()
            self.setFixedWidth(self._collapsed_width)
            self.setFixedHeight(90)
        else:
            self._collapsed_widget.hide()
            self._expanded_widget.show()
            self.setFixedWidth(self._expanded_width)
            self.setMinimumHeight(0)
            self.setMaximumHeight(16777215)
            target_h = max(320, min(600, self.canvas.height() - 80))
            self.resize(self._expanded_width, target_h)
            self.reposition()
            self.raise_()

    def reposition(self) -> None:
        x = max(10, self.canvas.width() - self.width() - 16)
        y = 14
        self.move(x, y)
        if not self._collapsed:
            self.setMaximumHeight(max(240, self.canvas.height() - 110))

    # ──────────────────────────────────────────────────────
    #  刷新调度
    # ──────────────────────────────────────────────────────
    def _schedule_refresh(self) -> None:
        if not self._collapsed:
            self._timer.start()

    def refresh(self) -> None:
        self._timer.start()

    def _clear_form(self) -> None:
        while self.form.count():
            item = self.form.takeAt(0)
            if item is None:
                continue
            w = item.widget()
            if w is not None:
                w.deleteLater()
                continue
            sub_layout = item.layout()
            if sub_layout is not None:
                while sub_layout.count():
                    sub_item = sub_layout.takeAt(0)
                    if sub_item is not None:
                        sub_w = sub_item.widget()
                        if sub_w is not None:
                            sub_w.deleteLater()

    def _add_section(self, title_text: str) -> None:
        lbl = QLabel(title_text)
        lbl.setStyleSheet(
            f"color: {theme.ACCENT.name()}; font-weight: bold; "
            f"font-size: 12px; margin-top: 6px; background: transparent;"
        )
        self.form.addWidget(lbl)

    def _add_row(self, label_text: str, widget: QWidget) -> None:
        row = QHBoxLayout()
        row.setSpacing(8)
        label = QLabel(label_text)
        label.setFixedWidth(76)
        label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        label.setStyleSheet(
            f"color: {theme.SUBINK.name()}; font-size: 12px; background: transparent;"
        )
        row.addWidget(label)
        row.addWidget(widget, 1)
        self.form.addLayout(row)

    def _add_buttons(self, buttons: list[tuple[str, Callable[[], Any]]]) -> None:
        row = QHBoxLayout()
        row.setSpacing(6)
        for text, slot in buttons:
            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(slot)
            row.addWidget(btn)
        row.addStretch(1)
        self.form.addLayout(row)

    def _make_line(self, text: Any, on_commit: Callable[[str], Any]) -> QLineEdit:
        edit = QLineEdit(str(text))
        edit.editingFinished.connect(lambda: on_commit(edit.text().strip()))
        return edit

    def _make_spin(
        self, value: Any, vmin: float, vmax: float,
        decimals: int, on_commit: Callable[[float], Any],
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(vmin, vmax)
        spin.setDecimals(decimals)
        spin.setValue(float(value))
        spin.setKeyboardTracking(False)
        spin.editingFinished.connect(lambda: on_commit(spin.value()))
        return spin

    def _make_check(self, checked: Any, on_toggle: Callable[[bool], Any]) -> QCheckBox:
        check = QCheckBox()
        check.setChecked(bool(checked))
        check.toggled.connect(on_toggle)
        return check

    def _make_combo(
        self, items: list[str], current: Any,
        on_change: Callable[[str], Any],
    ) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        if str(current) in items:
            combo.setCurrentText(str(current))
        combo.currentTextChanged.connect(on_change)
        return combo

    def _make_color_button(
        self, color: QColor, on_commit: Callable[[QColor], Any]
    ) -> QPushButton:
        btn = QPushButton()
        btn.setFixedHeight(24)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        local_color = QColor(color)

        def paint() -> None:
            btn.setStyleSheet(
                f"background:{local_color.name()};"
                f"border:1px solid {theme.PANEL_BORDER.name()};"
                f"border-radius:4px;"
            )

        def pick() -> None:
            nonlocal local_color
            c = QColorDialog.getColor(local_color, self, "选择颜色")
            if c.isValid():
                local_color = c
                paint()
                on_commit(c)

        btn.clicked.connect(pick)
        paint()
        return btn

    # ──────────────────────────────────────────────────────
    #  文档操作
    # ──────────────────────────────────────────────────────
    def _doc_action(self, fn: Callable[[], Any]) -> None:
        doc = self.canvas.doc
        doc.begin_action()
        try:
            fn()
        finally:
            doc.end_action()
        doc.changed.emit()

    # ──────────────────────────────────────────────────────
    #  刷新逻辑
    # ──────────────────────────────────────────────────────
    def _do_refresh(self) -> None:
        if self._collapsed:
            return
        doc = self.canvas.doc
        selected = [o for o in doc.objects if o.selected and o in doc.objects]
        if not selected:
            self.hide()
            return
        self._clear_form()
        if len(selected) == 1:
            obj = selected[0]
            self.title.setText(
                getattr(obj, "name", "") or self._get_type_label(obj)
            )
            self.type_label.setText(self._get_type_label(obj))
            self._build_single(obj)
        else:
            self.title.setText(f"已选 {len(selected)} 个对象")
            self.type_label.setText("批量操作")
            self._build_multi(selected)
        self.form.addStretch(1)
        self.reposition()
        if not self._collapsed:
            self.show()
            self.raise_()

    def _get_type_label(self, obj: Any) -> str:
        name = type(obj).__name__
        cn: dict[str, str] = {
            "FreePoint": "自由点",
            "PointOnObject": "吸附点",
            "IntersectPoint": "交点",
            "DivisionPoint": "等分点",
            "PolygonVertex": "多边形顶点",
            "Incenter": "内心",
            "Centroid": "重心",
            "ExprPoint": "表达式点",
            "TransformPoint": "变换点",
            "IterPoint": "迭代点",
            "CircleAxisPoint": "圆轴点",
            "Segment": "线段",
            "Line": "直线",
            "Ray": "射线",
            "ParallelLine": "平行线",
            "PerpLine": "垂线",
            "AngleBisector": "角平分线",
            "AngleDivLine": "等分角线",
            "PerpBisector": "中垂线",
            "DirectedLine": "方向直线",
            "Circle": "圆",
            "ThreePointCircle": "过三点圆",
            "ExprCircle": "表达式圆",
            "InvertedCircle": "反演圆",
            "Ellipse": "椭圆",
            "RegularPolygon": "正多边形",
            "CubicBezier": "贝塞尔曲线",
            "FunctionCurve": "函数曲线",
            "ImplicitCurve": "隐函数曲线",
            "ChainFill": "链式填充",
            "TextObject": "文本",
            "ScriptButtonObject": "脚本按钮",
            "TableObject": "表格",
            "PieChartObject": "饼图",
            "BarChartObject": "柱状图",
            "LineChartObject": "折线图",
            "DonutChartObject": "环形图",
            "ImageObject": "图片",
            "InkStroke": "墨迹",
            "Measure": "度量",
            "AngleMeasure": "角度",
            "RatioMeasure": "比例",
            "RegionMeasure": "区域度量",
            "ExprSegment": "表达式线段",
            "ExprAngle": "表达式角度",
            "TransformDriver": "变换驱动器",
        }
        return cn.get(name, name)

    def _build_multi(self, objs: list[Any]) -> None:
        self._add_section("批量操作")
        visible_all = all(getattr(o, "visible", True) for o in objs)
        self._add_buttons([
            (
                "隐藏" if visible_all else "显示",
                lambda: self._set_visible(objs, not visible_all),
            ),
            ("删除", self.canvas.doc.remove_selected),
            ("置顶", lambda: self._reorder(objs, True)),
            ("置底", lambda: self._reorder(objs, False)),
        ])

    def _build_single(self, obj: Any) -> None:
        doc = self.canvas.doc
        tn = type(obj).__name__

        self._add_section("基础")
        self._add_row(
            "名称",
            self._make_line(
                getattr(obj, "name", ""),
                lambda t: doc.rename_object(obj, t),
            ),
        )
        self._add_row(
            "可见",
            self._make_check(
                getattr(obj, "visible", True),
                lambda v: self._set_visible([obj], v),
            ),
        )
        self._add_buttons([
            ("删除", lambda: doc.remove(obj)),
            ("置顶", lambda: self._reorder([obj], True)),
            ("置底", lambda: self._reorder([obj], False)),
        ])

        if isinstance(obj, FreePoint):
            self._add_section("坐标")
            self._add_row(
                "X",
                self._make_spin(
                    obj.x, -1e6, 1e6, 3,
                    lambda v: self._set_point_coord(obj, "x", v),
                ),
            )
            self._add_row(
                "Y",
                self._make_spin(
                    obj.y, -1e6, 1e6, 3,
                    lambda v: self._set_point_coord(obj, "y", v),
                ),
            )
        elif isinstance(obj, PointOnObject):
            self._add_section("参数")
            self._add_row(
                "t",
                self._make_spin(
                    obj.t, 0.0, 1.0, 4,
                    lambda v: self._set_attr_and_recompute(obj, "t", v),
                ),
            )
        elif isinstance(obj, MediaObject):
            self._add_section("布局")
            self._add_row(
                "X",
                self._make_spin(
                    obj.x, -1e6, 1e6, 3,
                    lambda v: self._set_attr_and_changed(obj, "x", v),
                ),
            )
            self._add_row(
                "Y",
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
            if hasattr(obj, "rotation"):
                self._add_row(
                    "旋转",
                    self._make_spin(
                        getattr(obj, "rotation", 0.0),
                        0.0, 360.0, 1,
                        lambda v: self._set_attr_and_changed(obj, "rotation", v),
                    ),
                )

            if tn == "ScriptButtonObject":
                self._add_section("按钮样式")
                self._add_row(
                    "文字",
                    self._make_line(
                        getattr(obj, "text", ""),
                        lambda t: self._set_attr_and_changed(obj, "text", t),
                    ),
                )
                self._add_row(
                    "背景",
                    self._make_color_button(
                        QColor(getattr(obj, "color", "#1971c2")),
                        lambda c: self._set_attr_and_changed(obj, "color", c.name()),
                    ),
                )
                self._add_row(
                    "字色",
                    self._make_color_button(
                        QColor(getattr(obj, "text_color", "#ffffff")),
                        lambda c: self._set_attr_and_changed(
                            obj, "text_color", c.name()
                        ),
                    ),
                )
                run_fn = getattr(obj, "run", None)
                edit_fn = getattr(obj, "edit", None)
                btns: list[tuple[str, Callable[[], Any]]] = []
                if callable(run_fn):
                    btns.append(("▶ 运行", lambda: run_fn(self.canvas)))
                if callable(edit_fn):
                    btns.append(("✎ 编辑", lambda: edit_fn(self.canvas)))
                if btns:
                    self._add_buttons(btns)

            elif tn == "TextObject":
                self._add_section("文本样式")
                self._add_row(
                    "内容",
                    self._make_line(
                        getattr(obj, "text", ""),
                        lambda t: self._set_attr_and_changed(obj, "text", t),
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
                        getattr(obj, "size", 16),
                        6, 200, 0,
                        lambda v: self._set_attr_and_changed(obj, "size", int(v)),
                    ),
                )

        elif tn == "FunctionCurve":
            self._add_section("函数")
            self._add_row(
                "表达式",
                self._make_line(
                    getattr(obj, "expr", ""),
                    lambda t: self._set_function_curve_expr(obj, "expr", t),
                ),
            )
            if getattr(obj, "kind", "") == "parametric":
                self._add_row(
                    "Y 表达式",
                    self._make_line(
                        getattr(obj, "expr2", ""),
                        lambda t: self._set_function_curve_expr(obj, "expr2", t),
                    ),
                )
            self._add_row(
                "颜色",
                self._make_color_button(
                    QColor(getattr(obj, "color", "#1971c2")),
                    lambda c: self._set_function_curve_color(obj, c),
                ),
            )

        elif tn in ("ExprSegment", "ExprAngle", "ExprCircle"):
            self._add_section("约束")
            self._add_row(
                "表达式",
                self._make_line(
                    getattr(obj, "expr", ""),
                    lambda t: self._set_expr(obj, t),
                ),
            )

        self._add_section("依赖")
        parents = getattr(obj, "parents", [])
        children = getattr(obj, "children", [])
        self._add_row(
            "关系", QLabel(f"{len(parents)} 父 / {len(children)} 子")
        )
        self._add_buttons([
            ("选父", lambda: self._select_related(obj, "parents")),
            ("选子", lambda: self._select_related(obj, "children")),
        ])

    # ──────────────────────────────────────────────────────
    #  操作
    # ──────────────────────────────────────────────────────
    def _set_visible(self, objs: list[Any], visible: bool) -> None:
        def doit():
            for o in objs:
                o.visible = bool(visible)
            self.canvas.doc._mutation_count += 1
        self._doc_action(doit)

    def _reorder(self, objs: list[Any], front: bool) -> None:
        def doit() -> None:
            doc_objects = self.canvas.doc.objects
            if front:
                for o in objs:
                    if o in doc_objects:
                        doc_objects.remove(o)
                        doc_objects.append(o)
            else:
                for o in reversed(objs):
                    if o in doc_objects:
                        doc_objects.remove(o)
                        doc_objects.insert(0, o)
            self.canvas.doc._mutation_count += 1
        self._doc_action(doit)

    def _select_related(self, obj: Any, mode: str) -> None:
        related = list(obj.parents) if mode == "parents" else list(obj.children)
        self.canvas.doc.set_selection(related)

    def _set_point_coord(self, obj: Any, axis: str, value: float) -> None:
        def doit() -> None:
            setattr(obj, axis, float(value))
            self.canvas.doc.recompute_from(obj)
        self._doc_action(doit)

    def _set_attr_and_recompute(self, obj: Any, name: str, value: Any) -> None:
        def doit() -> None:
            setattr(obj, name, value)
            self.canvas.doc.recompute_from(obj)
        self._doc_action(doit)

    def _set_attr_and_changed(self, obj: Any, name: str, value: Any) -> None:
        self._doc_action(lambda: setattr(obj, name, value))

    def _set_expr(self, obj: Any, text: str) -> None:
        def doit() -> None:
            setattr(obj, "expr", text)
            self.canvas.doc.refresh_variables()
        self._doc_action(doit)

    def _set_function_curve_expr(self, obj: Any, field: str, text: str) -> None:
        def doit() -> None:
            setattr(obj, field, text)
            if hasattr(obj, "invalidate_cache"):
                obj.invalidate_cache()
        self._doc_action(doit)

    def _set_function_curve_color(self, obj: Any, color: QColor) -> None:
        def doit() -> None:
            obj.color = color.name()
            if hasattr(obj, "invalidate_cache"):
                obj.invalidate_cache()
        self._doc_action(doit)