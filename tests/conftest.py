import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """全局 Qt 环境。"""
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def clean_variables():
    """每个测试隔离变量系统。"""
    from core.variables import get_store

    store = get_store()
    saved_vars = dict(store._vars)
    saved_version = store.version

    yield

    store._vars = saved_vars
    store.version = saved_version


@pytest.fixture
def doc():
    """新建一个空文档。"""
    from core.document import Document
    return Document()


@pytest.fixture
def canvas(doc, qapp):
    """离屏画布。"""
    try:
        from ui.canvas import Canvas
    except Exception as e:
        pytest.skip(f"无法创建 Canvas：{e}")

    c = Canvas(doc)
    c.resize(420, 320)

    c.origin = QPointF(210.0, 160.0)
    c.scale = 40.0
    c._origin_ready = True
    c.cursor_wpt = (0.0, 0.0)

    return c