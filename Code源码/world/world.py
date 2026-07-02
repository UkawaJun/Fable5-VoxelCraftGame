"""World: chunk management, block access, explosions, block updates, mobs.

世界协调者：
  - 区块字典 + 后台生成线程（主线程永不因生成掉帧）
  - get/set_block 热路径（直接读 numpy 数组，O(1)）
  - dislodge/explode：方块 -> 碎屑（见 entities/debris.py）
  - 方块更新队列：沙子失去支撑 -> 连锁下落
  - 生物生成/卸载
"""

import math
import random
import threading
from collections import deque
from queue import Empty, Queue

import numpy as np

from settings import (BLOCK_UPDATES_PER_FRAME, CHUNK_SY,
                      EXPLOSION_DEBRIS_CAP, GEN_RESULTS_PER_FRAME,
                      MOB_CAP_PER_TYPE, MOB_DESPAWN_DIST, MOB_SPAWN_INTERVAL,
                      MOB_SPAWN_MAX, MOB_SPAWN_MIN, RENDER_DISTANCE, TNT_FUSE)
from content.registry import (BLOCKS, EMISSIVE_LUT, GRAVITY_LUT, OPAQUE_LUT,
                              SOLID_LUT, SPAWN_RULES, ENTITY_TYPES, block_id)
from world.chunk import Chunk
from world.terrain import generate_chunk, surface_height
from world import lighting
from world import water as water_sim
from content.fluids import FLUID_LUT as _FLUID_LUT
from entities.debris import DebrisSystem
from entities.tnt import PrimedTNT


