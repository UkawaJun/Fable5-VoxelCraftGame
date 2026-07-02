"""Item definitions + the demo hotbar. 物品定义与热栏内容。

热栏现在有 18 格：数字键 1-9 选前 9 格，鼠标滚轮可循环到全部。
添加新物品模板：
    register_item("rain_wand", ItemType(
        display="唤雨杖", icon_tile=TILE["water"],
        on_use=lambda world, player: world.weather.force("RAIN") or True))
放置类物品用 block_item() 工厂一行生成。
"""

from content.registry import block_item

# Hotbar (slots cycled with the scroll wheel; 1-9 select the first nine) ----
HOTBAR = [
    block_item("grass"),
    block_item("cobblestone"),
    block_item("planks"),
    block_item("bricks"),
    block_item("glass"),
    block_item("sand"),
    block_item("gravel"),
    block_item("ice"),
    block_item("glowstone"),
    block_item("lantern"),
    block_item("jack_o_lantern"),
    block_item("redstone_lamp"),
    block_item("gold_block"),
    block_item("diamond_block"),
    block_item("obsidian"),
    block_item("bookshelf"),
    block_item("tnt"),
    block_item("jump_pad"),
    block_item("water", "水(可放置流动)"),
    block_item("spruce_planks"),
    block_item("white_wool"),
    block_item("hay_bale"),
]

# extra placeables (not on the hotbar; reachable via middle-click pick) ----
block_item("dirt")
block_item("stone")
block_item("mossy_cobble")
block_item("log")
block_item("leaves")
block_item("snow_grass")
block_item("clay")
block_item("path")
