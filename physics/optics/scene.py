"""光学场景同步模块。

职责：
1. 收集当前文档中的平面镜和光线。
2. 在画布渲染 / 拾取前同步光线路径。
3. 解决“非父依赖平面镜移动后光线不重算”的问题。
4. 通过签名机制避免无关变化导致全量追迹。

注意：
- 不在这里增删文档对象。
- 不发射 doc.changed。
- 不修改 Document 核心依赖图。
"""
from __future__ import annotations


def sync_optics(doc, force: bool = False) -> None:
    """同步文档中的光学对象。

    该函数可由 Canvas 在 render_scene / pick 前调用，
    也可在测试中直接调用。
    """
    if doc is None:
        return

    settings = getattr(doc, "settings", None)
    settings_version = getattr(settings, "version", 0)

    # 使用 Document.get_typed 缓存，避免每次扫描全部对象。
    mirror_objs = doc.get_typed("PlaneMirror")
    ray_objs = doc.get_typed("LightRay")

    # 可见性变化未必总触发 _mutation_count，
    # 这里把可见数量纳入 key，保证隐藏 / 显示镜子后能刷新。
    vis_mirror_count = 0
    for o in mirror_objs:
        if getattr(o, "exists", False) and getattr(o, "visible", True):
            vis_mirror_count += 1

    vis_ray_count = 0
    for o in ray_objs:
        if getattr(o, "exists", False) and getattr(o, "visible", True):
            vis_ray_count += 1

    key = (
        getattr(doc, "_mutation_count", 0),
        getattr(doc, "_objects_version", 0),
        settings_version,
        vis_mirror_count,
        vis_ray_count,
    )

    if not force and getattr(doc, "_optics_sync_key", None) == key:
        return

    mirrors = [
        o for o in mirror_objs
        if getattr(o, "exists", False) and getattr(o, "visible", True)
    ]
    rays = [
        o for o in ray_objs
        if getattr(o, "exists", False) and getattr(o, "visible", True)
    ]

    if not rays:
        doc._optics_sync_key = key
        return

    if settings is not None:
        try:
            max_reflections = int(settings.get("physics.optics_max_reflections", 16))
        except Exception:
            max_reflections = 16
        double_sided = bool(settings.get("physics.optics_mirror_double_sided", True))
    else:
        max_reflections = 16
        double_sided = True

    # 性能保护：防止设置中写入异常大值。
    max_reflections = max(1, min(256, max_reflections))

    # 镜子签名：
    # 如果只是无关几何对象变化，但所有可见镜子没变，
    # 则可以让光线跳过实际追迹。
    mirror_items = []
    for m in mirrors:
        try:
            mirror_items.append((
                getattr(m, "id", 0),
                float(m.a.x),
                float(m.a.y),
                float(m.b.x),
                float(m.b.y),
                getattr(m, "hatch_side", "right"),
                bool(getattr(m, "double_sided", double_sided)),
            ))
        except Exception:
            continue

    mirror_sig = (double_sided, tuple(mirror_items))
    old_sig = getattr(doc, "_optics_mirror_sig", None)

    if old_sig != mirror_sig:
        doc._optics_mirror_sig = mirror_sig
        doc._optics_mirror_version = int(getattr(doc, "_optics_mirror_version", 0)) + 1

    mirror_version = int(getattr(doc, "_optics_mirror_version", 0))

    for ray in rays:
        try:
            ray.update_trace(mirrors, max_reflections, double_sided, mirror_version)
        except Exception:
            import traceback
            traceback.print_exc()

    doc._optics_sync_key = key