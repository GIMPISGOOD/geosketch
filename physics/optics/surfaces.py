"""光学表面抽象基类。

设计契约
────────
任何想要参与 ``trace_light_path`` 的对象，继承 ``OpticalSurface``
并实现两个方法即可：

- ``ray_hit(origin, direction)``
    射线与表面的最近正向交点。
- ``interact(hit_point, direction)``
    给定命中点与入射方向，返回交互结果。

``tracer.trace_light_path`` 与 ``scene.sync_optics`` 都不再知道
"平面镜 / 折射面 / 透镜 / 光阑" 这些具体类型，只通过本接口交互。

签名缓存
────────
``optics_signature()`` 返回一个可哈希元组，用于 ``scene.sync_optics``
判断"影响追迹的属性是否变化"。默认返回空元组，子类应覆写以包含
所有会影响光线传播的几何与物理属性。
"""
from __future__ import annotations

from geo.base import GeoObject


class OpticalSurface(GeoObject):
    """可参与光线追迹的光学表面（mixin 式基类）。

    子类必须实现 ``ray_hit`` 与 ``interact``。
    ``OpticalSurface`` 自身不覆写 ``__init__``，
    以便与 ``Segment`` / ``Circle`` / ``DirectedLine`` 等几何基类
    做多重继承时，MRO 正确落到 ``GeoObject.__init__``。
    """

    # 该表面的一次交互是否占用 ``max_reflections`` 配额。
    # 镜面 / 折射面默认占用；未来的光屏 / 探测器可覆写为 False。
    consumes_interaction_budget: bool = True

    # ──────────────────────────────────────────────
    #  必须实现的接口
    # ──────────────────────────────────────────────

    def ray_hit(self, origin, direction):
        """射线与表面的最近正向交点。

        参数
        ----
        origin : (float, float)
        direction : (float, float)，单位向量

        返回
        ----
        (t, hit_x, hit_y) 或 None
            ``t > 0`` 是沿 ``direction`` 的参数距离。
            返回 ``None`` 表示未命中。
        """
        raise NotImplementedError(
            f"{type(self).__name__} 未实现 ray_hit()"
        )

    def interact(self, hit_point, direction):
        """给定命中点与入射方向，计算交互结果。

        参数
        ----
        hit_point : (float, float)
        direction : (float, float)，单位向量，从光源指向命中点

        返回
        ----
        dict:
            {
                "kind": "reflect" | "refract" | "absorb",
                "direction": (dx, dy) | None,  # None 表示终止追迹
                "reason": str,                  # 供 stop_reason 使用
            }

        - ``reflect``：方向为反射方向，占用交互配额。
        - ``refract``：方向为折射方向，占用交互配额。
        - ``absorb``：方向为 None，终止追迹。
        """
        raise NotImplementedError(
            f"{type(self).__name__} 未实现 interact()"
        )

    # ──────────────────────────────────────────────
    #  可选覆写
    # ──────────────────────────────────────────────

    def is_active_for_ray(self, direction):
        """该表面在当前入射方向下是否活跃。

        单面镜返回 False 以拒绝背面入射；双面镜始终返回 True。
        默认返回 True。
        """
        return True

    def optics_signature(self):
        """影响追迹的属性签名，用于 scene 缓存失效判断。

        默认返回空元组。子类应覆写以包含所有几何与物理属性。
        """
        return ()