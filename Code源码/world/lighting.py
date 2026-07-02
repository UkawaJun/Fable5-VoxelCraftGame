"""Block-light propagation (point lights like glowstone). 方块光照传播。

每个方块存一个光级 0..15。发光方块(emissive)向外洪泛，每格 -1，被不透明方块阻挡。
结果烘焙进区块网格顶点，夜里萤石/灯笼会真实照亮周围。

性能关键：relight 用 **numpy 向量化传播**（在光源包围盒内迭代 15 次），
而不是逐格 Python BFS —— 这样放一个光源的开销从上万次 Python 循环降到几毫秒。
没有光源时直接清零返回（开销几乎为 0）。
"""

import numpy as np

from settings import CHUNK_SX, CHUNK_SY, CHUNK_SZ
from content.registry import EMISSIVE_LUT, OPAQUE_LUT

SX, SY, SZ = CHUNK_SX, CHUNK_SY, CHUNK_SZ
MAX_LIGHT = 15


def emit_level(block_id: int) -> int:
    e = float(EMISSIVE_LUT[block_id])
    return int(round(e * MAX_LIGHT)) if e > 0 else 0


def _gather_3x3(world, cx, cz):
    """Stitch the 3x3 chunk neighbourhood into one (48,128,48) block array.
    Centre chunk occupies [16:32]. Missing neighbours -> air."""
    W = np.zeros((SX * 3, SY, SZ * 3), dtype=np.uint8)
    for ox in (-1, 0, 1):
        for oz in (-1, 0, 1):
            c = world.chunks.get((cx + ox, cz + oz))
            if c is not None:
                W[(ox + 1) * SX:(ox + 2) * SX, :,
                  (oz + 1) * SZ:(oz + 2) * SZ] = c.blocks
    return W


def relight_chunk(world, chunk):
    """Recompute chunk.light from scratch (vectorised, bounded to emitters)."""
    cx, cz = chunk.cx, chunk.cz
    region = affected_chunks(cx << 4, cz << 4)
    # O(1) early-out: if no chunk in the 3x3 holds a light source, stay dark.
    # 探索时绝大多数区块没有光源，这一步避免昂贵的 295KB 拼接与扫描。
    if not (region & world.emitter_chunks):
        if chunk.light.any():
            chunk.light = np.zeros((SX, SY, SZ), dtype=np.uint8)
        return
    W = _gather_3x3(world, cx, cz)
    seed_full = np.rint(EMISSIVE_LUT[W] * MAX_LIGHT).astype(np.int8)
    if not seed_full.any():                          # index was stale -> clean it
        world.emitter_chunks -= region
        if chunk.light.any():
            chunk.light = np.zeros((SX, SY, SZ), dtype=np.uint8)
        return

    # bounding box of emitters, expanded by the light radius and clipped
    xs, ys, zs = np.nonzero(seed_full)
    x0 = max(0, int(xs.min()) - MAX_LIGHT)
    x1 = min(SX * 3, int(xs.max()) + MAX_LIGHT + 1)
    y0 = max(0, int(ys.min()) - MAX_LIGHT)
    y1 = min(SY, int(ys.max()) + MAX_LIGHT + 1)
    z0 = max(0, int(zs.min()) - MAX_LIGHT)
    z1 = min(SZ * 3, int(zs.max()) + MAX_LIGHT + 1)

    opaque = OPAQUE_LUT[W[x0:x1, y0:y1, z0:z1]]
    seed = seed_full[x0:x1, y0:y1, z0:z1]
    light = seed.copy()
    m = np.empty_like(light)

    for _ in range(MAX_LIGHT):                       # vectorised flood, <=15 passes
        np.copyto(m, light)
        np.maximum(m[1:, :, :],  light[:-1, :, :] - 1, out=m[1:, :, :])
        np.maximum(m[:-1, :, :], light[1:, :, :] - 1,  out=m[:-1, :, :])
        np.maximum(m[:, 1:, :],  light[:, :-1, :] - 1, out=m[:, 1:, :])
        np.maximum(m[:, :-1, :], light[:, 1:, :] - 1,  out=m[:, :-1, :])
        np.maximum(m[:, :, 1:],  light[:, :, :-1] - 1, out=m[:, :, 1:])
        np.maximum(m[:, :, :-1], light[:, :, 1:] - 1,  out=m[:, :, :-1])
        m[opaque] = 0                                # opaque blocks light
        np.maximum(m, seed, out=m)                   # re-assert emitters
        if np.array_equal(m, light):
            break
        light, m = m, light

    full = np.zeros((SX * 3, SY, SZ * 3), dtype=np.int8)
    full[x0:x1, y0:y1, z0:z1] = light
    chunk.light = np.clip(full[SX:2 * SX, :, SZ:2 * SZ],
                          0, MAX_LIGHT).astype(np.uint8)


def affected_chunks(x, z):
    """Chunk keys whose light may change when block (x,*,z) edits.
    Light radius 15 < 16, so only the 3x3 around the edited chunk."""
    cx, cz = x >> 4, z >> 4
    return {(cx + ox, cz + oz) for ox in (-1, 0, 1) for oz in (-1, 0, 1)}
