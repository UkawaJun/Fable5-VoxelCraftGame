"""Slime: hops around, squashes on landing, splits when killed.

史莱姆：起跳移动 + 落地压扁；被打死会分裂成两只小史莱姆（小到一定程度才消失）。
添加新生物模板（见 README）：继承 MobBase，覆写 ai_* 钩子，register_entity 登记。
"""

import math
import random

from content.registry import register_entity
from entities.mob import MobBase


class Slime(MobBase):
    COLOR = (0.30, 0.82, 0.35, 0.6)   # translucent green
    KNOCKBACK_FACTOR = 1.3

    def __init__(self, pos, size: float = 1.0):
        super().__init__(pos)
        self.size = size
        s = 0.7 * size
        self.AABB_SIZE = (s, 0.65 * size, s)
        self.MASS = 2.0 * size            # light -> tossed far by explosions
        self.max_health = max(2.0, 8.0 * size)
        self.health = self.max_health
        self.jump_timer = random.uniform(0.6, 1.8)
        self.squash = 0.0                 # 1 = fully squashed (landing anim)
        self._was_airborne = False

    def update(self, world, dt):
        if self._was_airborne and self.on_ground:
            self.squash = 1.0
        self._was_airborne = not self.on_ground
        self.squash = max(0.0, self.squash - dt * 4.0)
        super().update(world, dt)

    # slimes don't walk — they jump (移动方式 = 朝随机方向起跳)
    def ai_idle(self, world, dt):
        self._decelerate(world, dt)
        self._try_jump(world, dt)

    def ai_wander(self, world, dt):
        self._decelerate(world, dt)
        self._try_jump(world, dt)

    def _try_jump(self, world, dt):
        if not self.on_ground:
            return
        self.jump_timer -= dt
        if self.jump_timer <= 0:
            self.jump_timer = random.uniform(0.7, 2.0) / max(0.6, self.size)
            a = self.heading if self.panic > 0 else random.uniform(0, math.tau)
            hop = 3.2 * (1.4 if self.panic > 0 else 1.0)
            self.vel[0] = math.cos(a) * hop
            self.vel[2] = math.sin(a) * hop
            self.vel[1] = 7.5
            self.yaw = a
            self.squash = 0.6

    def on_death(self):
        self._split = self.size > 0.55    # flagged; world spawns children

    def on_remove(self, world):
        """Spawn two smaller slimes when a big one dies. 分裂。"""
        if getattr(self, "_split", False):
            for _ in range(2):
                child = Slime((self.pos[0] + random.uniform(-0.3, 0.3),
                               self.pos[1] + 0.2,
                               self.pos[2] + random.uniform(-0.3, 0.3)),
                              size=self.size * 0.55)
                child.vel[0] = random.uniform(-2, 2)
                child.vel[1] = 4.0
                child.vel[2] = random.uniform(-2, 2)
                world.entities.append(child)

    @property
    def visual_scale(self):
        s = self.squash
        return 1.0 + 0.45 * s, 1.0 - 0.45 * s


register_entity("slime", Slime, spawn_on=["grass", "snow_grass"], max_count=8)
