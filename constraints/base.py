"""约束基类与注册表。"""
from typing import List, Any, Dict, Type

class GeometricConstraint:
    """几何约束基类。"""
    _next_id = 1
    def __init__(self):
        self.cid = f"c{GeometricConstraint._next_id}"
        GeometricConstraint._next_id += 1
        self.enabled = True
        self.status = "ok"

    def involved_points(self) -> List[Any]:
        raise NotImplementedError

    def residual(self) -> List[float]:
        raise NotImplementedError

    def jacobian(self, vars_map: Dict[int, int]) -> List[List[float]]:
        """雅可比矩阵。优先使用解析解，否则使用带异常保护的数值差分。"""
        # ★ 新增：解析雅可比钩子
        analytic = getattr(self, '_jacobian_analytic', None)
        if analytic is not None:
            try:
                return analytic(vars_map)
            except Exception:
                pass

        # 数值差分（中心差分）
        eps = 1e-7
        pts = self.involved_points()
        n_res = len(self.residual())
        n_cols = 2 * len(vars_map)
        jac = [[0.0] * n_cols for _ in range(n_res)]
        
        for p in pts:
            if id(p) not in vars_map:
                continue
            idx = vars_map[id(p)]
            for axis in range(2):
                old = p.x if axis == 0 else p.y
                r_plus = r_minus = None
                try:
                    if axis == 0: p.x = old + eps
                    else: p.y = old + eps
                    r_plus = self.residual()
                    
                    if axis == 0: p.x = old - eps
                    else: p.y = old - eps
                    r_minus = self.residual()
                finally:
                    # ★ 致命修复：无论是否抛出异常，必须恢复坐标，杜绝状态污染
                    if axis == 0: p.x = old
                    else: p.y = old
                
                if r_plus is not None and r_minus is not None:
                    for j in range(min(n_res, len(r_plus), len(r_minus))):
                        jac[j][idx * 2 + axis] = (r_plus[j] - r_minus[j]) / (2 * eps)
        return jac

    def dump(self) -> dict:
        raise NotImplementedError

    @classmethod
    def build(cls, point_map: dict, params: dict) -> 'GeometricConstraint':
        raise NotImplementedError

CONSTRAINT_REGISTRY: Dict[str, Type[GeometricConstraint]] = {}

def register_constraint(name: str):
    def deco(cls):
        cls.type_name = name
        CONSTRAINT_REGISTRY[name] = cls
        return cls
    return deco