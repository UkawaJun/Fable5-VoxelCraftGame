"""Procedurally generated 16px texture atlas — no external art assets.

程序化纹理图集：启动时用 numpy 生成全部像素风贴图（确定性，每次相同）。
Only numpy + PIL — headless-testable, the GPU upload happens in renderer.py.
"""

import numpy as np

from content.tiles import ATLAS_COLS, ATLAS_PX, TILE, TILE_PX

T = TILE_PX


def _rng(tile_idx):
    return np.random.default_rng(98765 + tile_idx * 131)


def _noise_tile(rng, base, var=14, alpha=255):
    """base RGB + per-pixel brightness jitter. 噪点贴图基底。"""
    t = np.zeros((T, T, 4), dtype=np.int16)
    jitter = rng.integers(-var, var + 1, (T, T, 1))
    t[:, :, :3] = np.array(base, dtype=np.int16) + jitter
    t[:, :, 3] = alpha
    return t


def _clamp(t):
    return np.clip(t, 0, 255).astype(np.uint8)


def build_atlas() -> np.ndarray:
    """Returns (ATLAS_PX, ATLAS_PX, 4) uint8 RGBA array."""
    atlas = np.zeros((ATLAS_PX, ATLAS_PX, 4), dtype=np.uint8)

    def put(name, tile):
        idx = TILE[name]
        r, c = idx // ATLAS_COLS, idx % ATLAS_COLS
        atlas[r * T:(r + 1) * T, c * T:(c + 1) * T] = _clamp(tile)

    # ---- terrain ----
    rng = _rng(TILE["grass_top"])
    g = _noise_tile(rng, (96, 168, 64), 18)
    put("grass_top", g)

    rng = _rng(TILE["dirt"])
    d = _noise_tile(rng, (134, 96, 67), 16)
    put("dirt", d)

    rng = _rng(TILE["grass_side"])
    gs = _noise_tile(rng, (134, 96, 67), 16)
    gs[0:4, :, 0] = 96 + rng.integers(-14, 14, (4, T))
    gs[0:4, :, 1] = 168 + rng.integers(-14, 14, (4, T))
    gs[0:4, :, 2] = 64 + rng.integers(-10, 10, (4, T))
    put("grass_side", gs)

    rng = _rng(TILE["stone"])
    s = _noise_tile(rng, (128, 128, 130), 12)
    for _ in range(6):                       # darker cracks/blotches
        x, y = rng.integers(0, T, 2)
        w, h = rng.integers(2, 5, 2)
        s[y:y + h, x:x + w, :3] -= 22
    put("stone", s)

    rng = _rng(TILE["sand"])
    put("sand", _noise_tile(rng, (219, 206, 160), 12))

    rng = _rng(TILE["log_side"])
    ls = _noise_tile(rng, (104, 78, 48), 8)
    stripes = (np.arange(T) % 4 < 2)
    ls[:, stripes, :3] -= 18
    put("log_side", ls)

    rng = _rng(TILE["log_top"])
    lt = _noise_tile(rng, (160, 130, 86), 8)
    yy, xx = np.mgrid[0:T, 0:T]
    rings = (np.sqrt((xx - 7.5) ** 2 + (yy - 7.5) ** 2).astype(int) % 3) == 0
    lt[rings, :3] -= 26
    put("log_top", lt)

    rng = _rng(TILE["leaves"])
    lv = _noise_tile(rng, (58, 122, 44), 20)
    holes = rng.random((T, T)) < 0.18
    lv[holes, 3] = 0                          # cut-out transparency
    put("leaves", lv)

    rng = _rng(TILE["planks"])
    pl = _noise_tile(rng, (178, 142, 90), 8)
    pl[::4, :, :3] -= 30                      # plank seams
    grain = rng.random((T, T)) < 0.08
    pl[grain, :3] -= 14
    put("planks", pl)

    rng = _rng(TILE["glass"])
    gl = np.zeros((T, T, 4), dtype=np.int16)
    gl[:, :, :3] = (200, 225, 235)
    gl[:, :, 3] = 28
    gl[0, :, 3] = gl[-1, :, 3] = gl[:, 0, 3] = gl[:, -1, 3] = 190
    for i in range(3, 8):                     # sparkle streak
        gl[i, i + 3, 3] = 140
        gl[i, i + 4, 3] = 140
    put("glass", gl)

    rng = _rng(TILE["water"])
    w = _noise_tile(rng, (52, 96, 200), 10, alpha=150)
    put("water", w)

    rng = _rng(TILE["snow_top"])
    put("snow_top", _noise_tile(rng, (238, 242, 248), 7))

    rng = _rng(TILE["snow_side"])
    ss = _noise_tile(rng, (134, 96, 67), 16)
    ss[0:4, :, :3] = 240 + rng.integers(-8, 6, (4, T, 1))
    put("snow_side", ss)

    rng = _rng(TILE["bedrock"])
    b = _noise_tile(rng, (70, 70, 74), 30)
    put("bedrock", b)

    rng = _rng(TILE["glowstone"])
    gw = _noise_tile(rng, (200, 160, 80), 18)
    spots = rng.random((T, T)) < 0.22
    gw[spots, :3] = (252, 232, 150)
    put("glowstone", gw)

    rng = _rng(TILE["ice"])
    ic = _noise_tile(rng, (160, 200, 240), 8, alpha=210)
    for i in range(2, 13):                    # cracks
        ic[i, (i * 2) % T, :3] = (210, 235, 250)
    put("ice", ic)

    # ---- TNT ----
    rng = _rng(TILE["tnt_side"])
    ts = _noise_tile(rng, (190, 48, 38), 12)
    ts[6:10, :, :3] = 235                     # white band
    for x in range(1, T, 3):                  # dark dashes = "lettering"
        ts[7:9, x, :3] = 40
    put("tnt_side", ts)

    rng = _rng(TILE["tnt_top"])
    tt = _noise_tile(rng, (190, 48, 38), 12)
    tt[6:10, 6:10, :3] = (90, 80, 70)         # fuse plate
    put("tnt_top", tt)

    # ---- jump pad ----
    rng = _rng(TILE["jump_pad_top"])
    jp = _noise_tile(rng, (120, 60, 170), 12)
    jp[0:2, :, :3] = (200, 150, 255)
    jp[-2:, :, :3] = (200, 150, 255)
    jp[:, 0:2, :3] = (200, 150, 255)
    jp[:, -2:, :3] = (200, 150, 255)
    yy, xx = np.mgrid[0:T, 0:T]
    diamond = (np.abs(xx - 7.5) + np.abs(yy - 7.5)) < 4    # spring marker
    jp[diamond, :3] = (235, 220, 255)
    put("jump_pad_top", jp)

    rng = _rng(TILE["jump_pad_side"])
    js = _noise_tile(rng, (84, 44, 120), 10)
    js[0:3, :, :3] = (160, 110, 220)
    put("jump_pad_side", js)

    # ---- misc ----
    put("white", np.full((T, T, 4), 255, dtype=np.int16))

    sun = np.zeros((T, T, 4), dtype=np.int16)
    dist = np.sqrt((xx - 7.5) ** 2 + (yy - 7.5) ** 2)
    glow = np.clip(255 * (1.0 - dist / 8.0) * 1.6, 0, 255)
    sun[:, :, 0] = 255
    sun[:, :, 1] = 244
    sun[:, :, 2] = 200
    sun[:, :, 3] = glow
    put("sun", sun)

    moon = np.zeros((T, T, 4), dtype=np.int16)
    moon[:, :, :3] = (224, 228, 240)
    moon[:, :, 3] = np.where(dist < 6.0, 235, 0)
    rng = _rng(TILE["moon"])
    craters = rng.random((T, T)) < 0.1
    moon[craters & (dist < 6.0), :3] = (190, 195, 210)
    put("moon", moon)

    rain = np.zeros((T, T, 4), dtype=np.int16)
    rain[:, 7:9, :3] = (170, 200, 255)
    rain[:, 7:9, 3] = 150
    put("rain", rain)

    snow = np.zeros((T, T, 4), dtype=np.int16)
    snow[6:10, 6:10, :3] = 250
    snow[6:10, 6:10, 3] = 230
    put("snowflake", snow)


    # ============ new blocks ============
    yy2, xx2 = np.mgrid[0:T, 0:T]

    rng = _rng(TILE["cobblestone"])
    cob = _noise_tile(rng, (122, 122, 126), 10)
    for _ in range(7):                        # rounded cobbles -> dark seams
        cx, cy = rng.integers(2, 14, 2)
        rr = rng.integers(2, 4)
        m = (xx2 - cx) ** 2 + (yy2 - cy) ** 2 < rr * rr
        cob[m, :3] += 14
    cob[(xx2 % 5 == 0) | (yy2 % 5 == 0), :3] -= 26
    put("cobblestone", cob)

    rng = _rng(TILE["mossy_cobble"])
    moss = _clamp(_noise_tile(rng, (122, 122, 126), 10)).astype(np.int16)
    green = rng.random((T, T)) < 0.30
    moss[green, 0] = 70
    moss[green, 1] = 120
    moss[green, 2] = 60
    moss[(xx2 % 5 == 0) | (yy2 % 5 == 0), :3] -= 24
    put("mossy_cobble", moss)

    rng = _rng(TILE["gravel"])
    grav = _noise_tile(rng, (130, 122, 116), 22)
    spots = rng.random((T, T)) < 0.18
    grav[spots, :3] -= 30
    put("gravel", grav)

    rng = _rng(TILE["bricks"])
    bri = _noise_tile(rng, (160, 74, 58), 10)
    bri[yy2 % 4 == 0, :3] = (188, 182, 170)            # horizontal mortar
    offset = ((yy2 // 4) % 2) * 4
    bri[(xx2 + offset) % 8 == 0, :3] = (188, 182, 170)  # staggered verticals
    put("bricks", bri)

    rng = _rng(TILE["bookshelf"])
    bsh = _noise_tile(rng, (178, 142, 90), 8)           # plank base
    bsh[6:9, :, :3] = (150, 116, 70)                    # shelf plank
    bsh[0:2, :, :3] = (150, 116, 70)
    bsh[-2:, :, :3] = (150, 116, 70)
    book_cols = [(190, 60, 60), (60, 110, 190), (80, 170, 90),
                 (200, 180, 70), (160, 80, 180)]
    for x in range(1, T - 1, 2):                        # book spines
        col = book_cols[(x // 2) % len(book_cols)]
        for ys, ye in ((2, 6), (9, 13)):
            bsh[ys:ye, x, :3] = col
    put("bookshelf", bsh)

    rng = _rng(TILE["pumpkin_top"])
    pkt = _noise_tile(rng, (214, 130, 40), 10)
    pkt[(xx2 % 4 == 0), :3] -= 24                       # ridges
    pkt[6:10, 6:10, :3] = (120, 96, 50)                # stem
    put("pumpkin_top", pkt)

    rng = _rng(TILE["jack_side"])
    jak = _noise_tile(rng, (214, 130, 40), 8)
    jak[(xx2 % 4 == 0), :3] -= 22                       # ridges
    eyes = (((xx2 > 2) & (xx2 < 6)) | ((xx2 > 9) & (xx2 < 13))) & (yy2 > 4) & (yy2 < 8)
    mouth = (yy2 > 9) & (yy2 < 13) & (xx2 > 2) & (xx2 < 13) & ((xx2 + yy2) % 2 == 0)
    glow = eyes | mouth
    jak[glow, 0] = 255
    jak[glow, 1] = 220
    jak[glow, 2] = 80
    put("jack_side", jak)

    rng = _rng(TILE["lantern"])
    lan = _noise_tile(rng, (60, 50, 40), 6)             # dark iron frame
    core = (xx2 > 3) & (xx2 < 12) & (yy2 > 3) & (yy2 < 12)
    lan[core, 0] = 255
    lan[core, 1] = 224
    lan[core, 2] = 120
    put("lantern", lan)

    rng = _rng(TILE["gold_block"])
    gold = _noise_tile(rng, (232, 196, 70), 8)
    gold[(xx2 + yy2) % 6 == 0, :3] = (255, 240, 160)   # shine streaks
    put("gold_block", gold)

    rng = _rng(TILE["diamond_block"])
    dia = _noise_tile(rng, (120, 220, 222), 8)
    sp = rng.random((T, T)) < 0.10
    dia[sp, :3] = (245, 255, 255)
    dia[0, :, :3] = dia[:, 0, :3] = (90, 180, 185)
    put("diamond_block", dia)

    rng = _rng(TILE["obsidian"])
    obs = _noise_tile(rng, (26, 20, 38), 10)
    streak = rng.random((T, T)) < 0.06
    obs[streak, :3] = (90, 60, 130)
    put("obsidian", obs)

    rng = _rng(TILE["redstone_lamp"])
    lamp = _noise_tile(rng, (220, 120, 50), 10)
    grid = (xx2 % 4 == 0) | (yy2 % 4 == 0)
    lamp[grid, :3] = (255, 200, 120)
    put("redstone_lamp", lamp)


    # ---- village / decoration blocks ----
    rng = _rng(TILE["spruce_planks"])
    sp = _noise_tile(rng, (110, 82, 52), 8)
    sp[::4, :, :3] -= 26
    grain = rng.random((T, T)) < 0.08
    sp[grain, :3] -= 12
    put("spruce_planks", sp)

    rng = _rng(TILE["white_wool"])
    wo = _noise_tile(rng, (236, 236, 236), 8)
    fuzz = rng.random((T, T)) < 0.25
    wo[fuzz, :3] -= 14
    put("white_wool", wo)

    rng = _rng(TILE["clay"])
    put("clay", _noise_tile(rng, (162, 166, 176), 8))

    rng = _rng(TILE["hay_side"])
    hs = _noise_tile(rng, (190, 160, 60), 10)
    hs[::3, :, :3] -= 22                      # binding bands
    put("hay_side", hs)

    rng = _rng(TILE["hay_top"])
    ht = _noise_tile(rng, (210, 184, 86), 8)
    ht[6:10, 6:10, :3] -= 24                  # swirl centre
    put("hay_top", ht)

    rng = _rng(TILE["path_top"])
    pt = _noise_tile(rng, (150, 120, 78), 10)
    pt[0, :, :3] -= 18; pt[-1, :, :3] -= 18
    pt[:, 0, :3] -= 18; pt[:, -1, :3] -= 18
    put("path_top", pt)

    return atlas


def tile_uv(tile_idx: int, inset: float = 0.0015):
    """(u0, v0, u_size, v_size) of a tile in the atlas, with bleed inset."""
    step = 1.0 / ATLAS_COLS
    u0 = (tile_idx % ATLAS_COLS) * step + inset
    v0 = (tile_idx // ATLAS_COLS) * step + inset
    return u0, v0, step - 2 * inset, step - 2 * inset
