"""AABB vs voxel-grid physics. 实体与体素网格的逐轴扫掠碰撞。

All entities share this code; behaviour differences come purely from the
universal physics parameters (mass / friction / bounciness / gravity_scale /
drag) on blocks and entities — the engine reads parameters, never types.
"""

import math

from settings import GRAVITY, MAX_FALL_SPEED
from content.registry import BLOCKS, SOLID_LUT

_EPS = 1e-4


def _solid(world, x, y, z) -> bool:
    return SOLID_LUT[world.get_block(x, y, z)]


def move_entity(world, e, dt):
    """Move entity by vel*dt with axis-separated collision (Y first).

    Returns the block id the entity LANDED on this frame (0 = none),
    and stores the downward impact speed in e.impact_speed.
    """
    hw = e.AABB_SIZE[0] * 0.5
    hd = e.AABB_SIZE[2] * 0.5
    h = e.AABB_SIZE[1]

    landed_block = 0
    e.impact_speed = 0.0
    was_falling = e.vel[1] < 0.0
    e.on_ground = False

    px, py, pz = float(e.pos[0]), float(e.pos[1]), float(e.pos[2])

    # ---- Y axis ----
    dy = e.vel[1] * dt
    ny = py + dy
    if dy < 0:
        y_cell = math.floor(ny)
        if _hits_layer(world, px, pz, hw, hd, y_cell):
            impact = -e.vel[1]
            ny = y_cell + 1.0 + _EPS
            e.on_ground = True
            e.impact_speed = impact
            landed_block = _layer_block(world, px, pz, hw, hd, y_cell)
            e.vel[1] = 0.0
    elif dy > 0:
        top_cell = math.floor(ny + h)
        if _hits_layer(world, px, pz, hw, hd, top_cell):
            ny = top_cell - h - _EPS
            e.vel[1] = 0.0
    py = ny

    # ---- X axis ----
    dx = e.vel[0] * dt
    if dx != 0.0:
        nx = px + dx
        edge = nx + hw if dx > 0 else nx - hw
        x_cell = math.floor(edge)
        if _hits_wall_x(world, x_cell, py, pz, h, hd):
            nx = (x_cell - hw - _EPS) if dx > 0 else (x_cell + 1.0 + hw + _EPS)
            e.vel[0] = 0.0
            e.hit_wall = True
        px = nx

    # ---- Z axis ----
    dz = e.vel[2] * dt
    if dz != 0.0:
        nz = pz + dz
        edge = nz + hd if dz > 0 else nz - hd
        z_cell = math.floor(edge)
        if _hits_wall_z(world, px, py, z_cell, h, hw):
            nz = (z_cell - hd - _EPS) if dz > 0 else (z_cell + 1.0 + hd + _EPS)
            e.vel[2] = 0.0
            e.hit_wall = True
        pz = nz

    # standing check when not moving vertically (walked off a ledge?)
    if not e.on_ground and abs(e.vel[1]) < _EPS:
        below = math.floor(py - 0.05)
        if _hits_layer(world, px, pz, hw, hd, below):
            e.on_ground = True
            if was_falling:
                landed_block = _layer_block(world, px, pz, hw, hd, below)

    e.pos[0], e.pos[1], e.pos[2] = px, py, pz
    return landed_block


def _cells(lo, hi):
    return range(math.floor(lo + _EPS), math.floor(hi - _EPS) + 1)


def _hits_layer(world, px, pz, hw, hd, y) -> bool:
    if y < 0:
        return False
    for cx in _cells(px - hw, px + hw):
        for cz in _cells(pz - hd, pz + hd):
            if _solid(world, cx, y, cz):
                return True
    return False


def _layer_block(world, px, pz, hw, hd, y) -> int:
    for cx in _cells(px - hw, px + hw):
        for cz in _cells(pz - hd, pz + hd):
            bid = world.get_block(cx, y, cz)
            if SOLID_LUT[bid]:
                return bid
    return 0


def _hits_wall_x(world, x_cell, py, pz, h, hd) -> bool:
    for cy in _cells(py, py + h):
        for cz in _cells(pz - hd, pz + hd):
            if _solid(world, x_cell, cy, cz):
                return True
    return False


def _hits_wall_z(world, px, py, z_cell, h, hw) -> bool:
    for cy in _cells(py, py + h):
        for cx in _cells(px - hw, px + hw):
            if _solid(world, cx, cy, z_cell):
                return True
    return False


def physics_step(world, e, dt):
    """Shared per-frame physics: gravity, water, movement, landing effects.

    Landing effects use BLOCK physics parameters:
      on_step callback (jump pad) -> takes priority
      bounciness > 0              -> reflect vertical velocity
    """
    # water: any entity whose centre is inside a water cell
    cx = math.floor(e.pos[0])
    cy = math.floor(e.pos[1] + e.AABB_SIZE[1] * 0.5)
    cz = math.floor(e.pos[2])
    bt_in = BLOCKS[world.get_block(cx, cy, cz)]
    e.in_water = (bt_in is not None and bt_in.name == "water")

    g = GRAVITY * e.GRAVITY_SCALE * (0.35 if e.in_water else 1.0)
    e.vel[1] -= g * dt
    if e.in_water:
        e.vel[1] *= max(0.0, 1.0 - 2.5 * dt)   # water drag
    if e.vel[1] < -MAX_FALL_SPEED:
        e.vel[1] = -MAX_FALL_SPEED
    if e.DRAG:
        damp = max(0.0, 1.0 - e.DRAG * dt)
        e.vel[0] *= damp
        e.vel[2] *= damp

    e.hit_wall = False
    # substep when moving fast (anti-tunnelling 防穿墙：爆炸击飞/卡顿大dt)
    max_d = max(abs(e.vel[0]), abs(e.vel[1]), abs(e.vel[2])) * dt
    steps = min(6, int(max_d / 0.45) + 1)
    landed = 0
    sub = dt / steps
    for _ in range(steps):
        lb = move_entity(world, e, sub)
        if lb:
            landed = lb

    if landed:
        bt = BLOCKS[landed]
        pos_below = (math.floor(e.pos[0]),
                     math.floor(e.pos[1] - 0.1),
                     math.floor(e.pos[2]))
        if bt.on_step is not None and e.impact_speed > 1.0:
            bt.on_step(world, pos_below, e)
        elif bt.bounciness > 0.0 and e.impact_speed > 3.0:
            e.vel[1] = e.impact_speed * bt.bounciness
            e.on_ground = False
    return landed


def ground_friction(world, e) -> float:
    """Friction of the block under the entity's feet (default air = 0.6)."""
    bid = world.get_block(math.floor(e.pos[0]),
                          math.floor(e.pos[1] - 0.1),
                          math.floor(e.pos[2]))
    bt = BLOCKS[bid]
    return bt.friction if (bt is not None and bid != 0) else 0.6
