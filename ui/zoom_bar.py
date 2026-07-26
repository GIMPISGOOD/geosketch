"""右下角缩放控件：以画布中心为锚点缩放；滚轮缩放仍以光标为锚点。
支持主题切换时的图标热刷新。"""
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QWidget

from ui.icons import zoom_icon


class ZoomBar(QWidget):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setObjectName("zoomBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        self._icon_btns = []  # 记录 (kind, btn) 用于换肤刷新

        def mk(kind: str, tip: str, slot) -> QToolButton:
            b = QToolButton(self)
            b.setIcon(zoom_icon(kind))
            b.setIconSize(QSize(16, 16))
            b.setToolTip(tip)
            b.clicked.connect(slot)
            layout.addWidget(b)
            self._icon_btns.append((kind, b))
            return b

        mk("out", "缩小（以画布中心为锚点）", lambda: canvas.zoom_step(-1))
        
        self._label = QLabel("100%", self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFixedWidth(50)
        layout.addWidget(self._label)
        
        mk("in", "放大（以画布中心为锚点）", lambda: canvas.zoom_step(1))
        mk("reset", "重置视图：100%，原点居中", canvas.reset_view)

        # 监听画布缩放信号，更新百分比文本
        canvas.zoom_changed.connect(lambda pct: self._label.setText(f"{pct:.0f}%"))

    def refresh_icons(self) -> None:
        """换肤时调用：重新生成并设置图标，使颜色跟随新主题。"""
        for kind, btn in self._icon_btns:
            btn.setIcon(zoom_icon(kind))