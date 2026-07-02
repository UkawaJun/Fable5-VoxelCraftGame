"""Block / Item / Entity registries — the core extension mechanism.

注册表机制：引擎只认 ID 和属性，所有内容（方块/物品/生物）在这里登记。
添加新内容 = 调一次 register_*()，引擎代码零修改。

Physics parameters live on every BlockType (§4.5 of DESIGN.md):
  mass / friction / bounciness / blast_resistance / gravity_affected
"""

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

# ----------------------------------------------------------------------------
# Block registry
# ----------------------------------------------------------------------------

MAX_BLOCK_TYPES = 256  # uint8 storage


@dataclass
class BlockType:
    name: str = ""              # assigned by register_block
    display: str = ""
    # texture atlas tile indices: (top, side, bottom). int -> all faces same.
    textures: tuple = (0, 0, 0)
    solid: bool = True            # collides with entities
    opaque: bool = True           # culls neighbour faces / blocks light
    translucent: bool = False     # rendered in the blended pass (water/glass/ice)
    alpha_test: bool = False      # cut-out transparency (leaves)
    hardness: float = 1.0         # kept for future timed digging (demo: instant)
    drops: Optional[str] = None   # None = drops itself
    emissive: float = 0.0         # 0..1 self illumination (glowstone)
    # ---- universal physics parameters (万物物理参数) ----
    mass: float = 2.0             # debris launch speed = impulse / mass
    friction: float = 0.6         # surface friction (ice = 0.05)
    bounciness: float = 0.0       # restitution of the surface
    blast_resistance: float = 3.0 # inf => unbreakable by explosions
    gravity_affected: bool = False  # sand-like: falls when unsupported
    # ---- callbacks: fn(world, pos, actor) ----
    on_interact: Optional[Callable] = None  # right click
    on_place: Optional[Callable] = None
    on_break: Optional[Callable] = None
    on_step: Optional[Callable] = None      # an entity landed on it
    # assigned by register_block:
    id: int = -1

    def tex(self):
        t = self.textures
        if isinstance(t, int):
            return (t, t, t)
        if len(t) == 1:
            return (t[0], t[0], t[0])
        if len(t) == 2:            # (top, side) -> bottom = top
            return (t[0], t[1], t[0])
        return t


BLOCKS: list = [None] * MAX_BLOCK_TYPES   # id -> BlockType
BLOCK_BY_NAME: dict = {}
_next_block_id = 0

# numpy lookup tables, rebuilt after every registration (fast hot-path access)
OPAQUE_LUT = np.zeros(MAX_BLOCK_TYPES, dtype=bool)
SOLID_LUT = np.zeros(MAX_BLOCK_TYPES, dtype=bool)
EMISSIVE_LUT = np.zeros(MAX_BLOCK_TYPES, dtype=np.float32)
TRANSLUCENT_LUT = np.zeros(MAX_BLOCK_TYPES, dtype=bool)
ALPHATEST_LUT = np.zeros(MAX_BLOCK_TYPES, dtype=bool)
GRAVITY_LUT = np.zeros(MAX_BLOCK_TYPES, dtype=bool)
# per-face texture tiles: TEX_LUT[face_dir, block_id]; dirs: +x -x +y -y +z -z
TEX_LUT = np.zeros((6, MAX_BLOCK_TYPES), dtype=np.int32)


def register_block(name: str, bt: BlockType) -> BlockType:
    """Register a block type. 添加新方块的唯一入口（见 README 模板）。"""
    global _next_block_id
    if name in BLOCK_BY_NAME:
        raise ValueError(f"block '{name}' already registered")
    bt.name = name
    if not bt.display:
        bt.display = name
    bt.id = _next_block_id
    _next_block_id += 1
    BLOCKS[bt.id] = bt
    BLOCK_BY_NAME[name] = bt

    i = bt.id
    OPAQUE_LUT[i] = bt.opaque
    SOLID_LUT[i] = bt.solid
    EMISSIVE_LUT[i] = bt.emissive
    TRANSLUCENT_LUT[i] = bt.translucent
    ALPHATEST_LUT[i] = bt.alpha_test
    GRAVITY_LUT[i] = bt.gravity_affected
    top, side, bottom = bt.tex()
    TEX_LUT[0, i] = TEX_LUT[1, i] = TEX_LUT[4, i] = TEX_LUT[5, i] = side
    TEX_LUT[2, i] = top
    TEX_LUT[3, i] = bottom
    return bt


def block(name: str) -> BlockType:
    return BLOCK_BY_NAME[name]


def block_id(name: str) -> int:
    return BLOCK_BY_NAME[name].id


# ----------------------------------------------------------------------------
# Item registry
# ----------------------------------------------------------------------------

@dataclass
class ItemType:
    name: str = ""
    display: str = ""
    icon_tile: int = 0                       # atlas tile drawn in the hotbar
    places_block: Optional[str] = None       # block name placed on right click
    on_use: Optional[Callable] = None        # fn(world, player) -> bool(handled)


ITEMS: dict = {}


def register_item(name: str, it: ItemType) -> ItemType:
    it.name = name
    if not it.display:
        it.display = name
    ITEMS[name] = it
    return it


def block_item(block_name: str, display: str = "") -> ItemType:
    """Factory: an item that places the given block. 一行生成放置类物品。"""
    bt = BLOCK_BY_NAME[block_name]
    return register_item(block_name, ItemType(
        display=display or bt.display,
        icon_tile=bt.tex()[1],
        places_block=block_name,
    ))


# ----------------------------------------------------------------------------
# Entity registry
# ----------------------------------------------------------------------------

ENTITY_TYPES: dict = {}        # name -> class
SPAWN_RULES: dict = {}         # name -> dict(spawn_on=[block names], max_count=int)


def register_entity(name: str, cls, spawn_on=None, max_count=0):
    """Register a mob class. spawn_on: surface blocks it may spawn on."""
    ENTITY_TYPES[name] = cls
    cls.TYPE_NAME = name
    if spawn_on:
        SPAWN_RULES[name] = {"spawn_on": list(spawn_on), "max_count": max_count}
    return cls
