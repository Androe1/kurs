#version 330
// Gül yaprakları (ana geçiş ve yansıma geçişi). Köşeler CPU'da dünya uzayında hazırlanır.
uniform mat4 u_viewproj;
uniform float u_mirror;          // 1: zemindeki yansıma (y -> -y)

in vec3 in_pos;
in vec3 in_nrm;
in vec2 in_uv;
in vec4 in_info;                 // k (içten dışa), yaprak no, AO (+n yüzü), AO (-n yüzü)
in vec2 in_extra;                // sıvılık (1 = kan damlası malzemesi), ıslaklık

out vec3 v_pos;
out vec3 v_nrm;
out vec2 v_uv;
out vec4 v_info;
out vec2 v_extra;
out float v_height;

void main() {
    vec3 p = in_pos;
    vec3 n = in_nrm;
    v_height = p.y;
    if (u_mirror > 0.5) { p.y = -p.y; n.y = -n.y; }
    v_pos = p;
    v_nrm = n;
    v_uv = in_uv;
    v_info = in_info;
    v_extra = in_extra;
    gl_Position = u_viewproj * vec4(p, 1.0);
}
