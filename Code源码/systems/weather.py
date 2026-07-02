"""Weather state machine + precipitation particle data.

天气状态机：CLEAR <-> RAIN/SNOW，随机持续时间，转移概率见 _NEXT。
粒子只维护 numpy 位置数组（CPU 整批更新），渲染走 GPU 实例化。
雪原群系下"雨"自动呈现为雪。
"""

import math
import random

import numpy as np

from settings import (RAIN_PARTICLES, SNOW_PARTICLES, WEATHER_MAX_DURATION,
                      WEATHER_MIN_DURATION)

CLEAR, RAIN, SNOW = "CLEAR", "RAIN", "SNOW"

_NEXT = {
    CLEAR: [(CLEAR, 0.45), (RAIN, 0.40), (SNOW, 0.15)],
    RAIN:  [(CLEAR, 0.70), (RAIN, 0.20), (SNOW, 0.10)],
    SNOW:  [(CLEAR, 0.70), (SNOW, 0.20), (RAIN, 0.10)],
}

_AREA = 18.0          # particles live in a box around the camera
_TOP, _BOTTOM = 14.0, -10.0


class WeatherSystem:
    def __init__(self):
        self.state = CLEAR
        self.timer = random.uniform(WEATHER_MIN_DURATION, WEATHER_MAX_DURATION)
        self.intensity = 0.0          # ramps 0..1 over transitions
        n = max(RAIN_PARTICLES, SNOW_PARTICLES)
        self.particles = np.zeros((n, 3), dtype=np.float32)
        self.drift_phase = np.random.uniform(0, math.tau, n).astype(np.float32)
        self._seeded = False

    # ------------------------------------------------------------------
    def update(self, dt, cam_pos):
        self.timer -= dt
        if self.timer <= 0:
            self._switch()

        target = 0.0 if self.state == CLEAR else 1.0
        self.intensity += (target - self.intensity) * min(1.0, dt / 3.0)

        if self.intensity < 0.02:
            return
        n = self.active_count()
        p = self.particles[:n]
        if not self._seeded:
            self._reseed_all(cam_pos)
            self._seeded = True

        if self.state == SNOW:
            p[:, 1] -= 2.2 * dt
            self.drift_phase[:n] += dt * 1.5
            p[:, 0] += np.sin(self.drift_phase[:n]) * dt * 0.8
            p[:, 2] += np.cos(self.drift_phase[:n] * 0.7) * dt * 0.8
        else:
            p[:, 1] -= 19.0 * dt

        # recycle: fell below / drifted out of the box -> re-drop near the top
        out = ((p[:, 1] < cam_pos[1] + _BOTTOM) |
               (np.abs(p[:, 0] - cam_pos[0]) > _AREA) |
               (np.abs(p[:, 2] - cam_pos[2]) > _AREA))
        cnt = int(out.sum())
        if cnt:
            p[out, 0] = cam_pos[0] + np.random.uniform(-_AREA, _AREA, cnt)
            p[out, 1] = cam_pos[1] + np.random.uniform(_TOP * 0.5, _TOP, cnt)
            p[out, 2] = cam_pos[2] + np.random.uniform(-_AREA, _AREA, cnt)

    def _reseed_all(self, cam_pos):
        n = self.particles.shape[0]
        self.particles[:, 0] = cam_pos[0] + np.random.uniform(-_AREA, _AREA, n)
        self.particles[:, 1] = cam_pos[1] + np.random.uniform(_BOTTOM, _TOP, n)
        self.particles[:, 2] = cam_pos[2] + np.random.uniform(-_AREA, _AREA, n)

    def _switch(self):
        r = random.random()
        acc = 0.0
        for state, prob in _NEXT[self.state]:
            acc += prob
            if r <= acc:
                self.state = state
                break
        self.timer = random.uniform(WEATHER_MIN_DURATION, WEATHER_MAX_DURATION)
        self._seeded = False

    def force(self, state: str):
        """Debug / item hook: world.weather.force("RAIN")."""
        self.state = state
        self.timer = random.uniform(WEATHER_MIN_DURATION, WEATHER_MAX_DURATION)
        self._seeded = False

    def cycle(self):
        order = [CLEAR, RAIN, SNOW]
        self.force(order[(order.index(self.state) + 1) % 3])

    # ------------------------------------------------------------------
    def active_count(self) -> int:
        full = SNOW_PARTICLES if self.state == SNOW else RAIN_PARTICLES
        return int(full * self.intensity)

    @property
    def darken(self) -> float:
        """0..1 sky darkening factor for the sky/ambient. 雨天压暗。"""
        return self.intensity * (0.8 if self.state == RAIN else 0.55)

    def serialize(self):
        return {"state": self.state, "timer": self.timer}

    def deserialize(self, d):
        self.state = d.get("state", CLEAR)
        self.timer = float(d.get("timer", 120.0))
        self.intensity = 0.0 if self.state == CLEAR else 1.0
