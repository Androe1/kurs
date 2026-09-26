#version 330
// Gül yaprağı: kadife dokulu, ıslak (kan) parlaklıklı, ince olduğu için ışığı arkasından geçiren yüzey.
#include "common.glsl"

uniform vec3 u_eye;
uniform float u_mirror;
uniform float u_time;

uniform vec3 u_spot_pos;
uniform vec3 u_spot_dir;
uniform vec2 u_spot_cos;         // dış, iç koni kosinüsü
uniform vec3 u_spot_col;
uniform sampler2DShadow u_shadow;
uniform mat4 u_light_vp;

uniform vec3 u_back_dir;         // arkadan vuran uzak ışığa doğru
uniform vec3 u_back_col;
uniform vec3 u_amb;
uniform float u_floor_glow;      // zemindeki kandan yansıyan kırmızı dolgu
uniform float u_light_gain;      // kararma / titreme
uniform float u_toon;            // boyama görünümü: yumuşak bantlı gölge, kenar fırça vurguları
uniform mat3 u_view3;            // G-buffer için görüş uzayı dönüşümü
uniform sampler2D u_petal_tex;       // referans çizimden döşenebilir fırça dokusu (yaprağın a, v koordinatlarıyla)
uniform float u_petal_on;            // 0: doku yüklenmedi
uniform float u_petal_amt;           // dokunun yaprak rengine etkisi
uniform float u_petal_scale;         // birim uzunluk başına doku tekrarı (çizimle aynı fırça ölçeği)
uniform vec3 u_pal[4];               // referans çizimin renk tonları (kırmızı = 1): gölge, orta, parlak, kenar vurgusu

in vec3 v_pos;
in vec3 v_nrm;
in vec2 v_uv;
in vec4 v_info;
in vec2 v_extra;
in float v_height;

layout(location = 0) out vec4 frag;
layout(location = 1) out vec4 gbuf;    // görüş uzayı normali + yaprak kimliği (mürekkep çizgileri için)

float shadowAt(vec3 p, vec3 n) {
    vec4 c = u_light_vp * vec4(p + n * 0.004, 1.0);
    vec3 q = c.xyz / c.w * 0.5 + 0.5;
    if (q.x < 0.0 || q.x > 1.0 || q.y < 0.0 || q.y > 1.0) return 1.0;
    float s = 0.0;
    vec2 texel = vec2(1.0 / 2048.0);
    for (int x = -1; x <= 1; x++)
        for (int y = -1; y <= 1; y++)
            s += texture(u_shadow, vec3(q.xy + vec2(x, y) * texel * 1.5, q.z - 0.0008));
    return s / 9.0;
}

// Sıvı yüzeyler için sahte ortam: karanlık, yukarıda spot ışığın parlak lekesi
vec3 envLight(vec3 P, vec3 r) {
    vec3 toSpot = normalize(u_spot_pos - P);
    float c = max(dot(r, toSpot), 0.0);
    float s = pow(c, 1500.0) * 60.0 + pow(c, 40.0) * 1.2 + pow(max(r.y, 0.0), 5.0) * 0.18;
    float b = pow(max(dot(r, u_back_dir), 0.0), 60.0) * 2.5 + pow(max(dot(r, u_back_dir), 0.0), 600.0) * 20.0;
    return u_spot_col * s * 0.12 + u_back_col * b;
}

