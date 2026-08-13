"""注入 Document.save / load：支持 constraints.json。"""
from core.document import Document
from .base import CONSTRAINT_REGISTRY
import json, zipfile

_original_save = Document.save
_original_load = Document.load

def _new_save(self, path):
    _original_save(self, path)
    if not hasattr(self, 'constraints') or not self.constraints: return
    
    data = []
    for c in self.constraints:
        data.append({
            "id": c.cid,
            "type": c.type_name,
            "params": c.dump()
        })
        
    with zipfile.ZipFile(path, "a") as zf:
        zf.writestr("constraints.json", json.dumps(data, ensure_ascii=False, indent=1))

def _new_load(self, path):
    _original_load(self, path)
    with zipfile.ZipFile(path, "r") as zf:
        if "constraints.json" in zf.namelist():
            data = json.loads(zf.read("constraints.json"))
            point_map = {o.id: o for o in self.objects}
            self.constraints = []
            for item in data:
                cls = CONSTRAINT_REGISTRY.get(item["type"])
                if cls:
                    try:
                        c = cls.build(point_map, item["params"])
                        c.cid = item["id"]
                        self.constraints.append(c)
                    except Exception: pass

def patch_save_load():
    setattr(Document, "save", _new_save)
    setattr(Document, "load", _new_load)