"""All block definitions, data-driven. 所有方块都在这里定义，一条一个。

添加新方块模板（详见 README §二次开发）：
    register_block("my_block", BlockType(
        textures=(TILE["..."], TILE["..."]),   # (top, side[, bottom]) 或单个int
        mass=2.0, friction=0.6, blast_resistance=3.0, ...))

物理参数演示用例 (每个方块演示一个参数):
  sand      -> gravity_affected  悬空下落
  ice       -> friction=0.05     行走打滑
  bedrock   -> blast_resistance=inf  炸不动
  glowstone -> emissive          夜间发光
  tnt       -> 爆炸 + 碎屑
  jump_pad  -> bounciness + on_step  弹飞实体与碎屑
"""

import math

from content.registry import BlockType, register_block
from content.tiles import TILE
from content import interactions

INF = math.inf

# id 0 is always air ------------------------------------------------------
AIR = register_block("air", BlockType(
    solid=False, opaque=False, mass=0.0, blast_resistance=0.0))

register_block("grass", BlockType(
    display="草方块",
    textures=(TILE["grass_top"], TILE["grass_side"], TILE["dirt"]),
    mass=1.6, friction=0.6, blast_resistance=1.2))

register_block("dirt", BlockType(
    display="泥土", textures=TILE["dirt"],
    mass=1.6, friction=0.6, blast_resistance=1.2))

register_block("stone", BlockType(
    display="石头", textures=TILE["stone"],
    hardness=3.0, mass=3.0, blast_resistance=6.0))

register_block("sand", BlockType(
    display="沙子", textures=TILE["sand"],
    mass=1.4, friction=0.55, blast_resistance=0.8,
    gravity_affected=True))                       # ★ 失去支撑会下落

register_block("log", BlockType(
    display="原木",
    textures=(TILE["log_top"], TILE["log_side"]),
    mass=2.0, blast_resistance=4.0))

register_block("leaves", BlockType(
    display="树叶", textures=TILE["leaves"],
    opaque=False, alpha_test=True,
    mass=0.25, blast_resistance=0.2))             # 超轻 -> 爆炸时飞天

register_block("planks", BlockType(
    display="木板", textures=TILE["planks"],
    mass=1.8, blast_resistance=3.5))

register_block("glass", BlockType(
    display="玻璃", textures=TILE["glass"],
    opaque=False, translucent=True,
    mass=1.0, blast_resistance=0.3))

register_block("water", BlockType(
    display="水", textures=TILE["water"],
    solid=False, opaque=False, translucent=True,
    mass=0.0, blast_resistance=INF))              # 水炸不掉（也不产生碎屑）

register_block("snow_grass", BlockType(
    display="雪草",
    textures=(TILE["snow_top"], TILE["snow_side"], TILE["dirt"]),
    mass=1.6, friction=0.5, blast_resistance=1.2))

register_block("bedrock", BlockType(
    display="基岩", textures=TILE["bedrock"],
    hardness=INF, mass=100.0, blast_resistance=INF))   # ★ 抗爆∞

register_block("glowstone", BlockType(
    display="萤石", textures=TILE["glowstone"],
    emissive=1.0,                                  # ★ 夜间不变暗
    mass=1.2, blast_resistance=1.0))

register_block("ice", BlockType(
    display="冰", textures=TILE["ice"],
    opaque=False, translucent=True,
    friction=0.05,                                 # ★ 低摩擦
    mass=1.5, blast_resistance=0.8))

register_block("tnt", BlockType(
    display="TNT",
    textures=(TILE["tnt_top"], TILE["tnt_side"]),
    mass=1.5, blast_resistance=0.5,
    on_interact=interactions.tnt_interact))        # ★ 右键点燃

register_block("jump_pad", BlockType(
    display="跳跳垫",
    textures=(TILE["jump_pad_top"], TILE["jump_pad_side"]),
    bounciness=0.85,                               # ★ 碎屑落上反复弹跳
    mass=1.5, blast_resistance=2.0,
    on_step=interactions.jump_pad_step))           # ★ 实体落上被弹飞

# ============ 新增方块 (richer variety) ============

register_block("cobblestone", BlockType(
    display="圆石", textures=TILE["cobblestone"],
    hardness=3.0, mass=3.0, blast_resistance=6.0))

register_block("mossy_cobble", BlockType(
    display="苔石", textures=TILE["mossy_cobble"],
    hardness=3.0, mass=3.0, blast_resistance=6.0))

register_block("gravel", BlockType(
    display="砂砾", textures=TILE["gravel"],
    mass=1.4, friction=0.55, blast_resistance=0.8,
    gravity_affected=True))                        # 像沙子一样会塌

register_block("bricks", BlockType(
    display="砖块", textures=TILE["bricks"],
    hardness=2.0, mass=2.2, blast_resistance=5.0))

register_block("bookshelf", BlockType(
    display="书架",
    textures=(TILE["planks"], TILE["bookshelf"], TILE["planks"]),
    mass=1.6, blast_resistance=1.5))

register_block("jack_o_lantern", BlockType(
    display="南瓜灯",
    textures=(TILE["pumpkin_top"], TILE["jack_side"], TILE["pumpkin_top"]),
    emissive=1.0,                                  # ★ 光源 (满级15)
    mass=1.2, blast_resistance=1.0))

register_block("lantern", BlockType(
    display="灯笼", textures=TILE["lantern"],
    emissive=0.93,                                 # ★ 光源 (约14级)
    mass=0.8, blast_resistance=0.5))

register_block("gold_block", BlockType(
    display="金块", textures=TILE["gold_block"],
    hardness=3.0, mass=6.0, blast_resistance=6.0))

register_block("diamond_block", BlockType(
    display="钻石块", textures=TILE["diamond_block"],
    hardness=5.0, mass=5.0, blast_resistance=8.0))

register_block("obsidian", BlockType(
    display="黑曜石", textures=TILE["obsidian"],
    hardness=50.0, mass=12.0, blast_resistance=1200.0))  # 极难炸

register_block("redstone_lamp", BlockType(
    display="红石灯", textures=TILE["redstone_lamp"],
    emissive=1.0,                                  # ★ 光源 (满级15)
    mass=1.2, blast_resistance=1.0))

# ============ 流动水：7 个流动级别（与源块 water 同贴图，渲染高度递减） ============
# water = 源(满, level 8); water1..water7 = 流动(7 最高、1 最低)，最远从源流 7 格。
for _lvl in range(1, 8):
    register_block(f"water{_lvl}", BlockType(
        display=f"流水{_lvl}", textures=TILE["water"],
        solid=False, opaque=False, translucent=True,
        mass=0.0, blast_resistance=INF))

# ============ 村庄建材 / 装饰方块 ============
register_block("spruce_planks", BlockType(
    display="云杉木板", textures=TILE["spruce_planks"],
    mass=1.8, blast_resistance=3.5))

register_block("white_wool", BlockType(
    display="白羊毛", textures=TILE["white_wool"],
    mass=0.4, blast_resistance=0.4))           # 很轻，爆炸时漫天飞

register_block("clay", BlockType(
    display="黏土", textures=TILE["clay"],
    mass=1.6, blast_resistance=1.0))

register_block("hay_bale", BlockType(
    display="干草捆",
    textures=(TILE["hay_top"], TILE["hay_side"]),
    mass=0.8, blast_resistance=0.6))

register_block("path", BlockType(
    display="小路",
    textures=(TILE["path_top"], TILE["dirt"], TILE["dirt"]),
    mass=1.4, friction=0.65, blast_resistance=1.0))
