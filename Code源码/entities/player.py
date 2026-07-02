"""Player entity: input intent -> friction-based movement -> physics.

玩家移动用"摩擦收敛"模型：水平速度向目标速度收敛，收敛速率 ∝ 脚下方块摩擦，
所以站在冰上(0.05)会打滑 —— 物理参数直接产生手感差异，无特判代码。

新增：
  疾跑 sprint —— 按住 Ctrl，水平目标速度 ×1.6。
  飞行 flying —— 双击空格切换；飞行时无重力，空格上升/Shift 下降，仍与方块碰撞。
"""

import math

from settings import (FLY_SPEED, FLY_VERT_SPEED, PLAYER_AABB, PLAYER_EYE,
                      PLAYER_JUMP_SPEED, PLAYER_SPEED, PLAYER_SPRINT_MULT)
from physics.physics import ground_friction, move_entity
from entities.entity import Entity
from content.items import HOTBAR


class Player(Entity):
    TYPE_NAME = "player"
    AABB_SIZE = PLAYER_AABB
    MASS = 5.0
    KNOCKBACK_FACTOR = 1.0

    def __init__(self, pos):
        super().__init__(pos)
        self.pitch = 0.0
        self.hotbar = HOTBAR
        self.slot = 0
        # input intent, set by main.py each frame
        self.move_x = 0.0     # strafe  (-1..1)
        self.move_z = 0.0     # forward (-1..1)
        self.want_jump = False
        self.sprinting = False
        self.flying = False
        self.fly_up = False   # Space while flying
        self.fly_down = False # Shift while flying

    @property
    def eye_pos(self):
        p = self.pos.copy()
        p[1] += PLAYER_EYE
        return p

    def look_dir(self):
        cp = math.cos(self.pitch)
        return (math.cos(self.yaw) * cp,
                math.sin(self.pitch),
                math.cos(self.pitch) * 0 + math.sin(self.yaw) * cp)

    def selected_item(self):
        return self.hotbar[self.slot]

    # ------------------------------------------------------------------
    def update(self, world, dt):
        self.age += dt
        fx, fz = math.cos(self.yaw), math.sin(self.yaw)     # forward
        rx, rz = -fz, fx                                    # right
        wx = fx * self.move_z + rx * self.move_x
        wz = fz * self.move_z + rz * self.move_x
        mag = math.hypot(wx, wz)

        if self.flying:
            self._update_fly(world, dt, wx, wz, mag)
            return

        speed = PLAYER_SPEED * (PLAYER_SPRINT_MULT if self.sprinting else 1.0)
        if mag > 1e-6:
            wx, wz = wx / mag * speed, wz / mag * speed
        else:
            wx = wz = 0.0

        if self.on_ground:
            f = ground_friction(world, self)
            k = min(1.0, f * 12.0 * dt)
        else:
            k = min(1.0, 1.8 * dt)                          # weak air control
        self.vel[0] += (wx - self.vel[0]) * k
        self.vel[2] += (wz - self.vel[2]) * k

        if self.want_jump:
            if self.on_ground:
                self.vel[1] = PLAYER_JUMP_SPEED
            elif self.in_water:
                self.vel[1] = 3.0                           # swim up

        self.physics(world, dt)

        if self.pos[1] < -12:                               # void -> respawn
            world.respawn(self)

    def _update_fly(self, world, dt, wx, wz, mag):
        """No gravity; vertical from keys; still collides with terrain."""
        if mag > 1e-6:
            wx, wz = wx / mag * FLY_SPEED, wz / mag * FLY_SPEED
        else:
            wx = wz = 0.0
        k = min(1.0, 10.0 * dt)
        self.vel[0] += (wx - self.vel[0]) * k
        self.vel[2] += (wz - self.vel[2]) * k
        vy = (FLY_VERT_SPEED if self.fly_up else 0.0) - \
             (FLY_VERT_SPEED if self.fly_down else 0.0)
        self.vel[1] = vy
        move_entity(world, self, dt)                        # collide, no gravity
        if self.pos[1] < -12:
            world.respawn(self)

    def toggle_fly(self):
        self.flying = not self.flying
        self.vel[1] = 0.0

    def serialize(self):
        d = super().serialize()
        d["pitch"] = self.pitch
        d["slot"] = self.slot
        d["flying"] = self.flying
        return d

    def deserialize(self, data):
        super().deserialize(data)
        self.pitch = data.get("pitch", 0.0)
        self.slot = int(data.get("slot", 0))
        self.flying = bool(data.get("flying", False))
