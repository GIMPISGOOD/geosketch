"""动画系统顶层包。
删除本包即可完全卸载动画功能，不影响原有系统。
"""
import logging

logger = logging.getLogger(__name__)


def inject():
    try:
        # 1. 注入 Document 扩展（animations 列表 + 序列化钩子）
        from . import serialization
        serialization.patch_document()

        # 2. 注入 MainWindow：动画菜单 + 时间轴面板
        patch_main_window()

        # 3. 注册轨道类型（触发 tracks.py 中的注册）
        from . import tracks  # noqa: F401

        logger.info("✔ 动画系统已加载")
        return True
    except Exception as e:
        logger.warning(f"✘ 动画系统加载失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def patch_main_window():
    from ui.main_window import MainWindow
    original_init = MainWindow.__init__

    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)

        # 动画菜单
        mb = self.menuBar()
        am = mb.addMenu("动画(&A)")

        from PySide6.QtGui import QAction, QKeySequence

        play_act = QAction("▶ 播放动画", self)
        play_act.setShortcut(QKeySequence("Ctrl+Shift+A"))
        play_act.triggered.connect(lambda: self._anim_play())
        am.addAction(play_act)

        stop_act = QAction("■ 停止动画", self)
        stop_act.triggered.connect(lambda: self._anim_stop())
        am.addAction(stop_act)

        am.addSeparator()

        timeline_act = QAction("时间轴面板", self)
        timeline_act.triggered.connect(lambda: self._anim_toggle_timeline())
        am.addAction(timeline_act)

        # 动画控制器（单例，挂到 MainWindow）
        from .controller import AnimationController
        self._anim_controller = AnimationController(self.doc, self.canvas)

        # 时间轴面板
        from .ui.timeline import TimelineDock
        self._timeline_dock = TimelineDock(self._anim_controller, self.canvas, self)
        self.addDockWidget(
            __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.DockWidgetArea.BottomDockWidgetArea,
            self._timeline_dock
        )
        self._timeline_dock.setVisible(False)

        # 绑定快捷键方法
        self._anim_play = lambda: self._anim_controller.play()
        self._anim_stop = lambda: self._anim_controller.stop()
        self._anim_toggle_timeline = lambda: self._timeline_dock.setVisible(
            not self._timeline_dock.isVisible()
        )

    setattr(MainWindow, "__init__", new_init)


inject()