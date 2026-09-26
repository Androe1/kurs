#version 330
// Zemin: ayna gibi siyah-kırmızı kan birikintisi. Düşen gül ve damlalar üzerinde halka halka dalga (ripple) açar.
#include "common.glsl"

uniform mat4 u_viewproj;
uniform mat4 u_inv_viewproj;
uniform vec2 u_res;
uniform float u_time;

uniform vec4 u_ripples[32];      // x, z, başlangıç zamanı, genlik (m)
uniform vec4 u_ripples2[32];     // dalga boyu (m), hız (m/s), sönüm (s), -
uniform int u_nripples;

uniform sampler2D u_refl;        // aynalanmış sahne (yarım çözünürlük)
uniform float u_refl_gain;
uniform float u_beam_refl;       // huzme yansımasının gücü

uniform vec3 u_spot_pos;
uniform vec3 u_spot_dir;
uniform vec2 u_spot_cos;
uniform vec3 u_spot_col;
uniform sampler2DShadow u_shadow;
uniform mat4 u_light_vp;
uniform vec3 u_back_dir;
uniform vec3 u_back_col;
uniform float u_light_gain;

uniform float u_ripple_ink;      // dalga tepelerini çizgi olarak boya

in vec2 v_uv;
layout(location = 0) out vec4 frag;
layout(location = 1) out vec4 gbuf;

float rippleEnv = 0.0;           // o noktadaki toplam dalga zarfı (çizgi kalınlığı/opaklığı için)

float rippleH(vec2 xz) {
    float h = 0.0;
    rippleEnv = 0.0;
    for (int i = 0; i < u_nripples; i++) {
        vec4 r = u_ripples[i];
        vec4 q = u_ripples2[i];
        float tau = u_time - r.z;
        if (tau <= 0.0) continue;
        float d = length(xz - r.xy);
        float x = q.y * tau - d;                         // dalga cephesinin gerisinde kalan mesafe
        if (x < -0.04) continue;
        float lam = q.x * (1.0 - 0.4 * smoothstep(0.0, 0.5, x));   // içe doğru sıklaşan halkalar
        float env = smoothstep(-0.035, 0.02, x) * exp(-max(x, 0.0) / (0.1 + 0.22 * min(tau, 2.0)));
        float amp = r.w * env * exp(-tau / q.z) / sqrt(1.0 + d / 0.04);
        h += amp * sin(6.2831853 * x / lam);
        rippleEnv += amp;
    }
    return h;
}

float shadowAt(vec3 p) {
    vec4 c = u_light_vp * vec4(p, 1.0);
    vec3 q = c.xyz / c.w * 0.5 + 0.5;
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) return 1.0;
    float s = 0.0;
    for (int x = -2; x <= 2; x++)
        for (int y = -2; y <= 2; y++)
            s += texture(u_shadow, vec3(q.xy + vec2(x, y) / 2048.0 * 2.0, q.z - 0.0015));
    return s / 25.0;
}

