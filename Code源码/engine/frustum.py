"""View-frustum culling (Gribb-Hartmann plane extraction).

视锥剔除：看不见的区块不发 draw call。
"""

import numpy as np


class Frustum:
    def __init__(self):
        self.planes = np.zeros((6, 4))

    def update(self, vp):
        """vp: row-major (proj @ view), clip = vp @ point."""
        m = vp
        p = self.planes
        p[0] = m[3] + m[0]   # left
        p[1] = m[3] - m[0]   # right
        p[2] = m[3] + m[1]   # bottom
        p[3] = m[3] - m[1]   # top
        p[4] = m[3] + m[2]   # near
        p[5] = m[3] - m[2]   # far
        n = np.linalg.norm(p[:, :3], axis=1, keepdims=True)
        n[n == 0] = 1.0
        self.planes = p / n

    def aabb_visible(self, mn, mx) -> bool:
        """Test axis-aligned box (positive-vertex method)."""
        for px, py, pz, pw in self.planes:
            x = mx[0] if px >= 0 else mn[0]
            y = mx[1] if py >= 0 else mn[1]
            z = mx[2] if pz >= 0 else mn[2]
            if px * x + py * y + pz * z + pw < 0:
                return False
        return True