void main() {
    if (u_mirror > 0.5 && v_height < -0.002) discard;     // sıvının altında kalan kısım yansımaz

    vec3 n = normalize(v_nrm);
    bool front = gl_FrontFacing;
    if (u_mirror > 0.5) front = !front;
    if (!front) n = -n;
    float ao = front ? v_info.z : v_info.w;
    ao = clamp(ao, 0.0, 1.0);

    // Işık hesabı gerçek dünyada yapılır; yansımada göz zeminin altına aynalanır.
    vec3 P = v_pos, E = u_eye;
    if (u_mirror > 0.5) { P.y = -P.y; n.y = -n.y; E.y = -E.y; }
    vec3 V = normalize(E - P);
    float a = v_uv.x, v = v_uv.y, k = v_info.x, id = v_info.y;
    float liquid = clamp(v_extra.x, 0.0, 1.0);
    float wet = clamp(v_extra.y, 0.0, 1.0);

    // ---- yaprak rengi (tonlar referans çizimden ölçülür): dipte bordo-siyah, uca doğru kan kırmızısı,
    // kenarlar saf kırmızı
    vec3 deep = 0.035 * u_pal[0];
    vec3 mid = 0.24 * u_pal[1];
    vec3 hi = 0.40 * u_pal[2];
    vec3 alb = mix(deep, mid, smoothstep(0.02, 0.5, v));
    float edge = smoothstep(0.7, 1.0, abs(a)) * smoothstep(0.3, 0.8, v) + smoothstep(0.82, 1.0, v / (1.0 - 0.3 * pow(abs(a), 2.2)));
    alb = mix(alb, hi, clamp(0.35 * edge + 0.25 * smoothstep(0.5, 1.0, v), 0.0, 1.0));
    // damarlar ve lekeler
    float vein = sin(a * 46.0 + 3.0 * vnoise(vec3(a * 3.0, v * 7.0, id * 3.7)));
    alb *= 0.96 + 0.04 * vein * smoothstep(0.05, 0.4, v);
    alb *= 0.88 + 0.24 * vnoise(vec3(a * 5.0 + id * 1.3, v * 6.0, id * 7.1));
    // çizimden alınan fırça dokusu: yaprağın gerçek boyuyla (dış yapraklar içtekilerin ~2 katı) ölçeklenir,
    // darbeler yaprak boyunca (dipten uca) uzanır; her yaprak dokunun başka bir yerinden başlar
    if (u_petal_on > 0.5) {
        vec2 size = vec2(0.43 + 0.5 * k, 0.30 + 0.30 * k);
        vec2 tuv = vec2(a * 0.5, v) * size * u_petal_scale + fract(vec2(0.37, 0.61) * id + 0.13);
        vec3 T = texture(u_petal_tex, tuv).rgb;
        alb *= max(mix(vec3(1.0), T, u_petal_amt), vec3(0.15));
    }
    // iç yüz (merkeze bakan) biraz daha koyu ve doygun
    alb *= front ? 1.0 : 0.85;

    // ---- sıvı malzemesi (damladan yeni biçimlenen yapraklar): koyu, çok parlak kan
    vec3 blood = vec3(0.06, 0.0004, 0.003);
    alb = mix(alb, blood, liquid);
    float rough = mix(0.5, 0.07, liquid);

    // ---- spot ışık (gölgeli)
    vec3 L = normalize(u_spot_pos - P);
    float att = spotAtten(P, u_spot_pos, u_spot_dir, u_spot_cos.x, u_spot_cos.y);
    float sh = shadowAt(P, n);
    // arka yüzden gelen ışık: ince yaprağın içinden geçer (kırmızı parlama)
    float shBack = shadowAt(P, -n);
    vec3 lightC = u_spot_col * att * u_light_gain;

    float NdL = dot(n, L);
    float wrap = max((NdL + 0.35) / 1.35, 0.0);
    // boyama: ışık yumuşak kenarlı üç banda ayrılır (resimdeki gibi düz boya alanları)
    float wb = wrap * 3.0;
    float band = (floor(wb) + smoothstep(0.3, 0.7, fract(wb))) / 3.0;
    wrap = mix(wrap, band, u_toon);
    vec3 diff = alb * wrap * sh;
    vec3 trans = 0.42 * u_pal[2] * max(-NdL, 0.0) * shBack * (1.0 - 0.8 * liquid) * mix(0.6, 1.0, v);

    vec3 H = normalize(L + V);
    float NdH = max(dot(n, H), 0.0);
    float NdV = max(dot(n, V), 1e-3);
    float F = fresnel(max(dot(H, V), 0.0), 0.03);
    // kadife: geniş, sönük parlama; ıslak kaplama: lekeler hâlinde küçük, keskin parlamalar
    float velvet = ggx(NdH, 0.6) * F * 0.6;
    float wetMask = smoothstep(0.35, 0.75, vnoise(vec3(a * 3.0 + id * 2.1, v * 4.0, id)) + 0.3 * wet);
    float coat = ggx(NdH, mix(0.16, 0.06, liquid)) * F * mix(wet * wetMask, 3.0, liquid);
    float spec = (velvet * (1.0 - liquid) + coat) * max(NdL, 0.0) * sh;
    // kadife parlaması (yaprak kenarlarında, bakış açısına göre)
    float sheen = pow(1.0 - NdV, 4.0) * 0.5 * (1.0 - liquid) * max(wrap, 0.0) * sh;

    // boyanmış parlama: speküler keskin kenarlı açık lekelere dönüşür
    spec = mix(spec, smoothstep(0.25, 0.45, spec) * 1.4 + spec * 0.3, u_toon);
    vec3 col = lightC * (diff + trans + spec + sheen * 0.5 * u_pal[3]);
    // yaprak kenarlarında açık kırmızı fırça vurgusu (referans çizimdeki gibi)
    float rimPaint = smoothstep(0.78, 0.98, abs(a)) * smoothstep(0.3, 0.85, v) + smoothstep(0.86, 1.0, v / (1.0 - 0.3 * pow(abs(a), 2.2)));
    col += lightC * 0.55 * u_pal[3] * clamp(rimPaint, 0.0, 1.0) * max(wrap, 0.15) * sh * u_toon * (1.0 - liquid) * 0.8;

    // ---- arkadan vuran uzak ışık: kenar ışığı
    float NdB = dot(n, u_back_dir);
    vec3 back = u_back_col * u_light_gain * (alb * max((NdB + 0.2) / 1.2, 0.0) * 0.6
                   + vec3(0.5, 0.04, 0.03) * max(-NdB, 0.0) * 0.5
                   + ggx(max(dot(n, normalize(u_back_dir + V)), 0.0), rough) * 0.05 * max(NdB, 0.0));
    col += back * ao;

    // ---- ortam (kameradan gelen çok sönük kırmızı dolgu) + zeminden yansıyan kırmızı + sıvı yansıması
    col += alb * u_amb * ao * u_light_gain * (0.4 + 0.6 * max(dot(n, V), 0.0)) * 3.0;
    col += alb * vec3(0.9, 0.05, 0.05) * max(-n.y, 0.0) * u_floor_glow * ao * u_light_gain;
    vec3 R = reflect(-V, n);
    col += envLight(P, R) * fresnel(NdV, 0.04) * mix(0.25 * wet, 1.0, liquid) * mix(0.4, 1.0, ao) * u_light_gain;

    // arka kontur ışığı: gülün silueti karanlıktan ayrılsın
    float rimF = pow(1.0 - NdV, 3.0) * smoothstep(-0.25, 0.55, dot(n, u_back_dir));
    col += u_back_col * 0.9 * u_pal[3] * rimF * 0.9 * mix(0.4, 1.0, ao) * u_light_gain;

    col *= mix(0.25, 1.0, ao);
    frag = vec4(max(col, 0.0), 1.0);
    gbuf = vec4(normalize(u_view3 * n), (id + 1.0) / 32.0);
}
