from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (QApplication, QFileDialog, QLabel,
                               QMainWindow, QStatusBar)
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QInputDialog, QMessageBox
from ui.variable_widgets import VariableWizard, VariableRangeDialog

import geo            # noqa: F401
import tools          # noqa: F401
import plugins        # noqa: F401
from core.document import Document
from core.registry import TOOL_REGISTRY
from ui import theme
from ui.canvas import Canvas
from ui.icons import build_tool_icon
from ui.variable_widgets import VariableWizard
from plugins.expr_tools import ExprSegmentTool, ExprAngleTool


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoSketch · 几何画板")
        self.resize(1240, 780)

        self.doc = Document()
        self.canvas = Canvas(self.doc)
        self.setCentralWidget(self.canvas)

        self._actions: dict[type, QAction] = {}
        self._create_tool_actions()
        self._build_menubar()
        self._build_statusbar()

        self._build_var_menu()

        theme.bus.changed.connect(self._on_theme_changed)
        self.canvas.set_tool(TOOL_REGISTRY[0]["cls"]())

    def _create_tool_actions(self) -> None:
        for spec in TOOL_REGISTRY:
            act = QAction(spec["name"], self, checkable=True)
            act.setIcon(build_tool_icon(spec))
            if spec["shortcut"]:
                act.setShortcut(QKeySequence(spec["shortcut"]))
            act.setStatusTip(spec["hint"])
            act.triggered.connect(
                lambda _=False, s=spec: self.canvas.set_tool(s["cls"]()))
            self.addAction(act)
            self._actions[spec["cls"]] = act
        self.canvas.tool_activated.connect(self._sync_actions)

    def _build_var_menu(self):
        mb = self.menuBar()
        top = mb.addMenu("变量与函数(&B)")
        self._var_submenu = top.addMenu("变量(&A)")
        self._var_submenu.aboutToShow.connect(self._rebuild_var_submenu)
        func = top.addMenu("函数(&F)")          # 预留，后续实现
        func.setEnabled(False)

    def _rebuild_var_submenu(self):
        m = self._var_submenu
        m.clear()
        act = QAction("新建变量…", self)
        act.triggered.connect(self._new_variable)
        m.addAction(act)
        m.addSeparator()

        store = self.doc.vars
        if store.names():
            for name in store.names():
                var = store.get_var(name)
                # 每个变量一个子菜单：修改值 / 修改范围 / 删除
                assert var is not None
                sub = m.addMenu(f"{name} = {var.value:.3f}")
                a_val = QAction("修改值…", self)
                a_val.triggered.connect(lambda _=False, n=name: self._edit_variable(n))
                sub.addAction(a_val)
                a_rng = QAction(f"修改范围…（当前 {var.vmin:g} ~ {var.vmax:g}）", self)
                a_rng.triggered.connect(lambda _=False, n=name: self._edit_variable_range(n))
                sub.addAction(a_rng)
                a_del = QAction("删除变量", self)
                a_del.triggered.connect(lambda _=False, n=name: self._delete_variable(n))
                sub.addAction(a_del)
        else:
            e = QAction("（暂无变量）", self); e.setEnabled(False)
            m.addAction(e)

        m.addSeparator()
        s = QAction("表达式线段…", self)
        s.triggered.connect(lambda: self.canvas.set_tool(ExprSegmentTool()))
        m.addAction(s)
        g = QAction("表达式角度…", self)
        g.triggered.connect(lambda: self.canvas.set_tool(ExprAngleTool()))
        m.addAction(g)

    def _new_variable(self):
        wiz = VariableWizard(self)
        if wiz.exec():
            name, val, lo, hi = wiz.result_data()
            self.doc.vars.define(name, val, lo, hi)
            self.doc.refresh_variables()
            self.canvas.var_panel.refresh()

    def _edit_variable_range(self, name):
        var = self.doc.vars.get_var(name)
        if var is None:
            return
        dlg = VariableRangeDialog(name, var.vmin, var.vmax, self)
        if dlg.exec():
            lo, hi = dlg.result_data()
            self.doc.vars.set_range(name, lo, hi)
            self.doc.refresh_variables()
            self.canvas.var_panel.refresh()      # 滑杆按新范围重建

    def _delete_variable(self, name):
        reply = QMessageBox.question(
            self, "删除变量",
            f"确定删除变量「{name}」吗？\n引用它的表达式线段/角度将随之失效。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.doc.vars.delete(name)
            self.doc.refresh_variables()
            self.canvas.var_panel.refresh()

    def _edit_variable(self, name):
        var = self.doc.vars.get_var(name)
        if var is None:
            return
        val, ok = QInputDialog.getDouble(
            self, "修改变量", f"{name} =", var.value, var.vmin, var.vmax, 3)
        if ok:
            self.doc.vars.set(name, val)
            self.doc.refresh_variables()
            self.canvas.var_panel.refresh()

    def _sync_actions(self, tool) -> None:
        for cls, act in self._actions.items():
            act.setChecked(type(tool) is cls)

    def _build_menubar(self) -> None:
        mb = self.menuBar()

        fm = mb.addMenu("文件(&F)")
        for text, slot, key in (
            ("新建(&N)", self.doc.clear, QKeySequence.StandardKey.New),
            ("打开(&O)…", self._open, QKeySequence.StandardKey.Open),
            ("保存(&S)…", self._save, QKeySequence.StandardKey.Save),
        ):
            act = QAction(text, self)
            act.setShortcut(key)
            act.triggered.connect(slot)
            fm.addAction(act)
        export_act = QAction("导出图像(&E)…", self)
        export_act.setShortcut(QKeySequence("Ctrl+E"))
        export_act.triggered.connect(self._export_image)
        fm.addAction(export_act)
        fm.addSeparator()
        quit_act = QAction("退出(&X)", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        fm.addAction(quit_act)

        # 工具菜单：插件工具
        tm = mb.addMenu("工具(&T)")
        plugin_specs = [s for s in TOOL_REGISTRY if s.get("panel") == "menu"]
        for spec in plugin_specs:
            tm.addAction(self._actions[spec["cls"]])
        if not plugin_specs:
            e = tm.addAction("（暂无插件工具）"); e.setEnabled(False)

                # 视图菜单：撤销 / 重做
        vm = mb.addMenu("视图(&W)")
        self._undo_act = QAction("撤销(&U)", self)
        self._undo_act.setShortcut(QKeySequence.StandardKey.Undo)      # Ctrl+Z
        self._undo_act.triggered.connect(self.doc.undo)
        vm.addAction(self._undo_act)
        self._redo_act = QAction("重做(&R)", self)
        self._redo_act.setShortcut(QKeySequence.StandardKey.Redo)      # Ctrl+Shift+Z
        self._redo_act.triggered.connect(self.doc.redo)
        vm.addAction(self._redo_act)
        self.doc.history_changed.connect(self._update_history_actions)
        self._update_history_actions()

        # 主题菜单：互斥单选
        thm = mb.addMenu("主题(&M)")
        tgroup = QActionGroup(self)
        tgroup.setExclusive(True)
        for name in theme.theme_names():
            act = QAction(name, self, checkable=True)
            act.setChecked(name == theme.active_name())
            act.triggered.connect(lambda _=False, n=name: theme.set_theme(n))
            tgroup.addAction(act)
            thm.addAction(act)

    def _on_theme_changed(self, name) -> None:
        app = QApplication.instance()
        assert isinstance(app, QApplication)
        
        app.setStyleSheet(theme.app_stylesheet())
        
        for spec in TOOL_REGISTRY:                    # 重建工具图标配色
            self._actions[spec["cls"]].setIcon(build_tool_icon(spec))
        self.canvas.refresh_theme()

    def _export_image(self) -> None:
        from ui.export_wizard import ExportWizard
        ExportWizard(self.canvas, self).exec()

    def _build_statusbar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)
        self._hint_label = QLabel("就绪")
        self._coord_label = QLabel("(    0.00 ,    0.00 )")
        self._coord_label.setFont(theme.LABEL_FONT)
        self._count_label = QLabel("0 个对象")
        sb.addWidget(self._hint_label, 1)
        sb.addPermanentWidget(self._count_label)
        sb.addPermanentWidget(self._coord_label)
        self.canvas.cursor_info.connect(self._coord_label.setText)
        self.canvas.tool_changed.connect(self._hint_label.setText)
        self.doc.changed.connect(
            lambda: self._count_label.setText(f"{len(self.doc.objects)} 个对象"))

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存", "sketch.json", "GeoSketch 文件 (*.json)")
        if path:
            self.doc.save(path)

    def _update_history_actions(self) -> None:
        self._undo_act.setEnabled(self.doc.can_undo)
        self._redo_act.setEnabled(self.doc.can_redo)

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开", "", "GeoSketch 文件 (*.json)")
        if path:
            self.doc.load(path)