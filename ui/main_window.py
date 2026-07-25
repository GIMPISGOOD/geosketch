from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (QFileDialog, QLabel, QMainWindow, QStatusBar)

import geo            # noqa: F401  触发几何对象注册
import tools          # noqa: F401  触发工具注册
from core.document import Document
from core.registry import TOOL_REGISTRY
from ui import theme
from ui.canvas import Canvas


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("GeoSketch · 几何画板 v0.1")
        self.resize(1240, 780)

        self.doc = Document()
        self.canvas = Canvas(self.doc)
        self.setCentralWidget(self.canvas)

        self._actions: dict[type, QAction] = {}
        self._build_shortcuts()
        self._build_statusbar()
        self._build_menu()

        self.canvas.set_tool(TOOL_REGISTRY[0]["cls"]())   # 默认：选择

    # ---------- 窗口级快捷键（工具栏已移到画布悬浮件）----------
    def _build_shortcuts(self) -> None:
        for spec in TOOL_REGISTRY:
            act = QAction(spec["name"], self, checkable=True)
            if spec["shortcut"]:                       # 空快捷键不建 QKeySequence
                act.setShortcut(QKeySequence(spec["shortcut"]))
            act.setStatusTip(spec["hint"])
            act.triggered.connect(
                lambda _=False, s=spec: self.canvas.set_tool(s["cls"]()))
            self.addAction(act)
            self._actions[spec["cls"]] = act
        self.canvas.tool_activated.connect(self._sync_actions)

    def _sync_actions(self, tool) -> None:
        for cls, act in self._actions.items():
            act.setChecked(type(tool) is cls)

    # ---------- 状态栏 ----------
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

    # ---------- 菜单：显式 QAction，避开 addAction 重载歧义 ----------
    def _build_menu(self) -> None:
        fm = self.menuBar().addMenu("文件(&F)")
        for text, slot, key in (
            ("新建(&N)", self.doc.clear, QKeySequence.StandardKey.New),
            ("打开(&O)…", self._open, QKeySequence.StandardKey.Open),
            ("保存(&S)…", self._save, QKeySequence.StandardKey.Save),
        ):
            act = QAction(text, self)
            act.setShortcut(key)
            act.triggered.connect(slot)
            fm.addAction(act)
        fm.addSeparator()
        quit_act = QAction("退出(&X)", self)
        quit_act.setShortcut(QKeySequence.StandardKey.Quit)
        quit_act.triggered.connect(self.close)
        fm.addAction(quit_act)

    def _save(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "保存", "sketch.json", "GeoSketch 文件 (*.json)")
        if path:
            self.doc.save(path)

    def _open(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "打开", "", "GeoSketch 文件 (*.json)")
        if path:
            self.doc.load(path)