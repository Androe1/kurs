#version 330
// Bloom: 13 örnekli küçültme (ilk seviyede yumuşak eşik)
uniform sampler2D u_src;
uniform vec2 u_texel;           // kaynak dokunun piksel boyu
uniform float u_threshold;
uniform int u_first;
in vec2 v_uv;
out vec4 frag;

vec3 s(vec2 o) { return texture(u_src, v_uv + o * u_texel).rgb; }

void main() {
    vec3 a = s(vec2(-2, 2)), b = s(vec2(0, 2)), c = s(vec2(2, 2));
    vec3 d = s(vec2(-2, 0)), e = s(vec2(0, 0)), f = s(vec2(2, 0));
    vec3 g = s(vec2(-2, -2)), h = s(vec2(0, -2)), i = s(vec2(2, -2));
    vec3 j = s(vec2(-1, 1)), k = s(vec2(1, 1)), l = s(vec2(-1, -1)), m = s(vec2(1, -1));
    vec3 col = e * 0.125 + (a + c + g + i) * 0.03125 + (b + d + f + h) * 0.0625 + (j + k + l + m) * 0.125;
    if (u_first == 1) {
        float br = max(col.r, max(col.g, col.b));
        float knee = u_threshold * 0.6;
        float soft = clamp(br - u_threshold + knee, 0.0, 2.0 * knee);
        soft = soft * soft / (4.0 * knee + 1e-5);
        col *= max(soft, br - u_threshold) / max(br, 1e-5);
    }
    frag = vec4(col, 1.0);
}
