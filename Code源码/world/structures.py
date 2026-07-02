"""Naturally-generated villages. 自然生成的村庄。

确定性、均匀分布：世界按 REGION×REGION 区块划分，每个区域按哈希概率放一个村庄，
位置在区域内抖动。一个村庄 = 1 口水井(含无限水源) + 3~5 栋房屋(3 种模板)。
村庄可能跨多个区块，生成时每个区块只写入落在自己范围内的那部分（跨区块拼接）。
"""

import numpy as np

from settings import CHUNK_SX, CHUNK_SY, CHUNK_SZ, SEA_LEVEL
from world.perlin import hash_pos
from world.terrain import surface_height
from content.registry import block_id

REGION = 9                 # chunks per village region (~144 blocks)
VILLAGE_CHANCE = 65        # percent of regions that contain a village
_EXTENT = 20               # village reach from centre (blocks)

# resolve block ids once
def _bid():
    names = ["air", "cobblestone", "planks", "spruce_planks", "bricks",
             "white_wool", "glass", "hay_bale", "lantern", "glowstone",
             "path", "dirt", "water"]
    return {n: block_id(n) for n in names}


_B = None
_village_cache = {}


# ----------------------------------------------------------------------------
# placement
# ----------------------------------------------------------------------------
def village_for_region(seed, rgx, rgz):
    """Return the world-block centre (vx, vz) of this region's village, or None."""
    h = hash_pos(seed ^ 0x5151, rgx, rgz)
    if h % 100 >= VILLAGE_CHANCE:
        return None
    ocx = h % REGION
    ocz = (h // REGION) % REGION
    vx = (rgx * REGION + ocx) * CHUNK_SX + 8
    vz = (rgz * REGION + ocz) * CHUNK_SZ + 8
    base = surface_height(seed, vx, vz)
    if base <= SEA_LEVEL + 1 or base >= CHUNK_SY - 12:   # avoid water / peaks
        return None
    return (vx, vz, base)


# ----------------------------------------------------------------------------
# building templates -> dict {(dx,dy,dz): name}, dy=0 is the floor
# ----------------------------------------------------------------------------
def _hollow_box(W, D, H, wall, floor, roof):
    """Floor + perimeter walls + roof. Returns dict in local coords."""
    d = {}
    for x in range(W):
        for z in range(D):
            d[(x, 0, z)] = floor
            d[(x, H, z)] = roof
    for y in range(1, H):
        for x in range(W):
            d[(x, y, 0)] = wall
            d[(x, y, D - 1)] = wall
        for z in range(D):
            d[(x * 0, y, z)] = wall      # keep linter calm (overwritten below)
            d[(0, y, z)] = wall
            d[(W - 1, y, z)] = wall
    return d


def _template_cottage():
    W, D, H = 5, 5, 4
    d = _hollow_box(W, D, H, "cobblestone", "planks", "spruce_planks")
    d[(2, 1, 0)] = "air"; d[(2, 2, 0)] = "air"          # door
    d[(0, 2, 2)] = "glass"; d[(4, 2, 2)] = "glass"      # windows
    d[(2, 3, 2)] = "lantern"                            # light
    return W, D, H, d


def _template_barn():
    W, D, H = 7, 5, 5
    d = _hollow_box(W, D, H, "spruce_planks", "planks", "bricks")
    d[(3, 1, 0)] = "air"; d[(3, 2, 0)] = "air"          # door
    d[(1, 1, 1)] = "hay_bale"; d[(2, 1, 1)] = "hay_bale"
    d[(5, 1, 3)] = "hay_bale"
    d[(0, 3, 2)] = "glass"; d[(6, 3, 2)] = "glass"
    d[(1, 4, 1)] = "glowstone"                          # light
    return W, D, H, d


def _template_cabin():
    W, D, H = 5, 6, 4
    d = _hollow_box(W, D, H, "planks", "planks", "white_wool")
    d[(2, 1, 0)] = "air"; d[(2, 2, 0)] = "air"          # door
    d[(0, 2, 2)] = "glass"; d[(4, 2, 3)] = "glass"
    d[(2, 3, 3)] = "lantern"
    return W, D, H, d


_TEMPLATES = [_template_cottage, _template_barn, _template_cabin]


def _well():
    """3x3 cobble well with an infinite water source in the middle."""
    d = {}
    for x in range(3):
        for z in range(3):
            d[(x, 0, z)] = "cobblestone"
    d[(1, 0, 1)] = "water"                              # source (1x1 -> stays put)
    for cx, cz in ((0, 0), (2, 0), (0, 2), (2, 2)):     # corner posts + roof
        d[(cx, 1, cz)] = "cobblestone"
        d[(cx, 2, cz)] = "cobblestone"
    for x in range(3):
        for z in range(3):
            d[(x, 3, z)] = "planks"
    return 3, 3, 3, d


# ----------------------------------------------------------------------------
# full-village block map (cached per village)
# ----------------------------------------------------------------------------
def _village_blocks(seed, vx, vz, base):
    key = (vx, vz)
    cached = _village_cache.get(key)
    if cached is not None:
        return cached
    global _B
    if _B is None:
        _B = _bid()

    blocks = {}                       # (wx,wy,wz) -> block id
    floor_y = base + 1                # buildings sit one above the ground

    def place(W, D, H, tmpl, ox, oz):
        # foundation + clear, then the template
        for x in range(W):
            for z in range(D):
                wx, wz = vx + ox + x, vz + oz + z
                for yy in range(base - 2, floor_y):          # foundation
                    blocks[(wx, yy, wz)] = _B["cobblestone"]
                for yy in range(floor_y + 1, floor_y + H + 2):  # clear interior/air
                    blocks[(wx, yy, wz)] = _B["air"]
        for (dx, dy, dz), name in tmpl.items():
            blocks[(vx + ox + dx, floor_y + dy, vz + oz + dz)] = _B[name]

    # well at the centre
    wW, wD, wH, wd = _well()
    place(wW, wD, wH, wd, -1, -1)

    # 3..5 houses at deterministic offsets around the centre
    offsets = [(-13, -11), (10, -12), (-12, 9), (11, 10), (-2, -16)]
    hcount = 3 + hash_pos(seed ^ 0x2727, vx, vz) % 3       # 3..5
    for i in range(hcount):
        ox, oz = offsets[i]
        t = _TEMPLATES[hash_pos(seed ^ (0x99 + i), vx + ox, vz + oz) % 3]
        W, D, H, td = t()
        place(W, D, H, td, ox, oz)
        # a little path block from house door area toward centre
        px = vx + ox + W // 2
        pz = vz + oz + (D if oz < 0 else -1)
        blocks[(px, floor_y - 1, pz)] = _B["path"]

    _village_cache[key] = blocks
    return blocks


# ----------------------------------------------------------------------------
# stamp the part of any nearby village that falls inside this chunk
# ----------------------------------------------------------------------------
def stamp_chunk(seed, cx, cz, blocks):
    """blocks: the chunk's (SX,SY,SZ) array. Writes village pieces in-place."""
    bx0, bz0 = cx * CHUNK_SX, cz * CHUNK_SZ
    rgx0 = cx // REGION
    rgz0 = cz // REGION
    for drx in (-1, 0, 1):
        for drz in (-1, 0, 1):
            v = village_for_region(seed, rgx0 + drx, rgz0 + drz)
            if v is None:
                continue
            vx, vz, base = v
            # quick reject: village centre far from this chunk?
            if (vx + _EXTENT < bx0 or vx - _EXTENT > bx0 + CHUNK_SX or
                    vz + _EXTENT < bz0 or vz - _EXTENT > bz0 + CHUNK_SZ):
                continue
            vd = _village_blocks(seed, vx, vz, base)
            for (wx, wy, wz), bid in vd.items():
                lx, lz = wx - bx0, wz - bz0
                if 0 <= lx < CHUNK_SX and 0 <= lz < CHUNK_SZ and 0 <= wy < CHUNK_SY:
                    blocks[lx, wy, lz] = bid
