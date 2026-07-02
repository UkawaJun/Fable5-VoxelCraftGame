"""Vectorised chunk mesh generation — the performance core (DESIGN §4.1).

向量化网格生成：数组位移做面剔除 + 坐标广播批量拼顶点，无逐方块 Python 循环。
顶点格式: pos(3f) uv(2f) shade(1f) light(1f) = 7 floats。

流体：相邻水块之间不画内部面；水面顶点按水位高度下沉(level/8)。
"""

import numpy as np

from settings import CHUNK_SX, CHUNK_SY, CHUNK_SZ
from content.registry import (EMISSIVE_LUT, OPAQUE_LUT, TEX_LUT,
                              TRANSLUCENT_LUT, block_id)
from content.fluids import FLUID_LUT, FLUID_LEVEL
from content.tiles import ATLAS_COLS

SX, SY, SZ = CHUNK_SX, CHUNK_SY, CHUNK_SZ

# direction order: +x -x +y -y +z -z
_OFFSETS = ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1))
_SHADE = (0.80, 0.80, 1.00, 0.45, 0.62, 0.62)

_FACE_CORNERS = np.array([
    [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]],   # +x
    [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]],   # -x
    [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]],   # +y
    [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]],   # -y
    [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]],   # +z
    [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]],   # -z
], dtype=np.float32)

_TRI = (0, 1, 2, 0, 2, 3)
_FACE_VERTS = _FACE_CORNERS[:, _TRI, :]                       # (6dir, 6vert, 3)

_E = 0.02
_UV_QUAD = np.array([[_E, 1 - _E], [1 - _E, 1 - _E],
                     [1 - _E, _E], [_E, _E]], dtype=np.float32)
_FACE_UVS = _UV_QUAD[list(_TRI)]                             # (6vert, 2)
_STEP = 1.0 / ATLAS_COLS


def build_chunk_mesh(world, chunk):
    """Returns (solid_f32, translucent_f32), each (N*6, 7) float32 (may be empty).
    Reads the 4 neighbour chunks for correct border-face culling + lighting."""
    core = chunk.blocks
    P = np.zeros((SX + 2, SY + 2, SZ + 2), dtype=np.uint8)
    P[1:-1, 1:-1, 1:-1] = core
    cx, cz = chunk.cx, chunk.cz
    nb = world.chunks.get((cx - 1, cz))
    if nb is not None:
        P[0, 1:-1, 1:-1] = nb.blocks[SX - 1, :, :]
    nb = world.chunks.get((cx + 1, cz))
    if nb is not None:
        P[-1, 1:-1, 1:-1] = nb.blocks[0, :, :]
    nb = world.chunks.get((cx, cz - 1))
    if nb is not None:
        P[1:-1, 1:-1, 0] = nb.blocks[:, :, SZ - 1]
    nb = world.chunks.get((cx, cz + 1))
    if nb is not None:
        P[1:-1, 1:-1, -1] = nb.blocks[:, :, 0]

    L = np.zeros((SX + 2, SY + 2, SZ + 2), dtype=np.uint8)
    L[1:-1, 1:-1, 1:-1] = chunk.light
    nb = world.chunks.get((cx - 1, cz))
    if nb is not None:
        L[0, 1:-1, 1:-1] = nb.light[SX - 1, :, :]
    nb = world.chunks.get((cx + 1, cz))
    if nb is not None:
        L[-1, 1:-1, 1:-1] = nb.light[0, :, :]
    nb = world.chunks.get((cx, cz - 1))
    if nb is not None:
        L[1:-1, 1:-1, 0] = nb.light[:, :, SZ - 1]
    nb = world.chunks.get((cx, cz + 1))
    if nb is not None:
        L[1:-1, 1:-1, -1] = nb.light[:, :, 0]

    core_fluid = FLUID_LUT[core]
    trans_core = TRANSLUCENT_LUT[core]
    solid_core = (core != 0) & ~trans_core

    solid_parts, trans_parts = [], []
    for d, (dx, dy, dz) in enumerate(_OFFSETS):
        nbr = P[1 + dx:SX + 1 + dx, 1 + dy:SY + 1 + dy, 1 + dz:SZ + 1 + dz]
        nbr_light = L[1 + dx:SX + 1 + dx, 1 + dy:SY + 1 + dy, 1 + dz:SZ + 1 + dz]
        # face is open if neighbour is non-opaque, a different block, and
        # not "both fluid" (don't draw faces between adjacent water levels)
        both_fluid = core_fluid & FLUID_LUT[nbr]
        open_face = (~OPAQUE_LUT[nbr]) & (nbr != core) & ~both_fluid
        vis_s = solid_core & open_face
        vis_t = trans_core & open_face
        if vis_s.any():
            solid_parts.append(_emit(core, nbr_light, vis_s, d))
        if vis_t.any():
            trans_parts.append(_emit(core, nbr_light, vis_t, d))

    solid = (np.concatenate(solid_parts) if solid_parts
             else np.zeros((0, 7), dtype=np.float32))
    trans = (np.concatenate(trans_parts) if trans_parts
             else np.zeros((0, 7), dtype=np.float32))
    return solid, trans


def _emit(core, nbr_light, vis, d):
    """Batch-build (N*6, 7) vertices for one face direction. 全程无循环。"""
    xs, ys, zs = np.nonzero(vis)
    bids = core[xs, ys, zs]
    n = len(xs)

    pos = np.stack([xs, ys, zs], axis=1).astype(np.float32)   # (N,3)
    verts = pos[:, None, :] + _FACE_VERTS[d][None]            # (N,6,3)

    # fluid surface height: lower the TOP vertices by (1 - level/8)
    flvl = FLUID_LEVEL[bids].astype(np.float32)               # (N,) 0 or 1..8
    dip = np.where(flvl > 0, 1.0 - flvl / 8.0 * 0.92, 0.0)    # (N,)
    if dip.any():
        top_mask = (_FACE_VERTS[d][:, 1] > 0.5).astype(np.float32)  # (6,)
        verts[:, :, 1] -= dip[:, None] * top_mask[None, :]

    tiles = TEX_LUT[d][bids]
    off = np.stack([(tiles % ATLAS_COLS), (tiles // ATLAS_COLS)],
                   axis=1).astype(np.float32) * _STEP
    uvs = off[:, None, :] + _FACE_UVS[None] * _STEP

    shade = np.full((n, 6, 1), _SHADE[d], dtype=np.float32)
    lite = nbr_light[xs, ys, zs].astype(np.float32) / 15.0
    lite = np.maximum(lite, EMISSIVE_LUT[bids])
    light = np.repeat(lite[:, None], 6, axis=1)[:, :, None]

    out = np.concatenate([verts, uvs, shade, light], axis=2)  # (N,6,7)
    return out.reshape(-1, 7)
