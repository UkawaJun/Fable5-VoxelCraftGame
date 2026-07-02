# Fable5-VoxelCraftGame
VoxelCraft is a high-performance voxel game framework written entirely in pure Python and generated from scratch by Claude Fable 5. Inspired by Minecraft, it leverages numpy vectorization for fast chunk updates, features rich physics, flowing water, day-night cycles, villages, and mobs — all running smoothly at 60 FPS.

该项目主要作为记录对Claude Code Fable5的尝鲜，所有内容均为Claude Code Fable5一口气生成，仅进行了三次改动的结果，运行方式很直接且进行了性能优化的工作

# VoxelCraft

> **一个完全由 Claude Fable 5 从零生成的纯 Python 高性能体素游戏框架**

**中文简介**：  
VoxelCraft 是一个纯 Python 编写的高性能体素游戏框架，完全由 Claude Fable 5 从零生成。以 Minecraft 为原型，采用 numpy 向量化实现快速区块更新与渲染，具备完整物理系统、流动水、昼夜循环、自然村庄与生物，稳定 60 FPS 运行。

**English**：  
VoxelCraft is a high-performance voxel game framework written entirely in pure Python and generated from scratch by Claude Fable 5. Inspired by Minecraft, it leverages numpy vectorization for fast chunk updates, features rich physics, flowing water, day-night cycles, villages, and mobs — all running smoothly at 60 FPS.

---

## ✨ 项目概述

VoxelCraft 是一个**可直接游玩的 3D 第一人称体素 Demo**，目标是展示高性能 Python 体素引擎的完整实现。

核心亮点：
- 纯 Python + numpy 向量化网格生成 + ModernGL 渲染
- 完整物理模拟（爆炸碎屑、落沙、跳跳垫、质量差异击退等）
- 数据驱动的内容系统（新方块/物品/生物极简扩展）
- SQLite 差量存档 + 自动保存
- 丰富的世界系统（流动水、昼夜、天气、村庄、生物）

整个项目从架构设计、性能策略、物理系统到内容注册机制，**全部由 Claude Fable 5 在一次长对话中从零生成**，人类仅进行确认与少量整理。

---

## 🚀 安装与运行

```bash
pip install -r requirements.txt
python main.py
```

**要求**：Python 3.10+，支持 OpenGL 3.3 的显卡。

存档位于 `saves/world1.db`，删除该文件即可用新种子开新世界（种子可在 `settings.py` 中修改）。

**Windows 打包**：双击 `build_exe.bat` 可打包成单文件 `VoxelCraft.exe`。

---

## 🎮 操作说明

| 按键              | 功能                                      |
|-------------------|-------------------------------------------|
| W/A/S/D + 鼠标    | 移动 / 视角控制                           |
| 空格              | 跳跃（水中上浮）                          |
| 双击空格          | 切换飞行模式（飞行时空格上升、Shift下降） |
| 按住 Ctrl         | 疾跑（加速 1.6 倍）                       |
| 鼠标左键          | 破坏方块 / 攻击生物（可长按连击）         |
| 鼠标右键          | 放置方块 / 互动（右键点燃 TNT）           |
| 鼠标中键          | 吸取指向方块到热栏                        |
| 1~9 / 滚轮        | 切换热栏                                  |
| F3                | 调试信息（FPS、坐标、区块数、实体数等）   |
| F5                | 手动存档                                  |
| 按住 T            | 时间快进（约 30 倍速，观看日出日落）      |
| Y                 | 切换天气（晴 → 雨 → 雪）                  |
| Esc               | 释放鼠标 / 退出                           |

---

## 🌍 玩法与内容亮点

