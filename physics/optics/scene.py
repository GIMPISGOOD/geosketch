"""光学场景同步模块。

职责
────
1. 收集当前文档中的光学表面与光线。
2. 在画布渲染 / 拾取前同步光线路径。
3. 解决"非父依赖表面移动后光线不重算"的问题。
4. 通过签名机制避免无关变化导致全量追迹。

设计原则
────────
- 不增删文档对象。
- 不发射 ``doc.changed``。
- 不修改 Document 核心依赖图。
- 不硬编码具体光学类型：只通过 ``OpticalSurface`` 基类交互。
"""
from __future__ import annotations

from physics.optics.surfaces import OpticalSurface


def _scan_document(doc):
    """扫描文档，返回 (all_surfaces, all_rays)。

    结果按 ``doc._objects_version`` 缓存。
    只过滤"是不是光学对象"，不过滤 visible / exists，
    后者在调用方处理，以便可见性变化无需重新扫描。
    """
    cached_version = getattr(doc, "_optics_scan_version", -1)
    cached = getattr(doc, "_optics_scan_result", None)
    if cached_version == doc._objects_version and cached is not None:
        return cached

    all_surfaces = []
    all_rays = []
    for o in doc.objects:
        if isinstance(o, OpticalSurface):
            all_surfaces.append(o)
        elif getattr(o, "type_name", None) == "LightRay":
            all_rays.append(o)

    result = (all_surfaces, all_rays)
    doc._optics_scan_version = doc._objects_version
    doc._optics_scan_result = result
    return result


def sync_optics(doc, force: bool = False) -> None:
    """同步文档中的光学对象。

    该函数可由 Canvas 在 render_scene / pick 前调用，
    也可在测试中直接调用。
    """
    if doc is None:
        return

    settings = getattr(doc, "settings", None)
    settings_version = getattr(settings, "version", 0)

    all_surfaces, all_rays = _scan_document(doc)

    surfaces = []
    rays = []
    vis_surface_ids = []
    vis_ray_ids = []

    for o in all_surfaces:
        if getattr(o, "exists", False) and getattr(o, "visible", True):
            surfaces.append(o)
            vis_surface_ids.append(getattr(o, "id", 0))

    for o in all_rays:
        if getattr(o, "exists", False) and getattr(o, "visible", True):
            rays.append(o)
            vis_ray_ids.append(getattr(o, "id", 0))

    key = (
        getattr(doc, "_mutation_count", 0),
        getattr(doc, "_objects_version", 0),
        settings_version,
        tuple(sorted(vis_surface_ids)),
        tuple(sorted(vis_ray_ids)),
    )
    if not force and getattr(doc, "_optics_sync_key", None) == key:
        return

    if not rays:
        doc._optics_sync_key = key
        return

    if settings is not None:
        try:
            max_reflections = int(
                settings.get("physics.optics_max_reflections", 16)
            )
        except Exception:
            max_reflections = 16
    else:
        max_reflections = 16

    max_reflections = max(1, min(256, max_reflections))

    # ── 表面签名：由各表面自己计算，scene 不做类型分派 ──
    surface_items = []
    for s in surfaces:
        try:
            surface_items.append(
                (getattr(s, "id", 0), s.optics_signature())
            )
        except Exception:
            continue

    surface_sig = tuple(surface_items)
    old_sig = getattr(doc, "_optics_mirror_sig", None)

    if old_sig != surface_sig:
        doc._optics_mirror_sig = surface_sig
        doc._optics_mirror_version = (
            int(getattr(doc, "_optics_mirror_version", 0)) + 1
        )

    surface_version = int(getattr(doc, "_optics_mirror_version", 0))

    for ray in rays:
        try:
            ray.update_trace(surfaces, max_reflections, surface_version)
        except Exception:
            import traceback
            traceback.print_exc()

    doc._optics_sync_key = key