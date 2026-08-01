import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """模型层测试也需要 Qt 环境（geo 模块导入时会创建 QFont）。"""
    app = QApplication.instance() or QApplication([])
    yield app