### 物理系统演示（核心特色）
- **TNT 爆炸**：右键点燃 → 白闪引信 → 爆炸。被炸方块变成**带翻滚的碎屑**抛飞，落地弹跳后写回为真实方块。多个 TNT 可连锁殉爆。
- **跳跳垫**：踩上去可弹飞约 8 格，碎屑落上也会被反复弹起。
- **沙子 / 砂砾**：失去支撑会自动整列下落。
- **冰面**：摩擦极低，走上去会打滑。
- **质量差异**：轻的史莱姆被爆炸击飞很远，重的猪几乎不动。
- **基岩**：挖不动、炸不动（抗爆无限）。

### 世界系统
- **流动水**：可无限流动（最远 7 格），支持无限水源机制，可形成瀑布和湖泊。
- **昼夜循环**：游戏内一天约 10 分钟，支持日出日落、太阳/月亮运行、动态天空色。
- **天气系统**：晴天 / 下雨 / 下雪 + GPU 粒子效果。
- **自然村庄**：世界中会生成小村庄（水井 + 3 种房屋模板），位置由种子决定。
- **生物**：
  - 村民（人形游荡）
  - 史莱姆（会跳跃，被打死会分裂成更小的）
  - 猪（慢速游走）

### 光照与视觉
- 夜间放置萤石、灯笼、南瓜灯、红石灯会真实照亮周围区域。
- 支持方块光照传播（v0.2 新增）。

---

## 🛠 项目结构

```
main.py              主入口与游戏循环
settings.py          全局配置（渲染距离、物理参数、时间等）
engine/              渲染引擎（相机、网格生成、渲染管线、着色器）
world/               世界与区块管理（numpy 数据、柏林噪声、地形生成、射线拾取）
physics/             物理系统（AABB 碰撞、碎屑模拟、爆炸）
systems/             环境系统（时间、天空、天气）
content/             ★ 内容定义层（方块、物品、交互注册 — 二次开发主要修改这里）
entities/            实体系统（玩家、生物、TNT、碎屑）
persistence/         SQLite 存档系统
ui/                  HUD（准星、热栏、调试信息）
```

**设计原则**：`engine` 不依赖游戏逻辑，`content` 不关心渲染细节。添加新内容只需修改 `content/` 和 `entities/mobs/` 目录。

---

## 🔧 二次开发模板

所有新内容注册后即可在游戏中出现，无需修改引擎代码。

### 添加一个新方块（≤ 5 行）
```python
# content/blocks.py 末尾
register_block("ruby_ore", BlockType(
    name="ruby_ore",
    textures=..., 
    hardness=3.0,
    mass=3.0,
    blast_resistance=6.0,
    drops="ruby"
))
```

### 添加交互（右键 / 踩踏）
```python
def super_jump(world, pos, entity):
    entity.velocity[1] = 25.0

register_block("super_pad", BlockType(..., on_step=super_jump))
```

### 添加新生物
继承 `MobBase`，覆写 AI 状态机方法，然后 `register_entity(...)` 即可。

完整扩展示例见 `DESIGN.md` 第 5 节。

---

## 🧪 测试与验证

项目包含多套测试脚本：

```bash
python test_headless.py    # 无头测试（地形、物理、爆炸、碎屑、存档等）
python test_features.py    # 功能测试（光照、战斗、生物分裂、疾跑飞行、新方块等）
```

---

## 📜 License

本项目采用 **Unlicense**，完全公共领域授权。  
任何人可自由使用、修改、商用、分发，无任何限制和义务。

---

**这个项目完整展示了 Claude Fable 5 在复杂系统级游戏框架上的强大能力**。  
从提示词到可运行的完整 Demo（包含渲染、物理、世界生成、存档、扩展机制），全部由 AI 独立完成。

欢迎运行、测试、扩展，或把你的新想法反馈给 Claude Fable 5 继续迭代！

*（本 README 由原始两个文档合并 + 优化整理）*


```bash
python test_headless.py    # 28 项：地形/物理/爆炸/碎屑/沙子/存档
python test_features.py    # 34 项：光照/战斗/分裂/疾跑/飞行/新方块
```
