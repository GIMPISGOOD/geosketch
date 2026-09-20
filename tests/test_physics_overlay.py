"""测试物理光学工具的实时预览动画 (Overlay) 是否正常渲染。"""
import pytest
from unittest.mock import MagicMock
from PySide6.QtGui import QPainter

from physics.optics.tools import LightSourceTool, PlaneMirrorTool, LightRayTool
from physics.optics.objects import PlaneMirror
from geo.points import FreePoint

@pytest.fixture
def mock_env(qapp):
    """提供 Mock 的 canvas, view 和 painter"""
    canvas = MagicMock()
    canvas.doc = MagicMock()
    canvas.doc.objects = []
    canvas.scale = 1.0
    
    # Mock QPointF 行为，避免 Qt 底层对象在 Mock 中报错
    class MockQPointF:
        def __init__(self, x, y):
            self._x = x
            self._y = y
        def x(self): return self._x
        def y(self): return self._y
            
    view = MagicMock()
    view.to_screen.side_effect = lambda x, y: MockQPointF(x, y)
    
    painter = MagicMock(spec=QPainter)
    return canvas, view, painter

def test_light_source_overlay(mock_env):
    """测试点光源工具的预览圆"""
    canvas, view, p = mock_env
    tool = LightSourceTool()
    tool.activated(canvas)
    
    # 初始状态无光标，不绘制
    tool.draw_overlay(p, view)
    assert not p.drawEllipse.called
    
    # 移动后绘制预览圆
    tool.move(canvas, (10.0, 10.0), None)
    tool.draw_overlay(p, view)
    assert p.drawEllipse.called

def test_plane_mirror_overlay(mock_env):
    """测试平面镜工具的预览虚线和端点圆"""
    canvas, view, p = mock_env
    tool = PlaneMirrorTool()
    tool.activated(canvas)
    
    # state 0 (未点击第一个点) 时不绘制
    tool.move(canvas, (10.0, 10.0), None)
    tool.draw_overlay(p, view)
    assert not p.drawLine.called
    
    # 模拟第一步完成，进入 state 1
    tool.state = 1
    tool.a = FreePoint(0, 0)
    tool.cursor = (10.0, 10.0)
    tool.draw_overlay(p, view)
    assert p.drawLine.called
    assert p.drawEllipse.called

def test_light_ray_overlay(mock_env):
    """测试光线工具的预览入射线和镜面吸附圆"""
    canvas, view, p = mock_env
    tool = LightRayTool()
    tool.activated(canvas)
    
    # state 0 (未选择光源) 时不绘制
    tool.move(canvas, (10.0, 10.0), None)
    tool.draw_overlay(p, view)
    assert not p.drawLine.called
    
    # 模拟第一步完成，进入 state 1 (已选择光源)
    tool.state = 1
    tool.source = FreePoint(0, 0)
    tool.cursor = (10.0, 10.0)
    tool.hover = None
    tool.draw_overlay(p, view)
    assert p.drawLine.called
    assert not p.drawEllipse.called # 没悬停在镜子上，不画终点圆
    
    # 悬停在平面镜上时，绘制终点吸附圆
    p.reset_mock()
    tool.hover = MagicMock(spec=PlaneMirror)
    tool.draw_overlay(p, view)
    assert p.drawLine.called
    assert p.drawEllipse.called