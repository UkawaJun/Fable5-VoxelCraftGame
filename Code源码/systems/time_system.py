"""In-game time: day/night cycle, sun position, ambient light.

时间系统：time_of_day ∈ [0,1)
  0.00 日出  0.25 正午  0.50 日落  0.75 午夜
"""

import math

from settings import DAY_LENGTH, START_TIME


class TimeSystem:
    def __init__(self):
        self.time_of_day = START_TIME
        self.day_count = 0
        self.speed = 1.0          # debug fast-forward (hold T)

    def update(self, dt):
        self.time_of_day += dt * self.speed / DAY_LENGTH
        while self.time_of_day >= 1.0:
            self.time_of_day -= 1.0
            self.day_count += 1

    @property
    def sun_elevation(self) -> float:
        """-1..1, >0 means the sun is up."""
        return math.sin(self.time_of_day * math.tau)

    def sun_direction(self):
        """Unit vector pointing AT the sun (east -> overhead -> west arc)."""
        a = self.time_of_day * math.tau
        x, y, z = math.cos(a), math.sin(a), 0.28
        n = math.sqrt(x * x + y * y + z * z)
        return (x / n, y / n, z / n)

    def ambient(self) -> float:
        """Global light level 0.12 (night) .. 1.0 (noon)."""
        return max(0.12, min(1.0, self.sun_elevation * 1.6 + 0.18))

    def clock_str(self) -> str:
        # 0.0 == 06:00 (sunrise)
        h = (self.time_of_day * 24.0 + 6.0) % 24.0
        return f"Day {self.day_count}  {int(h):02d}:{int(h % 1 * 60):02d}"

    def serialize(self):
        return {"time_of_day": self.time_of_day, "day_count": self.day_count}

    def deserialize(self, d):
        self.time_of_day = float(d.get("time_of_day", START_TIME))
        self.day_count = int(d.get("day_count", 0))
