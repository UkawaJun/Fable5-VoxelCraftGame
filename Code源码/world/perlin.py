"""Vectorised classic Perlin noise (numpy, no C extension).

numpy 向量化柏林噪声：一次调用算出整张网格的噪声图。
Reference: Ken Perlin, "Improving Noise" (2002) — 2D variant.
"""

import numpy as np

# 8 gradient directions
_GRADS = np.array(
    [[1, 1], [-1, 1], [1, -1], [-1, -1],
     [1, 0], [-1, 0], [0, 1], [0, -1]], dtype=np.float64)


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


class Perlin:
    def __init__(self, seed: int):
        rng = np.random.default_rng(seed)
        p = rng.permutation(256)
        self.perm = np.concatenate([p, p, p[:2]]).astype(np.int64)

    def noise2(self, x, y):
        """x, y: numpy arrays (same shape). Returns noise in roughly [-1, 1]."""
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        xi = np.floor(x).astype(np.int64)
        yi = np.floor(y).astype(np.int64)
        xf = x - xi
        yf = y - yi
        xi &= 255
        yi &= 255

        u = _fade(xf)
        v = _fade(yf)

        perm = self.perm
        aa = perm[perm[xi] + yi]
        ab = perm[perm[xi] + yi + 1]
        ba = perm[perm[xi + 1] + yi]
        bb = perm[perm[xi + 1] + yi + 1]

        def dot(hash_, dx, dy):
            g = _GRADS[hash_ & 7]
            return g[..., 0] * dx + g[..., 1] * dy

        n00 = dot(aa, xf, yf)
        n10 = dot(ba, xf - 1.0, yf)
        n01 = dot(ab, xf, yf - 1.0)
        n11 = dot(bb, xf - 1.0, yf - 1.0)

        nx0 = n00 + u * (n10 - n00)
        nx1 = n01 + u * (n11 - n01)
        return (nx0 + v * (nx1 - nx0)) * 1.4142  # normalise closer to [-1,1]

    def fbm(self, x, y, octaves=4, lacunarity=2.0, persistence=0.5):
        """Fractal Brownian Motion: layered noise. 分形叠加。"""
        x = np.asarray(x, dtype=np.float64)
        y = np.asarray(y, dtype=np.float64)
        total = np.zeros(np.broadcast(x, y).shape, dtype=np.float64)
        amp, freq, amp_sum = 1.0, 1.0, 0.0
        for _ in range(octaves):
            total += amp * self.noise2(x * freq, y * freq)
            amp_sum += amp
            amp *= persistence
            freq *= lacunarity
        return total / amp_sum


def hash_pos(seed: int, x: int, z: int) -> int:
    """Deterministic per-position hash (tree placement etc.). 确定性哈希。"""
    h = (x * 73856093) ^ (z * 19349663) ^ (seed * 83492791)
    h = (h ^ (h >> 13)) * 1274126177
    return (h ^ (h >> 16)) & 0x7FFFFFFF
