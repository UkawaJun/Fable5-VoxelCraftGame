"""Primed TNT entity. 点燃的TNT：白闪 + 引信倒计时 + 爆炸。"""

import math
import random

from settings import TNT_FUSE, TNT_POWER, TNT_RADIUS
from entities.entity import Entity


class PrimedTNT(Entity):
    TYPE_NAME = "primed_tnt"
    AABB_SIZE = (0.98, 0.98, 0.98)
    MASS = 3.0

    def __init__(self, pos, fuse: float = TNT_FUSE):
        super().__init__(pos)
        self.fuse = fuse
        # small random hop, like MC
        a = random.uniform(0, math.tau)
        self.vel[0] = math.cos(a) * 1.2
        self.vel[2] = math.sin(a) * 1.2
        self.vel[1] = 4.0

    def update(self, world, dt):
        super().update(world, dt)
        if self.on_ground:
            self.vel[0] *= 0.85
            self.vel[2] *= 0.85
        self.fuse -= dt
        if self.fuse <= 0 and not self.dead:
            self.dead = True
            c = self.centre()
            world.explode(c[0], c[1], c[2], TNT_POWER, TNT_RADIUS)

    @property
    def flash(self) -> float:
        """0..1 white flash, blinking faster as the fuse runs out."""
        speed = 4.0 + max(0.0, (TNT_FUSE - self.fuse)) * 4.0
        return 0.5 + 0.5 * math.sin(self.age * speed * math.pi)

    def serialize(self):
        d = super().serialize()
        d["fuse"] = self.fuse
        return d

    def deserialize(self, data):
        super().deserialize(data)
        self.fuse = data.get("fuse", TNT_FUSE)
