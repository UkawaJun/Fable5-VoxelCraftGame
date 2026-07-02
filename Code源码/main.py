"""PyCraft — Python voxel demo. Entry point.

Run:  python main.py
Keys: WASD move, Space jump, LMB dig, RMB place/interact, 1-9/wheel hotbar,
      F3 debug, F5 save, T (hold) fast time, Y cycle weather, Esc release mouse.
"""

import math
import os
import random
import sys
import time as _time

import moderngl
import numpy as np
import pyglet
from pyglet.window import key, mouse

import settings as S
# content registration side-effects (blocks / items / mobs) —— 注册表机制
import content.blocks      # noqa: F401
import content.items       # noqa: F401
import entities.mobs.slime # noqa: F401
import entities.mobs.pig   # noqa: F401
import entities.mobs.villager  # noqa: F401

from engine.camera import Camera
from engine.renderer import Renderer
from entities.player import Player
from persistence.savegame import SaveGame
from systems.sky import sky_colors
from systems.time_system import TimeSystem
from systems.weather import WeatherSystem
from ui.hud import Hud
from world.raycast import raycast
from world.world import World

MOUSE_SENS = 0.0023
CLICK_REPEAT = 0.22


class Game(pyglet.window.Window):
    def __init__(self):
        config = pyglet.gl.Config(double_buffer=True, depth_size=24,
                                  major_version=3, minor_version=3)
        super().__init__(S.WINDOW_WIDTH, S.WINDOW_HEIGHT,
                         caption=S.WINDOW_TITLE, resizable=True,
                         vsync=S.VSYNC, config=config)
        self.ctx = moderngl.create_context()
        self.renderer = Renderer(self.ctx)
        self.hud = Hud(self.ctx, self.renderer.atlas_tex)

        # ---- world / save ----
        # PyInstaller 打包后 __file__ 在临时解压目录，存档必须放 exe 旁边
        if getattr(sys, "frozen", False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
        save_path = os.path.join(base_dir, S.SAVE_DIR, S.WORLD_NAME + ".db")
        self.save = SaveGame(save_path)
        existing = self.save.exists
        seed = self.save.get_meta("seed") if existing else S.WORLD_SEED
        self.world = World(seed, self.save)
        self.time_sys = TimeSystem()
        self.weather = WeatherSystem()
        self.world.time = self.time_sys
        self.world.weather = self.weather
        self.player = Player(self.world.spawn_pos)
        self.world.player = self.player
        if existing:
            self.time_sys.deserialize(self.save.get_meta("time", {}) or {})
            self.weather.deserialize(self.save.get_meta("weather", {}) or {})
            self.save.load_player_into(self.player)
            self.save.load_entities_into(self.world)

        self.camera = Camera(S.FOV, self.width / self.height, S.NEAR, S.FAR)
        self.keys = key.KeyStateHandler()
        self.push_handlers(self.keys)
        self.set_exclusive_mouse(True)
        self.captured = True

        self.held_button = None
        self.repeat_timer = 0.0
        self.autosave_timer = S.AUTOSAVE_INTERVAL
        self.chunk_timer = 0.0
        self.shake_amp = 0.0
        self.target = None
        self.last_space = 0.0      # for double-tap-to-fly detection
        self._fps = 0.0
        self._last_draw = _time.perf_counter()

        self._preload_spawn(fresh=not existing)
        pyglet.clock.schedule_interval(self.update, 1 / 120.0)

    # ------------------------------------------------------------------
    def _preload_spawn(self, fresh: bool):
        """Synchronously wait for the spawn chunks so the player doesn't
        fall through ungenerated terrain. 出生点同步预载。"""
        self.world.ensure_chunks_around(self.player.pos[0], self.player.pos[2])
        deadline = _time.time() + 8.0
        while _time.time() < deadline:
            self.world.process_gen_results(budget=64)
            if self.world.is_loaded(self.player.pos[0], self.player.pos[2]):
                break
            _time.sleep(0.02)
        y = self.world.surface_y(int(self.player.pos[0]),
                                 int(self.player.pos[2]))
        if y is not None and (fresh or self.player.pos[1] <= y):
            self.player.pos[1] = y + 1.05    # 安全地表出生

    # ------------------------------------------------------------------
    # update loop
    # ------------------------------------------------------------------
    def update(self, dt):
        dt = min(dt, 0.05)

        self.time_sys.speed = 30.0 if self.keys[key.T] else 1.0
        self.time_sys.update(dt)
        self.weather.update(dt, self.player.eye_pos)

        self.chunk_timer -= dt
        if self.chunk_timer <= 0:
            self.chunk_timer = 0.3
            self.world.ensure_chunks_around(self.player.pos[0],
                                            self.player.pos[2])
        self.world.process_gen_results()

        # ---- player input intent ----
        p = self.player
        p.move_z = (1.0 if self.keys[key.W] else 0.0) - \
                   (1.0 if self.keys[key.S] else 0.0)
        p.move_x = (1.0 if self.keys[key.D] else 0.0) - \
                   (1.0 if self.keys[key.A] else 0.0)
        p.want_jump = self.keys[key.SPACE]
        p.sprinting = self.keys[key.LCTRL] or self.keys[key.RCTRL]
        p.fly_up = self.keys[key.SPACE]
        p.fly_down = self.keys[key.LSHIFT] or self.keys[key.RSHIFT]
        if self.world.is_loaded(p.pos[0], p.pos[2]):
            p.update(self.world, dt)

        self.world.update_entities(dt)
        self.world.process_block_updates()
        self.world.process_light_updates()
        self.world.process_water()

        # ---- events: explosions -> camera shake (相机震动) ----
        for ev in self.world.events:
            if ev[0] == "explosion":
                (ex, ey, ez), power = ev[1], ev[2]
                d = math.dist((ex, ey, ez), tuple(p.eye_pos))
                self.shake_amp = min(
                    0.5, self.shake_amp + power * 0.05 * max(0.1, 1 - d / 30))
        self.world.events.clear()
        self.shake_amp *= max(0.0, 1.0 - 6.0 * dt)
        if self.shake_amp > 0.002:
            self.camera.shake = np.random.uniform(-1, 1, 3) * self.shake_amp
        else:
            self.camera.shake[:] = 0

        # ---- hold-to-repeat clicks ----
        if self.held_button is not None and self.captured:
            self.repeat_timer -= dt
            if self.repeat_timer <= 0:
                self.repeat_timer = CLICK_REPEAT
                self._click(self.held_button)

        # ---- autosave ----
        self.autosave_timer -= dt
        if self.autosave_timer <= 0:
            self.autosave_timer = S.AUTOSAVE_INTERVAL
            self._save()

    # ------------------------------------------------------------------
    # rendering
    # ------------------------------------------------------------------
    def on_draw(self):
        now = _time.perf_counter()
        frame = now - self._last_draw
        self._last_draw = now
        if frame > 0:
            self._fps = self._fps * 0.95 + (1.0 / frame) * 0.05

        self.ctx.screen.use()
        self.ctx.viewport = (0, 0, *self.get_framebuffer_size())
        p = self.player
        self.camera.aspect = max(0.1, self.width / max(1, self.height))
        self.camera.pos = p.eye_pos
        self.camera.yaw = p.yaw
        self.camera.pitch = p.pitch

        self.renderer.update_chunk_meshes(self.world, self.camera.pos)

        hit = raycast(self.world, p.eye_pos, p.look_dir(), S.REACH)
        self.target = hit
        highlight = hit[0] if hit else None

        zen, hor = sky_colors(self.time_sys.time_of_day, self.weather.darken)
        self.renderer.render(self.camera, self.world, self.time_sys,
                             self.weather, zen, hor, highlight)

        debug = None
        if self.hud.show_debug:
            debug = [
                f"FPS {self._fps:5.1f}   {self.time_sys.clock_str()}",
                f"pos ({p.pos[0]:.1f}, {p.pos[1]:.1f}, {p.pos[2]:.1f})"
                f"  yaw {math.degrees(p.yaw):.0f}",
                f"chunks {len(self.world.chunks)}"
                f" (dirty {len(self.world.dirty)})"
                f"  entities {len(self.world.entities)}"
                f"  debris {self.world.debris.count}",
                f"weather {self.weather.state}"
                f" ({self.weather.intensity:.2f})   seed {self.world.seed}",
            ]
        self.hud.render(self.width, self.height, p, debug)

    # ------------------------------------------------------------------
    # input
    # ------------------------------------------------------------------
    def on_mouse_motion(self, x, y, dx, dy):
        self._look(dx, dy)

    def on_mouse_drag(self, x, y, dx, dy, buttons, modifiers):
        self._look(dx, dy)

    def _look(self, dx, dy):
        if not self.captured:
            return
        p = self.player
        p.yaw += dx * MOUSE_SENS
        p.pitch = max(-1.55, min(1.55, p.pitch + dy * MOUSE_SENS))

    def on_mouse_press(self, x, y, button, modifiers):
        if not self.captured:
            self.set_exclusive_mouse(True)
            self.captured = True
            return
        self.held_button = button
        self.repeat_timer = CLICK_REPEAT * 1.6
        self._click(button)

    def on_mouse_release(self, x, y, button, modifiers):
        self.held_button = None

    def _click(self, button):
        hit = raycast(self.world, self.player.eye_pos,
                      self.player.look_dir(), S.REACH)
        if button == mouse.LEFT:
            eye = self.player.eye_pos
            d = self.player.look_dir()
            from world.raycast import raycast_entity
            ent = raycast_entity(self.world, eye, d, S.REACH)
            block_dist = (math.dist(tuple(eye), (hit[0][0] + 0.5, hit[0][1] + 0.5,
                          hit[0][2] + 0.5)) if hit else 1e9)
            if ent is not None and ent[1] < block_dist:
                ent[0].hurt(4.0, source_pos=tuple(eye))   # attack the mob
            elif hit:
                self.world.break_block(*hit[0])
        elif button == mouse.RIGHT:
            if not hit:
                return
            bpos, normal = hit
            # 1) block interaction (e.g. ignite TNT) takes priority
            if self.world.interact_block(*bpos, self.player):
                return
            # 2) item use / block placement
            item = self.player.selected_item()
            if item.on_use and item.on_use(self.world, self.player):
                return
            if item.places_block:
                tx = bpos[0] + normal[0]
                ty = bpos[1] + normal[1]
                tz = bpos[2] + normal[2]
                self.world.place_block(tx, ty, tz, item.places_block)
        elif button == mouse.MIDDLE and hit:
            bid = self.world.get_block(*hit[0])
            from content.registry import BLOCKS
            name = BLOCKS[int(bid)].name
            for i, it in enumerate(self.player.hotbar):
                if it.places_block == name:
                    self.player.slot = i
                    break

    def on_mouse_scroll(self, x, y, sx, sy):
        n = len(self.player.hotbar)
        self.player.slot = int(self.player.slot - sy) % n

    def on_key_press(self, symbol, modifiers):
        p = self.player
        if key._1 <= symbol <= key._9:
            p.slot = min(symbol - key._1, len(p.hotbar) - 1)
        elif symbol == key.SPACE:
            now = _time.perf_counter()
            if now - self.last_space < 0.3:    # double-tap -> toggle flight
                p.toggle_fly()
            self.last_space = now
        elif symbol == key.F3:
            self.hud.show_debug = not self.hud.show_debug
        elif symbol == key.F5:
            self._save()
        elif symbol == key.Y:
            self.weather.cycle()
        elif symbol == key.ESCAPE:
            if self.captured:
                self.set_exclusive_mouse(False)
                self.captured = False
                return pyglet.event.EVENT_HANDLED   # don't close the window
        return None

    # ------------------------------------------------------------------
    def _save(self):
        self.save.save_all(self.world, self.player, self.time_sys,
                           self.weather)

    def on_close(self):
        self._save()
        self.save.close()
        super().on_close()


def main():
    random.seed()
    Game()
    pyglet.app.run()


if __name__ == "__main__":
    main()
