"""Entity base class. 实体基类：位置/速度/AABB/物理参数/血量/序列化。

Entity physics parameters (万物物理参数 —— 实体侧):
  MASS              explosion impulse -> velocity = impulse / mass
  GRAVITY_SCALE     1.0 normal, <1 floaty
  DRAG              air resistance per second
  KNOCKBACK_FACTOR  multiplier on received knockback
"""

import numpy as np

from physics.physics import physics_step


class Entity:
    TYPE_NAME = "entity"
    AABB_SIZE = (0.6, 0.6, 0.6)        # w, h, d
    MASS = 5.0
    GRAVITY_SCALE = 1.0
    DRAG = 0.0
    KNOCKBACK_FACTOR = 1.0

    def __init__(self, pos):
        self.pos = np.array(pos, dtype=np.float64)   # feet-centre position
        self.vel = np.zeros(3, dtype=np.float64)
        self.on_ground = False
        self.in_water = False
        self.hit_wall = False
        self.impact_speed = 0.0
        self.dead = False
        self.age = 0.0
        self.yaw = 0.0                               # facing, radians
        self.max_health = 1.0
        self.health = 1.0
        self.hurt_timer = 0.0                        # >0 -> red flash

    # -- physics ------------------------------------------------------------
    def physics(self, world, dt):
        return physics_step(world, self, dt)

    def update(self, world, dt):
        self.age += dt
        if self.hurt_timer > 0:
            self.hurt_timer = max(0.0, self.hurt_timer - dt)
        self.physics(world, dt)
        if self.pos[1] < -16:
            self.dead = True                         # fell out of the world

    def apply_knockback(self, impulse_vec):
        self.vel += np.asarray(impulse_vec) * (self.KNOCKBACK_FACTOR / self.MASS)
        self.on_ground = False

    def hurt(self, amount, source_pos=None):
        """Take damage; returns True if it died. 受到伤害。"""
        if self.dead:
            return False
        self.health -= amount
        self.hurt_timer = 0.35
        if source_pos is not None:                   # knock away from attacker
            d = self.centre() - np.asarray(source_pos, dtype=np.float64)
            d[1] = 0.0
            n = np.linalg.norm(d)
            if n > 1e-6:
                kb = d / n * 6.0
                kb[1] = 4.5
                self.vel += kb
                self.on_ground = False
        if self.health <= 0:
            self.dead = True
            self.on_death()
            return True
        return False

    def on_death(self):
        """Hook for death effects (override in subclasses). 死亡回调。"""
        pass

    def on_remove(self, world):
        """Called by the world right before this entity is removed
        (death or despawn). 用于死亡分裂等效果。"""
        pass

    def centre(self):
        c = self.pos.copy()
        c[1] += self.AABB_SIZE[1] * 0.5
        return c

    # -- persistence ----------------------------------------------------------
    def serialize(self) -> dict:
        return {
            "pos": [float(v) for v in self.pos],
            "vel": [float(v) for v in self.vel],
            "yaw": float(self.yaw),
            "health": float(self.health),
        }

    def deserialize(self, data: dict):
        self.pos[:] = data.get("pos", self.pos)
        self.vel[:] = data.get("vel", self.vel)
        self.yaw = data.get("yaw", 0.0)
        self.health = data.get("health", self.max_health)
