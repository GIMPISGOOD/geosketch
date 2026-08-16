"""注入 Document.save / load：支持 constraints.json。
★ 注意：_load_state 已由 document_ext patch，此处只处理文件级别的约束加载。
"""
from core.document import Document
from .base import CONSTRAINT_REGISTRY
import json
import zipfile

_original_save = Document.save
_original_load = Document.load


def _new_save(self, path):
    _original_save(self, path)
    if not hasattr(self, 'constraints') or not self.constraints:
        return
    data = []
    for c in self.constraints:
        try:
            data.append({
                "id": c.cid,
                "type": c.type_name,
                "params": c.dump()
            })
        except Exception:
            pass
    if data:
        with zipfile.ZipFile(path, "a") as zf:
            zf.writestr("constraints.json",
                        json.dumps(data, ensure_ascii=False, indent=1))


def _new_load(self, path):
    _original_load(self, path)
    # ★ 从文件加载约束（_load_state 已恢复几何对象）
    try:
        with zipfile.ZipFile(path, "r") as zf:
            if "constraints.json" in zf.namelist():
                data = json.loads(zf.read("constraints.json"))
                point_map = {o.id: o for o in self.objects}
                # ★ 不覆盖 _load_state 已恢复的约束，而是合并
                existing_cids = {c.cid for c in getattr(self, 'constraints', [])}
                for item in data:
                    if item.get("id") in existing_cids:
                        continue  # 已由 _load_state 恢复
                    cls = CONSTRAINT_REGISTRY.get(item["type"])
                    if cls:
                        try:
                            c = cls.build(point_map, item["params"])
                            c.cid = item["id"]
                            self.constraints.append(c)
                        except Exception:
                            pass
    except Exception:
        pass


def patch_save_load():
    setattr(Document, "save", _new_save)
    setattr(Document, "load", _new_load)