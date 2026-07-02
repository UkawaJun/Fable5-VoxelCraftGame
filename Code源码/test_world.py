"""Headless tests for water / villages / villager. 不开窗口验证新系统。
Run: python test_world.py"""
import collections, sys
import numpy as np
import content.blocks, content.items, content.fluids as fl
import entities.mobs.villager
from world.world import World
from world.chunk import Chunk
from world.terrain import generate_chunk
from world import structures as st
from entities.debris import DebrisSystem
from entities.mobs.villager import Villager
from content.registry import block_id, ENTITY_TYPES

P = 0
def check(name, cond):
    global P
    print(f"[{'PASS' if cond else 'FAIL'}] {name}", flush=True)
    if not cond:
        sys.exit(1)
    P += 1

def mini():
    w = World.__new__(World)
    w.chunks = {}; w.dirty = set(); w.light_dirty = set(); w.emitter_chunks = set()
    w.removed = []; w.update_queue = collections.deque()
    w.water_queue = collections.deque(); w.events = []; w.entities = []
    w.player = None; w._spawn_timer = 999; w.debris = DebrisSystem(w)
    c = Chunk(0, 0); c.blocks[:, :40, :] = block_id("stone"); w.chunks[(0, 0)] = c
    return w

def drain(w, fn, limit=4000):
    n = 0
    while w.water_queue and n < limit:
        fn(budget=300); n += 1
    return n

def main():
    S = fl.SOURCE_ID

    # ---------- WATER ----------
    w = mini()
    w.set_block(8, 41, 8, S)
    drain(w, w.process_water)
    dist = 0
    for k in range(1, 12):
        if fl.FLUID_LUT[w.get_block(8 + k, 41, 8)]:
            dist = k
        else:
            break
    check(f"water spreads exactly 7 blocks (got {dist})", dist == 7)
    check("source is permanent (infinite)", w.get_block(8, 41, 8) == S)
    check("level decreases with distance",
          int(fl.FLUID_LEVEL[w.get_block(9, 41, 8)]) == 7 and
          int(fl.FLUID_LEVEL[w.get_block(15, 41, 8)]) == 1)
    check("water settles (queue empties -> 0 cost)", len(w.water_queue) == 0)

    w = mini()
    for yy in range(34, 41):
        w.set_block(8, yy, 8, 0, water=False)
    w.water_queue.clear()
    w.set_block(8, 41, 8, S)
    drain(w, w.process_water)
    check("water flows down a shaft",
          all(fl.FLUID_LUT[w.get_block(8, yy, 8)] for yy in range(35, 41)))

    w = mini()
    w.set_block(6, 41, 8, S); w.set_block(8, 41, 8, S)
    drain(w, w.process_water)
    check("infinite water: gap between 2 sources becomes a source",
          w.get_block(7, 41, 8) == S)

    # ---------- VILLAGES ----------
    seed = 20260612
    found = None
    for rgx in range(0, 8):
        for rgz in range(0, 8):
            v = st.village_for_region(seed, rgx, rgz)
            if v:
                found = v; break
        if found:
            break
    check("a village exists within a few regions", found is not None)
    vx, vz, base = found
    ccx, ccz = vx // 16, vz // 16
    counts = {}
    water_in_well = False
    for dcx in (-1, 0, 1):
        for dcz in (-1, 0, 1):
            b = generate_chunk(seed, ccx + dcx, ccz + dcz)
            for nm in ("cobblestone", "planks", "spruce_planks", "glass",
                       "lantern", "bricks", "white_wool"):
                counts[nm] = counts.get(nm, 0) + int((b == block_id(nm)).sum())
            if (b == S).sum() > 0:
                water_in_well = True
    check("village has cobblestone walls/foundation", counts["cobblestone"] > 100)
    check("village uses >=2 house materials (3 templates)",
          sum(1 for k in ("planks", "spruce_planks", "white_wool", "bricks")
              if counts[k] > 0) >= 2)
    check("village has glass windows + a light", counts["glass"] > 0 and counts["lantern"] > 0)
    check("well contains an (infinite) water source", water_in_well)
    b1 = generate_chunk(seed, ccx, ccz)
    b2 = generate_chunk(seed, ccx, ccz)
    check("village generation deterministic", np.array_equal(b1, b2))

    # village density: count villages over a 12x12 region grid
    vcount = sum(1 for gx in range(12) for gz in range(12)
                 if st.village_for_region(seed, gx, gz))
    check(f"village density reasonable ({vcount}/144 regions)",
          40 <= vcount <= 130)

    # ---------- VILLAGER ----------
    check("villager registered", "villager" in ENTITY_TYPES)
    w = mini()
    w.chunks[(0, 0)].blocks[:, :40, :] = block_id("grass")
    v = Villager((8.5, 41.0, 8.5)); v.state = 1; v.heading = 0.5
    v.state_timer = 99
    w.entities.append(v)
    x0, z0 = v.pos[0], v.pos[2]
    for _ in range(180):
        w.update_entities(1 / 60)
    moved = abs(v.pos[0] - x0) + abs(v.pos[2] - z0)
    check(f"villager wanders around (moved {moved:.1f})", moved > 0.4)
    check("villager stays grounded + animates", v.on_ground and v.anim_phase > 0)

    print(f"\nAll {P} world checks passed.")

if __name__ == "__main__":
    main()
