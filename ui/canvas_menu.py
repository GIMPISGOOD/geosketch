from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QMenu, QInputDialog, QColorDialog, QDialog, QDialogButtonBox, 
                               QFormLayout, QLineEdit, QPushButton, QSpinBox, QVBoxLayout, QDoubleSpinBox)
from media.base import MediaObject
from media.script_button import ScriptButtonObject

def show_context_menu(canvas, ev):
    local_pos = QPointF(ev.pos())
    hit = canvas.pick(local_pos)
    selected = [o for o in canvas.doc.objects if o.selected]

    if hit is not None:
        if hit not in selected:
            canvas.doc.set_selection([hit])
            selected = [hit]

    menu = QMenu(canvas)
    if hit is not None:
        if isinstance(hit, ScriptButtonObject):
            menu.addAction("▶ 运行脚本", lambda: hit.run(canvas))
            menu.addAction("🧩 简单编辑脚本", lambda: simple_edit_script_button(canvas, hit))
            menu.addAction("✎ 高级编辑脚本", lambda: hit.edit(canvas))
            menu.addSeparator()
        if type(hit).__name__ == "TextObject":
            menu.addAction("✎ 编辑文本", lambda: edit_text_object(canvas, hit))
            menu.addSeparator()
        if isinstance(hit, MediaObject) and hasattr(hit, "edit") and callable(hit.edit):
            menu.addAction("✎ 编辑对象", lambda: hit.edit(canvas))
            menu.addSeparator()
        if type(hit).__name__ in ("FunctionCurve", "ImplicitCurve"):
            menu.addAction("✎ 编辑函数", lambda: edit_function_object(canvas, hit))
            menu.addSeparator()

    if selected:
        menu.addAction("重命名…", lambda: rename_objects(canvas, selected))
        visible_all = all(getattr(o, "visible", True) for o in selected)
        menu.addAction(
            "隐藏" if visible_all else "显示",
            lambda: set_visible(canvas, selected, not visible_all),
        )
        menu.addSeparator()
        menu.addAction("复制", canvas.doc.copy_selection)
        menu.addAction("剪切", canvas.doc.cut_selection)
        menu.addAction("复制一份", lambda: duplicate_selected(canvas))
        menu.addSeparator()
        menu.addAction("置顶", lambda: reorder_objects(canvas, selected, True))
        menu.addAction("置底", lambda: reorder_objects(canvas, selected, False))
        menu.addSeparator()
        menu.addAction("选择父对象", lambda: select_related(canvas, selected, "parents"))
        menu.addAction("选择子对象", lambda: select_related(canvas, selected, "children"))
        menu.addSeparator()
        # ★ 度量绑定变量创建
        metric_info = _get_metric_info(selected)
        if metric_info:
            menu.addSeparator()
            menu.addAction(
                f"📏 创建 {metric_info['label']} 变量...",
                lambda: create_metric_variable(canvas, selected, metric_info)
            )
        menu.addAction("删除", canvas.doc.remove_selected)

    if getattr(canvas.doc, "_clipboard", None):
        if not menu.isEmpty():
            menu.addSeparator()
        menu.addAction("粘贴", lambda: canvas.doc.paste())

    if not menu.isEmpty():
        menu.exec(ev.globalPos())
        return True
    return False

def edit_function_object(canvas, obj):
    from ui.formula_editor import FormulaEditor
    dlg = FormulaEditor(canvas, obj, canvas)
    if dlg.exec():
        dlg.build_function()
        canvas.doc.changed.emit()

def doc_action(canvas, fn):
    canvas.doc.begin_action()
    try:
        fn()
    finally:
        canvas.doc.end_action()
    canvas.doc.changed.emit()

def rename_objects(canvas, objs):
    if len(objs) != 1:
        return
    obj = objs[0]
    old_name = getattr(obj, "name", "") or ""
    name, ok = QInputDialog.getText(canvas, "重命名对象", "对象名称：", text=old_name)
    if ok and name.strip():
        canvas.doc.rename_object(obj, name.strip())

def set_visible(canvas, objs, visible):
    def doit():
        for o in objs:
            o.visible = bool(visible)
    doc_action(canvas, doit)

def duplicate_selected(canvas):
    canvas.doc.copy_selection()
    canvas.doc.paste()

def reorder_objects(canvas, objs, front):
    def doit():
        if front:
            for o in objs:
                if o in canvas.doc.objects:
                    canvas.doc.objects.remove(o)
                    canvas.doc.objects.append(o)
        else:
            for o in reversed(objs):
                if o in canvas.doc.objects:
                    canvas.doc.objects.remove(o)
                    canvas.doc.objects.insert(0, o)
    doc_action(canvas, doit)

def select_related(canvas, objs, mode):
    related = []
    for o in objs:
        if mode == "parents":
            related.extend(o.parents)
        else:
            related.extend(o.children)
    unique = []
    seen = set()
    for o in related:
        if id(o) not in seen:
            seen.add(id(o))
            unique.append(o)
    canvas.doc.set_selection(unique)

