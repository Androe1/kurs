#version 330
// Hacimsel ışık: spot ışığın sisli havadaki huzmesi. Gölge haritası sayesinde gülün ve damlanın
// gölgesi huzmenin içinde karanlık bir sütun olarak görünür. Yarım çözünürlükte çizilir.
#include "common.glsl"

uniform mat4 u_inv_viewproj;
uniform sampler2D u_depth;      // sahne derinliği (tam çözünürlük)
uniform int u_mirror;
uniform float u_time;
uniform float u_density;

uniform vec3 u_spot_pos;
uniform vec3 u_spot_dir;
uniform vec2 u_spot_cos;
uniform vec3 u_spot_col;
uniform sampler2DShadow u_shadow;
uniform mat4 u_light_vp;
uniform float u_light_gain;

in vec2 v_uv;
out vec4 frag;

float shadowAt(vec3 p) {
    vec4 c = u_light_vp * vec4(p, 1.0);
    vec3 q = c.xyz / c.w * 0.5 + 0.5;
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) return 1.0;
    return texture(u_shadow, vec3(q.xy, q.z - 0.002));
}

void main() {
    vec2 ndc = v_uv * 2.0 - 1.0;
    vec4 pn = u_inv_viewproj * vec4(ndc, -1.0, 1.0);
    vec4 pf = u_inv_viewproj * vec4(ndc, 1.0, 1.0);
    vec3 ro = pn.xyz / pn.w;
    vec3 rd = normalize(pf.xyz / pf.w - ro);

    // sahne derinliğinden en uzak mesafe
    float z = texture(u_depth, v_uv).r;
    vec4 pw = u_inv_viewproj * vec4(ndc, z * 2.0 - 1.0, 1.0);
    float tmax = (z >= 0.99999) ? 40.0 : length(pw.xyz / pw.w - ro);
    if (u_mirror == 1) {
        ro.y = -ro.y;
        rd.y = -rd.y;
        // yansımada yalnızca zeminin üstü
        if (rd.y > 0.0) tmax = min(tmax, 40.0); else tmax = min(tmax, -ro.y / rd.y);
    }
    if (ro.y + rd.y * tmax < 0.0 && rd.y < 0.0) tmax = min(tmax, -ro.y / rd.y);

    // huzmeyi saran dikey silindir (ekseni spot hedefinden geçer) ile kesişim
    vec3 axisP = u_spot_pos;
    vec2 oc = ro.xz - axisP.xz;
    vec2 dxz = rd.xz;
    float R = 1.6;
    float A = dot(dxz, dxz), B = dot(oc, dxz), C = dot(oc, oc) - R * R;
    float disc = B * B - A * C;
    if (disc < 0.0 || A < 1e-8) { frag = vec4(0.0); return; }
    float sq = sqrt(disc);
    float t0 = max((-B - sq) / A, 0.0), t1 = min((-B + sq) / A, tmax);
    if (t1 <= t0) { frag = vec4(0.0); return; }

    const int STEPS = 40;
    float dt = (t1 - t0) / float(STEPS);
    float jitter = hash12(gl_FragCoord.xy + fract(u_time * 7.13) * 91.7);
    vec3 acc = vec3(0.0);
    for (int i = 0; i < STEPS; i++) {
        float t = t0 + (float(i) + jitter) * dt;
        vec3 p = ro + rd * t;
        if (p.y < 0.0) break;
        vec3 d = p - u_spot_pos;
        float dist = length(d);
        float c = dot(d / dist, u_spot_dir);
        float cone = smoothstep(u_spot_cos.x, u_spot_cos.y, c);
        if (cone <= 0.0) continue;
        float fog = 0.45 + 0.9 * fbm3(p * vec3(2.2, 1.1, 2.2) + vec3(0.02, -0.07, 0.015) * u_time * 10.0);
        float phase = 0.5 + 0.8 * pow(max(dot(rd, -d / dist), 0.0), 3.0);   // ışığa bakınca daha parlak
        float fall = 6.0 / (dist + 1.0);
        acc += cone * fall * fog * phase * shadowAt(p) * dt;
    }
    frag = vec4(acc * u_spot_col * u_density * u_light_gain, 1.0);
}
