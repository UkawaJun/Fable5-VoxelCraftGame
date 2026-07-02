"""Fluid lookup tables built from registered block names. 流体查表。

water       = source, level 8 (满格、永不枯竭)
water1..7   = flowing levels (7 highest .. 1 lowest); a source spreads 7 blocks.
渲染高度 = level/8；流体之间不画内部面。
"""

import numpy as np

from content.registry import MAX_BLOCK_TYPES, BLOCK_BY_NAME, block_id

FLUID_LUT = np.zeros(MAX_BLOCK_TYPES, dtype=bool)     # is this block a fluid?
FLUID_LEVEL = np.zeros(MAX_BLOCK_TYPES, dtype=np.uint8)  # 0 = not fluid, 1..8
LEVEL_TO_ID = [0] * 9                                 # level -> block id (1..8)
SOURCE_ID = 0
SOURCE_LEVEL = 8


def init():
    global SOURCE_ID
    SOURCE_ID = block_id("water")
    FLUID_LUT[SOURCE_ID] = True
    FLUID_LEVEL[SOURCE_ID] = SOURCE_LEVEL
    LEVEL_TO_ID[SOURCE_LEVEL] = SOURCE_ID
    for lvl in range(1, 8):
        i = block_id(f"water{lvl}")
        FLUID_LUT[i] = True
        FLUID_LEVEL[i] = lvl
        LEVEL_TO_ID[lvl] = i
    LEVEL_TO_ID[0] = 0


init()
