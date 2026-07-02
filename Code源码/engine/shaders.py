"""All GLSL shaders (OpenGL 3.3 core), embedded as strings."""

CHUNK_VS = """
#version 330
uniform mat4 u_mvp;
uniform vec3 u_chunk_offset;
uniform vec3 u_cam_pos;
in vec3 in_pos;
in vec2 in_uv;
in float in_shade;
in float in_light;
out vec2 v_uv;
out float v_shade;
out float v_light;
out float v_dist;
void main() {
    vec3 wp = in_pos + u_chunk_offset;
    gl_Position = u_mvp * vec4(wp, 1.0);
    v_uv = in_uv;
    v_shade = in_shade;
    v_light = in_light;
    v_dist = distance(wp, u_cam_pos);
}
"""

CHUNK_FS = """
#version 330
uniform sampler2D u_atlas;
uniform float u_ambient;
uniform vec3 u_fog_color;
uniform float u_fog_start;
uniform float u_fog_end;
uniform float u_alpha_test;     // 1.0 = discard transparent texels (leaves)
in vec2 v_uv;
in float v_shade;
in float v_light;               // baked block-light 0..1 (point lights)
in float v_dist;
out vec4 frag;
void main() {
    vec4 tex = texture(u_atlas, v_uv);
    if (u_alpha_test > 0.5 && tex.a < 0.5) discard;
    // daylight (directional shade * sun ambient) vs block-light, take the max.
    // block-light gets a warm tint so torches/glowstone read as warm.
    float day = v_shade * u_ambient;
    vec3 warm = vec3(1.0, 0.86, 0.66);
    vec3 lit = max(vec3(day), warm * v_light);
    vec3 rgb = tex.rgb * lit;
    float fog = smoothstep(u_fog_start, u_fog_end, v_dist);
    rgb = mix(rgb, u_fog_color, fog);
    frag = vec4(rgb, tex.a);
}
"""

SKY_VS = """
#version 330
in vec2 in_pos;
out vec2 v_ndc;
void main() {
    v_ndc = in_pos;
    gl_Position = vec4(in_pos, 0.9999, 1.0);
}
"""

SKY_FS = """
#version 330
uniform mat4 u_inv_vp;
uniform vec3 u_zenith;
uniform vec3 u_horizon;
in vec2 v_ndc;
out vec4 frag;
void main() {
    vec4 pn = u_inv_vp * vec4(v_ndc, -1.0, 1.0);
    vec4 pf = u_inv_vp * vec4(v_ndc,  1.0, 1.0);
    vec3 dir = normalize(pf.xyz / pf.w - pn.xyz / pn.w);
    float k = smoothstep(-0.04, 0.45, dir.y);
    vec3 col = mix(u_horizon, u_zenith, k);
    frag = vec4(col, 1.0);
}
"""

# textured quad in world space (sun / moon)
BILLBOARD_VS = """
#version 330
uniform mat4 u_mvp;
in vec3 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    gl_Position = u_mvp * vec4(in_pos, 1.0);
    v_uv = in_uv;
}
"""

BILLBOARD_FS = """
#version 330
uniform sampler2D u_atlas;
uniform vec4 u_tint;
in vec2 v_uv;
out vec4 frag;
void main() {
    vec4 tex = texture(u_atlas, v_uv);
    frag = vec4(tex.rgb * u_tint.rgb, tex.a * u_tint.a);
}
"""

# coloured box-model entities (mobs, primed TNT)
ENTITY_VS = """
#version 330
uniform mat4 u_mvp;
uniform mat4 u_model;
in vec3 in_pos;
in float in_shade;
out float v_shade;
void main() {
    gl_Position = u_mvp * (u_model * vec4(in_pos, 1.0));
    v_shade = in_shade;
}
"""