def simple_edit_script_button(canvas, obj):
    from media.script_button_wizard import ScriptButtonWizard
    dlg = ScriptButtonWizard(canvas, obj, parent=canvas)
    if dlg.exec():
        def doit():
            dlg.apply_to(obj)
        doc_action(canvas, doit)

def edit_text_object(canvas, obj):
    dlg = QDialog(canvas)
    dlg.setWindowTitle("编辑文本")
    dlg.setMinimumWidth(360)
    layout = QVBoxLayout(dlg)
    form = QFormLayout()
    text_edit = QLineEdit(getattr(obj, "text", ""))
    size_spin = QSpinBox()
    size_spin.setRange(6, 200)
    size_spin.setValue(int(getattr(obj, "size", 16)))
    color_holder = [QColor(getattr(obj, "color", "#1f2937"))]
    color_btn = QPushButton()
    color_btn.setFixedHeight(22)

    def paint_color():
        color_btn.setStyleSheet(
            f"background:{color_holder[0].name()};"
            f"border:1px solid rgba(0,0,0,0.30);"
            f"border-radius:5px;"
        )

    def pick_color():
        c = QColorDialog.getColor(color_holder[0], canvas, "选择文本颜色")
        if c.isValid():
            color_holder[0] = c
            paint_color()

    color_btn.clicked.connect(pick_color)
    paint_color()
    form.addRow("文本内容", text_edit)
    form.addRow("字号", size_spin)
    form.addRow("颜色", color_btn)
    layout.addLayout(form)
    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
    )
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    layout.addWidget(buttons)
    if dlg.exec():
        def doit():
            obj.text = text_edit.text()
            obj.size = int(size_spin.value())
            obj.color = color_holder[0].name()

            # ★ 异步资源预取拦截
            if "[ACG]" in obj.text:
                from ui.canvas_render import trigger_egg
                trigger_egg(canvas)

        doc_action(canvas, doit)

# ============================================================
# 度量绑定变量
# ============================================================
def _get_metric_info(objs):
    """检查选中对象是否支持创建度量变量。"""
    if len(objs) == 1:
        obj = objs[0]
        tn = type(obj).__name__
        if tn == "Segment":
            return {"label": "长度", "metric": "length", "obj": obj}
        if tn in ("Circle", "ExprCircle"):
            return {"label": "半径", "metric": "radius", "obj": obj}
        if tn == "RegularPolygon":
            return {"label": "面积", "metric": "area", "obj": obj}
        if tn == "AngleMeasure":
            return {"label": "角度", "metric": "degrees", "obj": obj}
    return None


class MetricVariableDialog(QDialog):
    """度量变量创建对话框。"""

    def __init__(self, metric_label, initial_val, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"创建 {metric_label} 变量")
        self.setMinimumWidth(320)
        layout = QFormLayout(self)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入变量名...")
        layout.addRow("变量名:", self.name_edit)

        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.001, 1000.0)
        self.step_spin.setDecimals(3)
        self.step_spin.setValue(0.1)
        self.step_spin.setSingleStep(0.1)
        layout.addRow("步长 (Step):", self.step_spin)

        vmin = max(0.0, initial_val - 5.0)
        vmax = initial_val + 5.0

        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(-1e6, 1e6)
        self.vmin_spin.setDecimals(3)
        self.vmin_spin.setValue(vmin)
        layout.addRow("最小值:", self.vmin_spin)

        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(-1e6, 1e6)
        self.vmax_spin.setDecimals(3)
        self.vmax_spin.setValue(vmax)
        layout.addRow("最大值:", self.vmax_spin)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_data(self):
        return (
            self.name_edit.text().strip(),
            self.step_spin.value(),
            self.vmin_spin.value(),
            self.vmax_spin.value(),
        )


def create_metric_variable(canvas, objs, metric_info):
    """创建度量绑定变量。"""
    from core.variables import is_valid_name

    obj = metric_info["obj"]
    metric = metric_info["metric"]
    label = metric_info["label"]

    store = canvas.doc.vars
    initial_val = store._compute_metric(obj, metric)
    if initial_val is None:
        return

    dlg = MetricVariableDialog(label, initial_val, canvas)
    default_name = f"{label[0]}{len(store.names()) + 1}"
    dlg.name_edit.setText(default_name)

    if dlg.exec():
        name, step, vmin, vmax = dlg.get_data()
        if not name or not is_valid_name(name):
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.warning(canvas, "提示", "变量名不合法或已存在。")
            return

        binding = {"obj_id": obj.id, "metric": metric}
        store.define(name, initial_val, vmin, vmax, expr="", step=step, binding=binding)
        store.update_bindings(canvas.doc)
        canvas.doc.refresh_variables()