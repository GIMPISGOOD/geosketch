from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QMenu, QInputDialog, QColorDialog, QDialog, QDialogButtonBox,
                               QFormLayout, QLineEdit, QPushButton, QSpinBox, QVBoxLayout,
                               QDoubleSpinBox, QComboBox, QMessageBox)
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
        metrics = _get_available_metrics(selected)
        if metrics:
            menu.addSeparator()
            if len(metrics) == 1:
                info = metrics[0]
                menu.addAction(
                    f"📏 绑定“{info['label']}”到变量…",
                    lambda _=False, i=info: bind_metric_variable(canvas, i)
                )
            else:
                bind_menu = menu.addMenu("📏 绑定到变量")
                for info in metrics:
                    bind_menu.addAction(
                        info["label"],
                        lambda _=False, i=info: bind_metric_variable(canvas, i)
                    )

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
        canvas.doc._mutation_count += 1

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

        canvas.doc._mutation_count += 1

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
def _get_available_metrics(objs):
    """检查选中对象可提供哪些度量绑定。"""
    if len(objs) != 1:
        return []

    obj = objs[0]

    from core.variables import available_metrics, compute_metric, binding_display_name

    out = []
    for metric, label in available_metrics(obj):
        val = compute_metric(obj, metric)
        if val is None:
            continue

        kind = getattr(obj, "kind", "")
        if metric == "degrees" or kind == "angle":
            value_text = f"{val:.1f}°"
        else:
            value_text = f"{val:.3f}"

        var_name = binding_display_name(obj, metric)

        out.append(
            {
                "label": f"{var_name} = {value_text}",
                "metric": metric,
                "obj": obj,
                "var_name": var_name,
            }
        )

    return out


class BindVariableDialog(QDialog):
    """度量绑定对话框：可以绑定到已有变量，也可以新建变量。"""

    def __init__(self, metric_label, initial_val, store, parent=None):
        super().__init__(parent)
        self.setWindowTitle("绑定到变量")
        self.setMinimumWidth(380)

        layout = QFormLayout(self)

        self.target = QComboBox()
        self.target.addItem("新建变量…")
        self.target.addItems(store.names())
        layout.addRow("目标变量:", self.target)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("输入新变量名…")
        layout.addRow("新变量名:", self.name_edit)

        self.step_spin = QDoubleSpinBox()
        self.step_spin.setRange(0.001, 1000.0)
        self.step_spin.setDecimals(3)
        self.step_spin.setValue(0.1)
        self.step_spin.setSingleStep(0.1)
        layout.addRow("步长:", self.step_spin)

        pad = max(5.0, abs(initial_val) * 0.5 + 1.0)

        self.vmin_spin = QDoubleSpinBox()
        self.vmin_spin.setRange(-1e6, 1e6)
        self.vmin_spin.setDecimals(3)
        self.vmin_spin.setValue(initial_val - pad)
        layout.addRow("最小值:", self.vmin_spin)

        self.vmax_spin = QDoubleSpinBox()
        self.vmax_spin.setRange(-1e6, 1e6)
        self.vmax_spin.setDecimals(3)
        self.vmax_spin.setValue(initial_val + pad)
        layout.addRow("最大值:", self.vmax_spin)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

        self.target.currentIndexChanged.connect(self._sync)
        self._sync()

    def _sync(self):
        is_new = self.target.currentIndex() == 0
        self.name_edit.setEnabled(is_new)
        self.step_spin.setEnabled(is_new)
        self.vmin_spin.setEnabled(is_new)
        self.vmax_spin.setEnabled(is_new)

    def get_data(self):
        if self.target.currentIndex() == 0:
            return {
                "new": True,
                "name": self.name_edit.text().strip(),
                "step": float(self.step_spin.value()),
                "vmin": float(self.vmin_spin.value()),
                "vmax": float(self.vmax_spin.value()),
            }
        return {
            "new": False,
            "name": self.target.currentText(),
        }


def bind_metric_variable(canvas, metric_info):
    """把 metric_info 对应的度量绑定到已有变量或新变量。"""
    from core.variables import is_valid_name, compute_metric

    obj = metric_info["obj"]
    metric = metric_info["metric"]
    store = canvas.doc.vars

    initial = compute_metric(obj, metric)
    if initial is None:
        QMessageBox.warning(canvas, "提示", "当前度量值不可用。")
        return

    dlg = BindVariableDialog(metric_info["label"], initial, store, canvas)

    base = metric_info.get("var_name") or "度量"

    default_name = f"{base}{len(store.names()) + 1}"
    i = 2
    while store.get_var(default_name) is not None:
        default_name = f"{base}{i}"
        i += 1

    dlg.name_edit.setText(default_name)

    if not dlg.exec():
        return

    data = dlg.get_data()
    binding = {"obj_id": obj.id, "metric": metric}

    if data["new"]:
        name = data["name"]
        if not name or not is_valid_name(name):
            QMessageBox.warning(canvas, "提示", "变量名不合法。")
            return
        if store.get_var(name) is not None:
            QMessageBox.warning(canvas, "提示", "变量名已存在。")
            return

        store.define(
            name=name,
            value=initial,
            vmin=data["vmin"],
            vmax=data["vmax"],
            expr="",
            step=data["step"],
            binding=binding,
        )
    else:
        name = data["name"]
        var = store.get_var(name)
        if var is None:
            return

        var.expr = ""
        var.binding = binding
        store.version += 1
        store.changed.emit()

    store.update_bindings(canvas.doc)
    canvas.doc.refresh_variables()