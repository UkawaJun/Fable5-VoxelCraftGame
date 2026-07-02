"""Sky colours: keyframed gradients over the day, weather-aware.

天空颜色：在关键帧表上做环形插值；雾色 = 地平线色，远景自然融入天际。
"""

# keyframes: time_of_day -> (zenith RGB 天顶, horizon RGB 地平线)
_KEYS = [
    (0.00, (0.32, 0.32, 0.52), (0.98, 0.62, 0.36)),   # sunrise 日出
    (0.06, (0.34, 0.55, 0.86), (0.74, 0.84, 0.95)),   # morning
    (0.25, (0.24, 0.52, 0.94), (0.66, 0.82, 0.98)),   # noon 正午
    (0.44, (0.34, 0.52, 0.85), (0.80, 0.78, 0.80)),   # late afternoon
    (0.50, (0.30, 0.26, 0.48), (0.99, 0.52, 0.26)),   # sunset 日落
    (0.56, (0.05, 0.06, 0.14), (0.16, 0.14, 0.26)),   # dusk
    (0.75, (0.01, 0.02, 0.06), (0.05, 0.06, 0.12)),   # midnight 午夜
    (0.94, (0.04, 0.05, 0.12), (0.12, 0.10, 0.20)),   # pre-dawn
    (1.00, (0.32, 0.32, 0.52), (0.98, 0.62, 0.36)),   # wrap = sunrise
]


def _lerp3(a, b, t):
    return (a[0] + (b[0] - a[0]) * t,
            a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


def sky_colors(time_of_day: float, weather_darken: float = 0.0):
    """Returns (zenith_rgb, horizon_rgb). weather_darken: 0 clear .. 1 storm."""
    t = time_of_day % 1.0
    for i in range(len(_KEYS) - 1):
        t0, z0, h0 = _KEYS[i]
        t1, z1, h1 = _KEYS[i + 1]
        if t0 <= t <= t1:
            k = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            zen, hor = _lerp3(z0, z1, k), _lerp3(h0, h1, k)
            break
    else:
        zen, hor = _KEYS[0][1], _KEYS[0][2]
    if weather_darken > 0.0:
        g = 1.0 - 0.55 * weather_darken
        grey_z = sum(zen) / 3.0
        grey_h = sum(hor) / 3.0
        zen = _lerp3(zen, (grey_z, grey_z, grey_z * 1.05), weather_darken * 0.7)
        hor = _lerp3(hor, (grey_h, grey_h, grey_h * 1.05), weather_darken * 0.7)
        zen = (zen[0] * g, zen[1] * g, zen[2] * g)
        hor = (hor[0] * g, hor[1] * g, hor[2] * g)
    return zen, hor


def sun_visual(time_of_day: float):
    """(scale, tint) — the sun grows and turns orange near the horizon.
    日出日落时太阳变大变橙。"""
    import math
    elev = math.sin(time_of_day * math.tau)
    low = max(0.0, 1.0 - abs(elev) * 3.0)          # 1 near horizon
    scale = 1.0 + low * 0.6
    tint = (1.0, 1.0 - low * 0.25, 1.0 - low * 0.55)
    return scale, tint
