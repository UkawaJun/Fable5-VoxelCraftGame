"""MobBase: tiny AI state machine skeleton. 生物AI状态机骨架。

States: IDLE -> WANDER -> (back to IDLE). Subclasses override the
ai_* hooks they care about — adding a new mob means subclassing this
and registering it (see README templates / entities/mobs/*.py).

战斗：可被玩家攻击 -> hurt() 扣血 + 击退 + 惊慌逃跑(panic)。
"""

import math
import random

import numpy as np

from physics.physics import ground_friction
from entities.entity import Entity

IDLE, WANDER = 0, 1


class MobBase(Entity):
    WALK_SPEED = 1.2
    JUMP_SPEED = 6.5

    def __init__(self, pos):
        super().__init__(pos)
        self.state = IDLE
        self.state_timer = random.uniform(1.0, 3.0)
        self.heading = random.uniform(0, math.tau)   # wander direction
        self.anim_phase = 0.0                        # legs / squash animation
        self.panic = 0.0                             # >0 -> flee faster

    # ------------------------------------------------------------------
    def update(self, world, dt):
        self.age += dt
        if self.hurt_timer > 0:
            self.hurt_timer = max(0.0, self.hurt_timer - dt)
        if self.panic > 0:
            self.panic = max(0.0, self.panic - dt)
        self.state_timer -= dt
        if self.state == IDLE:
            self.ai_idle(world, dt)
            if self.state_timer <= 0:
                self.state = WANDER
                self.state_timer = random.uniform(2.0, 5.0)
                self.heading = random.uniform(0, math.tau)
        else:
            self.ai_wander(world, dt)
            if self.state_timer <= 0:
                self.state = IDLE
                self.state_timer = random.uniform(1.0, 4.0)
        self.physics(world, dt)
        if self.pos[1] < -16:
            self.dead = True

    # -- combat ----------------------------------------------------------
    def hurt(self, amount, source_pos=None):
        died = super().hurt(amount, source_pos)
        if not died and source_pos is not None:
            dx = self.pos[0] - source_pos[0]
            dz = self.pos[2] - source_pos[2]
            self.heading = math.atan2(dz, dx)         # flee away
            self.state = WANDER
            self.state_timer = 2.5
            self.panic = 2.0
        return died

    # -- hooks (override these) ----------------------------------------
    def ai_idle(self, world, dt):
        self._decelerate(world, dt)

    def ai_wander(self, world, dt):
        speed = self.WALK_SPEED * (2.2 if self.panic > 0 else 1.0)
        self._walk_towards(world, self.heading, speed, dt)
        # hop over obstacles
        if self.hit_wall and self.on_ground:
            self.vel[1] = self.JUMP_SPEED

    # -- helpers ---------------------------------------------------------
    def _walk_towards(self, world, heading, speed, dt):
        wish = np.array([math.cos(heading), 0.0, math.sin(heading)])
        f = ground_friction(world, self) if self.on_ground else 0.15
        k = min(1.0, f * 12.0 * dt)
        self.vel[0] += (wish[0] * speed - self.vel[0]) * k
        self.vel[2] += (wish[2] * speed - self.vel[2]) * k
        # face where we walk (smoothed)
        target = math.atan2(self.vel[2], self.vel[0])
        d = (target - self.yaw + math.pi) % math.tau - math.pi
        self.yaw += d * min(1.0, 8.0 * dt)
        self.anim_phase += math.hypot(self.vel[0], self.vel[2]) * dt * 3.0

    def _decelerate(self, world, dt):
        if self.on_ground:
            f = ground_friction(world, self)
            k = max(0.0, 1.0 - f * 12.0 * dt)
            self.vel[0] *= k
            self.vel[2] *= k
