"""多平面镜连续反射与无限延伸测试。

覆盖：
1. 单镜反射后无限延伸
2. 双镜连续反射
3. 最大反射次数限制
4. 后续新增平面镜后光线自动更新
5. 隐藏平面镜后不再参与反射
6. 保存 / 加载后多镜光路恢复
"""
import physics  # noqa: F401  确保物理对象注册

from core.document import Document
from geo.points import FreePoint, PointOnObject
from physics.optics.objects import LightSourcePoint, PlaneMirror, LightRay
from physics.optics.scene import sync_optics


def _get_rays(doc):
    return [o for o in doc.objects if isinstance(o, LightRay)]


def _make_single_mirror(doc):
    """光源从 (0,1) 射向水平镜面 (0,0)，反射后向上无限延伸。"""
    src = LightSourcePoint(0, 1)

    a = FreePoint(-1, 0)
    b = FreePoint(1, 0)
    mirror = PlaneMirror(a, b)

    doc.add(src)
    doc.add(a)
    doc.add(b)
    doc.add(mirror)

    incident = PointOnObject(mirror, 0.5)
    doc.add(incident)

    ray = LightRay(src, incident, mirror)
    doc.add(ray)

    return src, mirror, incident, ray


def _make_two_mirrors(doc):
    """光源 (-1,1) 射向水平镜 (0,0)，反射后击中竖直镜 x=2。"""
    src = LightSourcePoint(-1, 1)

    a1 = FreePoint(-1, 0)
    b1 = FreePoint(1, 0)
    m1 = PlaneMirror(a1, b1)

    doc.add(src)
    doc.add(a1)
    doc.add(b1)
    doc.add(m1)

    incident = PointOnObject(m1, 0.5)
    doc.add(incident)

    ray = LightRay(src, incident, m1)
    doc.add(ray)

    a2 = FreePoint(2, -1)
    b2 = FreePoint(2, 3)
    m2 = PlaneMirror(a2, b2)

    doc.add(a2)
    doc.add(b2)
    doc.add(m2)

    return src, m1, m2, incident, ray


class TestMultiMirrorOptics:

    def test_single_mirror_infinite(self, doc):
        _, mirror, _, ray = _make_single_mirror(doc)
        sync_optics(doc)

        assert ray.exists
        assert len(ray.path) == 2
        assert ray.infinite is True
        assert ray.last_dir is not None

        # 入射方向向下，水平镜反射后应向上。
        assert abs(ray.last_dir[0]) < 1e-6
        assert ray.last_dir[1] > 0.9

        # 无限延伸射线上的点应可被拾取。
        assert ray.distance_to(0, 5) < 1e-6

    def test_two_mirror_reflection(self, doc):
        _, m1, m2, _, ray = _make_two_mirrors(doc)
        sync_optics(doc)

        # path 应为：光源 -> 初始入射点 -> 第二面镜子命中点。
        assert len(ray.path) == 3
        assert ray.reflection_count == 2
        assert ray.infinite is True

        hit = ray.path[2]
        assert abs(hit[0] - 2.0) < 1e-6
        assert abs(hit[1] - 2.0) < 1e-6

    def test_max_reflections_limits_secondary(self, doc):
        _make_two_mirrors(doc)
        doc.settings.set("physics.optics_max_reflections", 1)
        sync_optics(doc)

        rays = _get_rays(doc)
        assert len(rays) == 1
        ray = rays[0]

        # max=1 时只允许初始镜反射，不允许第二面镜子反射。
        assert ray.reflection_count == 1
        assert len(ray.path) == 2
        assert ray.infinite is True

    def test_add_mirror_later(self, doc):
        # 构造一个斜向反射的场景，避免平行镜导致的无限反弹
        src = LightSourcePoint(-1, 1)
        a1 = FreePoint(-1, 0)
        b1 = FreePoint(1, 0)
        m1 = PlaneMirror(a1, b1)
        
        doc.add(src)
        doc.add(a1)
        doc.add(b1)
        doc.add(m1)
        
        incident = PointOnObject(m1, 0.5) # 入射点在 (0, 0)
        doc.add(incident)
        
        ray = LightRay(src, incident, m1)
        doc.add(ray)
        
        sync_optics(doc)
        
        # 初始反射：(-1,1) -> (0,0) -> 方向(1,1) 无限延伸
        assert len(ray.path) == 2
        assert ray.reflection_count == 1
        
        # 在反射光线路径上 (x=2) 新增一面竖直镜，应产生第二次反射。
        a2 = FreePoint(2, -1)
        b2 = FreePoint(2, 3)
        m2 = PlaneMirror(a2, b2)
        
        doc.add(a2)
        doc.add(b2)
        doc.add(m2)
        
        sync_optics(doc)
        
        # 击中 x=2, y=2 的点，然后向左反射，不再击中 m1
        assert len(ray.path) == 3
        assert ray.reflection_count == 2
        assert ray.infinite is True
        
        hit = ray.path[2]
        assert abs(hit[0] - 2.0) < 1e-6
        assert abs(hit[1] - 2.0) < 1e-6

    def test_hidden_mirror_not_reflect(self, doc):
        _, m1, m2, _, ray = _make_two_mirrors(doc)
        sync_optics(doc)

        assert len(ray.path) == 3

        # 隐藏第二面镜子后，应不再参与反射。
        m2.visible = False
        sync_optics(doc)

        assert len(ray.path) == 2
        assert ray.reflection_count == 1

    def test_save_load_multiray(self, doc, tmp_path):
        _make_two_mirrors(doc)
        sync_optics(doc)

        path = tmp_path / "optics_multi.wgeo"
        doc.save(str(path))

        doc2 = Document()
        doc2.load(str(path))
        sync_optics(doc2)

        rays = _get_rays(doc2)
        assert len(rays) == 1

        ray = rays[0]
        assert ray.exists
        assert len(ray.path) == 3
        assert ray.reflection_count == 2
        assert ray.infinite is True