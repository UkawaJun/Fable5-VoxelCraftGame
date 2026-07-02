"""Debris system: blocks knocked loose fly as entities, then settle back
into the voxel grid — the block<->entity two-way conversion (DESIGN §4.5.1).

碎屑系统：方块→实体→方块 的双向转换，TNT 爆炸与落沙共用。
所有碎屑存在一组 numpy 数组里，整批积分；逐个做体素碰撞（数量有上限）。
"""

import math

import numpy as np

from settings import GRAVITY, MAX_DEBRIS
from content.registry import BLOCKS, SOLID_LUT

_SETTLE_SPEED = 0.8     # below this (and grounded) the settle timer runs
_SETTLE_TIME = 0.35     # seconds of rest before re-placing into the grid
_FORCE_SETTLE_AGE = 30.0


class DebrisSystem:
    def __init__(self, world, cap: int = MAX_DEBRIS):
        self.world = world
        self.cap = cap
        self.pos = np.zeros((cap, 3), dtype=np.float64)
        self.vel = np.zeros((cap, 3), dtype=np.float64)
        self.bid = np.zeros(cap, dtype=np.int32)
        self.rot = np.zeros(cap, dtype=np.float32)       # tumble angle
        self.rotv = np.zeros(cap, dtype=np.float32)      # tumble speed
        self.settle = np.zeros(cap, dtype=np.float32)
        self.age = np.zeros(cap, dtype=np.float32)
        self.grounded = np.zeros(cap, dtype=bool)
        self.active = np.zeros(cap, dtype=bool)
        self._free = list(range(cap - 1, -1, -1))
        self.count = 0

    # ------------------------------------------------------------------
    def spawn(self, bid: int, pos, vel) -> bool:
        """block -> debris. Returns False when at capacity (caller decides
        whether the block just vanishes instead)."""
        if not self._free:
            return False
        i = self._free.pop()
        self.pos[i] = pos
        self.vel[i] = vel
        self.bid[i] = bid
        self.rot[i] = 0.0
        speed = float(np.linalg.norm(vel))
        self.rotv[i] = (np.random.uniform(-1, 1)) * (2.0 + speed * 0.6)
        self.settle[i] = 0.0
        self.age[i] = 0.0
        self.grounded[i] = False
        self.active[i] = True
        self.count += 1
        return True

    def _kill(self, i: int):
        self.active[i] = False
        self._free.append(i)
        self.count -= 1

    # ------------------------------------------------------------------
    def update(self, dt: float):
        if self.count == 0:
            return
        act = self.active
        # ---- batch integration (vectorised) ----
        self.vel[act, 1] -= GRAVITY * dt
        self.age[act] += dt
        self.rot[act] += self.rotv[act] * dt

        world = self.world
        for i in np.nonzero(act)[0]:
            self._step_one(world, int(i), dt)

    def _step_one(self, world, i: int, dt: float):
        px, py, pz = self.pos[i]
        vx, vy, vz = self.vel[i]
        nx, ny, nz = px + vx * dt, py + vy * dt, pz + vz * dt

        # if chunk not loaded, freeze in place (far-away debris)
        if not world.is_loaded(nx, nz):
            self.vel[i] = 0
            return

        # ---- vertical ----
        if vy <= 0.0:
            cell_y = math.floor(ny - 0.05)
            if SOLID_LUT[world.get_block(math.floor(nx), cell_y, math.floor(nz))]:
                ny = cell_y + 1.05
                impact = -vy
                surf = BLOCKS[world.get_block(math.floor(nx), cell_y, math.floor(nz))]
                bounce = 0.25 + (surf.bounciness if surf else 0.0)
                if impact > 2.5:
                    vy = impact * min(bounce, 0.95)
                    vx *= 0.55
                    vz *= 0.55
                    self.rotv[i] *= 0.6
                    self.grounded[i] = False
                else:
                    vy = 0.0
                    vx *= 0.6
                    vz *= 0.6
                    self.grounded[i] = True
            else:
                self.grounded[i] = False
        else:
            head = math.floor(ny + 0.3)
            if SOLID_LUT[world.get_block(math.floor(nx), head, math.floor(nz))]:
                vy = 0.0
                ny = py

        # ---- horizontal (point sample at body centre) ----
        cy = math.floor(ny + 0.125)
        if SOLID_LUT[world.get_block(math.floor(nx), cy, math.floor(pz))]:
            nx = px
            vx = 0.0
        if SOLID_LUT[world.get_block(math.floor(nx), cy, math.floor(nz))]:
            nz = pz
            vz = 0.0

        self.pos[i] = (nx, ny, nz)
        self.vel[i] = (vx, vy, vz)

        # ---- settling: debris -> block (落定 -> 写回体素网格) ----
        speed = abs(vx) + abs(vy) + abs(vz)
        if (self.grounded[i] and speed < _SETTLE_SPEED) or self.age[i] > _FORCE_SETTLE_AGE:
            self.settle[i] += dt
            if self.settle[i] >= _SETTLE_TIME or self.age[i] > _FORCE_SETTLE_AGE:
                self._place(world, i)
        else:
            self.settle[i] = 0.0

        if self.pos[i][1] < -32:
            self._kill(i)                      # fell out of the world

    def _place(self, world, i: int):
        """Re-place the debris as a real block at the nearest free cell."""
        x = math.floor(self.pos[i][0])
        z = math.floor(self.pos[i][2])
        y = math.floor(self.pos[i][1] + 0.1)
        bid = int(self.bid[i])
        for dy in range(0, 8):                 # occupied -> search upward
            yy = y + dy
            if yy < 0 or yy > 126:
                continue
            cur = world.get_block(x, yy, z)
            if cur == 0 or not SOLID_LUT[cur]:
                world.set_block(x, yy, z, bid)
                self._kill(i)
                return
        self._kill(i)                          # nowhere to go -> vanish

    # ------------------------------------------------------------------
    def render_arrays(self):
        """(positions, rotations, block_ids) of active debris, for the
        instanced renderer."""
        idx = np.nonzero(self.active)[0]
        return (self.pos[idx].astype(np.float32),
                self.rot[idx].astype(np.float32),
                self.bid[idx].astype(np.float32))

    # ------------------------------------------------------------------
    def serialize(self) -> list:
        out = []
        for i in np.nonzero(self.active)[0]:
            out.append({"bid": int(self.bid[i]),
                        "pos": [float(v) for v in self.pos[i]],
                        "vel": [float(v) for v in self.vel[i]]})
        return out

    def deserialize(self, items: list):
        for d in items:
            self.spawn(d["bid"], d["pos"], d["vel"])
