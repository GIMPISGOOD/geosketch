"""右下角缩放控件：以画布中心为锚点缩放；滚轮缩放仍以光标为锚点。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QToolButton, QWidget)


class ZoomBar(QWidget):
    def __init__(self, canvas, parent=None):
        super().__init__(parent)
        self.setObjectName("zoomBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(2)

        def mk(text: str, tip: str, slot) -> QToolButton:
            b = QToolButton(self)
            b.setText(text)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            layout.addWidget(b)
            return b

        mk("−", "缩小（以画布中心为锚点）", lambda: canvas.zoom_step(-1))
        self._label = QLabel("100%", self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFixedWidth(50)
        layout.addWidget(self._label)
        mk("+", "放大（以画布中心为锚点）", lambda: canvas.zoom_step(1))
        mk("⌂", "重置视图：100%，原点居中", canvas.reset_view)

        canvas.zoom_changed.connect(lambda pct: self._label.setText(f"{pct:.0f}%"))

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(35, 60, 92, 40))
        self.setGraphicsEffect(shadow)