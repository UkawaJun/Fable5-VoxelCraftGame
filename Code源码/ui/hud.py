"""HUD: crosshair, hotbar (real block textures), debug text, item name.

HUD 全部用 moderngl 绘制（文本经 PIL 渲染成纹理），不与 pyglet 绘图混用，
避免 GL 状态冲突。
"""

import moderngl
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from engine import shaders
from engine.texture_atlas import tile_uv

_SLOT = 46          # hotbar slot size in px
_ICON = 34


class TextTexture:
    """PIL-rendered text -> GL texture, regenerated only when text changes."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.tex = None
        self.size = (0, 0)
        self.text = None
        try:
            self.font = ImageFont.load_default(size=14)
        except TypeError:                      # older Pillow
            self.font = ImageFont.load_default()

    def set(self, text: str):
        if text == self.text:
            return
        self.text = text
        lines = text.split("\n")
        try:
            w = max(8, max(int(self.font.getlength(ln)) for ln in lines) + 4)
        except AttributeError:                 # very old Pillow bitmap font
            w = max(8, max(len(ln) for ln in lines) * 8 + 4)
        lh = 18
        h = lh * len(lines) + 4
        img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        for i, ln in enumerate(lines):
            d.text((3, 3 + i * lh), ln, fill=(20, 20, 20, 255), font=self.font)
            d.text((2, 2 + i * lh), ln, fill=(255, 255, 255, 255), font=self.font)
        if self.tex is not None:
            self.tex.release()
        self.tex = self.ctx.texture(img.size, 4, img.tobytes())
        self.tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.size = img.size


class Hud:
    def __init__(self, ctx, atlas_tex):
        self.ctx = ctx
        self.atlas_tex = atlas_tex
        self.prog = ctx.program(vertex_shader=shaders.HUD_VS,
                                fragment_shader=shaders.HUD_FS)
        self.vbo = ctx.buffer(reserve=6 * 4 * 4, dynamic=True)
        self.vao = ctx.vertex_array(
            self.prog, [(self.vbo, "2f 2f", "in_pos", "in_uv")])
        self.debug_text = TextTexture(ctx)
        self.item_text = TextTexture(ctx)
        self.show_debug = False

    # ------------------------------------------------------------------
    def _rect(self, x, y, w, h, color, tex=None, uv=(0, 0, 1, 1)):
        u0, v0, us, vs = uv
        verts = np.array([
            [x, y, u0, v0], [x + w, y, u0 + us, v0],
            [x + w, y + h, u0 + us, v0 + vs],
            [x, y, u0, v0], [x + w, y + h, u0 + us, v0 + vs],
            [x, y + h, u0, v0 + vs]], dtype=np.float32)
        self.vbo.write(verts.tobytes())
        if tex is not None:
            tex.use(0)
            self.prog["u_tex"].value = 0
            self.prog["u_use_tex"].value = 1.0
        else:
            self.prog["u_use_tex"].value = 0.0
        self.prog["u_color"].value = color
        self.vao.render()

    # ------------------------------------------------------------------
    def render(self, width, height, player, debug_lines=None):
        ctx = self.ctx
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.enable(moderngl.BLEND)
        self.prog["u_screen"].value = (width, height)

        # crosshair 准星
        cx, cy = width // 2, height // 2
        wcol = (1.0, 1.0, 1.0, 0.85)
        self._rect(cx - 8, cy - 1, 16, 2, wcol)
        self._rect(cx - 1, cy - 8, 2, 16, wcol)

        # hotbar 热栏
        items = player.hotbar
        total = len(items) * _SLOT
        x0 = (width - total) // 2
        y0 = height - _SLOT - 8
        for i, item in enumerate(items):
            x = x0 + i * _SLOT
            self._rect(x, y0, _SLOT - 2, _SLOT - 2, (0.08, 0.08, 0.1, 0.55))
            pad = (_SLOT - 2 - _ICON) // 2
            self._rect(x + pad, y0 + pad, _ICON, _ICON, (1, 1, 1, 1),
                       tex=self.atlas_tex, uv=tile_uv(item.icon_tile))
            if i == player.slot:
                b = 2
                sel = (1.0, 1.0, 1.0, 0.95)
                self._rect(x - b, y0 - b, _SLOT - 2 + 2 * b, b, sel)
                self._rect(x - b, y0 + _SLOT - 2, _SLOT - 2 + 2 * b, b, sel)
                self._rect(x - b, y0, b, _SLOT - 2, sel)
                self._rect(x + _SLOT - 2, y0, b, _SLOT - 2, sel)

        # selected item name 物品名
        self.item_text.set(player.selected_item().display)
        tw, th = self.item_text.size
        self._rect((width - tw) // 2, y0 - th - 6, tw, th, (1, 1, 1, 1),
                   tex=self.item_text.tex)

        # debug overlay (F3)
        if self.show_debug and debug_lines:
            self.debug_text.set("\n".join(debug_lines))
            tw, th = self.debug_text.size
            self._rect(8, 8, tw, th, (1, 1, 1, 1), tex=self.debug_text.tex)

        ctx.disable(moderngl.BLEND)
        ctx.enable(moderngl.DEPTH_TEST)
