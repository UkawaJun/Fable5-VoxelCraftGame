"""ModernGL render pipeline. 渲染管线：天空 → 太阳/月亮 → 区块(实体色) →
实体 → 碎屑(实例化) → 半透明区块 → 天气粒子 → 高亮线框 → HUD。

Per-chunk static VBOs; block edits rebuild only the touched chunk's mesh
(budgeted per frame). Debris & particles are GPU-instanced.
"""

import math

import moderngl
import numpy as np

from settings import (FAR, MAX_DEBRIS, MESH_BUDGET_PER_FRAME,
                      RAIN_PARTICLES, RENDER_DISTANCE, SNOW_PARTICLES)
from engine import shaders
from engine.camera import rot_y, scale, translate, write_mat
from engine.frustum import Frustum
from engine.mesh_builder import build_chunk_mesh
from engine.texture_atlas import build_atlas, tile_uv
from content.tiles import ATLAS_COLS, ATLAS_PX, TILE

# ---------------------------------------------------------------- cube data
_FACE_CORNERS = np.array([
    [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 1, 1]],
    [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 1, 0]],
    [[0, 1, 1], [1, 1, 1], [1, 1, 0], [0, 1, 0]],
    [[0, 0, 0], [1, 0, 0], [1, 0, 1], [0, 0, 1]],
    [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 1, 1]],
    [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 1, 0]],
], dtype=np.float32)
_TRI = (0, 1, 2, 0, 2, 3)
_SHADES = (0.8, 0.8, 1.0, 0.45, 0.62, 0.62)
_UVQ = np.array([[0, 1], [1, 1], [1, 0], [0, 0]], dtype=np.float32)


def _cube_verts(centred_y: bool, with_uv: bool) -> np.ndarray:
    parts = []
    for d in range(6):
        corners = _FACE_CORNERS[d][list(_TRI)]            # (6,3)
        pos = corners - np.array([0.5, 0.5 if centred_y else 0.0, 0.5],
                                 dtype=np.float32)
        shade = np.full((6, 1), _SHADES[d], dtype=np.float32)
        if with_uv:
            uv = _UVQ[list(_TRI)]
            parts.append(np.concatenate([pos, uv, shade], axis=1))
        else:
            parts.append(np.concatenate([pos, shade], axis=1))
    return np.concatenate(parts).astype(np.float32)


_CUBE_EDGES = np.array([
    (0, 0, 0), (1, 0, 0), (1, 0, 0), (1, 0, 1), (1, 0, 1), (0, 0, 1),
    (0, 0, 1), (0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 1, 0), (1, 1, 1),
    (1, 1, 1), (0, 1, 1), (0, 1, 1), (0, 1, 0), (0, 0, 0), (0, 1, 0),
    (1, 0, 0), (1, 1, 0), (1, 0, 1), (1, 1, 1), (0, 0, 1), (0, 1, 1),
], dtype=np.float32)
# expand slightly to avoid z-fighting with block faces
_CUBE_EDGES = (_CUBE_EDGES - 0.5) * 1.004 + 0.5


