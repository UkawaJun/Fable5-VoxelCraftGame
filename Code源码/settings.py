"""Global configuration. Tweak values here — no engine code needs to change.

全局配置：渲染距离 / 日长 / 物理常数 / 按键等都在这里调。
"""

# ---------- Window ----------
WINDOW_TITLE = "PyCraft - Python Voxel Demo"
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
FOV = 70.0
NEAR, FAR = 0.1, 400.0
VSYNC = True

# ---------- World ----------
CHUNK_SX, CHUNK_SY, CHUNK_SZ = 16, 128, 16
RENDER_DISTANCE = 6           # chunks (radius)
SEA_LEVEL = 40
WORLD_SEED = 20260612         # default seed for a brand-new world
SAVE_DIR = "saves"
WORLD_NAME = "world1"
AUTOSAVE_INTERVAL = 60.0      # seconds

# ---------- Performance budgets (性能预算) ----------
MESH_BUDGET_PER_FRAME = 6     # max chunk meshes rebuilt per frame
GEN_RESULTS_PER_FRAME = 4     # max generated chunks integrated per frame
BLOCK_UPDATES_PER_FRAME = 64  # gravity/neighbour update queue budget
MAX_DEBRIS = 160              # global cap of airborne debris entities
EXPLOSION_DEBRIS_CAP = 90    # per-explosion debris cap

# ---------- Physics ----------
GRAVITY = 22.0                # m/s^2, tuned to feel like MC
MAX_FALL_SPEED = 50.0
PLAYER_SPEED = 4.5
PLAYER_SPRINT_MULT = 1.6      # 疾跑速度倍率 (hold Ctrl)
FLY_SPEED = 9.0              # 飞行水平速度
FLY_VERT_SPEED = 7.0        # 飞行升降速度 (Space / Shift)
PLAYER_JUMP_SPEED = 7.6       # ~1.25 block jump
PLAYER_AABB = (0.6, 1.8, 0.6) # w, h, d
PLAYER_EYE = 1.62
REACH = 6.0                   # block interaction distance

# ---------- Time (游戏内时间) ----------
DAY_LENGTH = 600.0            # real seconds per in-game day (10 min)
START_TIME = 0.06             # 0.0 sunrise, 0.25 noon, 0.5 sunset, 0.75 midnight

# ---------- Weather ----------
WEATHER_MIN_DURATION = 120.0  # real seconds a weather state lasts (min)
WEATHER_MAX_DURATION = 300.0
RAIN_PARTICLES = 1500
SNOW_PARTICLES = 900

# ---------- Explosion ----------
TNT_FUSE = 3.0                # seconds
TNT_POWER = 9.0               # blast strength at the centre
TNT_RADIUS = 4.5              # blocks

# ---------- Mobs ----------
MOB_CAP_PER_TYPE = 8
MOB_SPAWN_INTERVAL = 4.0      # seconds between spawn attempts
MOB_SPAWN_MIN, MOB_SPAWN_MAX = 16, 36   # distance ring around player
MOB_DESPAWN_DIST = 64
