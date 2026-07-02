# Fable5-VoxelCraftGame
VoxelCraft is a high-performance voxel game framework written entirely in pure Python and generated from scratch by Claude Fable 5. Inspired by Minecraft, it leverages numpy vectorization for fast chunk updates, features rich physics, flowing water, day-night cycles, villages, and mobs — all running smoothly at 60 FPS.

该项目主要作为记录对Claude Code Fable5的尝鲜，所有内容均为Claude Code Fable5一口气生成，仅进行了三次改动的结果，运行方式很直接且进行了性能优化的工作

# PyCraft — 高性能 Python 体素游戏 Demo

以 Minecraft 为原型的可游玩 Demo：numpy 向量化体素引擎 + ModernGL 渲染。
柏林噪声地形、日夜循环、天气、SQLite 存档、TNT 爆炸碎屑物理、史莱姆和猪。

## 安装与运行

```bash
pip install -r requirements.txt
# 或: pip install pyglet moderngl numpy Pillow
python main.py
```

要求：Python 3.10+，支持 OpenGL 3.3 的显卡/驱动。
存档位于 `saves/world1.db`，删除该文件即开新世界（种子在 settings.py）。

## 操作

| 按键 | 功能 |
|---|---|
| W/A/S/D + 鼠标 | 移动 / 视角 |
| 空格 | 跳跃（水中上浮） |
| 按住 Ctrl | 疾跑（加速 1.6 倍） |
| 双击空格 | 切换飞行；飞行时 空格上升 / Shift 下降 |
| 鼠标左键 | 破坏方块；对着生物则攻击（可按住连续） |
| 鼠标右键 | 放置方块 / 交互（对 TNT 右键 = 点燃） |
| 鼠标中键 | 选取指向的方块到热栏 |
| 1~9 / 滚轮 | 切换热栏（18 格，滚轮循环全部） |
| F3 | 调试信息（FPS/坐标/区块/实体数） |
| F5 | 手动存档（退出时自动存档，每 60s 自动存档） |
| T（按住） | 时间快进 30 倍（看日出日落） |
| Y | 切换天气（晴 → 雨 → 雪） |
| Esc | 释放鼠标；再点击窗口重新捕获 |

## 玩法测试清单（物理参数演示）

- **TNT**：放置后右键点燃 → 3 秒白闪 → 爆炸。被炸开的方块变成碎屑抛飞，
  落地弹跳后**落定为真实方块**（散落一地）。把多个 TNT 放在一起会连锁殉爆。
- **跳跳垫**：踩上去弹飞约 8 格；TNT 碎屑落上去也会被反复弹起。
- **沙子**：把支撑挖掉，沙子整列下落。
- **冰**：在冰面上走会打滑（摩擦 0.05）。
- **基岩**：挖不动、炸不动（抗爆 ∞）。
- **萤石**：夜里自发光。
- **爆炸质量差异**：树叶(0.25)飞天，石头(3.0)矮抛；史莱姆(轻)被炸飞很远，猪(重)纹丝不动。

## 项目结构

```
main.py            入口/主循环/输入        settings.py  全局配置
engine/            渲染引擎(与逻辑解耦)    world/       区块/地形/柏林噪声/射线
physics/           AABB碰撞+物理参数       systems/     时间/天空/天气
content/           ★方块/物品/交互定义     entities/    玩家/生物/TNT/碎屑
persistence/       SQLite存档              ui/          HUD
```

---

# 二次开发模板

所有扩展只动 `content/` 和 `entities/mobs/`，引擎零修改。

## 1. 添加一个新方块（≤5 行）

```python
# content/blocks.py 末尾追加：
register_block("ruby_ore", BlockType(
    display="红宝石矿", textures=TILE["stone"],   # 先复用石头贴图
    hardness=3.0, mass=3.0, blast_resistance=6.0))
```

要新贴图：在 `content/tiles.py` 的 TILE 表加一个索引，
然后在 `engine/texture_atlas.py` 的 `build_atlas()` 里加几行像素生成代码。
之后在 `content/items.py` 加 `block_item("ruby_ore")` 即可出现在热栏（≤9个槽位）。

