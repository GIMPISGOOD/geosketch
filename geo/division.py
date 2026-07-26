"""等分点：由两个端点 + 固定比例 t 确定的从动点。
拖动任一端点时按比例重算，始终保持等分；自身不可拖动（draggable 默认 False）。"""
from core.registry import register_geo
from geo.points import AbstractPoint


@register_geo("DivisionPoint")
class DivisionPoint(AbstractPoint):
    def __init__(self, a, b, t):
        super().__init__(parents=(a, b))
        self.a, self.b, self.t = a, b, float(t)
        self.recompute()

    def recompute(self):
        self.x = self.a.x + (self.b.x - self.a.x) * self.t
        self.y = self.a.y + (self.b.y - self.a.y) * self.t

    def dump(self):
        return {"t": self.t}

    @classmethod
    def build(cls, parents, params):
        return cls(parents[0], parents[1], params["t"])