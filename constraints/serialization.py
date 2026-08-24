"""约束文件级序列化。
★ 不再做猴子补丁。逻辑已整合到 core/document.py 的 save/load。
"""


def patch_save_load():
    """已废弃：序列化逻辑已原生集成到 Document。"""
    pass