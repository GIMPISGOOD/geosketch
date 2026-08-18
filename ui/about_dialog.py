"""关于对话框：带动态图标跳跃效果。"""
import math
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QWidget
import qtawesome as qta


class BouncingIconWidget(QWidget):
    """动态跳跃图标组件：模拟物理弹跳 + 挤压变形 + 动态阴影。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(140, 140)
        self._time = 0.0
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60fps
        self._timer.timeout.connect(self._tick)
        self._timer.start()
        self._icon_pixmap = qta.icon(
            "fa5s.drafting-compass",
            color="#1971c2"
        ).pixmap(56, 56)

    def _tick(self):
        self._time += 0.016
        self.update()

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 弹跳参数：bounce ∈ [0,1]，0=落地，1=最高点
        bounce = abs(math.sin(self._time * 2.8))

        # 挤压变形：落地时压扁，空中时拉伸
        squash_x = 1.0 + 0.18 * bounce
        squash_y = 1.0 - 0.18 * bounce

        # 图标垂直位置
        base_y = 95.0
        jump_height = 45.0
        icon_cy = base_y - jump_height * bounce

        cx = 70.0

        # 动态阴影：跳得越高，阴影越小越淡
        shadow_rx = 26.0 - 12.0 * bounce
        shadow_ry = 5.0 - 2.0 * bounce
        shadow_alpha = int(50 - 30 * bounce)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, shadow_alpha))
        p.drawEllipse(QPointF(cx, 112.0), shadow_rx, shadow_ry)

        # 绘制图标（带挤压变形）
        p.save()
        p.translate(cx, icon_cy)
        p.scale(squash_x, squash_y)
        p.drawPixmap(-28, -28, self._icon_pixmap)
        p.restore()

        p.end()

    def stop(self):
        self._timer.stop()


class AboutDialog(QDialog):
    """关于对话框。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("关于 GeoSketch")
        self.setFixedSize(440, 420)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(30, 16, 30, 20)

        # 跳跃图标
        self._icon = BouncingIconWidget()
        layout.addWidget(self._icon, 0, Qt.AlignmentFlag.AlignHCenter)

        # 应用名称
        name_lbl = QLabel("GeoSketch")
        name_lbl.setStyleSheet(
            "font-size: 30px; font-weight: 800; color: #1971c2;"
        )
        name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_lbl)

        # 副标题
        sub_lbl = QLabel("几何画板")
        sub_lbl.setStyleSheet("font-size: 15px; color: #5a6b82;")
        sub_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub_lbl)

        # 版本
        ver_lbl = QLabel("版本 0.8.13")
        ver_lbl.setStyleSheet("font-size: 12px; color: #8a8f98;")
        ver_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_lbl)

        layout.addSpacing(10)

        # 描述
        desc_lbl = QLabel(
            "一款基于 PySide6 的动态几何软件，\n"
            "支持几何构造、约束求解、函数曲线、\n"
            "动画系统、脚本编程与课件导出。\n\n"
            
            "Github GIMPISGOOD GeoSketch"
        )
        desc_lbl.setStyleSheet("font-size: 13px; color: #46566e;")
        desc_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc_lbl.setWordWrap(True)
        layout.addWidget(desc_lbl)

        layout.addStretch(1)

        # 关闭按钮
        close_btn = QPushButton("关闭")
        close_btn.setFixedWidth(110)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton {"
            "  background: #1971c2; color: #fff;"
            "  border: none; border-radius: 8px;"
            "  padding: 8px 0; font-weight: 600; font-size: 13px;"
            "}"
            "QPushButton:hover { background: #1565b8; }"
        )
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, 0, Qt.AlignmentFlag.AlignHCenter)

    def closeEvent(self, ev):
        self._icon.stop()
        super().closeEvent(ev)