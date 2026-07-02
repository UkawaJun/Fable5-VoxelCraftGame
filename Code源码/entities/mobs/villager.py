"""Villager: a humanoid that wanders around. 会乱跑的类人生物（村民）。

行为全部继承自 MobBase 的 IDLE<->WANDER 游走；外观是人形（头/身/双臂/双腿），
走动时手脚摆动（renderer._draw_villager 用 anim_phase 驱动）。
"""

from content.registry import register_entity
from entities.mob import MobBase


class Villager(MobBase):
    AABB_SIZE = (0.6, 1.85, 0.4)
    MASS = 5.0
    WALK_SPEED = 1.5
    SKIN = (0.78, 0.60, 0.46, 1.0)     # head / hands
    ROBE = (0.45, 0.32, 0.55, 1.0)     # body / legs (purple-ish robe)

    def __init__(self, pos):
        super().__init__(pos)
        self.max_health = 12.0
        self.health = 12.0

    # wandering behaviour inherited; anim_phase (set in MobBase._walk_towards)
    # drives the limb swing in the renderer.


register_entity("villager", Villager,
                spawn_on=["grass", "snow_grass", "path"], max_count=6)
