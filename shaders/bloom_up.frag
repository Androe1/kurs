#version 330
// Bloom: çadır filtresiyle büyütme (bir üst seviyeye eklenir)
uniform sampler2D u_src;
uniform vec2 u_texel;
uniform float u_weight;
in vec2 v_uv;
out vec4 frag;

vec3 s(vec2 o) { return texture(u_src, v_uv + o * u_texel).rgb; }

void main() {
    vec3 col = s(vec2(0, 0)) * 4.0
             + (s(vec2(-1, 0)) + s(vec2(1, 0)) + s(vec2(0, -1)) + s(vec2(0, 1))) * 2.0
             + (s(vec2(-1, -1)) + s(vec2(1, -1)) + s(vec2(-1, 1)) + s(vec2(1, 1)));
    frag = vec4(col / 16.0 * u_weight, 1.0);
}