class Renderer:
    def __init__(self, ctx: moderngl.Context):
        self.ctx = ctx
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA

        # ---- atlas texture (procedural) ----
        atlas = build_atlas()
        self.atlas_tex = ctx.texture((ATLAS_PX, ATLAS_PX), 4, atlas.tobytes())
        self.atlas_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        # ---- programs ----
        self.p_chunk = ctx.program(vertex_shader=shaders.CHUNK_VS,
                                   fragment_shader=shaders.CHUNK_FS)
        self.p_sky = ctx.program(vertex_shader=shaders.SKY_VS,
                                 fragment_shader=shaders.SKY_FS)
        self.p_bill = ctx.program(vertex_shader=shaders.BILLBOARD_VS,
                                  fragment_shader=shaders.BILLBOARD_FS)
        self.p_ent = ctx.program(vertex_shader=shaders.ENTITY_VS,
                                 fragment_shader=shaders.ENTITY_FS)
        self.p_debris = ctx.program(vertex_shader=shaders.DEBRIS_VS,
                                    fragment_shader=shaders.DEBRIS_FS)
        self.p_part = ctx.program(vertex_shader=shaders.PARTICLE_VS,
                                  fragment_shader=shaders.PARTICLE_FS)
        self.p_line = ctx.program(vertex_shader=shaders.LINE_VS,
                                  fragment_shader=shaders.LINE_FS)

        # ---- static geometry ----
        tri = np.array([-1, -1, 3, -1, -1, 3], dtype=np.float32)
        self.vao_sky = ctx.vertex_array(
            self.p_sky, [(ctx.buffer(tri.tobytes()), "2f", "in_pos")])

        ent_cube = _cube_verts(centred_y=False, with_uv=False)
        self.vao_ent = ctx.vertex_array(
            self.p_ent,
            [(ctx.buffer(ent_cube.tobytes()), "3f 1f", "in_pos", "in_shade")])

        deb_cube = _cube_verts(centred_y=True, with_uv=True)
        self.deb_inst = ctx.buffer(reserve=MAX_DEBRIS * 5 * 4, dynamic=True)
        self.vao_debris = ctx.vertex_array(
            self.p_debris,
            [(ctx.buffer(deb_cube.tobytes()), "3f 2f 1f",
              "in_pos", "in_uv", "in_shade"),
             (self.deb_inst, "3f 1f 1f/i", "i_pos", "i_rot", "i_tile")])

        quad = np.array([-0.5, -0.5, 0.5, -0.5, 0.5, 0.5,
                         -0.5, -0.5, 0.5, 0.5, -0.5, 0.5], dtype=np.float32)
        n_part = max(RAIN_PARTICLES, SNOW_PARTICLES)
        self.part_inst = ctx.buffer(reserve=n_part * 3 * 4, dynamic=True)
        self.vao_part = ctx.vertex_array(
            self.p_part,
            [(ctx.buffer(quad.tobytes()), "2f", "in_corner"),
             (self.part_inst, "3f/i", "i_pos")])

        self.bill_vbo = ctx.buffer(reserve=6 * 5 * 4, dynamic=True)
        self.vao_bill = ctx.vertex_array(
            self.p_bill, [(self.bill_vbo, "3f 2f", "in_pos", "in_uv")])

        self.vao_line = ctx.vertex_array(
            self.p_line,
            [(ctx.buffer(_CUBE_EDGES.tobytes()), "3f", "in_pos")])

        self.chunk_meshes = {}      # key -> [vao_s, vbo_s, n_s, vao_t, vbo_t, n_t]
        self.frustum = Frustum()

    # ------------------------------------------------------------------
    # chunk mesh maintenance
    # ------------------------------------------------------------------
    def update_chunk_meshes(self, world, cam_pos,
                            budget=MESH_BUDGET_PER_FRAME):
        for key in world.removed:
            self._release(key)
        world.removed.clear()

        if not world.dirty:
            return
        pcx, pcz = int(cam_pos[0]) // 16, int(cam_pos[2]) // 16
        keys = sorted(world.dirty,
                      key=lambda k: (k[0] - pcx) ** 2 + (k[1] - pcz) ** 2)
        for key in keys[:budget]:
            world.dirty.discard(key)
            chunk = world.chunks.get(key)
            if chunk is None:
                continue
            self._release(key)
            solid, trans = build_chunk_mesh(world, chunk)
            entry = [None, None, 0, None, None, 0]
            if len(solid):
                vbo = self.ctx.buffer(solid.tobytes())
                entry[0] = self.ctx.vertex_array(
                    self.p_chunk, [(vbo, "3f 2f 1f 1f", "in_pos", "in_uv",
                                    "in_shade", "in_light")])
                entry[1], entry[2] = vbo, len(solid)
            if len(trans):
                vbo = self.ctx.buffer(trans.tobytes())
                entry[3] = self.ctx.vertex_array(
                    self.p_chunk, [(vbo, "3f 2f 1f 1f", "in_pos", "in_uv",
                                    "in_shade", "in_light")])
                entry[4], entry[5] = vbo, len(trans)
            self.chunk_meshes[key] = entry

    def _release(self, key):
        entry = self.chunk_meshes.pop(key, None)
        if entry:
            for obj in (entry[0], entry[1], entry[3], entry[4]):
                if obj is not None:
                    obj.release()

    # ------------------------------------------------------------------
    # frame
    # ------------------------------------------------------------------
    def render(self, camera, world, time_sys, weather, zenith, horizon,
               highlight=None):
        ctx = self.ctx
        vp = camera.vp_matrix()
        self.frustum.update(vp)
        cam_pos = camera.pos + camera.shake
        ambient = max(time_sys.ambient() * (1.0 - 0.45 * weather.darken), 0.10)
        fog_end = (RENDER_DISTANCE - 0.2) * 16
        fog_start = fog_end * 0.55

        ctx.clear(horizon[0], horizon[1], horizon[2], depth=1.0)

        # ---- sky gradient ----
        ctx.disable(moderngl.DEPTH_TEST)
        inv_vp = np.linalg.inv(vp)
        write_mat(self.p_sky, "u_inv_vp", inv_vp)
        self.p_sky["u_zenith"].value = tuple(zenith)
        self.p_sky["u_horizon"].value = tuple(horizon)
        self.vao_sky.render()

        # ---- sun & moon ----
        ctx.enable(moderngl.BLEND)
        self._draw_sun_moon(vp, cam_pos, time_sys, weather)
        ctx.disable(moderngl.BLEND)
        ctx.enable(moderngl.DEPTH_TEST)

        # ---- solid chunks ----
        self.atlas_tex.use(0)
        pc = self.p_chunk
        write_mat(pc, "u_mvp", vp)
        pc["u_atlas"].value = 0
        pc["u_cam_pos"].value = tuple(cam_pos)
        pc["u_ambient"].value = ambient
        pc["u_fog_color"].value = tuple(horizon)
        pc["u_fog_start"].value = fog_start
        pc["u_fog_end"].value = fog_end
        pc["u_alpha_test"].value = 1.0

        visible_t = []
        for key, entry in self.chunk_meshes.items():
            mn = (key[0] * 16, 0, key[1] * 16)
            mx = (mn[0] + 16, 128, mn[2] + 16)
            if not self.frustum.aabb_visible(mn, mx):
                continue
            if entry[0] is not None:
                pc["u_chunk_offset"].value = (mn[0], 0.0, mn[2])
                entry[0].render()
            if entry[3] is not None:
                d = (mn[0] + 8 - cam_pos[0]) ** 2 + (mn[2] + 8 - cam_pos[2]) ** 2
                visible_t.append((d, key, entry))

        # ---- entities (mobs, primed TNT) ----
        ctx.enable(moderngl.BLEND)
        self._draw_entities(vp, world, ambient)

        # ---- debris (instanced) ----
        pos, rot, tile_ids = world.debris.render_arrays()
        n = len(pos)
        if n:
            tiles = np.zeros(n, dtype=np.float32)
            from content.registry import BLOCKS
            for i, bid in enumerate(tile_ids):
                tiles[i] = BLOCKS[int(bid)].tex()[1]
            data = np.concatenate(
                [pos, rot[:, None], tiles[:, None]], axis=1).astype("f4")
            self.deb_inst.write(data.tobytes())
            pd = self.p_debris
            write_mat(pd, "u_mvp", vp)
            pd["u_atlas"].value = 0
            pd["u_atlas_step"].value = 1.0 / ATLAS_COLS
            pd["u_ambient"].value = ambient
            self.vao_debris.render(instances=n)

        # ---- translucent chunks (far -> near) ----
        pc = self.p_chunk
        pc["u_alpha_test"].value = 0.0
        visible_t.sort(key=lambda t: -t[0])
        for _, key, entry in visible_t:
            pc["u_chunk_offset"].value = (key[0] * 16, 0.0, key[1] * 16)
            entry[3].render()

        # ---- weather particles ----
        self._draw_particles(vp, camera, weather)

        # ---- block highlight ----
        if highlight is not None:
            ctx.line_width = 2.0
            pl = self.p_line
            write_mat(pl, "u_mvp", vp)
            pl["u_offset"].value = tuple(float(v) for v in highlight)
            pl["u_color"].value = (0.05, 0.05, 0.05, 0.9)
            self.vao_line.render(moderngl.LINES)

        ctx.disable(moderngl.BLEND)

    # ------------------------------------------------------------------
    def _draw_sun_moon(self, vp, cam_pos, time_sys, weather):
        from systems.sky import sun_visual
        sun_dir = np.array(time_sys.sun_direction())
        scale_f, tint = sun_visual(time_sys.time_of_day)
        sun_alpha = max(0.0, 1.0 - weather.intensity * 0.9)
        self._billboard(vp, cam_pos, sun_dir, 34 * scale_f, TILE["sun"],
                        (*tint, sun_alpha))
        self._billboard(vp, cam_pos, -sun_dir, 22, TILE["moon"],
                        (1.0, 1.0, 1.0, sun_alpha))

    def _billboard(self, vp, cam_pos, direction, size, tile, tint):
        if direction[1] < -0.25:
            return
        centre = np.asarray(cam_pos) + direction * 300.0
        up = np.array([0.0, 1.0, 0.0])
        right = np.cross(direction, up)
        n = np.linalg.norm(right)
        right = right / n if n > 1e-6 else np.array([1.0, 0.0, 0.0])
        upv = np.cross(right, direction)
        u0, v0, us, vs = tile_uv(tile)
        c = [centre - right * size - upv * size,
             centre + right * size - upv * size,
             centre + right * size + upv * size,
             centre - right * size + upv * size]
        uv = [(u0, v0 + vs), (u0 + us, v0 + vs), (u0 + us, v0), (u0, v0)]
        idx = (0, 1, 2, 0, 2, 3)
        data = np.array([[*c[i], *uv[i]] for i in idx], dtype=np.float32)
        self.bill_vbo.write(data.tobytes())
        pb = self.p_bill
        write_mat(pb, "u_mvp", vp)
        pb["u_atlas"].value = 0
        pb["u_tint"].value = tint
        self.vao_bill.render()

    # ------------------------------------------------------------------
    def _draw_entities(self, vp, world, ambient):
        pe = self.p_ent
        write_mat(pe, "u_mvp", vp)
        pe["u_ambient"].value = ambient
        for e in world.entities:
            self._cur_hurt = min(1.0, e.hurt_timer / 0.35) * 0.75
            t = e.TYPE_NAME
            if t == "slime":
                self._draw_slime(pe, e)
            elif t == "pig":
                self._draw_pig(pe, e)
            elif t == "villager":
                self._draw_villager(pe, e)
            elif t == "primed_tnt":
                self._cur_hurt = 0.0
                self._box(pe, e.pos, e.yaw, (0, 0, 0), (0.98, 0.98, 0.98),
                          (0.78, 0.16, 0.12, 1.0), flash=e.flash * 0.7)

    def _box(self, prog, epos, yaw, offset, size, color, flash=0.0):
        m = (translate(epos) @ rot_y(-yaw) @ translate(offset) @ scale(size))
        write_mat(prog, "u_model", m)
        prog["u_color"].value = color
        prog["u_flash"].value = flash
        prog["u_hurt"].value = getattr(self, "_cur_hurt", 0.0)
        self.vao_ent.render()

    def _draw_slime(self, prog, e):
        sxz, sy = e.visual_scale
        w = 0.7 * sxz
        h = 0.65 * sy
        # inner core (opaque-ish) then translucent shell
        self._box(prog, e.pos, e.yaw, (0, h * 0.18, 0),
                  (w * 0.45, h * 0.5, w * 0.45), (0.16, 0.45, 0.18, 0.9))
        fx, fz = math.cos(e.yaw), math.sin(e.yaw)
        for side in (-1, 1):
            ox = fx * w * 0.28 - fz * side * w * 0.18
            oz = fz * w * 0.28 + fx * side * w * 0.18
            self._box(prog, e.pos, e.yaw, (ox, h * 0.55, oz),
                      (0.09, 0.09, 0.09), (0.05, 0.1, 0.05, 1.0))
        self._box(prog, e.pos, e.yaw, (0, 0, 0), (w, h, w), e.COLOR)

    def _draw_pig(self, prog, e):
        c = e.COLOR
        dark = (c[0] * 0.8, c[1] * 0.8, c[2] * 0.8, 1.0)
        swing = math.sin(e.anim_phase * 4.0) * 0.14
        self._box(prog, e.pos, e.yaw, (0, 0.30, 0), (0.8, 0.42, 0.5), c)
        self._box(prog, e.pos, e.yaw, (0.45, 0.42, 0), (0.34, 0.34, 0.34),
                  (min(1, c[0] * 1.05), c[1], c[2], 1.0))
        self._box(prog, e.pos, e.yaw, (0.63, 0.47, 0), (0.10, 0.12, 0.16),
                  dark)
        for fx_, fz_ in ((0.26, 0.14), (0.26, -0.14),
                         (-0.26, 0.14), (-0.26, -0.14)):
            s = swing if (fx_ > 0) == (fz_ > 0) else -swing
            self._box(prog, e.pos, e.yaw, (fx_ + s, 0.0, fz_),
                      (0.13, 0.32, 0.13), dark)

    def _draw_villager(self, prog, e):
        # humanoid: head / body / 2 arms / 2 legs, limbs swing while walking
        s = math.sin(e.anim_phase * 4.0) * 0.18
        robe, skin = e.ROBE, e.SKIN
        self._box(prog, e.pos, e.yaw, (s, 0.0, 0.12), (0.22, 0.72, 0.18), robe)
        self._box(prog, e.pos, e.yaw, (-s, 0.0, -0.12), (0.22, 0.72, 0.18), robe)
        self._box(prog, e.pos, e.yaw, (0, 0.72, 0), (0.28, 0.70, 0.50), robe)
        self._box(prog, e.pos, e.yaw, (-s, 0.74, 0.33), (0.16, 0.60, 0.16), skin)
        self._box(prog, e.pos, e.yaw, (s, 0.74, -0.33), (0.16, 0.60, 0.16), skin)
        self._box(prog, e.pos, e.yaw, (0.05, 1.42, 0), (0.42, 0.42, 0.42), skin)

    # ------------------------------------------------------------------
    def _draw_particles(self, vp, camera, weather):
        n = weather.active_count()
        if n <= 0:
            return
        data = weather.particles[:n].astype("f4")
        self.part_inst.write(data.tobytes())
        pp = self.p_part
        write_mat(pp, "u_mvp", vp)
        pp["u_atlas"].value = 0
        fwd = camera.direction()
        up = np.array([0.0, 1.0, 0.0])
        right = np.cross(fwd, up)
        nr = np.linalg.norm(right)
        right = right / nr if nr > 1e-6 else np.array([1.0, 0.0, 0.0])
        if weather.state == "SNOW":
            u0, v0, us, vs = tile_uv(TILE["snowflake"])
            pp["u_size"].value = (0.12, 0.12)
            pp["u_up"].value = tuple(np.cross(right, fwd))
        else:
            u0, v0, us, vs = tile_uv(TILE["rain"])
            pp["u_size"].value = (0.05, 0.55)
            pp["u_up"].value = (0.0, 1.0, 0.0)
        pp["u_right"].value = tuple(right)
        pp["u_uv_rect"].value = (u0, v0, us, vs)
        pp["u_alpha"].value = 0.75 * weather.intensity
        self.vao_part.render(instances=n)