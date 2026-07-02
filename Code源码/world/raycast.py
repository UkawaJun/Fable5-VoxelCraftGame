"""Voxel ray traversal (Amanatides & Woo DDA).

体素射线遍历：返回 (命中方块坐标, 命中面法线)。
破坏方块用前者；放置方块用 坐标+法线。
"""

import math

from content.registry import SOLID_LUT


def raycast(world, origin, direction, max_dist: float):
    ox, oy, oz = origin
    dx, dy, dz = direction
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-9:
        return None
    dx, dy, dz = dx / length, dy / length, dz / length

    x, y, z = math.floor(ox), math.floor(oy), math.floor(oz)

    step_x = 1 if dx > 0 else -1
    step_y = 1 if dy > 0 else -1
    step_z = 1 if dz > 0 else -1

    inf = float("inf")
    t_delta_x = abs(1.0 / dx) if dx != 0 else inf
    t_delta_y = abs(1.0 / dy) if dy != 0 else inf
    t_delta_z = abs(1.0 / dz) if dz != 0 else inf

    def frac(v):
        return v - math.floor(v)

    t_max_x = t_delta_x * ((1.0 - frac(ox)) if dx > 0 else frac(ox)) if dx != 0 else inf
    t_max_y = t_delta_y * ((1.0 - frac(oy)) if dy > 0 else frac(oy)) if dy != 0 else inf
    t_max_z = t_delta_z * ((1.0 - frac(oz)) if dz > 0 else frac(oz)) if dz != 0 else inf

    face = (0, 0, 0)
    t = 0.0
    while t <= max_dist:
        bid = world.get_block(x, y, z)
        if bid != 0 and SOLID_LUT[bid]:
            return (x, y, z), face
        if t_max_x < t_max_y:
            if t_max_x < t_max_z:
                x += step_x
                t = t_max_x
                t_max_x += t_delta_x
                face = (-step_x, 0, 0)
            else:
                z += step_z
                t = t_max_z
                t_max_z += t_delta_z
                face = (0, 0, -step_z)
        else:
            if t_max_y < t_max_z:
                y += step_y
                t = t_max_y
                t_max_y += t_delta_y
                face = (0, -step_y, 0)
            else:
                z += step_z
                t = t_max_z
                t_max_z += t_delta_z
                face = (0, 0, -step_z)
    return None


def raycast_entity(world, origin, direction, max_dist):
    """Nearest mob whose AABB the ray hits within max_dist.
    Returns (entity, distance) or None. 射线命中最近的生物(攻击用)。"""
    import math as _m
    ox, oy, oz = origin
    dx, dy, dz = direction
    length = _m.sqrt(dx * dx + dy * dy + dz * dz)
    if length < 1e-9:
        return None
    dx, dy, dz = dx / length, dy / length, dz / length

    best = None
    best_t = max_dist
    for e in world.entities:
        if getattr(e, "TYPE_NAME", "") == "primed_tnt" or e.dead:
            continue
        hw = e.AABB_SIZE[0] * 0.5
        hd = e.AABB_SIZE[2] * 0.5
        mn = (e.pos[0] - hw, e.pos[1], e.pos[2] - hd)
        mx = (e.pos[0] + hw, e.pos[1] + e.AABB_SIZE[1], e.pos[2] + hd)
        t = _ray_aabb((ox, oy, oz), (dx, dy, dz), mn, mx)
        if t is not None and 0.0 <= t < best_t:
            best_t = t
            best = e
    return (best, best_t) if best is not None else None


def _ray_aabb(o, d, mn, mx):
    """Slab method. Returns entry distance t>=0 or None."""
    tmin, tmax = 0.0, float("inf")
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if o[i] < mn[i] or o[i] > mx[i]:
                return None
        else:
            inv = 1.0 / d[i]
            t1 = (mn[i] - o[i]) * inv
            t2 = (mx[i] - o[i]) * inv
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return None
    return tmin
