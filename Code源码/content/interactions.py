"""Block interaction callbacks. 方块交互回调都集中在这里。

Unified signature: fn(world, pos, actor)
  world : the World object (full access: blocks, entities, weather...)
  pos   : (x, y, z) int block position
  actor : the entity that triggered it (player / mob / debris), may be None
"""


def tnt_interact(world, pos, actor):
    """Right-clicking TNT ignites it (变成点燃的TNT实体)."""
    world.ignite_tnt(pos)
    return True   # handled -> don't place a block instead


def jump_pad_step(world, pos, entity):
    """Standing/landing on a jump pad launches the entity upward.

    跳跳垫：固定上抛初速度 ~18 m/s -> 约 7~8 格跳高 (v^2 / 2g)。
    碎屑实体不会触发 on_step（它们走表面 bounciness 弹跳，见 debris.py），
    所以这里只会弹飞玩家和生物。
    """
    entity.vel[1] = 18.0
    entity.on_ground = False
    return True
