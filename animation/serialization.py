"""动画序列化：注入 Document 的 save/load 以及 snapshot/_load_state。"""
import json
import zipfile
from core.document import Document
from .clip import AnimationClip

_original_save = Document.save
_original_load = Document.load
_original_snapshot = Document.snapshot
_original_load_state = Document._load_state

# ═══════════════ 文件级保存/加载 ═══════════════
def _new_save(self, path):
    _original_save(self, path)
    animations = getattr(self, "animations", [])
    if not animations: return
    data = [clip.dump() for clip in animations]
    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr("animations.json", json.dumps(data, ensure_ascii=False, indent=1))

def _new_load(self, path):
    _original_load(self, path)
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "animations.json" in zf.namelist():
                data = json.loads(zf.read("animations.json"))
                self.animations = []
                for item in data:
                    try: self.animations.append(AnimationClip.build(self, item))
                    except: pass
    except: pass

# ═══════════════ ★ 内存级撤销/重做支持 ═══════════════
def _new_snapshot(self):
    data = _original_snapshot(self)
    animations = getattr(self, "animations", [])
    if animations:
        c_data = []
        for clip in animations:
            try: c_data.append(clip.dump())
            except: pass
        if c_data:
            data.append({"__animations__": c_data})
    return data

def _new_load_state(self, data):
    anim_data = []
    geo_data = []
    for item in data:
        if isinstance(item, dict) and "__animations__" in item:
            anim_data = item["__animations__"]
        else:
            geo_data.append(item)
            
    _original_load_state(self, geo_data)
    
    if hasattr(self, "animations"):
        self.animations = []
        for item in anim_data:
            try: self.animations.append(AnimationClip.build(self, item))
            except: pass

def patch_document():
    setattr(Document, "save", _new_save)
    setattr(Document, "load", _new_load)
    setattr(Document, "snapshot", _new_snapshot)
    setattr(Document, "_load_state", _new_load_state)