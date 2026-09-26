#version 330
// Kan sıvısı: yukarıdan inen yapışkan iplik, asılı damla ve düşen damlacıklar (SDF, yumuşak birleşim).
// u_mode 0: ana görüntü, 1: zemindeki yansıma (aynalanmış ışın), 2: spot ışığın gölge haritası (yalnız derinlik)
#include "common.glsl"

uniform int u_mode;
uniform mat4 u_viewproj;
uniform mat4 u_inv_viewproj;
uniform vec3 u_eye;
uniform vec2 u_res;
uniform float u_time;

uniform vec4 u_caps[14];        // iplik noktaları: xyz + yarıçap (ardışık noktalar yuvarlak konilerle bağlanır)
uniform int u_ncaps;
uniform vec4 u_drop;            // damla: merkez + yarıçap (0 = yok)
uniform vec4 u_drop_shape;      // dikey uzama, dalga genliği, dalga fazı, burulma
uniform vec4 u_blobs[28];       // serbest damlacıklar: xyz + yarıçap
uniform int u_nblobs;
uniform vec3 u_bmin;
uniform vec3 u_bmax;
uniform float u_blend;          // yumuşak birleşim yarıçapı
uniform float u_ridge;          // damla yüzeyinde yaprak kenarı gibi sarmal sırtlar (dönüşümün başı)

uniform vec3 u_spot_pos;
uniform vec3 u_spot_dir;
uniform vec2 u_spot_cos;
uniform vec3 u_spot_col;
uniform sampler2DShadow u_shadow;
uniform mat4 u_light_vp;
uniform vec3 u_back_dir;
uniform vec3 u_back_col;
uniform float u_light_gain;

uniform mat3 u_view3;

in vec2 v_uv;
layout(location = 0) out vec4 frag;
layout(location = 1) out vec4 gbuf;

float sdRoundCone(vec3 p, vec3 a, vec3 b, float r1, float r2) {
    vec3 ba = b - a;
    float l2 = dot(ba, ba);
    float rr = r1 - r2;
    float a2 = l2 - rr * rr;
    float il2 = 1.0 / l2;
    vec3 pa = p - a;
    float y = dot(pa, ba);
    float z = y - l2;
    vec3 xv = pa * l2 - ba * y;
    float x2 = dot(xv, xv);
    float y2 = y * y * l2;
    float z2 = z * z * l2;
    float k = sign(rr) * rr * rr * x2;
    if (sign(z) * a2 * z2 > k) return sqrt(x2 + z2) * il2 - r2;
    if (sign(y) * a2 * y2 < k) return sqrt(x2 + y2) * il2 - r1;
    return (sqrt(x2 * a2 * il2) + y * rr) * il2 - r1;
}

float sdEllipsoid(vec3 p, vec3 r) {
    float k0 = length(p / r);
    float k1 = length(p / (r * r));
    return k0 * (k0 - 1.0) / k1;
}

float mapLiquid(vec3 p) {
    float d = 1e3;
    for (int i = 0; i + 1 < u_ncaps; i++) {
        vec4 a = u_caps[i], b = u_caps[i + 1];
        d = min(d, sdRoundCone(p, a.xyz, b.xyz, a.w, b.w));      // zincir: eklemlerde şişkinlik olmasın
    }
    if (u_drop.w > 0.0) {
        vec3 q = p - u_drop.xyz;
        float tw = u_drop_shape.w;
        q.xz = mat2(cos(tw), -sin(tw), sin(tw), cos(tw)) * q.xz;
        float st = u_drop_shape.x;
        float ang = atan(q.z, q.x);
        float wob = u_drop_shape.y * (sin(3.0 * ang + u_drop_shape.z) * 0.6 + sin(5.0 * q.y / max(u_drop.w, 1e-3) + 1.7 * u_drop_shape.z) * 0.4);
        vec3 r = u_drop.w * vec3(1.0 / sqrt(st), st, 1.0 / sqrt(st));
        // alt kısmı dolgun, üstü boyuna doğru incelen damla
        r.xz *= 1.0 + 0.18 * clamp(-q.y / max(r.y, 1e-4), -1.0, 1.0);
        // sarmal sırtlar: sıvının yüzeyi yaprak kenarlarına bölünmeye başlar
        float sp = ang * 5.0 + q.y / max(u_drop.w, 1e-3) * 5.5 + u_drop_shape.w * 2.0;
        float ridge = pow(0.5 + 0.5 * cos(sp), 4.0) * u_ridge;
        d = smin(d, sdEllipsoid(q, r) - (wob + ridge) * u_drop.w, u_blend);
    }
    for (int i = 0; i < u_nblobs; i++) {
        vec4 b = u_blobs[i];
        d = smin(d, length(p - b.xyz) - b.w, u_blend * 0.6);
    }
    return d;
}

vec3 calcNormal(vec3 p) {
    const vec2 k = vec2(1.0, -1.0);
    const float h = 0.0006;
    return normalize(k.xyy * mapLiquid(p + k.xyy * h) + k.yyx * mapLiquid(p + k.yyx * h) +
                     k.yxy * mapLiquid(p + k.yxy * h) + k.xxx * mapLiquid(p + k.xxx * h));
}

vec2 boxHit(vec3 ro, vec3 rd) {
    vec3 inv = 1.0 / rd;
    vec3 t0 = (u_bmin - ro) * inv, t1 = (u_bmax - ro) * inv;
    vec3 tmin = min(t0, t1), tmax = max(t0, t1);
    return vec2(max(max(tmin.x, tmin.y), tmin.z), min(min(tmax.x, tmax.y), tmax.z));
}

