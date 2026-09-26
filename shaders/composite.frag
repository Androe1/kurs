#version 330
// Birleştirme ve "çizim" görünümü: ana sahne + ışık huzmesi, Kuwahara boya filtresi,
// el çizimi gibi titreyen mürekkep konturları (derinlik, normal ve yaprak kimliğinden), fırça/kâğıt dokusu.
#include "common.glsl"

uniform sampler2D u_hdr;
uniform sampler2D u_vol;
uniform sampler2D u_depth;
uniform sampler2D u_gbuf;
uniform vec2 u_vol_texel;
uniform vec2 u_res;
uniform float u_near;
uniform float u_far;
uniform float u_time;
uniform float u_ink;            // kontur gücü
uniform float u_paint;          // boya filtresi ve fırça dokusu

in vec2 v_uv;
out vec4 frag;

float lin(float z) {
    z = z * 2.0 - 1.0;
    return 2.0 * u_near * u_far / (u_far + u_near - z * (u_far - u_near));
}

// Genelleştirilmiş Kuwahara (8 yumuşak dilim, Gauss ağırlıklı): her dilimin ortalaması, dilim ne kadar
// düzgünse (varyansı azsa) o kadar ağır basar -> kenarları koruyan, blok yapmayan boya lekeleri.
// Örnek konumları ve dilim ağırlıkları CPU'da bir kez hesaplanır.
#define KN 37
uniform vec2 u_koff[KN];
uniform vec4 u_kw0[KN];          // dilim 0-3 ağırlıkları
uniform vec4 u_kw1[KN];          // dilim 4-7 ağırlıkları

vec3 kuwahara(vec2 uv) {
    vec2 px = 1.0 / u_res;
    vec3 m[8], sq[8];
    float wsum[8];
    for (int k = 0; k < 8; k++) { m[k] = vec3(0.0); sq[k] = vec3(0.0); wsum[k] = 0.0; }
    for (int i = 0; i < KN; i++) {
        vec3 c = texture(u_hdr, uv + u_koff[i] * px).rgb;
        vec3 c2 = c * c;
        vec4 a = u_kw0[i], b = u_kw1[i];
        m[0] += c * a.x; sq[0] += c2 * a.x; wsum[0] += a.x;
        m[1] += c * a.y; sq[1] += c2 * a.y; wsum[1] += a.y;
        m[2] += c * a.z; sq[2] += c2 * a.z; wsum[2] += a.z;
        m[3] += c * a.w; sq[3] += c2 * a.w; wsum[3] += a.w;
        m[4] += c * b.x; sq[4] += c2 * b.x; wsum[4] += b.x;
        m[5] += c * b.y; sq[5] += c2 * b.y; wsum[5] += b.y;
        m[6] += c * b.z; sq[6] += c2 * b.z; wsum[6] += b.z;
        m[7] += c * b.w; sq[7] += c2 * b.w; wsum[7] += b.w;
    }
    vec3 acc = vec3(0.0);
    float wt = 0.0;
    for (int k = 0; k < 8; k++) {
        vec3 mk = m[k] / wsum[k];
        vec3 vk = abs(sq[k] / wsum[k] - mk * mk);
        float sigma = sqrt(vk.r + vk.g + vk.b);
        float w = 1.0 / pow(1.0 + 18.0 * sigma, 6.0);
        acc += mk * w;
        wt += w;
    }
    return acc / wt;
}

float inkEdge(vec2 uv) {
    vec2 px = 1.0 / u_res;
    float boil = floor(u_time * 12.0);                      // çizgiler saniyede 12 kez "kaynar" (el çizimi)
    vec2 w = (vec2(vnoise2(uv * vec2(70.0, 40.0) + boil * 1.7),
                   vnoise2(uv * vec2(70.0, 40.0) + 13.1 + boil * 2.3)) - 0.5) * 2.2 * px;
    float rad = 0.9 + 1.4 * vnoise2(uv * vec2(26.0, 15.0) + boil * 0.37);
    vec2 c = uv + w;
    vec4 g0 = texture(u_gbuf, c);
    float d0 = lin(texture(u_depth, c).r);
    float e = 0.0;
    for (int k = 0; k < 8; k++) {
        float a = float(k) * PI * 0.25;
        vec2 o = vec2(cos(a), sin(a)) * rad * px;
        vec4 g = texture(u_gbuf, c + o);
        float d = lin(texture(u_depth, c + o).r);
        float obj = step(0.01, max(g.w, g0.w));
        float de = smoothstep(0.012, 0.045, abs(d - d0) / min(d, d0)) * obj;
        float ide = (abs(g.w - g0.w) > 0.012) ? 1.0 : 0.0;
        float ne = 0.0;
        if (g.w > 0.01 && g0.w > 0.01) ne = smoothstep(0.35, 0.8, 1.0 - dot(normalize(g.xyz + 1e-5), normalize(g0.xyz + 1e-5)));
        e = max(e, max(de, max(ide, ne)));
    }
    // çizgi boyunca kesik kesik, fırça basıncı gibi değişen koyuluk
    float press = 0.55 + 0.45 * vnoise2(uv * vec2(140.0, 80.0) + boil * 3.1);
    return e * press;
}

void main() {
    vec3 sharp = texture(u_hdr, v_uv).rgb;
    vec3 col = sharp;
    if (u_paint > 0.0) {
        vec3 k = kuwahara(v_uv);
        col = mix(sharp, k, u_paint);
        // fırça ve kâğıt dokusu: yalnızca aydınlık alanları hafifçe böler
        vec2 fc = gl_FragCoord.xy;
        float a = 0.6;
        mat2 rot = mat2(cos(a), -sin(a), sin(a), cos(a));
        float streak = fbm2(rot * fc * vec2(0.012, 0.16));
        float paper = vnoise2(fc * 0.45) * 0.6 + vnoise2(fc * 0.13) * 0.4;
        col *= mix(1.0, 0.8 + 0.32 * streak + 0.1 * (paper - 0.5), u_paint);
    }
    // mürekkep konturları
    float ink = inkEdge(v_uv) * u_ink;
    col = mix(col, vec3(0.008, 0.0, 0.002), clamp(ink * 0.9, 0.0, 1.0));

    // yarım çözünürlüklü ışık huzmesi (4 komşuyla yumuşatılır)
    vec3 v = texture(u_vol, v_uv).rgb * 0.4;
    v += texture(u_vol, v_uv + vec2(1.0, 0.0) * u_vol_texel).rgb * 0.15;
    v += texture(u_vol, v_uv - vec2(1.0, 0.0) * u_vol_texel).rgb * 0.15;
    v += texture(u_vol, v_uv + vec2(0.0, 1.0) * u_vol_texel).rgb * 0.15;
    v += texture(u_vol, v_uv - vec2(0.0, 1.0) * u_vol_texel).rgb * 0.15;
    frag = vec4(col + v, 1.0);
}
