import datetime
import os

from PySide6.QtGui import QAction, QActionGroup, QFont, QKeySequence
from PySide6.QtCore import Qt , QTimer
from PySide6.QtWidgets import (QApplication, QFileDialog, QLabel,
                               QMainWindow, QStatusBar)
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QInputDialog, QMessageBox
from ui.variable_widgets import VariableWizard, VariableRangeDialog

import geo            # noqa: F401
import tools          # noqa: F401
import plugins        # noqa: F401
import media           # noqa: F401
import transforms     # noqa: F401
from core.document import Document
from core.registry import TOOL_REGISTRY
from ui import theme
from ui.canvas import Canvas
from ui.icons import build_tool_icon
from ui.variable_widgets import VariableWizard
from plugins.expr_tools import ExprSegmentTool, ExprAngleTool
from ui.function_panel import FunctionEditorDock
from ui.settings_dialog import SettingsDialog        # ← 新增

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoSketch · 几何画板")
        self.resize(1240, 780)

        self.doc = Document()
        theme.set_settings(self.doc.settings)   # ← 新增：注入设置到主题模块
        self.canvas = Canvas(self.doc)
        self.setCentralWidget(self.canvas)  
        # ★ 触屏优化：全局启用触摸合成与手势
        self.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)
        # ★ 宏系统
        from core.macro import MacroManager, set_macro_manager

        self.macro_manager = MacroManager(self.doc)
        set_macro_manager(self.macro_manager)
        
        self.function_dock = FunctionEditorDock(self.canvas, self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.function_dock)
        self.doc.changed.connect(self.function_dock.refresh)
        self.function_dock.refresh()
        self._help_gallery = None
        self._actions: dict[type, QAction] = {}
        self._create_tool_actions()
        self._build_menubar()
        self._build_statusbar()
        self._build_var_menu()
        self._build_advanced_menu() 
        self._build_constraint_menu()# ★ 宏与脚本库移入高级菜单
        self._build_animation_menu()
        self._physics_menu = None
        self._build_physics_menu()
        theme.bus.changed.connect(self._on_theme_changed)
        self.canvas.set_tool(TOOL_REGISTRY[0]["cls"]())
        self.canvas.update_snow_state()
        self._current_path: str | None = None       # 跟踪当前文件路径（自动保存用）
        self._autosave_timer = QTimer(self)
        self._autosave_timer.timeout.connect(self._do_autosave)
        self.doc.settings.changed.connect(self._on_settings_changed)
        self._apply_ui_font()
        self._restart_autosave()

        from ui import anim_helpers                      # ← 新增
        anim_helpers.set_settings(self.doc.settings)  
                
    def _build_constraint_menu(self):
        """原生构建约束菜单。"""
        try:
            from core.registry import TOOL_REGISTRY
            mb = self.menuBar()
            cm = mb.addMenu("约束(&C)")
            constraint_specs = sorted(
                [s for s in TOOL_REGISTRY if s.get("panel") == "constraint"],
                key=lambda s: s.get("order", 99)
            )
            for spec in constraint_specs:
                cm.addAction(self._actions[spec["cls"]])
            if not constraint_specs:
                e = cm.addAction("（暂无约束工具）")
                e.setEnabled(False)
            for i, action in enumerate(mb.actions()):
                if action.text() in ("构造(&C)", "工具(&T)"):
                    mb.removeAction(cm.menuAction())
                    mb.insertMenu(mb.actions()[i + 1], cm)
                    break
        except Exception:
            pass


    def _build_animation_menu(self):
        """原生构建动画菜单（★ 轨迹已移至插件）。"""
        try:
            from animation.controller import AnimationController
            from animation.ui.timeline import TimelineDock
            from PySide6.QtGui import QAction, QKeySequence
            from PySide6.QtCore import Qt

            mb = self.menuBar()
            am = mb.addMenu("动画(&A)")

            play_act = QAction("▶ 播放动画", self)
            play_act.setShortcut(QKeySequence("Ctrl+Shift+A"))
            play_act.triggered.connect(self._anim_play)
            am.addAction(play_act)

            stop_act = QAction("■ 停止动画", self)
            stop_act.triggered.connect(self._anim_stop)
            am.addAction(stop_act)

            am.addSeparator()

            timeline_act = QAction("时间轴面板", self)
            timeline_act.triggered.connect(self._anim_toggle_timeline)
            am.addAction(timeline_act)

            self._anim_controller = AnimationController(self.doc, self.canvas)
            self._timeline_dock = TimelineDock(
                self._anim_controller, self.canvas, self)
            self.addDockWidget(
                Qt.DockWidgetArea.BottomDockWidgetArea,
                self._timeline_dock)
            self._timeline_dock.setVisible(False)
        except Exception:
            import traceback
            traceback.print_exc()

    def _anim_play(self):
        if hasattr(self, '_anim_controller'):
            self._anim_controller.play()

    def _anim_stop(self):
        if hasattr(self, '_anim_controller'):
            self._anim_controller.stop()

    def _anim_toggle_timeline(self):
        if hasattr(self, '_timeline_dock'):
            self._timeline_dock.setVisible(
                not self._timeline_dock.isVisible())

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
        func = top.addMenu("函数(&F)")
        new_func = QAction("新建函数…", self)
        new_func.triggered.connect(self.function_dock._editor.new_function)
        func.addAction(new_func)
        from plugins.expr_geo_tools import ExprCircleTool, new_expr_point
        ec = QAction("表达式圆…", self)
        ec.triggered.connect(lambda: self.canvas.set_tool(ExprCircleTool()))
        func.addAction(ec)
        ep = QAction("表达式点…", self)
        ep.triggered.connect(lambda: new_expr_point(self, self.doc))
        func.addAction(ep)

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
            name, val, lo, hi, expr = wiz.result_data()
            self.doc.vars.define(name, val, lo, hi, expr)
            self.doc.refresh_variables()
            self.function_dock.refresh()   # 或 self.canvas.var_panel.refresh()

    def _edit_variable_range(self, name):
        var = self.doc.vars.get_var(name)
        if var is None:
            return
        dlg = VariableRangeDialog(name, var.vmin, var.vmax, self)
        if dlg.exec():
            lo, hi = dlg.result_data()
            self.doc.vars.set_range(name, lo, hi)
            self.doc.refresh_variables()
            self.function_dock.refresh()      # 滑杆按新范围重建

    def _delete_variable(self, name):
        reply = QMessageBox.question(
            self, "删除变量",
            f"确定删除变量「{name}」吗？\n引用它的表达式线段/角度将随之失效。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.doc.vars.delete(name)
            self.doc.refresh_variables()
            self.function_dock.refresh()

    def _edit_variable(self, name):
        var = self.doc.vars.get_var(name)
        if var is None:
            return
        val, ok = QInputDialog.getDouble(
            self, "修改变量", f"{name} =", var.value, var.vmin, var.vmax, 3)
        if ok:
            self.doc.vars.set(name, val)
            self.doc.refresh_variables()
            self.function_dock.refresh()

    def _sync_actions(self, tool) -> None:
        for cls, act in self._actions.items():
            act.setChecked(type(tool) is cls)

    def _build_menubar(self) -> None:
        mb = self.menuBar()
        
        # ================= 1. 文件 =================
        fm = mb.addMenu("文件(&F)")
        for text, slot, key in (
            ("新建(&N)", self._new_document, QKeySequence.StandardKey.New),
            ("打开(&O)…", self._open, QKeySequence.StandardKey.Open),
            ("保存(&S)…", self._save, QKeySequence.StandardKey.Save),
        ):
            act = QAction(text, self)
            act.setShortcut(key)
            act.triggered.connect(slot)
            fm.addAction(act)
            
        info_act = QAction("文档信息(&I)…", self)
        info_act.triggered.connect(self._doc_info)
        fm.addAction(info_act)
        
        fm.addSeparator()
        export_act = QAction("导出图像(&E)…", self)
        export_act.setShortcut(QKeySequence("Ctrl+E"))
        export_act.triggered.connect(self._export_image)
        fm.addAction(export_act)
        
        export_cw = QAction("导出到课件(&C)…", self)
        export_cw.triggered.connect(self._export_courseware)
        fm.addAction(export_cw)
        
        fm.addSeparator()
        quit_act = QAction("退出(&X)", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        fm.addAction(quit_act)

        # ================= 2. 编辑 (从原视图菜单独立) =================
        em = mb.addMenu("编辑(&E)")
        self._undo_act = QAction("撤销(&U)", self)
        self._undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        self._undo_act.triggered.connect(self.doc.undo)
        em.addAction(self._undo_act)
        
        self._redo_act = QAction("重做(&R)", self)
        self._redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        self._redo_act.triggered.connect(self.doc.redo)
        em.addAction(self._redo_act)
        
        self.doc.history_changed.connect(self._update_history_actions)
        self._update_history_actions()
        
        em.addSeparator()
        for text, key, slot in (
            ("剪切(&T)", QKeySequence.StandardKey.Cut, lambda: self.doc.cut_selection()),
            ("复制(&C)", QKeySequence.StandardKey.Copy, lambda: self.doc.copy_selection()),
            ("粘贴(&P)", QKeySequence.StandardKey.Paste, lambda: self.doc.paste()),
        ):
            a = QAction(text, self)
            a.setShortcut(key)
            a.triggered.connect(slot)
            em.addAction(a)
            
        em.addSeparator()
        del_act = QAction("删除选中(&D)", self)
        del_act.setShortcut(QKeySequence.StandardKey.Delete)
        del_act.triggered.connect(self.doc.remove_selected)
        em.addAction(del_act)

        em.addSeparator()                              # ← 新增分隔线
        settings_act = QAction("偏好设置(&P)…", self)  # ← 新增
        settings_act.setShortcut(QKeySequence("Ctrl+,"))
        settings_act.triggered.connect(self._open_settings)
        em.addAction(settings_act)

        # ================= 3. 视图 =================
        vm = mb.addMenu("视图(&V)")
        self._func_editor_act = QAction("函数编辑器", self, checkable=True)
        self._func_editor_act.setChecked(True)
        self._func_editor_act.toggled.connect(self.function_dock.setVisible)
        self.function_dock.visibilityChanged.connect(self._func_editor_act.setChecked)
        vm.addAction(self._func_editor_act)
        
        vm.addSeparator()
        
        # 主题菜单移入视图
        thm = vm.addMenu("主题(&M)")
        tgroup = QActionGroup(self)
        tgroup.setExclusive(True)
        for name in theme.theme_names():
            act = QAction(name, self, checkable=True)
            act.setChecked(name == theme.active_name())
            act.triggered.connect(lambda _=False, n=name: theme.set_theme(n))
            tgroup.addAction(act)
            thm.addAction(act)
        thm.addSeparator()
        custom_act = QAction("自定义主题…", self)
        custom_act.triggered.connect(self._open_theme_editor)
        thm.addAction(custom_act)

        # ================= 4. 构造 (原"工具"菜单，预留未来扩展) =================
        cm = mb.addMenu("构造(&C)")
        plugin_specs = [s for s in TOOL_REGISTRY if s.get("panel") == "menu"]
        for spec in sorted(plugin_specs, key=lambda s: s.get("order", 99)):
            cm.addAction(self._actions[spec["cls"]])
        if not plugin_specs:
            e = cm.addAction("（暂无构造工具）"); e.setEnabled(False)

        # ================= 5. 度量 =================
        mm = mb.addMenu("度量(&M)")
        measure_specs = [s for s in TOOL_REGISTRY if s.get("panel") == "measure"]
        for spec in sorted(measure_specs, key=lambda s: s.get("order", 99)):
            mm.addAction(self._actions[spec["cls"]])
        if not measure_specs:
            e = mm.addAction("（暂无度量工具）"); e.setEnabled(False)

        # ================= 6. 变换 =================
        gm = mb.addMenu("变换(&T)")
        transform_specs = [s for s in TOOL_REGISTRY if s.get("panel") == "transform"]
        for spec in sorted(transform_specs, key=lambda s: s.get("order", 99)):
            gm.addAction(self._actions[spec["cls"]])
        if not transform_specs:
            e = gm.addAction("（暂无变换工具）"); e.setEnabled(False)

        # ================= 7. 插入 =================
        im = mb.addMenu("插入(&I)")
        insert_specs = [s for s in TOOL_REGISTRY if s.get("panel") == "insert"]
        for spec in sorted(insert_specs, key=lambda s: s.get("order", 99)):
            im.addAction(self._actions[spec["cls"]])
        if not insert_specs:
            e = im.addAction("（暂无插入工具）"); e.setEnabled(False)
            
        hm = mb.addMenu("帮助(&H)")

        help_act = QAction("示例项目库(&E)…", self)
        help_act.setShortcut(QKeySequence("F1"))
        help_act.triggered.connect(self._show_help_gallery)
        hm.addAction(help_act)

        about_act = QAction("关于(&A)…", self)
        about_act.triggered.connect(self._show_about)
        hm.addAction(about_act)
                
    def _open_script_library_manager(self):
        from ui.script_library_manager import ScriptLibraryManager
        ScriptLibraryManager(self.doc, self).exec()
        
    def _new_document(self):
        """新建文档：停止动画 → 清空文档 → 重置 UI。"""
        # 1. 停止动画播放
        # 1. 停止动画并重置控制器
        if hasattr(self, '_anim_controller'):
            self._anim_controller.stop()
            self._anim_controller.clip = None
            self._anim_controller._current_time = 0.0
            self._anim_controller._bound_version = -1

        # 2. 停止宏录制（如果正在录制）
        if hasattr(self, 'macro_manager') and self.macro_manager.is_recording():
            self.macro_manager.toggle_recording()
            self._update_macro_actions()

        # 3. 清空文档（已修复的 clear）
        self.doc.clear()

        # 4. 重置窗口标题
        self.setWindowTitle("GeoSketch · 几何画板")

        # 5. 重置宏管理器状态
        if hasattr(self, 'macro_manager'):
            self.macro_manager.changed.emit()

        # 6. 刷新函数面板
        self.function_dock.refresh()

        # 7. 更新雪花彩蛋状态
        self.canvas.update_snow_state()    
           
    def _show_help_gallery(self):
        """全屏显示帮助浏览视图。"""
        from ui.help_gallery import HelpGalleryWidget
        if hasattr(self, "_help_gallery") and self._help_gallery is not None:
            self._help_gallery.show()
            self._help_gallery.raise_()
            return

        self._help_gallery = HelpGalleryWidget(self.doc, self)
        self._help_gallery.setGeometry(self.rect())
        self._help_gallery.closed.connect(self._close_help_gallery)
        self._help_gallery.project_loaded.connect(self._on_project_loaded)
        self._help_gallery.show()
        self._help_gallery.raise_()

    def _close_help_gallery(self):
        """关闭帮助浏览视图。"""
        if hasattr(self, "_help_gallery") and self._help_gallery is not None:
            self._help_gallery.hide()

    def _on_project_loaded(self, path: str):
        """项目加载完成后的回调。"""
        self.setWindowTitle(f"{os.path.basename(path)} — GeoSketch")
                
    def _open_theme_editor(self):
        from ui.theme_editor import ThemeEditorDialog
        ThemeEditorDialog(self).exec()
        
    def _show_about(self):
        from ui.about_dialog import AboutDialog
        dlg = AboutDialog(self)
        dlg.exec()
                
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



    def _export_courseware(self) -> None:
        from ui.export_courseware import export_courseware
        export_courseware(self.canvas, self)

    def _build_statusbar(self) -> None:
        sb = QStatusBar(self)
        self.setStatusBar(sb)

        self._hint_label = QLabel("就绪")
        self._coord_label = QLabel("(    0.00 ,    0.00 )")
        self._coord_label.setFont(theme.LABEL_FONT)
        self._count_label = QLabel("0 个对象")
        self._rec_label = QLabel("")
        self._rec_label.setStyleSheet("")
        self._ai_label = QLabel("")

        sb.addWidget(self._hint_label, 1)
        sb.addPermanentWidget(self._count_label)
        sb.addPermanentWidget(self._coord_label)
        sb.addPermanentWidget(self._rec_label)
        sb.addPermanentWidget(self._ai_label)

        # ★ 宏状态刷新
        if hasattr(self, "macro_manager"):
            self.macro_manager.changed.connect(self._update_macro_actions)
            self._update_macro_actions()

        self.canvas.cursor_info.connect(self._coord_label.setText)
        self.canvas.tool_changed.connect(self._hint_label.setText)
        self.doc.changed.connect(
            lambda: self._count_label.setText(f"{len(self.doc.objects)} 个对象"))

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存",
            self._current_path                          # ← 改：优先用上次路径
            or f"sketch_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.wgeo",
            "GeoSketch 文件 (*.wgeo)")
        if path:
            self.doc.save(path)
            self._current_path = path                   # ← 新增
            
    def _update_history_actions(self) -> None:
        self._undo_act.setEnabled(self.doc.can_undo)
        self._redo_act.setEnabled(self.doc.can_redo)

    def _open(self) -> None:
        # ★ 修复：打开前检查是否有未保存的更改
        if self.doc.objects and not self._confirm_discard():
            return

        path, _ = QFileDialog.getOpenFileName(
            self, "打开", "", "GeoSketch 文件 (*.wgeo)")
        if path:
            # ★ 修复：打开前停止动画与宏录制
            if hasattr(self, '_anim_controller'):
                self._anim_controller.stop()
            if hasattr(self, 'macro_manager') and self.macro_manager.is_recording():
                self.macro_manager.toggle_recording()
                self._update_macro_actions()
            self.doc.load(path)
            self._current_path = path
            self.canvas.update_snow_state()
            self.canvas.refresh_physics_bar()
            self._refresh_physics_menu()
            self.setWindowTitle(
                f"{os.path.basename(path)} — GeoSketch")
            # ★ 刷新宏菜单
            if hasattr(self, "macro_manager"):
                self.macro_manager.changed.emit()

    def _confirm_discard(self) -> bool:
        """★ 新增：询问用户是否放弃当前未保存的更改。
        返回 True 表示可以继续（丢弃或已保存），False 表示取消操作。
        """
        if not self.doc.objects:
            return True
        reply = QMessageBox.question(
            self,
            "未保存的更改",
            "当前文档包含未保存的更改。\n是否放弃并继续？",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No |
            QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            return True
        if reply == QMessageBox.StandardButton.No:
            # 先保存再继续
            self._save()
            return True
        return False  # Cancel
                
    # ================= 宏系统 =================

    def _build_advanced_menu(self) -> None:
        """高级功能菜单：脚本库与宏系统。"""
        mb = self.menuBar()
        am = mb.addMenu("高级(&A)")
        
        # 1. 脚本库
        mgr_act = QAction("管理脚本库...", self)
        mgr_act.triggered.connect(self._open_script_library_manager)
        am.addAction(mgr_act)
        
        am.addSeparator()
        
        # 2. 宏系统
        self._record_act = QAction("● 开始录制宏", self, checkable=True)
        self._record_act.setShortcut(QKeySequence("Ctrl+Shift+R"))
        self._record_act.triggered.connect(self._toggle_macro_recording)
        am.addAction(self._record_act)
        
        self._play_last_act = QAction("回放最新宏", self)
        self._play_last_act.setShortcut(QKeySequence("Ctrl+Shift+P"))
        self._play_last_act.triggered.connect(self._play_last_macro)
        am.addAction(self._play_last_act)
        
        am.addSeparator()
        macro_mgr_act = QAction("宏管理器…", self)
        macro_mgr_act.triggered.connect(self._open_macro_dialog)
        am.addAction(macro_mgr_act)
        
        self._update_macro_actions()

    def _toggle_macro_recording(self):
        self.macro_manager.toggle_recording()
        self._update_macro_actions()

    def _play_last_macro(self):
        if self.macro_manager.is_recording():
            QMessageBox.information(
                self,
                "宏",
                "正在录制宏，请先停止录制再回放。"
            )
            return

        if not getattr(self.doc, "macros", []):
            QMessageBox.information(
                self,
                "宏",
                "还没有录制任何宏。"
            )
            return

        self.macro_manager.play_last()

    def _open_macro_dialog(self):
        from ui.macro_dialog import MacroDialog

        MacroDialog(self.macro_manager, self).exec()

    def _update_macro_actions(self):
        rec = self.macro_manager.is_recording()

        if hasattr(self, "_record_act"):
            self._record_act.setChecked(rec)
            self._record_act.setText("■ 停止录制" if rec else "● 开始录制")

        if hasattr(self, "_play_last_act"):
            self._play_last_act.setEnabled(bool(getattr(self.doc, "macros", [])))

        if hasattr(self, "_rec_label"):
            if rec:
                self._rec_label.setText("● 宏录制中")
                self._rec_label.setStyleSheet(
                    "color:#e03131;font-weight:700;"
                )
            else:
                self._rec_label.setText("")
                self._rec_label.setStyleSheet("")
    # ══════════════════════════════════════════════════
    #  偏好设置（P2 新增）
    # ══════════════════════════════════════════════════

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.doc.settings, self)
        dlg.exec()

    def _on_settings_changed(self, key: str) -> None:
        """``SettingsStore.changed`` 信号分发。"""
        section = key.split(".")[0] if "." in key else key

        if key == "*":
            # 全量刷新（load / reset）
            self._apply_ui_font()
            self.canvas._bg_cache = None
            self.canvas.update()
            self._restart_autosave()
            self._refresh_physics_menu()
            self.canvas.refresh_physics_bar()
            self._invalidate_optics_sync()
            return

        if section == "appearance":
            self._apply_ui_font()
            self.canvas._bg_cache = None
            self.canvas.update()
        elif section == "canvas":
            self.canvas._bg_cache = None
            self.canvas.update()
        elif section == "effects":
            pass
        elif section == "interaction":
            pass
        elif section == "workflow":
            self._restart_autosave()
        elif section == "ai":
            self._update_ai_status()
        elif section == "physics":
            self._refresh_physics_menu()
            self.canvas.refresh_physics_bar()
            self._invalidate_optics_sync()
            self.canvas.update()
            
    def _invalidate_optics_sync(self) -> None:
        """强制光学场景在下一次渲染前重新同步。"""
        try:
            self.doc._optics_sync_key = None
            self.doc._optics_mirror_sig = None

            from physics.optics.scene import sync_optics
            sync_optics(self.doc, force=True)
        except Exception:
            pass
                    
    def _apply_ui_font(self) -> None:
        """从设置读取字体 → 应用到 QApplication + 主题 + 状态栏。"""
        s = self.doc.settings
        font = QFont()
        families = s.get("appearance.ui_font_family",
                         ["Segoe UI", "PingFang SC", "Microsoft YaHei",
                          "sans-serif"])
        if isinstance(families, list):
            font.setFamilies(families)
        else:
            font.setFamilies([str(families)])
        font.setPointSize(int(s.get("appearance.ui_font_size", 10)))

        app = QApplication.instance()
        assert isinstance(app, QApplication)          # ← 类型缩窄，消除 Pylance 警告

        app.setFont(font)
        theme.set_settings(s)
        theme.refresh_fonts(s)
        app.setStyleSheet(theme.app_stylesheet())
        self.canvas.setStyleSheet(theme.canvas_qss())

        if hasattr(self, "_coord_label"):
            self._coord_label.setFont(theme.LABEL_FONT)
    # ══════════════════════════════════════════════════
    #  物理扩展菜单
    # ══════════════════════════════════════════════════

    def _physics_optics_enabled(self) -> bool:
        return bool(self.doc.settings.get("physics.optics_enabled", False))

    def _build_physics_menu(self) -> None:
        """根据设置构建「物理」菜单。"""

        if not self._physics_optics_enabled():
            return

        mb = self.menuBar()

        pm = mb.addMenu("物理(&P)")
        optics_menu = pm.addMenu("光学(&O)")

        specs = [
            s for s in TOOL_REGISTRY
            if s.get("panel") == "physics_optics"
        ]

        for spec in sorted(specs, key=lambda s: s.get("order", 999)):
            optics_menu.addAction(self._actions[spec["cls"]])

        if not specs:
            e = optics_menu.addAction("（暂无光学工具）")
            e.setEnabled(False)

        # 尽量插入到「帮助」之前
        help_action = None
        for act in mb.actions():
            if act.text().startswith("帮助"):
                help_action = act
                break

        if help_action is not None:
            mb.removeAction(pm.menuAction())
            mb.insertMenu(help_action, pm)

        self._physics_menu = pm

    def _remove_physics_menu(self) -> None:
        menu = getattr(self, "_physics_menu", None)
        if menu is not None:
            self.menuBar().removeAction(menu.menuAction())
            menu.deleteLater()
            self._physics_menu = None

    def _refresh_physics_menu(self) -> None:
        self._remove_physics_menu()
        self._build_physics_menu()
        
    def _restart_autosave(self) -> None:
        minutes = self.doc.settings.get("workflow.autosave_minutes", 0)
        if minutes > 0:
            self._autosave_timer.start(int(minutes * 60 * 1000))
        else:
            self._autosave_timer.stop()
            
    def _update_ai_status(self) -> None:
        """根据设置更新状态栏 AI 指示（不加载模型）。"""
        try:
            enabled = self.doc.settings.get("ai.enabled", False)
            if not enabled:
                self._ai_label.setText("")
                return
            provider = self.doc.settings.get("ai.provider", "local")
            if provider == "local":
                self._ai_label.setText("AI ● 本地")
            else:
                self._ai_label.setText("AI ● 远程")
            self._ai_label.setStyleSheet("color: #2f9e44;")
        except Exception:
            self._ai_label.setText("")
            
    def _do_autosave(self) -> None:
        if self._current_path and os.path.isfile(self._current_path):
            try:
                self.doc.save(self._current_path)
            except Exception:
                pass
                                       
    def _doc_info(self) -> None:
        title, ok = QInputDialog.getText(
            self, "文档信息", "标题（可留空）：", text=self.doc.meta.get("title", ""))
        if not ok:
            return

        author, ok2 = QInputDialog.getText(
            self, "文档信息", "作者（可留空，不强制署名）：",
            text=self.doc.meta.get("author", ""))

        self.doc.meta["title"] = title
        if ok2:
            self.doc.meta["author"] = author

        # 标题显示在窗口标题栏
        base = "GeoSketch · 几何画板"
        self.setWindowTitle(f"{title} - {base}" if title else base)

        # ★ snow 彩蛋：标题变化后检查是否下雪
        self.canvas.update_snow_state()