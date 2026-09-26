#version 330
in vec3 v_col;
layout(location = 0) out vec4 frag;
layout(location = 1) out vec4 gbuf;
void main() {
    vec2 q = gl_PointCoord * 2.0 - 1.0;
    float a = exp(-3.0 * dot(q, q));
    if (a < 0.02) discard;
    frag = vec4(v_col * a, 0.0);
    gbuf = vec4(0.0);
}
