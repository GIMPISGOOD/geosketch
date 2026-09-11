"""光学模块压力测试与性能验证。

覆盖：
1. 大规模场景（多光源、多光线、多平面镜）的追迹性能。
2. 极限反射次数（平行镜死循环防护）。
3. 场景同步缓存与签名机制的有效性（避免无效重算）。
4. 对象频繁创建与删除时的弱引用与内存稳定性。
"""
import time
import physics  # noqa: F401  确保物理对象注册

from geo.points import FreePoint, PointOnObject
from physics.optics.objects import LightSourcePoint, PlaneMirror, LightRay
from physics.optics.scene import sync_optics


class TestOpticsStress:

    def test_many_mirrors_and_rays_performance(self, doc):
        """压力测试：50 条光线，200 面随机平面镜。
        验证追迹算法不会在 O(N*M*K) 复杂度下卡死。
        """
        # 创建 200 面随机平面镜
        mirrors = []
        for i in range(200):
            x = (i % 20) * 2.0
            y = (i // 20) * 2.0
            a = FreePoint(x, y)
            b = FreePoint(x + 1.5, y + 0.5)
            m = PlaneMirror(a, b)
            doc.add(a)
            doc.add(b)
            doc.add(m)
            mirrors.append(m)

        # 创建 50 条光线
        rays = []
        for i in range(50):
            src = LightSourcePoint(-5.0, i * 0.5)
            doc.add(src)
            
            # 让光线射向第一面镜子
            incident = PointOnObject(mirrors[0], 0.5)
            doc.add(incident)
            
            ray = LightRay(src, incident, mirrors[0])
            doc.add(ray)
            rays.append(ray)

        # 测量同步时间
        start = time.perf_counter()
        sync_optics(doc)
        elapsed = time.perf_counter() - start

        # 性能断言：200面镜子 * 50条光线 * 16次反射
        # 在纯 Python 中可能需要几百毫秒，放宽到 2.0 秒以防 CI 机器较慢
        assert elapsed < 2.0, f"大规模场景追迹耗时过长: {elapsed:.2f}s"

        # 验证所有光线都成功计算了路径，没有抛出异常
        for ray in rays:
            assert len(ray.path) >= 2
            assert ray.reflection_count >= 1

    def test_max_reflections_parallel_mirrors(self, doc):
        """极限测试：两面平行镜子，验证最大反射次数截断，防止死循环。"""
        doc.settings.set("physics.optics_max_reflections", 128)
        
        # 底镜 y=0
        a1 = FreePoint(-10, 0)
        b1 = FreePoint(10, 0)
        m1 = PlaneMirror(a1, b1)
        
        # 顶镜 y=5
        a2 = FreePoint(-10, 5)
        b2 = FreePoint(10, 5)
        m2 = PlaneMirror(a2, b2)
        
        doc.add(a1); doc.add(b1); doc.add(m1)
        doc.add(a2); doc.add(b2); doc.add(m2)
        
        # 光源在入射点正上方，确保光线垂直入射，反射后垂直向上
        src = LightSourcePoint(0, 2)
        doc.add(src)
        
        incident = PointOnObject(m1, 0.5) # 入射点 (0,0)
        doc.add(incident)
        
        ray = LightRay(src, incident, m1)
        doc.add(ray)
        
        start = time.perf_counter()
        sync_optics(doc)
        elapsed = time.perf_counter() - start
        
        # 必须在极短时间内完成，证明没有死循环
        assert elapsed < 0.1, f"平行镜追迹耗时异常: {elapsed:.2f}s"
        
        # 验证反射次数被正确截断
        # 初始反射 1 次，后续在 m1 和 m2 之间反弹 127 次，总共 128 次
        assert ray.reflection_count == 128
        # path 包含起点 + 128 个反射点 = 129 个点
        assert len(ray.path) == 129
        assert ray.stop_reason == "max_reflections"

    def test_signature_caching_efficiency(self, doc):
        """缓存测试：验证无关对象变化不会触发光线的实际重算。"""
        a1 = FreePoint(-5, 0)
        b1 = FreePoint(5, 0)
        m1 = PlaneMirror(a1, b1)
        doc.add(a1); doc.add(b1); doc.add(m1)
        
        src = LightSourcePoint(0, 5)
        doc.add(src)
        incident = PointOnObject(m1, 0.5)
        doc.add(incident)
        ray = LightRay(src, incident, m1)
        doc.add(ray)
        
        # 第一次同步，建立缓存
        sync_optics(doc)
        initial_path_id = id(ray.path)
        initial_mirror_version = doc._optics_mirror_version
        
        # 添加一个完全无关的普通几何点
        unrelated_pt = FreePoint(100, 100)
        doc.add(unrelated_pt)
        
        # 第二次同步
        sync_optics(doc)
        
        # 验证镜子签名版本没有改变
        assert doc._optics_mirror_version == initial_mirror_version
        
        # 验证光线的 path 列表对象没有被重新创建（直接复用了缓存）
        # update_trace 内部的短路逻辑应该阻止了重新追迹
        assert id(ray.path) == initial_path_id, "无关对象变化导致了光线追迹缓存失效"

    def test_weakref_cleanup_on_deletion(self, doc):
        """内存与引用测试：验证删除平面镜后，光线不会持有强引用导致内存泄漏。"""
        src = LightSourcePoint(0, 5)
        doc.add(src)
        
        a1 = FreePoint(-5, 0)
        b1 = FreePoint(5, 0)
        m1 = PlaneMirror(a1, b1)
        doc.add(a1); doc.add(b1); doc.add(m1)
        
        incident = PointOnObject(m1, 0.5)
        doc.add(incident)
        
        ray = LightRay(src, incident, m1)
        doc.add(ray)
        
        # 创建几面额外的镜子，让光线在 update_trace 中缓存它们的弱引用
        extra_mirrors = []
        for i in range(5):
            a = FreePoint(i*2, 10)
            b = FreePoint(i*2+1, 10)
            m = PlaneMirror(a, b)
            doc.add(a); doc.add(b); doc.add(m)
            extra_mirrors.append(m)
            
        sync_optics(doc)
        
        # 验证光线内部确实缓存了弱引用
        assert len(ray._mirror_refs) > 0
        
        # 删除所有额外的镜子
        for m in extra_mirrors:
            doc.remove(m)
            
        # 再次同步，触发光线的重算和弱引用清理/重建
        sync_optics(doc)
        
        # 验证新的缓存中不包含已删除的镜子
        # _resolved_cached_mirrors 会过滤掉 exists=False 的对象
        resolved = ray._resolved_cached_mirrors()
        for m in extra_mirrors:
            assert m not in resolved
            
        # 验证光线没有崩溃，且基础路径依然存在
        assert len(ray.path) >= 2