void main() {
    vec2 ndc = v_uv * 2.0 - 1.0;
    vec4 pn = u_inv_viewproj * vec4(ndc, -1.0, 1.0);
    vec4 pf = u_inv_viewproj * vec4(ndc, 1.0, 1.0);
    vec3 ro = pn.xyz / pn.w;
    vec3 rd = normalize(pf.xyz / pf.w - ro);
    if (rd.y > -1e-4) discard;
    float t = -ro.y / rd.y;
    vec3 P = ro + rd * t;
    if (length(P.xz) > 30.0) discard;

    vec4 clip = u_viewproj * vec4(P, 1.0);
    gl_FragDepth = clip.z / clip.w * 0.5 + 0.5;

    // dalga normali (sayısal türev) + sıvının kendi çok hafif kıpırtısı
    const float e = 0.0015;
    float hx0 = rippleH(P.xz + vec2(e, 0.0));
    float h0 = rippleH(P.xz);
    float env0 = rippleEnv;
    float hx = hx0;
    float hz = rippleH(P.xz + vec2(0.0, e));
    vec3 N = normalize(vec3(-(hx - h0) / e, 1.0, -(hz - h0) / e));
    vec2 wob = vec2(fbm2(P.xz * 2.2 + vec2(u_time * 0.03, 0.0)), fbm2(P.xz * 2.2 + vec2(7.1, u_time * 0.025))) - 0.5;
    N = normalize(N + vec3(wob.x, 0.0, wob.y) * 0.025);

    vec3 V = -rd;
    float NdV = max(dot(N, V), 1e-3);
    float Fr = fresnel(NdV, 0.05);

    // yansıma: ekranda aynalanmış görüntüden, dalga eğimiyle kırılarak (hafif bulanık)
    vec2 suv = gl_FragCoord.xy / u_res;
    vec2 off = vec2(N.x, -N.z) * 0.045 / max(t, 0.4);
    vec2 px = 1.5 / u_res;
    vec3 refl = vec3(0.0);
    refl += texture(u_refl, clamp(suv + off + vec2(px.x, 0.0), vec2(0.001), vec2(0.999))).rgb;
    refl += texture(u_refl, clamp(suv + off - vec2(px.x, 0.0), vec2(0.001), vec2(0.999))).rgb;
    refl += texture(u_refl, clamp(suv + off + vec2(0.0, px.y), vec2(0.001), vec2(0.999))).rgb;
    refl += texture(u_refl, clamp(suv + off - vec2(0.0, px.y), vec2(0.001), vec2(0.999))).rgb;
    refl *= 0.25 * vec3(1.0, 0.8, 0.82);
    vec3 col = refl * mix(0.2, 1.0, Fr) * u_refl_gain;

    // sisli ışık huzmesinin sıvıdaki yansıması: dalgalar bu parlak bantta halka halka okunur
    vec3 R = reflect(rd, N);
    float beam = 0.0;
    if (R.y > 0.0) {
        for (int i = 0; i < 10; i++) {
            float sy = (float(i) + 0.5) / 10.0 * 3.0;              // yansıyan ışın boyunca 0..3 m yükseklik
            vec3 Q = P + R * (sy / R.y);
            vec3 dq = Q - u_spot_pos;
            float dist = length(dq);
            float cone = smoothstep(u_spot_cos.x, u_spot_cos.y, dot(dq / dist, u_spot_dir));
            vec4 c = u_light_vp * vec4(Q, 1.0);
            vec3 q = c.xyz / c.w * 0.5 + 0.5;
            float sh = texture(u_shadow, vec3(q.xy, q.z - 0.002));
            beam += cone * sh * 6.0 / (dist + 1.0) * (0.3 / R.y);
        }
        beam /= 10.0;
    }
    col += u_spot_col * beam * u_beam_refl * Fr * 1.8 * u_light_gain;

    // spot ışık: koyu kan birikintisinde sönük kırmızı havuz + dalga tepelerinde parlamalar
    vec3 L = normalize(u_spot_pos - P);
    float att = spotAtten(P, u_spot_pos, u_spot_dir, u_spot_cos.x, u_spot_cos.y) * shadowAt(P) * u_light_gain;
    vec3 H = normalize(L + V);
    float NdL = max(dot(N, L), 0.0);
    float Fh = fresnel(max(dot(H, V), 0.0), 0.05);
    col += u_spot_col * att * (vec3(0.012, 0.0004, 0.0007) * NdL
                               + ggx(max(dot(N, H), 0.0), 0.045) * Fh * NdL * 1.6
                               + ggx(max(dot(N, H), 0.0), 0.3) * Fh * NdL * 0.25 * vec3(1.0, 0.55, 0.55));

    // arkadaki uzak ışığın sıvı üstündeki parıltı yolu
    vec3 Hb = normalize(u_back_dir + V);
    float glint = ggx(max(dot(N, Hb), 0.0), 0.028) * fresnel(max(dot(Hb, V), 0.0), 0.05) * max(dot(N, u_back_dir), 0.0);
    col += u_back_col * glint * 0.22 * u_light_gain * smoothstep(9.0, 2.0, t) * smoothstep(2.2, 0.9, length(P.xz));

    // çizim görünümü: dalga tepeleri ince, açık renkli halka çizgileri
    float crest = smoothstep(0.55, 0.9, h0 / max(env0, 1e-6)) * smoothstep(0.00015, 0.0012, env0);
    float lit = smoothstep(0.0, 0.6, att) + 0.35;
    col += vec3(0.75, 0.2, 0.22) * crest * lit * u_ripple_ink * u_light_gain * smoothstep(2.5, 0.6, length(P.xz));

    frag = vec4(max(col, 0.0), 1.0);
    gbuf = vec4(0.0);
}