ENTITY_FS = """
#version 330
uniform vec4 u_color;
uniform float u_ambient;
uniform float u_flash;          // primed TNT white blink
uniform float u_hurt;           // red flash when a mob is hit
in float v_shade;
out vec4 frag;
void main() {
    vec3 rgb = u_color.rgb * (v_shade * u_ambient);
    rgb = mix(rgb, vec3(1.0), u_flash);
    rgb = mix(rgb, vec3(1.0, 0.18, 0.18), u_hurt);
    frag = vec4(rgb, u_color.a);
}
"""

# instanced debris cubes (textured with the block's own tile)
DEBRIS_VS = """
#version 330
uniform mat4 u_mvp;
uniform float u_atlas_step;
in vec3 in_pos;        // cube centred at origin, -0.5..0.5
in vec2 in_uv;
in float in_shade;
in vec3 i_pos;         // per-instance
in float i_rot;
in float i_tile;
out vec2 v_uv;
out float v_shade;
void main() {
    float c = cos(i_rot), s = sin(i_rot);
    vec3 p = in_pos * 0.30;                       // debris size
    p = vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
    float c2 = cos(i_rot * 0.7), s2 = sin(i_rot * 0.7);
    p = vec3(p.x, c2 * p.y - s2 * p.z, s2 * p.y + c2 * p.z);
    gl_Position = u_mvp * vec4(p + i_pos, 1.0);
    float col = mod(i_tile, 16.0);
    float row = floor(i_tile / 16.0);
    v_uv = (vec2(col, row) + in_uv) * u_atlas_step;
    v_shade = in_shade;
}
"""

DEBRIS_FS = """
#version 330
uniform sampler2D u_atlas;
uniform float u_ambient;
in vec2 v_uv;
in float v_shade;
out vec4 frag;
void main() {
    vec4 tex = texture(u_atlas, v_uv);
    if (tex.a < 0.4) discard;
    frag = vec4(tex.rgb * v_shade * u_ambient, 1.0);
}
"""

# instanced weather particles (camera-facing quads)
PARTICLE_VS = """
#version 330
uniform mat4 u_mvp;
uniform vec3 u_right;
uniform vec3 u_up;
uniform vec2 u_size;
in vec2 in_corner;     // -0.5..0.5 quad
in vec3 i_pos;
out vec2 v_uv;
void main() {
    vec3 wp = i_pos + u_right * in_corner.x * u_size.x
                    + u_up    * in_corner.y * u_size.y;
    gl_Position = u_mvp * vec4(wp, 1.0);
    v_uv = in_corner + 0.5;
}
"""

PARTICLE_FS = """
#version 330
uniform sampler2D u_atlas;
uniform vec4 u_uv_rect;        // u0, v0, usize, vsize
uniform float u_alpha;
in vec2 v_uv;
out vec4 frag;
void main() {
    vec4 tex = texture(u_atlas, u_uv_rect.xy + v_uv * u_uv_rect.zw);
    frag = vec4(tex.rgb, tex.a * u_alpha);
}
"""

# block highlight wireframe + generic 3D lines
LINE_VS = """
#version 330
uniform mat4 u_mvp;
uniform vec3 u_offset;
in vec3 in_pos;
void main() {
    gl_Position = u_mvp * vec4(in_pos + u_offset, 1.0);
}
"""

LINE_FS = """
#version 330
uniform vec4 u_color;
out vec4 frag;
void main() { frag = u_color; }
"""

# 2D HUD (pixel coords, origin top-left)
HUD_VS = """
#version 330
uniform vec2 u_screen;
in vec2 in_pos;
in vec2 in_uv;
out vec2 v_uv;
void main() {
    vec2 ndc = vec2(in_pos.x / u_screen.x * 2.0 - 1.0,
                    1.0 - in_pos.y / u_screen.y * 2.0);
    gl_Position = vec4(ndc, 0.0, 1.0);
    v_uv = in_uv;
}
"""

HUD_FS = """
#version 330
uniform sampler2D u_tex;
uniform vec4 u_color;
uniform float u_use_tex;
in vec2 v_uv;
out vec4 frag;
void main() {
    vec4 c = u_color;
    if (u_use_tex > 0.5) c *= texture(u_tex, v_uv);
    frag = c;
}
"""
