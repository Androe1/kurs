#version 330
// Son işlem: sarsıntı bulanıklığı, renk kayması, bloom, film ton eşlemesi, korku renk ayarı,
// vinyet, film greni, titreşim.
#include "common.glsl"

uniform sampler2D u_comp;
uniform sampler2D u_bloom;
uniform vec2 u_res;
uniform float u_time;
uniform float u_exposure;
uniform float u_bloom_amt;
uniform float u_ca;              // renk kayması (kromatik aberasyon)
uniform vec2 u_blur;             // sarsıntı hareket bulanıklığı (uv)
uniform float u_grain;
uniform float u_vignette;
uniform float u_flash;           // kırmızı parlama (vuruş anları)
uniform float u_fade;            // 0 siyah .. 1 tam görüntü
uniform float u_bars;            // sinema şeritleri (0..1)

in vec2 v_uv;
out vec4 frag;

vec3 sampleCA(vec2 uv) {
    vec2 c = uv - 0.5;
    float k = u_ca * dot(c, c);
    return vec3(texture(u_comp, uv - c * k).r, texture(u_comp, uv).g, texture(u_comp, uv + c * k * 1.4).b);
}

// ACES (Stephen Hill fit)
vec3 aces(vec3 color) {
    const mat3 m1 = mat3(0.59719, 0.07600, 0.02840, 0.35458, 0.90834, 0.13383, 0.04823, 0.01566, 0.83777);
    const mat3 m2 = mat3(1.60475, -0.10208, -0.00327, -0.53108, 1.10813, -0.07276, -0.07367, -0.00605, 1.07602);
    vec3 v = m1 * color;
    vec3 a = v * (v + 0.0245786) - 0.000090537;
    vec3 b = v * (0.983729 * v + 0.4329510) + 0.238081;
    return clamp(m2 * (a / b), 0.0, 1.0);
}

void main() {
    vec2 uv = v_uv;
    vec3 col = vec3(0.0);
    const int N = 9;
    for (int i = 0; i < N; i++) {
        float f = float(i) / float(N - 1) - 0.5;
        col += sampleCA(uv + u_blur * f);
    }
    col /= float(N);
    col += texture(u_bloom, uv).rgb * u_bloom_amt;
    col += vec3(0.5, 0.02, 0.02) * u_flash;
    col *= u_exposure;

    // tonu koruyan eşleme ile ACES karışımı: parlak kırmızılar turuncuya kaymaz
    float mx = max(col.r, max(col.g, col.b));
    float tm = (mx * (2.51 * mx + 0.03)) / (mx * (2.43 * mx + 0.59) + 0.14);
    vec3 hp = col * (clamp(tm, 0.0, 1.0) / max(mx, 1e-5));
    col = mix(hp, aces(col), 0.3);
    // korku ayarı: siyahları ez, kırmızıyı koru, yüksek ışıkları hafif soğut
    float l = dot(col, vec3(0.2126, 0.7152, 0.0722));
    col = mix(vec3(l), col, 1.05);
    col = pow(col, vec3(1.08, 1.12, 1.1));
    col = col * vec3(1.0, 0.97, 0.98);

    // vinyet
    vec2 c = uv - 0.5;
    c.x *= u_res.x / u_res.y;
    float vig = smoothstep(1.05, 0.25, length(c) * (1.0 + u_vignette));
    col *= mix(1.0, vig, 0.85);

    col *= u_fade;
    // sinema şeritleri
    float bar = 0.5 * (1.0 - (u_res.x / 2.39) / u_res.y) * u_bars;
    if (uv.y < bar || uv.y > 1.0 - bar) col = vec3(0.0);

    // sRGB
    col = mix(col * 12.92, 1.055 * pow(col, vec3(1.0 / 2.4)) - 0.055, step(0.0031308, col));
    // film greni + titreşim (dithering)
    // film greni: ~1.5 piksellik taneler, saniyede 30 kez yenilenir (gerçek film gibi; iyi sıkıştırılır)
    vec2 gp = floor(gl_FragCoord.xy / 1.5);
    float gt = floor(u_time * 30.0);
    float g = hash12(gp + fract(gt * 0.1337) * 1000.0) - 0.5;
    float g2 = hash12(gp * 1.31 + fract(gt * 0.0777) * 500.0) - 0.5;
    col += (g + g2) * u_grain * (0.35 + 0.65 * sqrt(max(col, 0.0)));
    col += (hash12(gl_FragCoord.xy + 17.0) - 0.5) / 255.0;
    frag = vec4(clamp(col, 0.0, 1.0), 1.0);
}