float shadowAt(vec3 p, vec3 n) {
    vec4 c = u_light_vp * vec4(p + n * 0.006, 1.0);
    vec3 q = c.xyz / c.w * 0.5 + 0.5;
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) return 1.0;
    return texture(u_shadow, vec3(q.xy, q.z - 0.001));
}

vec3 envLight(vec3 P, vec3 r) {
    vec3 toSpot = normalize(u_spot_pos - P);
    float c = max(dot(r, toSpot), 0.0);
    // spot ışığın diski + huzmenin geniş parıltısı, arkadaki ışık, sisli boşluğun sönük halkası
    float s = pow(c, 1500.0) * 60.0 + pow(c, 40.0) * 1.2 + pow(max(r.y, 0.0), 5.0) * 0.18;
    float b = pow(max(dot(r, u_back_dir), 0.0), 60.0) * 2.5 + pow(max(dot(r, u_back_dir), 0.0), 600.0) * 20.0;
    float ring = exp(-abs(r.y) * 6.0) * 0.03;
    return u_spot_col * s * 0.12 + u_back_col * b + vec3(ring, ring * 0.5, ring * 0.55);
}

void main() {
    vec2 ndc = v_uv * 2.0 - 1.0;
    vec4 pn = u_inv_viewproj * vec4(ndc, -1.0, 1.0);
    vec4 pf = u_inv_viewproj * vec4(ndc, 1.0, 1.0);
    vec3 a = pn.xyz / pn.w, b = pf.xyz / pf.w;
    vec3 ro = (u_mode == 2) ? u_eye : u_eye;
    vec3 rd = normalize(b - a);
    ro = a;
    if (u_mode == 1) { ro.y = -ro.y; rd.y = -rd.y; }

    vec2 tb = boxHit(ro, rd);
    if (tb.x > tb.y || tb.y < 0.0) discard;
    float t = max(tb.x, 0.0);
    float pixAng = 2.0 / u_res.y;                 // bir pikselin açısal boyu (yaklaşık)
    float bestCov = 0.0, bestT = t;
    bool hit = false;
    for (int i = 0; i < 110; i++) {
        vec3 p = ro + rd * t;
        float d = mapLiquid(p);
        float pr = max(t * pixAng, 1e-5);
        float cov = clamp(0.5 - d / pr, 0.0, 1.0);
        if (cov > bestCov) { bestCov = cov; bestT = t; }
        if (d < 0.25 * pr) { hit = true; bestCov = 1.0; bestT = t; break; }
        t += max(d * 0.9, 0.3 * pr);
        if (t > tb.y) break;
    }
    if (u_mode == 2) {
        if (!hit) discard;
    }
    if (bestCov < 0.02) discard;

    vec3 P = ro + rd * bestT;
    if (u_mode == 1 && P.y < 0.0) discard;
    vec3 Pw = P;
    if (u_mode == 1) Pw.y = -Pw.y;              // yansımada derinlik aynalanmış noktadan
    vec4 clip = u_viewproj * vec4(Pw, 1.0);
    gl_FragDepth = clip.z / clip.w * 0.5 + 0.5;
    if (u_mode == 2) { frag = vec4(1.0); gbuf = vec4(0.0); return; }

    vec3 N = calcNormal(P);
    vec3 V = -rd;
    vec3 L = normalize(u_spot_pos - P);
    float att = spotAtten(P, u_spot_pos, u_spot_dir, u_spot_cos.x, u_spot_cos.y) * u_light_gain;
    float sh = shadowAt(P, N);
    float NdL = max(dot(N, L), 0.0);
    vec3 H = normalize(L + V);
    float NdV = max(dot(N, V), 1e-3);
    float F = fresnel(max(dot(H, V), 0.0), 0.04);

    vec3 blood = vec3(0.028, 0.0002, 0.0016);
    vec3 col = blood * (NdL * 0.9 + 0.1) * att * u_spot_col * sh;
    col += u_spot_col * att * sh * ggx(max(dot(N, H), 0.0), 0.035) * F * NdL * 2.0;
    // ince kısımlar (iplik, damla kenarı) ışığı içinden geçirip koyu kırmızı parlar
    float thin = clamp(-mapLiquid(P - N * 0.012) / 0.012, 0.0, 1.0);
    col += vec3(0.16, 0.002, 0.008) * (1.0 - thin) * att * u_spot_col * (0.2 + 0.8 * max(dot(-N, L), 0.0)) * sh;
    // damla mercek gibi davranır: ışığın tam karşısında (altta) kızıl bir parıltı toplanır
    float focus = pow(max(dot(-N, L), 0.0), 3.0) * pow(max(dot(N, V), 0.0), 0.5);
    col += vec3(0.55, 0.012, 0.03) * focus * att * u_spot_col * 0.35;
    // arkadan kenar ışığı
    col += vec3(0.7, 0.05, 0.08) * u_back_col * pow(1.0 - NdV, 3.0) * smoothstep(-0.3, 0.6, dot(N, u_back_dir)) * u_light_gain;
    // ortam yansıması (parlak ıslak yüzey)
    col += envLight(P, reflect(rd, N)) * fresnel(NdV, 0.05) * u_light_gain * 1.6;
    col += u_back_col * ggx(max(dot(N, normalize(u_back_dir + V)), 0.0), 0.06) * 0.08 * max(dot(N, u_back_dir), 0.0) * u_light_gain;

    // boyanmış parlama: keskin beyaz leke
    col += vec3(1.0, 0.85, 0.85) * smoothstep(0.55, 0.7, ggx(max(dot(N, H), 0.0), 0.05) * F * NdL * att * sh) * 0.8;
    frag = vec4(col * bestCov, bestCov);
    gbuf = vec4(normalize(u_view3 * N) * bestCov, 0.95 * bestCov);
}
