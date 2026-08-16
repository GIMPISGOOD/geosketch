"""动画序列化：注入 Document.save / load，支持 animations.json。"""
from __future__ import annotations
import json
import zipfile

from core.document import Document
from .clip import AnimationClip

_original_save = Document.save
_original_load = Document.load


def _new_save(self, path):
    _original_save(self, path)
    animations = getattr(self, "animations", [])
    if not animations:
        return
    data = [clip.dump() for clip in animations]
    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr(
            "animations.json",
            json.dumps(data, ensure_ascii=False, indent=1)
        )


def _new_load(self, path):
    _original_load(self, path)
    with zipfile.ZipFile(path, "r") as zf:
        if "animations.json" in zf.namelist():
            data = json.loads(zf.read("animations.json"))
            self.animations = []
            for item in data:
                try:
                    clip = AnimationClip.build(self, item)
                    self.animations.append(clip)
                except Exception:
                    pass


def patch_document():
    # 给 Document 添加 animations 列表
    _original_init = Document.__init__

    def _new_init(self, *args, **kwargs):
        _original_init(self, *args, **kwargs)
        self.animations = []

    setattr(Document, "__init__", _new_init)
    setattr(Document, "save", _new_save)
    setattr(Document, "load", _new_load)