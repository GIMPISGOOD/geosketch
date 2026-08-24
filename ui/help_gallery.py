"""帮助浏览视图：仿 Scratch 扩展库风格。
修复：缩略图 HiDPI 模糊、入场动画。
"""
import json
import os
import zipfile
from PySide6.QtCore import Qt, Signal, QSize, QRectF, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QFont, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QTreeWidget, QTreeWidgetItem,
    QFrame, QSizePolicy, QGraphicsOpacityEffect
)
from ui import theme


class ProjectCardWidget(QWidget):
    """单个项目卡片：上 75% 缩略图 + 下 25% 元数据。"""
    clicked = Signal(str)

    def __init__(self, zip_path: str, parent=None):
        super().__init__(parent)
        self.zip_path = zip_path
        self._title = os.path.splitext(os.path.basename(zip_path))[0]
        self._author = ""
        self._desc = ""
        self._thumbnail = QPixmap()
        self._wgeo_data = None
        self._hovered = False
        self.setFixedSize(220, 280)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._parse_zip()

    def _parse_zip(self):
        try:
            if not zipfile.is_zipfile(self.zip_path):
                return
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                names = zf.namelist()
                img_exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
                for n in names:
                    if n.lower().endswith(img_exts):
                        img_data = zf.read(n)
                        self._thumbnail.loadFromData(img_data)
                        break
                for n in names:
                    if n.lower().endswith(".wgeo"):
                        self._wgeo_data = zf.read(n)
                        self._parse_wgeo_meta(self._wgeo_data)
                        break
        except Exception:
            pass

    def _parse_wgeo_meta(self, wgeo_bytes: bytes):
        import io
        try:
            with zipfile.ZipFile(io.BytesIO(wgeo_bytes), 'r') as wgeo_zf:
                if "meta.data" in wgeo_zf.namelist():
                    meta = json.loads(wgeo_zf.read("meta.data").decode("utf-8"))
                    self._title = meta.get("title", self._title) or self._title
                    self._author = meta.get("author", "")
                    self._desc = meta.get("description", "")
        except Exception:
            pass

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        # ★ 关键修复：启用平滑像素变换，消除缩略图锯齿
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w, h = self.width(), self.height()
        radius = 12.0
        card_path = QPainterPath()
        card_path.addRoundedRect(0, 0, w, h, radius, radius)

        if self._hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 25))
            p.drawRoundedRect(2, 4, w - 4, h - 2, radius, radius)

        p.setPen(QPen(QColor("#e0e4ea"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawPath(card_path)

        p.save()
        p.setClipPath(card_path)

        img_h = int(h * 0.75)
        if not self._thumbnail.isNull():
            # ★ 修复：考虑 devicePixelRatio 进行高清缩放
            dpr = self.devicePixelRatioF()
            target_w = int(w * dpr)
            target_h = int(img_h * dpr)
            scaled = self._thumbnail.scaled(
                target_w, target_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            scaled.setDevicePixelRatio(dpr)
            x_off = int((scaled.width() - w) / 2)
            y_off = int((scaled.height() - img_h) / 2)
            p.drawPixmap(0, 0, scaled, x_off, y_off, w, img_h)
        else:
            p.fillRect(0, 0, w, img_h, QColor("#e8f0fe"))
            p.setPen(QColor("#9aa5b1"))
            p.setFont(QFont("Microsoft YaHei", 24))
            p.drawText(QRectF(0, 0, w, img_h),
                       Qt.AlignmentFlag.AlignCenter, "?")

        meta_y = img_h
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#fafbfc"))
        p.drawRect(0, meta_y, w, h - img_h)

        p.setPen(QColor("#1f2937"))
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        p.drawText(QRectF(10, meta_y + 4, w - 20, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._title)

        p.setPen(QColor("#6b7280"))
        p.setFont(QFont("Microsoft YaHei", 9))
        info = self._author
        if self._desc:
            info += f"  {self._desc}" if info else self._desc
        if len(info) > 28:
            info = info[:26] + "…"
        p.drawText(QRectF(10, meta_y + 26, w - 20, 16),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   info)
        p.restore()

        if self._hovered:
            p.setPen(QPen(QColor("#1971c2"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(1, 1, w - 2, h - 2, radius, radius)
        p.end()

    def enterEvent(self, ev):
        self._hovered = True
        self.update()
        super().enterEvent(ev)

    def leaveEvent(self, ev):
        self._hovered = False
        self.update()
        super().leaveEvent(ev)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self._on_clicked()
        super().mousePressEvent(ev)

    def _on_clicked(self):
        if self._wgeo_data is None:
            return
        import tempfile
        fd, temp_path = tempfile.mkstemp(suffix=".wgeo")
        with os.fdopen(fd, 'wb') as f:
            f.write(self._wgeo_data)
        self.clicked.emit(temp_path)


class HelpGalleryWidget(QWidget):
    """帮助浏览主视图：全屏覆盖主窗口，带入场淡入动画。"""
    closed = Signal()
    project_loaded = Signal(str)

    def __init__(self, doc, parent=None):
        super().__init__(parent)
        self.doc = doc
        self._examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples"
        )
        self._cards = []
        self._build_ui()
        self._scan_examples()
        # ★ 入场淡入动画
        self._setup_enter_animation()

    def _setup_enter_animation(self):
        """打开时淡入 + 微缩放动画。"""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._opacity_effect)
        self._opacity_effect.setOpacity(0)

        self._fade_anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        self._fade_anim.setDuration(220)
        self._fade_anim.setStartValue(0.0)
        self._fade_anim.setEndValue(1.0)
        self._fade_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._scale_anim = QPropertyAnimation(self, b"geometry")
        self._scale_anim.setDuration(220)
        self._scale_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def showEvent(self, ev):
        super().showEvent(ev)
        # 播放入场动画
        self._fade_anim.start()

    def hideEvent(self, ev):
        self._opacity_effect.setOpacity(1)
        super().hideEvent(ev)

    def _build_ui(self):
        self.setStyleSheet("background: #f0f4f8;")
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        top_bar = self._build_top_bar()
        root_layout.addWidget(top_bar)

        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self._tree = QTreeWidget()
        self._tree.setFixedWidth(200)
        self._tree.setHeaderHidden(True)
        self._tree.setStyleSheet(
            "QTreeWidget {"
            "  background: #ffffff;"
            "  border: none;"
            "  border-right: 1px solid #e0e4ea;"
            "  font-size: 13px;"
            "  padding: 8px 0;"
            "}"
            "QTreeWidget::item {"
            "  padding: 8px 12px;"
            "  border-radius: 6px;"
            "  margin: 2px 6px;"
            "}"
            "QTreeWidget::item:selected {"
            "  background: #e8f0fe;"
            "  color: #1971c2;"
            "}"
            "QTreeWidget::item:hover {"
            "  background: #f0f4f8;"
            "}"
        )
        self._tree.itemClicked.connect(self._on_category_selected)
        body_layout.addWidget(self._tree)

        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet(
            "QScrollArea { background: #f0f4f8; border: none; }")
        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: #f0f4f8;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(20, 20, 20, 20)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setAlignment(
            Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        self._scroll.setWidget(self._grid_container)
        body_layout.addWidget(self._scroll, 1)
        root_layout.addLayout(body_layout, 1)

    def _build_top_bar(self):
        bar = QWidget()
        bar.setFixedHeight(52)
        bar.setStyleSheet(
            "background: #ffffff;"
            "border-bottom: 1px solid #e0e4ea;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)

        back_btn = QPushButton("← 返回编辑器")
        back_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        back_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent; color: #1971c2;"
            "  border: none; font-size: 14px; font-weight: 600;"
            "  padding: 6px 12px; border-radius: 6px;"
            "}"
            "QPushButton:hover { background: #e8f0fe; }"
        )
        back_btn.clicked.connect(self.closed.emit)
        layout.addWidget(back_btn)
        layout.addStretch(1)

        title_lbl = QLabel("示例项目库")
        title_lbl.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #1f2937;")
        layout.addWidget(title_lbl)
        layout.addStretch(1)

        spacer = QLabel("")
        spacer.setFixedWidth(100)
        layout.addWidget(spacer)
        return bar

    def _scan_examples(self):
        self._tree.clear()
        if not os.path.isdir(self._examples_dir):
            item = QTreeWidgetItem(self._tree)
            item.setText(0, "（无示例项目）")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return
        categories = sorted([
            d for d in os.listdir(self._examples_dir)
            if os.path.isdir(os.path.join(self._examples_dir, d))
        ])
        if not categories:
            item = QTreeWidgetItem(self._tree)
            item.setText(0, "（无示例项目）")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            return
        for cat in categories:
            cat_item = QTreeWidgetItem(self._tree)
            cat_item.setText(0, cat)
            cat_item.setData(0, Qt.ItemDataRole.UserRole, cat)
            cat_item.setExpanded(True)
            cat_dir = os.path.join(self._examples_dir, cat)
            zips = [f for f in os.listdir(cat_dir)
                    if f.lower().endswith(".zip")]
            count_item = QTreeWidgetItem(cat_item)
            count_item.setText(0, f"{len(zips)} 个项目")
            count_item.setFlags(
                count_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            count_item.setForeground(0, QColor("#9aa5b1"))
        if self._tree.topLevelItemCount() > 0:
            first = self._tree.topLevelItem(0)
            self._tree.setCurrentItem(first)  # pyright: ignore
            self._show_category(first.text(0)) # pyright: ignore

    def _on_category_selected(self, item, column):
        cat_name = item.data(0, Qt.ItemDataRole.UserRole)
        if cat_name:
            self._show_category(cat_name)

    def _show_category(self, category: str):
        for card in self._cards:
            self._grid_layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        cat_dir = os.path.join(self._examples_dir, category)
        if not os.path.isdir(cat_dir):
            return
        zips = sorted([
            f for f in os.listdir(cat_dir)
            if f.lower().endswith(".zip")
        ])
        row, col = 0, 0
        cols = 4
        for zip_name in zips:
            zip_path = os.path.join(cat_dir, zip_name)
            card = ProjectCardWidget(zip_path)
            card.clicked.connect(self._on_card_clicked)
            self._grid_layout.addWidget(card, row, col)
            self._cards.append(card)
            col += 1
            if col >= cols:
                col = 0
                row += 1

    def _on_card_clicked(self, temp_wgeo_path: str):
        try:
            self.doc.load(temp_wgeo_path)
            self.project_loaded.emit(temp_wgeo_path)
            self.closed.emit()
        except Exception as e:
            print(f"[HelpGallery] 加载项目失败: {e}")
        finally:
            try:
                if os.path.exists(temp_wgeo_path):
                    os.unlink(temp_wgeo_path)
            except Exception:
                pass