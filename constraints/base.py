"""约束基类与注册表。"""
from typing import List, Any, Dict, Type


class GeometricConstraint:
    """几何约束基类。不继承 GeoObject，独立于依赖图。"""
    _next_id = 1

    def __init__(self):
        self.cid = f"c{GeometricConstraint._next_id}"
        GeometricConstraint._next_id += 1
        self.enabled = True
        self.status = "ok"  # ok / conflict / degenerate / invalid_expr

    def involved_points(self) -> List[Any]:
        """返回此约束涉及的所有点对象。"""
        raise NotImplementedError

    def residual(self) -> List[float]:
        """残差向量。约束满足时全为 0。"""
        raise NotImplementedError

    def jacobian(self, vars_map: Dict[int, int]) -> List[List[float]]:
        """数值雅可比矩阵（中心差分）。

        参数:
            vars_map: {id(point): 该点在 free_points 中的索引}

        返回:
            矩阵行数 = len(residual())
            矩阵列数 = 2 * len(vars_map)  ← 每个点贡献 x, y 两列
        """
        eps = 1e-7
        pts = self.involved_points()
        n_res = len(self.residual())
        # ★ 修复：列数 = 2 × 自由点数量（每个点有 x, y 两个变量）
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols for _ in range(n_res)]

        for p in pts:
            if id(p) not in vars_map:
                continue
            idx = vars_map[id(p)]
            for axis in range(2):  # 0=x, 1=y
                old = p.x if axis == 0 else p.y
                # +ε
                if axis == 0:
                    p.x = old + eps
                else:
                    p.y = old + eps
                r_plus = self.residual()

                # −ε
                if axis == 0:
                    p.x = old - eps
                else:
                    p.y = old - eps
                r_minus = self.residual()

                # 恢复
                if axis == 0:
                    p.x = old
                else:
                    p.y = old

                # 中心差分
                for j in range(n_res):
                    jac[j][idx * 2 + axis] = (r_plus[j] - r_minus[j]) / (2 * eps)

        return jac

    # ── 序列化接口 ──
    def dump(self) -> dict:
        raise NotImplementedError

    @classmethod
    def build(cls, point_map: dict, params: dict) -> 'GeometricConstraint':
        raise NotImplementedError


# ── 注册表 ──
CONSTRAINT_REGISTRY: Dict[str, Type[GeometricConstraint]] = {}


def register_constraint(name: str):
    def deco(cls):
        cls.type_name = name
        CONSTRAINT_REGISTRY[name] = cls
        return cls
    return deco