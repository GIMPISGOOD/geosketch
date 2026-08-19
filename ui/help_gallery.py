"""帮助浏览视图：仿 Scratch 扩展库（Extension Gallery）风格。
全屏覆盖主窗口，左侧分类树 + 右侧网格卡片。
每个项目为一个 ZIP 包，内含一张缩略图和一个 .wgeo 文件。
元数据从 .wgeo 内部的 meta.data 读取。
"""
import json
import os
import zipfile
from PySide6.QtCore import Qt, Signal, QSize, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QPainterPath, QFont , QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QGridLayout, QTreeWidget, QTreeWidgetItem,
    QFrame, QSizePolicy
)
from ui import theme


# ============================================================
# 项目卡片
# ============================================================
class ProjectCardWidget(QWidget):
    """单个项目卡片：上 75% 缩略图 + 下 25% 元数据。"""

    clicked = Signal(str)  # 参数为 .wgeo 临时文件路径

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
        """从 ZIP 中提取缩略图和 .wgeo 内的 meta.data。"""
        try:
            if not zipfile.is_zipfile(self.zip_path):
                return
            with zipfile.ZipFile(self.zip_path, 'r') as zf:
                names = zf.namelist()

                # 提取缩略图（第一张图片）
                img_exts = (".png", ".jpg", ".jpeg", ".bmp", ".webp")
                for n in names:
                    if n.lower().endswith(img_exts):
                        img_data = zf.read(n)
                        self._thumbnail.loadFromData(img_data)
                        break

                # 提取 .wgeo 文件
                for n in names:
                    if n.lower().endswith(".wgeo"):
                        self._wgeo_data = zf.read(n)
                        # 从 .wgeo（本身是 ZIP）中读取 meta.data
                        self._parse_wgeo_meta(self._wgeo_data)
                        break
        except Exception:
            pass

    def _parse_wgeo_meta(self, wgeo_bytes: bytes):
        """从 .wgeo 文件（ZIP）中读取 meta.data。"""
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
        w, h = self.width(), self.height()
        radius = 12.0

        card_path = QPainterPath()
        card_path.addRoundedRect(0, 0, w, h, radius, radius)

        # 悬停阴影
        if self._hovered:
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(0, 0, 0, 25))
            p.drawRoundedRect(2, 4, w - 4, h - 2, radius, radius)

        # 卡片主体
        p.setPen(QPen(QColor("#e0e4ea"), 1))
        p.setBrush(QColor("#ffffff"))
        p.drawPath(card_path)

        p.save()
        p.setClipPath(card_path)

        # 上部 75%：缩略图
        img_h = int(h * 0.75)
        if not self._thumbnail.isNull():
            scaled = self._thumbnail.scaled(
                w, img_h,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation
            )
            x_off = (scaled.width() - w) // 2
            y_off = (scaled.height() - img_h) // 2
            p.drawPixmap(0, 0, scaled, x_off, y_off, w, img_h)
        else:
            grad_color = QColor("#e8f0fe")
            p.fillRect(0, 0, w, img_h, grad_color)
            p.setPen(QColor("#9aa5b1"))
            p.setFont(QFont("Microsoft YaHei", 24))
            p.drawText(QRectF(0, 0, w, img_h), Qt.AlignmentFlag.AlignCenter, "?")

        # 下部 25%：元数据
        meta_y = img_h
        meta_h = h - img_h
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#fafbfc"))
        p.drawRect(0, meta_y, w, meta_h)

        # 标题
        p.setPen(QColor("#1f2937"))
        p.setFont(QFont("Microsoft YaHei", 11, QFont.Weight.Bold))
        p.drawText(QRectF(10, meta_y + 4, w - 20, 20),
                   Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                   self._title)

        # 作者 + 描述
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

        # 悬停边框高亮
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
        """点击卡片：将 .wgeo 写入临时文件并加载。"""
        if self._wgeo_data is None:
            return
        import tempfile
        fd, temp_path = tempfile.mkstemp(suffix=".wgeo")
        with os.fdopen(fd, 'wb') as f:
            f.write(self._wgeo_data)
        self.clicked.emit(temp_path)


# ============================================================
# 帮助浏览主视图
# ============================================================
class HelpGalleryWidget(QWidget):
    """帮助浏览主视图：全屏覆盖主窗口。"""

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

    def _build_ui(self):
        self.setStyleSheet("background: #f0f4f8;")
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 顶部工具栏
        top_bar = self._build_top_bar()
        root_layout.addWidget(top_bar)

        # 主体：左侧导航 + 右侧内容
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 左侧分类树
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

        # 右侧滚动区域
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setStyleSheet("QScrollArea { background: #f0f4f8; border: none; }")

        self._grid_container = QWidget()
        self._grid_container.setStyleSheet("background: #f0f4f8;")
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setContentsMargins(20, 20, 20, 20)
        self._grid_layout.setSpacing(16)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

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
        title_lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #1f2937;")
        layout.addWidget(title_lbl)

        layout.addStretch(1)

        spacer = QLabel("")
        spacer.setFixedWidth(100)
        layout.addWidget(spacer)

        return bar

    def _scan_examples(self):
        """扫描 examples 目录，构建分类树。"""
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
            zips = [f for f in os.listdir(cat_dir) if f.lower().endswith(".zip")]
            count_item = QTreeWidgetItem(cat_item)
            count_item.setText(0, f"{len(zips)} 个项目")
            count_item.setFlags(count_item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            count_item.setForeground(0, QColor("#9aa5b1"))

        if self._tree.topLevelItemCount() > 0:
            first = self._tree.topLevelItem(0)
            self._tree.setCurrentItem(first) # pyright: ignore[reportArgumentType]
            self._show_category(first.text(0))

    def _on_category_selected(self, item, column):
        cat_name = item.data(0, Qt.ItemDataRole.UserRole)
        if cat_name:
            self._show_category(cat_name)

    def _show_category(self, category: str):
        """显示指定分类下的所有项目卡片。"""
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
        """卡片点击：加载 .wgeo 文件到文档，加载完成后删除临时副本。"""
        try:
            self.doc.load(temp_wgeo_path)
            self.project_loaded.emit(temp_wgeo_path)
            self.closed.emit()
        except Exception as e:
            print(f"[HelpGallery] 加载项目失败: {e}")
        finally:
            # ★ 无论成功或失败，都删除临时 .wgeo 副本
            try:
                import os
                if os.path.exists(temp_wgeo_path):
                    os.unlink(temp_wgeo_path)
            except Exception:
                pass