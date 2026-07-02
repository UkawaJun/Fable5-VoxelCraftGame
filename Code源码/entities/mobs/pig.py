"""Pig: slow wanderer with swinging legs. 猪：慢速游走、走走停停、腿部摆动。"""

from content.registry import register_entity
from entities.mob import MobBase


class Pig(MobBase):
    AABB_SIZE = (0.9, 0.9, 0.9)
    MASS = 6.0                 # heavy -> explosions barely move it (vs slime)
    WALK_SPEED = 1.3
    COLOR = (0.94, 0.62, 0.65, 1.0)   # pink

    def __init__(self, pos):
        super().__init__(pos)
        self.max_health = 10.0
        self.health = 10.0

    # all wandering behaviour comes from MobBase; anim_phase drives leg swing.


register_entity("pig", Pig, spawn_on=["grass", "snow_grass"], max_count=8)