## 2. 调整/新增物理参数

```python
# 让羊毛极轻、几乎无抗爆 —— 爆炸时漫天飞舞：
register_block("wool", BlockType(..., mass=0.3, blast_resistance=0.1))
# 超级冰，比冰更滑：
register_block("packed_ice", BlockType(..., friction=0.02))
# 想加全新参数（如 slipperiness）：在 registry.BlockType 加字段，
# 然后在消费它的系统里读取（如 physics.py），属性定义与消费分离。
```

## 3. 添加交互（右键 / 踩踏）

```python
# content/interactions.py — 统一签名 fn(world, pos, actor)：
def heal_pad_step(world, pos, entity):
    entity.vel[1] = 25.0          # 超级弹射

# content/blocks.py:
register_block("super_pad", BlockType(..., on_step=heal_pad_step))
# 可用回调: on_interact(右键) / on_place / on_break / on_step(踩踏)
# world 对象有完整能力: world.set_block / world.explode / world.weather.force ...
```

## 4. 添加一个新物品

```python
# content/items.py:
register_item("rain_wand", ItemType(
    display="唤雨杖", icon_tile=TILE["water"],
    on_use=lambda world, player: world.weather.force("RAIN") or True))
```

## 5. 添加一个新生物

```python
# entities/mobs/chicken.py:
from content.registry import register_entity
from entities.mob import MobBase

class Chicken(MobBase):
    AABB_SIZE = (0.4, 0.7, 0.4)
    MASS = 1.0                      # 很轻 -> 爆炸飞最远
    WALK_SPEED = 1.0
    COLOR = (0.95, 0.95, 0.9, 1.0)
    # 覆写 ai_idle / ai_wander 自定义行为；默认即"游走+跳过障碍"

register_entity("chicken", Chicken, spawn_on=["grass"], max_count=6)
```

然后在 `main.py` 顶部 `import entities.mobs.chicken`，
在 `engine/renderer.py` 的 `_draw_entities` 里加一个盒子模型分支
（参考 `_draw_pig`，几行 `self._box(...)` 拼装即可）。

## 6. 调整爆炸 / 性能

`settings.py`：`TNT_POWER / TNT_RADIUS / EXPLOSION_DEBRIS_CAP / MAX_DEBRIS /
RENDER_DISTANCE / DAY_LENGTH` 等都可直接改。

## 无头测试

```bash
python test_headless.py   # 不开窗口验证: 地形/物理/爆炸/碎屑/沙子/存档
```

## 打包成 exe（Windows）

双击 `build_exe.bat`：自动建虚拟环境 → 装依赖 → 跑无头测试 → PyInstaller 打包，
产物为 `dist\PyCraft.exe`（单文件，存档生成在 exe 旁的 `saves\`）。
首次打包约需几分钟。确认运行稳定后，可把脚本里的打包命令加上
`--noconsole` 去掉黑色控制台窗口（出问题排查时建议保留 console）。
注意：PyInstaller 不支持交叉编译，exe 只能在 Windows 上构建。


## 新系统说明（v0.2 更新）

- **方块光照**：`world/lighting.py` 用 BFS 洪泛传播方块光级(0..15)，发光方块
  (`emissive>0`：萤石/灯笼/南瓜灯/红石灯) 为种子，光级烘焙进区块网格顶点。
  放置/破坏会触发受影响区块重算光照（光半径 15 < 区块宽 16，只影响 3x3 邻域）。
- **生物战斗**：实体有 `health/hurt_timer`；`world.attack()` 用 `raycast_entity`
  命中最近生物并 `hurt()`（扣血+击退+惊慌逃跑）；大史莱姆死亡分裂成两只小的。
- **疾跑/飞行**：`entities/player.py`，疾跑改水平目标速度，飞行走独立无重力分支。
- **更多方块**：见 `content/blocks.py` 末尾，每种仍只用数据驱动注册，引擎零修改。

## 测试

```bash
python test_headless.py    # 28 项：地形/物理/爆炸/碎屑/沙子/存档
python test_features.py    # 34 项：光照/战斗/分裂/疾跑/飞行/新方块
```
