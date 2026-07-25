"""主题：浅色纸面风格。颜色 / 画笔 / 字体集中管理。"""
from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPen

# 画布：纸白纵向渐变
BG_TOP = QColor("#f8fafd")
BG_BOTTOM = QColor("#eaeff7")

# 网格与坐标轴（蓝灰系，层次分明）
GRID_MINOR = QColor(96, 125, 168, 26)      # 次网格
GRID_MAJOR = QColor(96, 125, 168, 62)      # 主网格（每 5 格）
AXIS = QColor("#33517e")                   # 坐标轴：深钢蓝，明确分界

# 几何对象
POINT_FILL = QColor("#f08c00")             # 琥珀点
POINT_RING = QColor("#ffffff")             # 白色描边，浅底上更醒目
SEGMENT = QColor("#1971c2")                # 湛蓝线段
CIRCLE = QColor("#2f9e44")                 # 预留：圆
SELECTED = QColor("#e64980")               # 选中高亮
PREVIEW = QColor("#f08c00")                # 橡皮筋 / 预览
LABEL = QColor("#46566e")                  # 刻度 / 点名

# 界面
ICON_INK = QColor("#33415c")
ACCENT = QColor("#1971c2")


def pen(color: QColor, width: float = 1.0) -> QPen:
    return QPen(QColor(color), float(width))


def dashed_pen(color: QColor, width: float = 1.0) -> QPen:
    p = QPen(QColor(color), float(width), Qt.PenStyle.DashLine)
    p.setDashPattern([6, 4])
    return p


def brush(color: QColor) -> QBrush:
    return QBrush(QColor(color))


LABEL_FONT = QFont("Consolas", 9)
LABEL_FONT.setStyleHint(QFont.StyleHint.Monospace)

AXIS_FONT = QFont("Georgia", 11, QFont.Weight.DemiBold)   # 斜体衬线，数学标注感
AXIS_FONT.setItalic(True)

INTERSECT = QColor("#0c8599")     # 交点：青蓝，暗示"派生点"身份