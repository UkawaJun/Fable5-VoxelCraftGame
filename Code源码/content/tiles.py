"""Texture atlas tile index table, shared by content definitions and the
procedural atlas generator (engine/texture_atlas.py).

图集瓦片索引表：content 与引擎共用，保证"定义方块"与"生成贴图"对得上号。
Atlas is a 16x16 grid of 16px tiles (256x256 px total).
"""

TILE = {
    "grass_top":     0,
    "grass_side":    1,
    "dirt":          2,
    "stone":         3,
    "sand":          4,
    "log_side":      5,
    "log_top":       6,
    "leaves":        7,
    "planks":        8,
    "glass":         9,
    "water":         10,
    "snow_top":      11,
    "snow_side":     12,
    "bedrock":       13,
    "glowstone":     14,
    "ice":           15,
    "tnt_side":      16,
    "tnt_top":       17,
    "jump_pad_top":  18,
    "jump_pad_side": 19,
    "white":         20,
    "sun":           21,
    "moon":          22,
    "rain":          23,
    "snowflake":     24,
    # ---- new blocks ----
    "cobblestone":      25,
    "mossy_cobble":     26,
    "gravel":           27,
    "bricks":           28,
    "bookshelf":        29,
    "pumpkin_top":      30,
    "jack_side":        31,
    "lantern":          32,
    "gold_block":       33,
    "diamond_block":    34,
    "obsidian":         35,
    "redstone_lamp":    36,
    "spruce_planks":    37,
    "white_wool":       38,
    "clay":             39,
    "hay_side":         40,
    "hay_top":          41,
    "path_top":         42,
}

ATLAS_COLS = 16        # tiles per row
TILE_PX = 16           # pixels per tile
ATLAS_PX = ATLAS_COLS * TILE_PX
