# geo/base.py
"""几何对象基类。

⚠ 分层铁律：本文件是最底层依赖，禁止 import geo/ 内任何模块
  （尤其是 points / segments 等子类），否则必然循环导入。
  依赖方向是单向的：points/segments → base，绝不反向。

两条支撑全局的不变量：
  1. 对象总在依赖之后创建 → 创建顺序天然是拓扑序
  2. 对象绝不缓存父对象的状态，一切在 recompute() 里现算
"""


class GeoObject:
    type_name = None          # 由 @register_geo 设置
    draggable = False         # 能否被鼠标直接拖动
    _next_id = 0

    def __init__(self, parents=()):
        GeoObject._next_id += 1
        self.id = GeoObject._next_id
        self.parents = list(parents)
        self.children = []
        for p in self.parents:
            p.children.append(self)
        self.visible = True
        self.selected = False
        self.exists = True

    @classmethod
    def bump_ids(cls, n):
        cls._next_id = max(cls._next_id, n)

    @classmethod
    def reset_ids(cls):
        cls._next_id = 0

    def recompute(self):
        """根据 parents 更新自身状态。自由对象（无依赖）无需实现。"""

    def distance_to(self, x, y):
        """世界坐标 (x,y) 到本对象的距离；返回 None 表示不可拾取。"""
        return None

    # ---- 序列化接口（与 @register_geo 配套）----
    def dump(self) -> dict:
        """导出自由参数（不由 parents 决定的那部分）。"""
        return {}

    @classmethod
    def build(cls, parents, params):
        """dump 的逆操作：从 parents + params 重建对象。"""
        raise NotImplementedError(f"{cls.__name__} 未实现 build()")