"""Terrain generation: pure function f(seed, cx, cz) -> block array.

地形生成是纯函数：同一种子永远生成同一地形。
未被玩家修改过的区块不存盘，按需重算 —— 存档体积极小。

Pipeline (all numpy, no per-block python loops except trees):
  heightmap = FBM perlin -> rolling hills + ridged mountains
  biome     = low-freq temperature noise -> snow / grass / desert
  layers    = bedrock | stone | dirt | surface | water  (vectorised fills)
  trees     = deterministic hash per column (margin band for cross-chunk trees)
"""

import numpy as np

from settings import CHUNK_SX, CHUNK_SY, CHUNK_SZ, SEA_LEVEL
from world.perlin import Perlin, hash_pos
from content.registry import block_id

_MARGIN = 3  # tree influence margin (trees up to 3 blocks outside the chunk)

_perlin_cache = {}


def _perlin(seed) -> Perlin:
    if seed not in _perlin_cache:
        _perlin_cache[seed] = Perlin(seed)
    return _perlin_cache[seed]


def _height_biome(seed, wxs, wzs):
    """Heightmap + biome for arbitrary world-coord grids (vectorised)."""
    p = _perlin(seed)
    X, Z = np.meshgrid(wxs, wzs, indexing="ij")

    base = p.fbm(X / 120.0, Z / 120.0, octaves=4)              # rolling hills
    ridge = 1.0 - np.abs(p.fbm(X / 260.0 + 512.3, Z / 260.0 - 512.3, octaves=3))
    mountains = np.clip(ridge - 0.55, 0.0, None) ** 2 * 90.0   # sparse peaks

    height = SEA_LEVEL + 3.0 + base * 9.0 + mountains
    height = np.clip(height, 2, CHUNK_SY - 10).astype(np.int32)

    temp = p.fbm(X / 320.0 + 7777.7, Z / 320.0 - 7777.7, octaves=3)
    # biome codes: 0 grass, 1 desert, 2 snow
    biome = np.zeros_like(height, dtype=np.int8)
    biome[temp > 0.45] = 1
    biome[temp < -0.40] = 2
    return height, biome


def generate_chunk(seed: int, cx: int, cz: int) -> np.ndarray:
    SX, SY, SZ = CHUNK_SX, CHUNK_SY, CHUNK_SZ
    b_air = 0
    b_grass = block_id("grass")
    b_dirt = block_id("dirt")
    b_stone = block_id("stone")
    b_sand = block_id("sand")
    b_water = block_id("water")
    b_snow = block_id("snow_grass")
    b_bedrock = block_id("bedrock")
    b_log = block_id("log")
    b_leaves = block_id("leaves")

    # extended grid (margin for cross-chunk trees)
    wxs = np.arange(cx * SX - _MARGIN, cx * SX + SX + _MARGIN)
    wzs = np.arange(cz * SZ - _MARGIN, cz * SZ + SZ + _MARGIN)
    height_ext, biome_ext = _height_biome(seed, wxs, wzs)

    m = _MARGIN
    height = height_ext[m:m + SX, m:m + SZ]      # (16,16)
    biome = biome_ext[m:m + SX, m:m + SZ]

    # ---- vectorised layer fill, working shape (SX, SZ, SY) ----
    ys = np.arange(SY)[None, None, :]            # (1,1,SY)
    h = height[:, :, None]                       # (SX,SZ,1)
    arr = np.zeros((SX, SZ, SY), dtype=np.uint8)

    arr[(ys < h - 3) & (ys > 0)] = b_stone
    dirt_mask = (ys >= h - 3) & (ys < h)
    arr[dirt_mask] = b_dirt

    # surface block by biome / altitude
    surf = np.where(biome == 1, b_sand,
                    np.where(biome == 2, b_snow, b_grass)).astype(np.uint8)
    beach = height <= SEA_LEVEL + 1                  # under/near water -> sand
    surf = np.where(beach, b_sand, surf)
    sx_idx, sz_idx = np.meshgrid(np.arange(SX), np.arange(SZ), indexing="ij")
    arr[sx_idx, sz_idx, height] = surf

    # water above terrain up to sea level
    water_mask = (ys > h) & (ys <= SEA_LEVEL)
    arr[water_mask & (arr == b_air)] = b_water

    arr[:, :, 0] = b_bedrock

    blocks = arr.swapaxes(1, 2).copy()           # -> (SX, SY, SZ)

    # ---- trees (deterministic, only grass biome, above water) ----
    x0, z0 = cx * SX, cz * SZ
    for ix in range(-m, SX + m):
        for iz in range(-m, SZ + m):
            wx, wz = x0 + ix, z0 + iz
            hcol = int(height_ext[ix + m, iz + m])
            if biome_ext[ix + m, iz + m] != 0 or hcol <= SEA_LEVEL + 1:
                continue
            if hash_pos(seed, wx, wz) % 53 != 0:
                continue
            trunk_h = 4 + hash_pos(seed + 1, wx, wz) % 3   # 4..6
            top = hcol + trunk_h
            if top + 2 >= SY:
                continue
            # trunk
            for y in range(hcol + 1, top + 1):
                _put(blocks, ix, y, iz, b_log)
            # leaves: two 5x5 layers, one 3x3, one plus-shape
            for dy, r in ((-2, 2), (-1, 2), (0, 1)):
                for dx in range(-r, r + 1):
                    for dz in range(-r, r + 1):
                        if abs(dx) == 2 and abs(dz) == 2:
                            continue          # cut corners
                        _put_leaf(blocks, ix + dx, top + dy, iz + dz, b_leaves)
            for dx, dz in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)):
                _put_leaf(blocks, ix + dx, top + 1, iz + dz, b_leaves)

    # stamp any village pieces that fall in this chunk (lazy import: avoid cycle)
    from world import structures
    structures.stamp_chunk(seed, cx, cz, blocks)
    return blocks


def _put(blocks, x, y, z, bid):
    if 0 <= x < CHUNK_SX and 0 <= y < CHUNK_SY and 0 <= z < CHUNK_SZ:
        blocks[x, y, z] = bid


def _put_leaf(blocks, x, y, z, bid):
    if 0 <= x < CHUNK_SX and 0 <= y < CHUNK_SY and 0 <= z < CHUNK_SZ:
        if blocks[x, y, z] == 0:
            blocks[x, y, z] = bid


def surface_height(seed: int, wx: int, wz: int) -> int:
    """Terrain height at a single column (for spawn point). 单列高度查询。"""
    h, _ = _height_biome(seed, np.array([wx]), np.array([wz]))
    return int(h[0, 0])
