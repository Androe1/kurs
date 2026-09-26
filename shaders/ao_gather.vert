#version 330
// Ortam kapanması: gül 48 yönden derinlik haritasına çizilir; her köşe için bu yönlerden kaçının
// açık olduğu (başka yaprak tarafından örtülmediği) kosinüs ağırlıklı sayılır. Yaprak ince olduğu
// için iki yüz ayrı hesaplanır. Sonuç transform feedback ile okunur.
#define NDIR 48
uniform sampler2D u_atlas;
uniform mat4 u_vp[NDIR];
uniform vec3 u_dirs[NDIR];
uniform vec2 u_grid;             // atlas sütun, satır
uniform float u_offset;

in vec3 in_pos;
in vec3 in_nrm;
out vec2 out_ao;

float visible(int j, vec3 p) {
    vec4 c = u_vp[j] * vec4(p, 1.0);
    vec3 q = c.xyz * 0.5 + 0.5;
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) return 1.0;
    vec2 tile = vec2(float(j % int(u_grid.x)), float(j / int(u_grid.x)));
    vec2 ts = vec2(textureSize(u_atlas, 0)) / u_grid;
    float s = 0.0;
    for (int x = -1; x <= 1; x++)
        for (int y = -1; y <= 1; y++) {
            vec2 px = clamp(q.xy * ts + vec2(x, y), vec2(0.5), ts - 0.5);
            float d = texture(u_atlas, (tile * ts + px) / vec2(textureSize(u_atlas, 0))).r;
            s += (q.z - 0.004 <= d) ? 1.0 : 0.0;
        }
    return s / 9.0;
}

void main() {
    vec3 n = normalize(in_nrm);
    float wf = 0.0, sf = 0.0, wb = 0.0, sb = 0.0;
    for (int j = 0; j < NDIR; j++) {
        float c = dot(n, u_dirs[j]);
        if (c > 0.0) { wf += c; sf += c * visible(j, in_pos + n * u_offset); }
        else { wb -= c; sb -= c * visible(j, in_pos - n * u_offset); }
    }
    out_ao = vec2(sf / max(wf, 1e-4), sb / max(wb, 1e-4));
}
