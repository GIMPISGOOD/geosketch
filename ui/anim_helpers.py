"""UI 动效工具函数。

所有面板/菜单/对话框的过渡动画统一调用此模块，
不再各自编写 ``QPropertyAnimation``。

对外契约：
    set_settings · should_animate · slide_width · fade_widget
"""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPropertyAnimation
from PySide6.QtWidgets import QWidget

_active_settings = None


def set_settings(settings_store) -> None:
    """注入当前文档的 SettingsStore（由 MainWindow 初始化时调用）。"""
    global _active_settings
    _active_settings = settings_store


def should_animate() -> bool:
    """总开关：``effects.enabled``。为 False 时所有动效直接跳到终态。"""
    if _active_settings is None:
        return True
    return bool(_active_settings.get("effects.enabled", True))


def panel_duration() -> int:
    """面板动画时长（ms），0 表示无动画。"""
    if _active_settings is None:
        return 200
    return int(_active_settings.get("effects.panel_toggle_ms", 200))


def slide_width(widget: QWidget,
                start_w: int,
                end_w: int,
                duration_ms: int,
                on_finish=None) -> QPropertyAnimation | None:
    """水平宽度滑动动画。

    参数
    ----
    widget      目标控件（动画期间 ``minimumWidth`` 被设为 0）
    start_w     起始宽度 (px)
    end_w       终止宽度 (px)
    duration_ms 动画时长；<= 0 时直接跳到终态
    on_finish   动画结束后的回调（如 ``setFixedWidth`` / ``reposition``）

    返回
    ----
    QPropertyAnimation 实例（调用方应持有引用防 GC），
    或 ``None``（直接跳到终态时）。
    """
    if not should_animate() or duration_ms <= 0:
        widget.setMinimumWidth(end_w)
        widget.setMaximumWidth(end_w)
        if on_finish is not None:
            on_finish()
        return None

    widget.setMinimumWidth(0)
    widget.setMaximumWidth(start_w)

    anim = QPropertyAnimation(widget, b"maximumWidth")
    anim.setDuration(duration_ms)
    anim.setStartValue(start_w)
    anim.setEndValue(end_w)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    def _cleanup():
        widget.setMinimumWidth(end_w)
        if on_finish is not None:
            on_finish()

    anim.finished.connect(_cleanup)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def fade_widget(widget: QWidget,
                target_opacity: float,
                duration_ms: int = 150,
                on_finish=None) -> QPropertyAnimation | None:
    """控件淡入 / 淡出。

    参数
    ----
    target_opacity  目标不透明度（0.0 = 全透明，1.0 = 不透明）
    """
    from PySide6.QtWidgets import QGraphicsOpacityEffect

    if not should_animate() or duration_ms <= 0:
        widget.setWindowOpacity(target_opacity)
        if on_finish is not None:
            on_finish()
        return None

    effect = widget.graphicsEffect()
    if not isinstance(effect, QGraphicsOpacityEffect):
        effect = QGraphicsOpacityEffect(widget)
        widget.setGraphicsEffect(effect)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration_ms)
    anim.setStartValue(effect.opacity())
    anim.setEndValue(target_opacity)
    anim.setEasingCurve(QEasingCurve.Type.InOutQuad)

    if on_finish is not None:
        anim.finished.connect(on_finish)
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim