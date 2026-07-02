# PyCraft — 高性能 Python 体素游戏框架设计文档

> 版本: v0.1 (设计稿，待确认后开始编码)
> 目标: 一个以 Minecraft 为原型、可游玩的 3D 第一人称体素 Demo，
> 底层为纯 Python 高性能引擎，强调"快速方块增删 + 物理模拟 + 易扩展"。

---

## 1. 设计目标与核心指标

| 目标 | 具体指标 |
|---|---|
| 流畅渲染 | 渲染距离 6~8 区块时稳定 60 FPS |
| 快速方块编辑 | 单次破坏/放置后，区块网格重建 < 5ms（下一帧即可见） |
| 物理模拟 | 玩家 + 生物 AABB 碰撞、重力、跳跃，每帧全量更新无卡顿 |
| 易扩展 | 新方块 ≤ 5 行注册代码；新物品 ≤ 3 行；新生物只需继承一个基类 |
| 零重型依赖 | 仅 `pyglet + moderngl + numpy + Pillow`，存档用标准库 `sqlite3` |

**性能策略总览（为什么能比"传统写法"快）：**

1. **数据层**：每个区块是一个 `numpy uint8` 三维数组（16×128×16），
   而不是 Python 对象字典 —— 内存连续、批量运算快两个数量级。
2. **网格层**：用 numpy 数组位移比较做 **面剔除**（只生成暴露在空气中的面），
   整个区块的网格一次性向量化生成，不写任何 per-block 的 Python 循环。
3. **渲染层**：ModernGL 把每个区块烘成一个 VBO，方块编辑只重建**所在区块**
   （跨边界时附带相邻区块），其余区块的 VBO 原封不动。
4. **裁剪层**：视锥剔除（Frustum Culling）按区块 AABB 过滤，看不见的区块不发 draw call。
5. **生成层**：地形生成放在后台线程，主线程永不因生成新区块而掉帧。

---

## 2. 技术栈

| 组件 | 选型 | 用途 |
|---|---|---|
| 窗口/输入 | pyglet 2.x | 窗口、键鼠事件、主循环、HUD 文本 |
| 渲染 | moderngl | OpenGL 3.3 Core，VBO/VAO/Shader 管理 |
| 数值计算 | numpy | 区块数据、网格生成、柏林噪声、碰撞批量检测 |
| 纹理 | Pillow | 启动时**程序化生成**纹理图集（无需外部美术资源） |
| 存档 | sqlite3 (标准库) | 世界元数据、区块、玩家、实体的本地数据库 |
| 噪声 | 自实现 | numpy 向量化 2D/3D Perlin + FBM 分形叠加 |

> 注：柏林噪声不用 C 扩展库（如 `noise`），自实现向量化版本，
> 一次调用即可算出整个 16×16 高度图，且保证跨平台零编译安装。

---

## 3. 项目结构

```
pycraft/
├── main.py                  # 入口：窗口、主循环、各系统装配
├── settings.py              # 全局配置（渲染距离、日长、按键、物理常数）
│
├── engine/                  # 渲染引擎层（与游戏逻辑解耦）
│   ├── camera.py            # 第一人称相机（视角矩阵、投影矩阵）
│   ├── frustum.py           # 视锥剔除
│   ├── mesh_builder.py      # ★ numpy 向量化区块网格生成（核心性能模块）
│   ├── renderer.py          # ModernGL 渲染管线：区块 / 实体 / 天空 / 粒子
│   ├── shaders.py           # 内嵌 GLSL（区块、实体、天空穹顶、雨雪粒子、HUD）
│   └── texture_atlas.py     # 程序化生成 16×16 像素风纹理图集
│
├── world/                   # 世界与地形
│   ├── chunk.py             # 区块：numpy 数据 + 脏标记 + 网格缓存
│   ├── world.py             # 区块管理、跨区块 get/set_block、异步加载队列
│   ├── perlin.py            # ★ numpy 向量化柏林噪声 (2D/3D + FBM)
│   ├── terrain.py           # 地形生成：高度图、生物群系、树、水面
│   └── raycast.py           # DDA 体素射线（准星指向哪个方块）
│
├── physics/
│   └── physics.py           # AABB 实体 vs 体素网格的扫掠碰撞、重力
│
├── systems/                 # 环境系统
│   ├── time_system.py       # 游戏内时间、日出日落角度
│   ├── sky.py               # 天空颜色渐变、太阳/月亮绘制、雾色联动
│   └── weather.py           # 天气状态机 + 雨/雪粒子
│
├── content/                 # ★ 内容定义层（玩家二次开发主要改这里）
│   ├── registry.py          # 方块/物品/实体 注册表（核心扩展机制）
│   ├── blocks.py            # 所有方块定义（一行一个，数据驱动）
│   ├── items.py             # 所有物品定义
│   └── interactions.py      # 方块交互回调（右键、踩踏、相邻更新等）
│
├── entities/
│   ├── entity.py            # Entity 基类（位置、AABB、速度、序列化）
│   ├── mob.py               # MobBase：AI 状态机骨架（idle/wander/jump）
│   ├── player.py            # 玩家：输入 → 移动意图 → 物理
│   └── mobs/
│       ├── slime.py         # 史莱姆：跳跃移动、落地压扁动画
│       └── pig.py           # 猪：随机游走、转头
│
├── persistence/
│   └── savegame.py          # SQLite 存档：脏区块差量保存、自动存档
│
└── ui/
    └── hud.py               # 准星、物品热栏、FPS/时间/天气调试信息
```

**分层原则**：`engine` 不 import 游戏逻辑；`content` 不 import 渲染细节。
添加新方块/物品/生物时**只动 `content/` 和 `entities/mobs/`**，引擎层零修改。

---

## 4. 核心系统设计

### 4.1 区块与高速网格生成（性能核心）

**数据结构**

```python
class Chunk:
    SX, SY, SZ = 16, 128, 16
    blocks: np.ndarray        # shape (16, 128, 16), dtype uint8, 0 = air
    dirty: bool               # 数据变了、网格待重建
    modified: bool            # 与生成器输出不同 → 需要写入存档
    vao / vbo                 # GPU 端网格句柄
```

**向量化面剔除（mesh_builder.py 的关键思想）**

对 6 个方向各做一次整数组位移比较，例如 +X 方向：

```python
solid = OPAQUE_LUT[blocks]                # uint8 查表 → bool 数组
exposed_px = solid[:-1] & ~solid[1:]      # 我是实心 & 右邻是空 → 该面可见
xs, ys, zs = np.nonzero(exposed_px)       # 一次性取出所有可见面坐标
```

再用预计算的"单位面模板 + 坐标广播"批量拼出顶点缓冲：
`vertices = FACE_TEMPLATE[None] + positions[:, None]`，全程无 Python 循环。
边界面与相邻区块数据拼接后同样向量化判断。

**顶点格式**（紧凑，单顶点 8 字节级别）：
位置 (3×f32 或压缩 u8) + 纹理图集 UV 索引 + 面朝向光照系数 + AO 可选。

**编辑流程**：`world.set_block(x,y,z,id)` → 标记所在区块 dirty
→（若在边界）标记邻接区块 dirty → 当帧末统一重建 dirty 区块网格。
重建预算制：每帧最多重建 N 个区块，避免连锁编辑造成尖峰。

### 4.2 柏林噪声与地形生成

- `perlin.py`：经典 Perlin 梯度噪声，置换表由世界种子决定；
  接口 `noise2(xs, ys)` 接受 numpy 网格，一次返回整张噪声图；
  `fbm(xs, ys, octaves, lacunarity, persistence)` 做分形叠加。
- **高度图**：`height = SEA_LEVEL + fbm(x/scale, z/scale, octaves=5) * amplitude`
- **生物群系**：第二张低频噪声做温度 → 草原 / 沙漠 / 雪原 三种，
  决定表层方块（草/沙/雪草）与是否生成树。
- **分层填充**（全部用 numpy 切片，无逐方块循环）：
  基岩(y=0) → 石头 → 泥土×3 → 表层方块；低于海平面的空气填水。
- **树木**：对每个柱子用 `hash(seed, x, z)` 决定是否长树（确定性，
  同一种子永远长在同一位置），树 = 原木干 + 树叶球。
- **重要保证**：生成是纯函数 `f(seed, cx, cz) → blocks`，
  未被玩家修改过的区块**不存盘**，按需重算 —— 存档体积极小。

### 4.3 时间系统与太阳

- 游戏内一天 = 现实 10 分钟（`settings.DAY_LENGTH` 可调）。
- `time_of_day ∈ [0,1)`：0.0 日出、0.25 正午、0.5 日落、0.75 午夜。
- **太阳/月亮**：方向 = 绕东西轴旋转的单位向量，渲染为始终面向相机的发光面片，
  跟随相机平移（永远在"无穷远"）。
- **天空颜色**：在关键帧表上插值
  `夜(深蓝) → 黎明(橙粉) → 白天(天蓝) → 黄昏(橙红) → 夜`，
  雾色与天空色联动，远处区块自然融入天际。
- **光照联动**：方块着色器里 `ambient = f(sun_height)`，
  夜晚整个世界自然变暗；日出日落时整体偏暖色。

### 4.4 天气系统

- 状态机：`CLEAR ↔ RAIN ↔ SNOW`（雪原群系下雨自动变下雪）。
  每个状态持续随机 2~5 游戏小时后按转移概率切换，存档保存当前天气与剩余时长。
- **降水粒子**：GPU 实例化渲染——CPU 只维护一个 `(N,3)` numpy 位置数组，
  每帧 `positions[:,1] -= speed*dt`，落到相机下方就回收到顶部重投；
  N≈2000 时 CPU 成本可忽略。雨是细长条，雪是慢速飘落小方片。
- **氛围联动**：下雨时天空色/雾色压暗、太阳隐藏。

### 4.5 物理系统 —— 万物皆有物理参数

- 实体统一为 **AABB**（玩家 0.6×1.8×0.6，史莱姆/猪各自尺寸）。
- 逐轴扫掠碰撞（先 Y 后 X、Z）：沿速度方向查询路径上的实心体素，
  命中则贴面停止；落地置 `on_ground=True`。
- 重力 `-22 m/s²`（手感接近 MC），跳跃初速度按 1.25 格跳高反推。
- 体素查询直接读区块 numpy 数组，单次 O(1)。
- 玩家不可把方块放进自己/生物的 AABB 内（与 MC 一致）。

**统一物理参数表**——每种方块、每种实体都携带，引擎按参数行事，
新内容只填数据不写物理代码：

| 参数 | 挂在谁身上 | 作用 |
|---|---|---|
| `mass` | 方块+实体 | 爆炸冲量 `v = impulse/mass`：轻的飞得远，重的纹丝不动 |
| `friction` | 方块表面 | 实体在其上行走/滑行的摩擦系数（冰=0.05，土=0.6） |
| `bounciness` | 方块表面+实体 | 碰撞恢复系数；碎屑落到弹性表面会二次弹跳 |
| `blast_resistance` | 方块 | 抗爆值；爆炸强度衰减后低于它则不被炸开（基岩=∞） |
| `gravity_affected` | 方块 | True 时失去支撑变碎屑下落（沙、沙砾） |
| `gravity_scale` / `drag` | 实体 | 重力倍率、空气阻力（碎屑、粒子有不同手感） |
| `knockback_factor` | 实体 | 受爆炸/击退影响的倍率 |

物理引擎只读参数、不认具体类型 —— "给沙子做下落" "做一块冰" "做弹性表面"
全部退化为**改一行数据**。

### 4.5.1 碎屑系统（FallingBlock / Debris）—— 方块↔实体的双向转换

体素系统的核心压力测试模块，TNT、落沙共用：

1. **方块 → 碎屑**：`world.dislodge(x,y,z, impulse)` 把方块从网格中移除，
   生成一个携带该方块贴图与物理参数的碎屑实体，初速度 = 冲量/质量。
2. **批量模拟**：所有碎屑存在一组 numpy 数组里
   （`positions(N,3) / velocities(N,3) / block_ids(N)`），
   每帧整批做重力积分 + 体素碰撞 + 弹跳衰减，百个碎屑成本可忽略。
3. **碎屑 → 方块**：速度低于阈值且落稳后，**写回最近的空体素**
   （落点被占则向上找），即"散落一地后相当于放置在那个位置"。
   超时 30s 未落稳（卡缝隙等）则强制就地放置，保证不泄漏实体。
4. 渲染：实例化绘制的小立方体，用方块本身的贴图，带翻滚旋转动画。

### 4.5.2 TNT 与爆炸

- **TNT 方块**：右键点燃 → 变为"点燃的TNT"实体（白闪膨胀动画，3s 引信），
  期间可被爆炸波及而**连锁殉爆**（随机短引信，和 MC 一致）。
- **爆炸解算**（半径 R≈4.5）：对球内每个方块算
  `强度 = power × (1 - dist/R) - blast_resistance`，
  强度 > 0 的方块被 `dislodge`，冲量方向 = 从爆心指向方块 + 随机抖动，
  大小 ∝ 剩余强度/方块质量 → **轻方块（树叶/沙）飞天，石头矮抛，基岩不动**。
- 性能保护：单次爆炸最多转化 ~200 个碎屑，超出部分直接移除不生成实体；
  被炸区块当帧批量重建网格（一次爆炸只触碰 1~4 个区块）。
- **实体冲击波**：球内实体获得 `impulse × knockback_factor / mass` 的击退
  （玩家会被炸飞，史莱姆飞得比猪远，因为轻）。
- 演出：爆炸闪光、烟雾粒子、轻微相机震动。

### 4.5.3 跳跳垫

- 表面参数 `bounciness=0.0` + `on_step` 回调：实体落上即获得固定上抛速度
  （约 8 格跳高），碎屑落上也会被重新弹飞——统一走物理参数，无特判代码。
- 与 TNT 联动测试：在跳跳垫上引爆 TNT，碎屑会被反复弹起后才落定。

### 4.6 射线拾取

`raycast.py`：Amanatides & Woo 的 DDA 体素遍历，从相机出发最远 6 格，
返回 `(命中方块坐标, 命中面法线)` —— 破坏用前者，放置用后者偏移。
准星高亮：被指向的方块绘制黑色线框。

### 4.7 存档系统（SQLite）

```sql
world_meta(key TEXT PRIMARY KEY, value TEXT)
    -- seed, time_of_day, day_count, weather, weather_timer, version
chunks(cx INT, cz INT, data BLOB, PRIMARY KEY(cx, cz))
    -- data = zlib 压缩的 numpy bytes（仅保存 modified 的区块）
player(id INT PRIMARY KEY, x,y,z REAL, yaw,pitch REAL, hotbar TEXT/*JSON*/)
entities(id INTEGER PRIMARY KEY, type TEXT, x,y,z REAL, data TEXT/*JSON*/)
```

- **差量保存**：只写 `modified=True` 的区块；16×128×16 草原区块压缩后约 1~3 KB。
- **自动存档**：每 60s 一次 + 退出时全量；写库在事务中批量提交。
- 存档路径 `saves/<世界名>.db`，启动时若存在则读取 seed/时间/天气/玩家位置无缝续玩。

### 4.8 生物系统

```
Entity (位置/速度/AABB/序列化)
 └── MobBase (重力物理 + AI状态机: IDLE → WANDER → (JUMP))
      ├── Slime  绿色半透明立方体；移动方式=朝随机方向起跳，
      │          落地有压扁-回弹缩放动画；体型小、跳得欢
      └── Pig    粉色盒子模型（身体+头+4腿）；慢速游走，走走停停，
                 转向时头部平滑插值；腿部摆动动画
```

- 渲染：盒子模型 = 若干带颜色/纹理的立方体拼装，一个实例化着色器统一绘制。
- 生成规则：玩家周围 24~40 格、草方块上方、数量上限（各 ≤ 8 只）；
  距离过远自动卸载（写回存档）。
- AI 用极简状态机（每个状态一个 `update(dt)`），便于扩展新行为。

### 4.9 方块/物品/交互 —— 注册表机制（易扩展的核心）

**数据驱动 + 回调**。所有内容都通过注册表登记，引擎只认 ID 和属性：

```python
# content/registry.py
@dataclass
class BlockType:
    name: str
    textures: tuple          # (top, side, bottom) 图集索引，或单值=六面同图
    solid: bool = True       # 是否参与碰撞
    opaque: bool = True      # 是否挡光/剔除邻面（玻璃/树叶=False）
    hardness: float = 1.0    # 破坏耗时系数（demo 中即时破坏，字段保留）
    drops: str | None = None # 破坏后掉落的物品名，None=掉自己
    translucent: bool = False
    emissive: float = 0.0    # 自发光（如萤石），夜间不变暗
    # ---- 物理参数（§4.5），所有方块必有，给默认值 ----
    mass: float = 2.0            # 影响被炸飞的初速度
    friction: float = 0.6        # 表面摩擦（冰=0.05）
    bounciness: float = 0.0      # 表面弹性（跳跳垫高）
    blast_resistance: float = 3.0  # 抗爆（树叶0.2 / 石头6 / 基岩inf）
    gravity_affected: bool = False # 沙/沙砾=True，失去支撑变碎屑
    on_interact: Callable | None = None   # 右键回调
    on_place:    Callable | None = None
    on_break:    Callable | None = None
    on_step:     Callable | None = None   # 实体踩踏回调
    tick:        Callable | None = None   # 随机刻（草蔓延等，可选）
```

初始方块表（demo）：
`草方块 / 泥土 / 石头 / 沙子(重力方块示例) / 原木 / 树叶 / 木板 / 玻璃 /
水(不可碰撞) / 雪草 / 基岩(抗爆∞示例) / 萤石(发光示例) /
冰(低摩擦示例) / TNT(爆炸+碎屑) / 跳跳垫(弹性表面示例)`

> 沙子、冰、基岩、萤石、TNT、跳跳垫各自只演示**一个**物理参数，
> 合在一起就是 §4.5 参数表的活体测试用例。

物品 = `ItemType(name, 显示名, 图标, on_use 回调)`；
"放置类物品"由 `block_item()` 工厂一行生成。热栏 1~9 选择物品。

---

## 5. 二次开发模板（文档内置，代码注释同步）

### 5.1 添加一个新方块（≤5 行）

```python
# content/blocks.py 末尾追加：
register_block("ruby_ore",
    BlockType(name="ruby_ore",
              textures=atlas.make("stone_base", spots="red"),  # 程序化贴图
              hardness=3.0, drops="ruby"))
```

写完即自动出现在创造热栏，可放置/破坏/存档，无需改引擎任何代码。

### 5.2 调整/新增物理参数

```python
# 让羊毛极轻、几乎无抗爆 —— 爆炸时漫天飞舞：
register_block("wool", BlockType(..., mass=0.3, blast_resistance=0.1))

# 做一块"超级冰"，比冰更滑：
register_block("packed_ice", BlockType(..., friction=0.02))
```

引擎读参数行事，所有物理行为（被炸飞的距离、行走打滑、碎屑弹跳）自动生效。

### 5.3 给方块加新属性

在 `BlockType` 加字段（如 `slipperiness: float = 1.0`），
然后在用到它的系统读取（如 `physics.py` 里乘上摩擦系数）——
属性定义与消费分离，互不破坏现有方块。

### 5.4 添加交互（右键/踩踏）

```python
# content/interactions.py
def jump_pad_step(world, pos, entity):
    entity.velocity[1] = 14.0          # 踩上去弹飞

register_block("jump_pad", BlockType(..., on_step=jump_pad_step))
```

回调统一签名 `fn(world, pos, actor)`，能拿到世界对象 → 可改方块、生成实体、改天气。

### 5.5 添加一个新物品

```python
register_item("rain_wand", ItemType(
    display="唤雨杖",
    on_use=lambda world, player: world.weather.force("RAIN")))
```

### 5.6 添加一个新生物

```python
# entities/mobs/chicken.py
class Chicken(MobBase):
    AABB_SIZE = (0.4, 0.7, 0.4)
    MODEL = box_model(body=(0.4,0.4,0.5,WHITE), head=..., legs=2)
    def ai_wander(self, dt): ...   # 只需覆写感兴趣的状态

register_entity("chicken", Chicken, spawn_on=["grass"], max_count=6)
```

---

## 6. 操作方式

| 按键 | 功能 |
|---|---|
| W/A/S/D + 鼠标 | 移动 / 视角 |
| 空格 | 跳跃 |
| 鼠标左键 | 破坏方块（瞬间） |
| 鼠标右键 | 放置方块 / 触发方块交互 |
| 1~9 / 滚轮 | 切换热栏 |
| F3 | 调试信息（FPS、坐标、区块数、时间、天气） |
| F5 | 手动存档 |
| T / Y | 时间快进 / 切换天气（调试用） |
| Esc | 释放鼠标 / 退出（自动存档） |

---

## 7. 打磨细节清单（"多打磨"的具体体现）

- 方块面**方向光照差异**（顶面最亮、底面最暗）+ 简易 AO 角落变暗 → 立体感
- 被指向方块的**线框高亮** + 放置/破坏音效占位接口
- 日出日落时太阳变大变橙、天空双色渐变（地平线色 ≠ 天顶色）
- 雾与渲染距离衔接，远处区块淡出而不是突兀消失
- 史莱姆落地压扁动画 / 猪腿摆动 —— 让生物"活"起来
- TNT 点燃后白闪加速 + 膨胀；爆炸闪光、烟雾粒子、相机震动
- 碎屑飞行时带翻滚旋转；落定瞬间"咔哒"对齐网格
- 连锁殉爆的随机引信差，让一片 TNT 炸成连绵的烟花而非一声闷响
- 水面半透明 + 略微下沉的水面高度；玻璃透视正确（透明面排序）
- 出生点自动找安全地表；坠入虚空传送回出生点
- 热栏 UI 用方块实际贴图渲染图标
- 后台线程预生成玩家移动方向的区块（永不"撞到世界边缘"）

## 8. 明确不做（demo 范围控制）

合成系统、生存血量/饥饿、洞穴与矿物分布、红石、多人联机、
方块破坏进度条（即时破坏）、音效资源（只留接口）。
以上均预留扩展点，但 demo 不实现，保证核心体验完成度。

## 9. 交付物与验收

- `pycraft/` 完整源码（结构如 §3），`python main.py` 直接运行
- `README.md`：安装（`pip install pyglet moderngl numpy pillow`）、操作、二次开发模板
- 验收：能跑 60FPS±、能挖/放方块、日出日落、下雨下雪、
  史莱姆和猪在地表活动、退出重进世界与修改完整保留；
  **物理验收**：TNT 炸开地形 → 碎屑抛飞弹跳 → 落定后写回为真实方块且存档保留；
  沙子悬空下落；冰面打滑；跳跳垫弹飞玩家与碎屑；基岩炸不动

---

**待你确认**：以上设计 OK 的话我就开始写代码；
如对 方块清单 / 一天时长 / 爆炸半径与碎屑上限 / 渲染距离 有偏好，请直接说明。
