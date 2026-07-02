"""Headless integration tests — no window/GPU needed.

无头测试：验证 地形生成 / 网格构建 / 物理 / 爆炸+碎屑 / 沙子下落 / 存档。
Run: python test_headless.py
"""

import math
import os
import sys
import tempfile
import time

import numpy as np

import content.blocks      # noqa: F401  (registration)
import content.items       # noqa: F401
import entities.mobs.slime # noqa: F401
import entities.mobs.pig   # noqa: F401

from content.registry import BLOCKS, SOLID_LUT, block_id
from entities.player import Player
from persistence.savegame import SaveGame
from systems.time_system import TimeSystem
from systems.weather import WeatherSystem
from world.terrain import generate_chunk
from world.world import World

PASS = 0


def check(name, cond):
    global PASS
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}")
    if not cond:
        sys.exit(1)
    PASS += 1


def wait_loaded(world, x, z, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        world.process_gen_results(budget=64)
        if world.is_loaded(x, z):
            return True
        time.sleep(0.01)
    return False


def step_world(world, seconds, dt=1 / 60):
    n = int(seconds / dt)
    for _ in range(n):
        world.update_entities(dt)
        world.process_block_updates()


def main():
    seed = 12345

    # ---- perlin / terrain determinism ----
    a = generate_chunk(seed, 0, 0)
    b = generate_chunk(seed, 0, 0)
    check("terrain deterministic", np.array_equal(a, b))
    check("terrain has stone", (a == block_id("stone")).sum() > 1000)
    check("terrain bedrock floor", (a[:, 0, :] == block_id("bedrock")).all())

    # ---- world & block access ----
    world = World(seed)
    world.ensure_chunks_around(8, 8)
    check("spawn chunks load", wait_loaded(world, 8, 8))
    deadline = time.time() + 20.0
    while world._pending and time.time() < deadline:
        world.process_gen_results(budget=200)
        time.sleep(0.01)
    check("all chunks generated", not world._pending)

    sy = world.surface_y(8, 8)
    check("surface found", sy is not None and 2 < sy < 120)
    world.set_block(8, sy + 1, 8, block_id("stone"))
    check("set/get block", world.get_block(8, sy + 1, 8) == block_id("stone"))
    world.break_block(8, sy + 1, 8)
    check("break block", world.get_block(8, sy + 1, 8) == 0)

    # ---- mesh builder ----
    from engine.mesh_builder import build_chunk_mesh
    chunk = world.chunks[(0, 0)]
    t0 = time.perf_counter()
    solid, trans = build_chunk_mesh(world, chunk)
    ms = (time.perf_counter() - t0) * 1000
    check(f"mesh built ({len(solid)} verts, {ms:.1f}ms)",
          len(solid) > 0 and ms < 50)
    check("mesh vertex format", solid.shape[1] == 7)

    # ---- sand falling (gravity_affected) ----
    sx, sz = 4, 4
    sy2 = world.surface_y(sx, sz)
    world.set_block(sx, sy2 + 5, sz, block_id("sand"))   # floating sand
    step_world(world, 3.0)
    placed = world.get_block(sx, sy2 + 1, sz)
    check("sand fell and re-placed",
          placed == block_id("sand") and
          world.get_block(sx, sy2 + 5, sz) == 0)

    # ---- jump pad on_step ----
    from entities.mobs.pig import Pig
    px, pz = 12, 12
    py = world.surface_y(px, pz)
    world.set_block(px, py + 1, pz, block_id("jump_pad"))
    pig = Pig((px + 0.5, py + 6.0, pz + 0.5))           # drop onto the pad
    pig.state_timer = 999.0                              # keep it idle
    world.entities.append(pig)
    launched = False
    for _ in range(240):
        world.update_entities(1 / 60)
        if pig.vel[1] > 10.0:
            launched = True
            break
    check("jump pad launches entity", launched)
    world.entities.clear()

    # ---- explosion + debris settling ----
    ex, ez = 0, 0
    ey = world.surface_y(ex, ez)
    before = world.get_block(ex, ey, ez)
    check("explosion target solid", SOLID_LUT[before])
    world.explode(ex + 0.5, ey + 0.5, ez + 0.5, 9.0, 4.5)
    check("explosion removed blocks", world.get_block(ex, ey, ez) == 0)
    check("explosion spawned debris", world.debris.count > 0)
    check("explosion event emitted",
          any(e[0] == "explosion" for e in world.events))
    n0 = world.debris.count
    step_world(world, 12.0)
    check(f"debris settled ({n0} -> {world.debris.count})",
          world.debris.count == 0)

    # ---- TNT chain: ignite -> primed entity -> explodes ----
    tx, tz = -8, -8
    ty = world.surface_y(tx, tz)
    world.set_block(tx, ty + 1, tz, block_id("tnt"))
    world.interact_block(tx, ty + 1, tz, None)           # right click
    check("tnt ignited (block -> entity)",
          world.get_block(tx, ty + 1, tz) == 0 and
          any(e.TYPE_NAME == "primed_tnt" for e in world.entities))
    step_world(world, 4.0)
    check("tnt exploded (crater)", world.get_block(tx, ty, tz) == 0)
    step_world(world, 12.0)

    # ---- bedrock unbreakable ----
    world.explode(0.5, 0.5, 0.5, 9.0, 4.5)
    check("bedrock survives explosion",
          world.get_block(0, 0, 0) == block_id("bedrock"))
    step_world(world, 10.0)

    # ---- save / load roundtrip ----
    tmp = os.path.join(tempfile.mkdtemp(), "t.db")
    save = SaveGame(tmp)
    player = Player(world.spawn_pos)
    player.pos[:] = (8.5, sy + 3.0, 8.5)
    player.slot = 7
    ts = TimeSystem()
    ts.time_of_day = 0.42
    ws = WeatherSystem()
    ws.force("RAIN")
    world.set_block(9, sy + 4, 9, block_id("glowstone"))
    save.save_all(world, player, ts, ws)

    world2 = World(save.get_meta("seed"), save)
    check("seed persisted", world2.seed == seed)
    world2.ensure_chunks_around(8, 8)
    check("spawn chunks reload", wait_loaded(world2, 8, 8, 15.0))
    check("modified chunk persisted",
          world2.get_block(9, sy + 4, 9) == block_id("glowstone"))
    check("sand modification persisted",
          world2.get_block(sx, sy2 + 1, sz) == block_id("sand"))
    p2 = Player(world2.spawn_pos)
    save.load_player_into(p2)
    check("player persisted",
          abs(p2.pos[1] - (sy + 3.0)) < 1e-6 and p2.slot == 7)
    ts2 = TimeSystem()
    ts2.deserialize(save.get_meta("time"))
    check("time persisted", abs(ts2.time_of_day - 0.42) < 1e-9)
    ws2 = WeatherSystem()
    ws2.deserialize(save.get_meta("weather"))
    check("weather persisted", ws2.state == "RAIN")
    save.close()

    # ---- texture atlas (numpy/PIL only) ----
    from engine.texture_atlas import build_atlas
    atlas = build_atlas()
    check("atlas built", atlas.shape == (256, 256, 4) and atlas.dtype == np.uint8)

    print(f"\nAll {PASS} checks passed.")


if __name__ == "__main__":
    main()
