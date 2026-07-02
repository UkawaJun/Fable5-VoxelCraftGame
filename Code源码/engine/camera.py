"""First-person camera + minimal matrix toolkit (row-major numpy).

Conventions: row-major matrices, v' = M @ v (column vector).
Upload to OpenGL with write_mat() which transposes to column-major.
"""

import math

import numpy as np


# ---------------------------------------------------------------- matrices
def perspective(fovy_deg, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy_deg) * 0.5)
    m = np.zeros((4, 4), dtype=np.float64)
    m[0, 0] = f / aspect
    m[1, 1] = f
    m[2, 2] = (far + near) / (near - far)
    m[2, 3] = (2.0 * far * near) / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, center, up=(0.0, 1.0, 0.0)):
    eye = np.asarray(eye, dtype=np.float64)
    f = np.asarray(center, dtype=np.float64) - eye
    f /= np.linalg.norm(f)
    up = np.asarray(up, dtype=np.float64)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.identity(4)
    m[0, :3] = s
    m[1, :3] = u
    m[2, :3] = -f
    m[0, 3] = -np.dot(s, eye)
    m[1, 3] = -np.dot(u, eye)
    m[2, 3] = np.dot(f, eye)
    return m


def translate(v):
    m = np.identity(4)
    m[:3, 3] = v
    return m


def scale(v):
    m = np.identity(4)
    m[0, 0], m[1, 1], m[2, 2] = v
    return m


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    m = np.identity(4)
    m[0, 0], m[0, 2] = c, s
    m[2, 0], m[2, 2] = -s, c
    return m


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    m = np.identity(4)
    m[1, 1], m[1, 2] = c, -s
    m[2, 1], m[2, 2] = s, c
    return m


def write_mat(prog, name, m):
    """Upload row-major numpy matrix to a GLSL mat4 uniform."""
    prog[name].write(np.ascontiguousarray(m.T, dtype="f4").tobytes())


# ---------------------------------------------------------------- camera
class Camera:
    def __init__(self, fov, aspect, near, far):
        self.fov = fov
        self.aspect = aspect
        self.near = near
        self.far = far
        self.pos = np.zeros(3)
        self.yaw = 0.0
        self.pitch = 0.0
        self.shake = np.zeros(3)       # explosion camera shake offset

    def direction(self):
        cp = math.cos(self.pitch)
        return np.array([math.cos(self.yaw) * cp,
                         math.sin(self.pitch),
                         math.sin(self.yaw) * cp])

    def view_matrix(self):
        eye = self.pos + self.shake
        return look_at(eye, eye + self.direction())

    def proj_matrix(self):
        return perspective(self.fov, self.aspect, self.near, self.far)

    def vp_matrix(self):
        return self.proj_matrix() @ self.view_matrix()