class World:
    def __init__(self, seed: int, save=None):
        self.seed = seed
        self.save = save
        self.chunks = {}                  # (cx, cz) -> Chunk
        self.dirty = set()                # chunks whose mesh needs rebuild
        self.light_dirty = set()          # chunks whose block-light needs recompute
        self.emitter_chunks = set()       # chunk keys that contain a light source
        self.removed = []                 # chunk keys unloaded this frame
        self.update_queue = deque()       # block positions to re-check
        self.water_queue = deque()        # fluid cells to re-evaluate
        self.events = []                  # ("explosion", pos, power) etc.

        self.entities = []                # mobs + primed TNT (not the player)
        self.player = None                # injected by main
        self.debris = DebrisSystem(self)
        self.weather = None               # injected by main
        self.time = None                  # injected by main

        self._spawn_timer = MOB_SPAWN_INTERVAL
        self._tnt_id = block_id("tnt")
        self._water_id = block_id("water")

        # background generator thread
        self._gen_in = Queue()
        self._gen_out = Queue()
        self._pending = set()
        t = threading.Thread(target=self._gen_worker, daemon=True)
        t.start()

        sx, sz = 8, 8
        sy = surface_height(seed, sx, sz) + 1
        self.spawn_pos = (sx + 0.5, sy + 0.5, sz + 0.5)

    # ------------------------------------------------------------------
    # block access (hot path)
    # ------------------------------------------------------------------
    def get_block(self, x: int, y: int, z: int) -> int:
        if y < 0 or y >= CHUNK_SY:
            return 0
        c = self.chunks.get((x >> 4, z >> 4))
        if c is None:
            return 0
        return c.blocks[x & 15, y, z & 15]

    def set_block(self, x: int, y: int, z: int, bid: int, notify=True,
                  light=True, water=True) -> bool:
        if y < 0 or y >= CHUNK_SY:
            return False
        key = (x >> 4, z >> 4)
        c = self.chunks.get(key)
        if c is None:
            return False
        lx, lz = x & 15, z & 15
        old = c.blocks[lx, y, lz]
        c.blocks[lx, y, lz] = bid
        c.modified = True
        self._mark_dirty(key)
        # border edits also dirty the neighbour's mesh
        if lx == 0:
            self._mark_dirty((key[0] - 1, key[1]))
        elif lx == 15:
            self._mark_dirty((key[0] + 1, key[1]))
        if lz == 0:
            self._mark_dirty((key[0], key[1] - 1))
        elif lz == 15:
            self._mark_dirty((key[0], key[1] + 1))
        # light recompute only when opacity/emission changed AND a light is near
        if light:
            self._mark_light(x, z, int(old), bid)
        if water and (_FLUID_LUT[bid] or _FLUID_LUT[old]
                      or water_sim.near_water(self, x, y, z)):
            water_sim.enqueue(self, x, y, z)
        if notify:
            self.update_queue.append((x, y + 1, z))   # support removed?
            self.update_queue.append((x, y, z))       # placed mid-air?
        return True

    def _mark_light(self, x, z, old, bid):
        """Queue light recompute only when it can actually change anything.
        放普通方块若附近没有光源，直接跳过（避免无谓的重算卡顿）。"""
        em = EMISSIVE_LUT[old] != EMISSIVE_LUT[bid]
        op = OPAQUE_LUT[old] != OPAQUE_LUT[bid]
        key = (x >> 4, z >> 4)
        if em:                                    # keep the emitter index current
            if EMISSIVE_LUT[bid] > 0:
                self.emitter_chunks.add(key)
            elif not EMISSIVE_LUT[self.chunks[key].blocks].any():
                self.emitter_chunks.discard(key)
        if not (em or op):
            return
        region = lighting.affected_chunks(x, z) & self.chunks.keys()
        if not region:
            return
        if em:
            self.light_dirty |= region            # placed/removed a light
            return
        for k in region:                          # shadow change: only if lit
            if self.chunks[k].light.any():
                self.light_dirty |= region
                break

    def is_loaded(self, x, z) -> bool:
        return (int(math.floor(x)) >> 4, int(math.floor(z)) >> 4) in self.chunks

    def _mark_dirty(self, key):
        if key in self.chunks:
            self.dirty.add(key)

    # ------------------------------------------------------------------
    # player actions
    # ------------------------------------------------------------------
    def break_block(self, x, y, z) -> int:
        bid = int(self.get_block(x, y, z))
        if bid == 0:
            return 0
        bt = BLOCKS[bid]
        if bt.hardness == math.inf:
            return 0                                   # bedrock
        if bt.on_break:
            bt.on_break(self, (x, y, z), self.player)
        self.set_block(x, y, z, 0)
        return bid

    def place_block(self, x, y, z, name: str) -> bool:
        bid = block_id(name)
        cur = int(self.get_block(x, y, z))
        if cur != 0 and SOLID_LUT[cur]:
            return False
        bt = BLOCKS[bid]
        if bt.solid and self._cell_blocked_by_entity(x, y, z):
            return False                               # 不能把方块放进实体身体里
        ok = self.set_block(x, y, z, bid)
        if ok and bt.on_place:
            bt.on_place(self, (x, y, z), self.player)
        return ok

    def _cell_blocked_by_entity(self, x, y, z) -> bool:
        for e in ([self.player] if self.player else []) + self.entities:
            hw = e.AABB_SIZE[0] * 0.5
            hd = e.AABB_SIZE[2] * 0.5
            if (x < e.pos[0] + hw and x + 1 > e.pos[0] - hw and
                    y < e.pos[1] + e.AABB_SIZE[1] and y + 1 > e.pos[1] and
                    z < e.pos[2] + hd and z + 1 > e.pos[2] - hd):
                return True
        return False

    def interact_block(self, x, y, z, actor) -> bool:
        bt = BLOCKS[int(self.get_block(x, y, z))]
        if bt is not None and bt.on_interact:
            return bool(bt.on_interact(self, (x, y, z), actor))
        return False

    # ------------------------------------------------------------------
    # block -> debris  (方块→碎屑)
    # ------------------------------------------------------------------
    def dislodge(self, x, y, z, vel) -> bool:
        bid = int(self.get_block(x, y, z))
        if bid == 0:
            return False
        if not self.debris.spawn(bid, (x + 0.5, y + 0.5, z + 0.5), vel):
            return False
        self.set_block(x, y, z, 0)
        return True

    # ------------------------------------------------------------------
    # explosion (DESIGN §4.5.2)
    # ------------------------------------------------------------------
    def explode(self, ex, ey, ez, power: float, radius: float):
        cx0, cy0, cz0 = math.floor(ex), math.floor(ey), math.floor(ez)
        r = int(math.ceil(radius))
        r2 = radius * radius
        destroyed = []
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    d2 = dx * dx + dy * dy + dz * dz
                    if d2 > r2:
                        continue
                    bx, by, bz = cx0 + dx, cy0 + dy, cz0 + dz
                    bid = int(self.get_block(bx, by, bz))
                    if bid == 0:
                        continue
                    bt = BLOCKS[bid]
                    dist = math.sqrt(d2)
                    strength = (power * (1.0 - dist / radius)
                                * random.uniform(0.85, 1.0)
                                - bt.blast_resistance)
                    if strength <= 0:
                        continue
                    if bid == self._tnt_id:            # 连锁殉爆
                        self.set_block(bx, by, bz, 0, notify=False, light=False)
                        self.spawn_primed_tnt((bx, by, bz),
                                              fuse=random.uniform(0.3, 0.9))
                        continue
                    destroyed.append((dist, bx, by, bz, bid, strength))

        destroyed.sort(key=lambda t: t[0])             # nearest get debris
        quota = EXPLOSION_DEBRIS_CAP
        lit_destroyed = False
        for dist, bx, by, bz, bid, strength in destroyed:
            lit_destroyed = lit_destroyed or EMISSIVE_LUT[bid] > 0
            self.set_block(bx, by, bz, 0, light=False)   # batch light below
            if quota <= 0:
                continue
            bt = BLOCKS[bid]
            dirv = np.array([bx + 0.5 - ex, by + 0.5 - ey, bz + 0.5 - ez])
            n = np.linalg.norm(dirv)
            dirv = dirv / n if n > 1e-6 else np.array([0.0, 1.0, 0.0])
            dirv += np.random.uniform(-0.15, 0.15, 3)
            # impulse / mass: light blocks fly, heavy blocks barely move ★
            speed = min(30.0, strength * 6.0 / max(bt.mass, 0.2))
            vel = dirv * speed
            vel[1] += speed * 0.3 + 1.5                # upward bias
            if self.debris.spawn(bid, (bx + 0.5, by + 0.5, bz + 0.5), vel):
                quota -= 1

        # knockback on entities (含玩家): impulse * factor / mass
        targets = ([self.player] if self.player else []) + self.entities
        kb_range = radius * 1.7
        for e in targets:
            dvec = e.centre() - np.array([ex, ey, ez])
            dist = float(np.linalg.norm(dvec))
            if dist > kb_range:
                continue
            dirv = dvec / dist if dist > 1e-6 else np.array([0.0, 1.0, 0.0])
            dirv[1] += 0.35
            imp = power * 5.0 * (1.0 - dist / kb_range)
            e.apply_knockback(dirv * imp)

        # ---- batch light update for the whole blast (避免每方块各标一次) ----
        rc = int(math.ceil(radius)) + 1
        for ccx in range((cx0 - rc) >> 4, ((cx0 + rc) >> 4) + 1):
            for ccz in range((cz0 - rc) >> 4, ((cz0 + rc) >> 4) + 1):
                k = (ccx, ccz)
                c = self.chunks.get(k)
                if c is not None and (lit_destroyed or c.light.any()):
                    self.light_dirty |= lighting.affected_chunks(
                        ccx << 4, ccz << 4) & self.chunks.keys()

        self.events.append(("explosion", (ex, ey, ez), power))

    def ignite_tnt(self, pos, fuse: float = TNT_FUSE):
        x, y, z = pos
        self.set_block(x, y, z, 0, notify=False)
        self.spawn_primed_tnt(pos, fuse)

    def spawn_primed_tnt(self, pos, fuse: float = TNT_FUSE):
        x, y, z = pos
        self.entities.append(PrimedTNT((x + 0.5, y + 0.05, z + 0.5), fuse))

    # ------------------------------------------------------------------
    # block update queue (gravity blocks 沙子下落)
    # ------------------------------------------------------------------
    def process_block_updates(self, budget=BLOCK_UPDATES_PER_FRAME):
        n = 0
        while self.update_queue and n < budget:
            x, y, z = self.update_queue.popleft()
            n += 1
            bid = int(self.get_block(x, y, z))
            if bid == 0 or not GRAVITY_LUT[bid]:
                continue
            below = int(self.get_block(x, y - 1, z))
            if below == 0 or not SOLID_LUT[below]:
                # unsupported gravity block -> debris falling straight down
                if self.debris.spawn(bid, (x + 0.5, y + 0.5, z + 0.5),
                                     (0.0, -0.2, 0.0)):
                    self.set_block(x, y, z, 0)   # queues the cell above -> chain

    # ------------------------------------------------------------------
    # block-light updates (萤石点光源)
    # ------------------------------------------------------------------
    def process_light_updates(self, budget=2):
        """Recompute block-light for dirty chunks, then mark their mesh dirty."""
        n = 0
        while self.light_dirty and n < budget:
            key = self.light_dirty.pop()
            c = self.chunks.get(key)
            if c is None:
                continue
            lighting.relight_chunk(self, c)
            self._mark_dirty(key)
            n += 1

    # ------------------------------------------------------------------
    # flowing water (世界协调入口；细节见 world/water.py)
    # ------------------------------------------------------------------
    def process_water(self, budget=96):
        water_sim.process(self, budget)

    # ------------------------------------------------------------------
    # chunk streaming
    # ------------------------------------------------------------------
    def _gen_worker(self):
        while True:
            cx, cz = self._gen_in.get()
            blocks = generate_chunk(self.seed, cx, cz)
            self._gen_out.put((cx, cz, blocks))

    def ensure_chunks_around(self, px, pz):
        pcx, pcz = int(math.floor(px)) >> 4, int(math.floor(pz)) >> 4
        wanted = []
        rd = RENDER_DISTANCE
        for cx in range(pcx - rd, pcx + rd + 1):
            for cz in range(pcz - rd, pcz + rd + 1):
                key = (cx, cz)
                if key in self.chunks or key in self._pending:
                    continue
                wanted.append((abs(cx - pcx) + abs(cz - pcz), key))
        wanted.sort()
        for _, key in wanted:
            stored = self.save.load_chunk(*key) if self.save else None
            if stored is not None:
                self._add_chunk(Chunk.from_bytes(key[0], key[1], stored))
            else:
                self._pending.add(key)
                self._gen_in.put(key)

        # unload far chunks
        limit = rd + 2
        for key in list(self.chunks.keys()):
            if max(abs(key[0] - pcx), abs(key[1] - pcz)) > limit:
                c = self.chunks.pop(key)
                if c.modified and self.save:
                    self.save.save_chunk(c)
                self.dirty.discard(key)
                self.light_dirty.discard(key)
                self.emitter_chunks.discard(key)
                self.removed.append(key)

    def process_gen_results(self, budget=GEN_RESULTS_PER_FRAME):
        for _ in range(budget):
            try:
                cx, cz, blocks = self._gen_out.get_nowait()
            except Empty:
                return
            self._pending.discard((cx, cz))
            self._add_chunk(Chunk(cx, cz, blocks))

    def _add_chunk(self, c: Chunk):
        key = (c.cx, c.cz)
        self.chunks[key] = c
        self._mark_dirty(key)
        self.light_dirty.add(key)
        for nk in ((key[0] + 1, key[1]), (key[0] - 1, key[1]),
                   (key[0], key[1] + 1), (key[0], key[1] - 1)):
            self._mark_dirty(nk)
            if nk in self.chunks:                 # new chunk's lights spill in
                self.light_dirty.add(nk)

    # ------------------------------------------------------------------
    # entities & spawning
    # ------------------------------------------------------------------
    def update_entities(self, dt):
        for e in list(self.entities):
            e.update(self, dt)
        # despawn the dead / the far-away; on_remove may spawn children
        pp = self.player.pos if self.player is not None else None
        current = self.entities
        self.entities = []                       # children land here
        survivors = []
        for e in current:
            far = (pp is not None and not isinstance(e, PrimedTNT) and
                   math.hypot(e.pos[0] - pp[0], e.pos[2] - pp[2]) >= MOB_DESPAWN_DIST)
            if e.dead or far:
                e.on_remove(self)
                continue
            survivors.append(e)
        self.entities = survivors + self.entities
        self.debris.update(dt)
        self._try_spawn_mobs(dt)

    def attack(self, attacker, damage, origin, direction, reach):
        """Raycast from origin along direction; damage the nearest mob hit.
        Returns the entity hit, or None. 左键攻击命中最近的生物。"""
        from world.raycast import raycast_entity
        hit = raycast_entity(self, origin, direction, reach)
        if hit is None:
            return None
        ent, _dist = hit
        ent.hurt(damage, source_pos=origin)
        return ent

    def _try_spawn_mobs(self, dt):
        if self.player is None:
            return
        self._spawn_timer -= dt
        if self._spawn_timer > 0:
            return
        self._spawn_timer = MOB_SPAWN_INTERVAL
        for name, rule in SPAWN_RULES.items():
            cap = min(rule["max_count"] or MOB_CAP_PER_TYPE, MOB_CAP_PER_TYPE)
            count = sum(1 for e in self.entities if e.TYPE_NAME == name)
            if count >= cap:
                continue
            a = random.uniform(0, math.tau)
            d = random.uniform(MOB_SPAWN_MIN, MOB_SPAWN_MAX)
            x = int(math.floor(self.player.pos[0] + math.cos(a) * d))
            z = int(math.floor(self.player.pos[2] + math.sin(a) * d))
            if not self.is_loaded(x, z):
                continue
            y = self.surface_y(x, z)
            if y is None:
                continue
            surf = BLOCKS[int(self.get_block(x, y, z))]
            if surf is None or surf.name not in rule["spawn_on"]:
                continue
            cls = ENTITY_TYPES[name]
            self.entities.append(cls((x + 0.5, y + 1.01, z + 0.5)))

    def surface_y(self, x: int, z: int):
        c = self.chunks.get((x >> 4, z >> 4))
        if c is None:
            return None
        col = c.blocks[x & 15, :, z & 15]
        solid = np.nonzero(SOLID_LUT[col])[0]
        return int(solid[-1]) if len(solid) else None

    def respawn(self, player):
        player.pos[:] = self.spawn_pos
        player.vel[:] = 0
