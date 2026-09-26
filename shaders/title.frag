#version 330
// "COMING SOON": ortadan dışa doğru yanarak belirir, kızıl hale, anamorfik ışık çizgisi, titreşim ve glitch.
#include "common.glsl"

uniform sampler2D u_text;       // keskin metin maskesi
uniform sampler2D u_text_blur;  // bulanık metin maskesi (hale)
uniform float u_time;
uniform float u_reveal;
uniform float u_bright;
uniform float u_glitch;
uniform float u_streak;

in vec2 v_uv;
out vec4 frag;

void main() {
    vec2 uv = v_uv;
    float fr = floor(u_time * 24.0);
    float band = floor(uv.y * 36.0);
    float gk = step(0.8, hash11(band * 3.1 + fr * 7.0)) * u_glitch;
    uv.x += (hash11(band * 1.7 + fr) - 0.5) * 0.035 * gk;

    float off = 0.0012 + 0.006 * gk;
    float m = texture(u_text, uv).r;
    float mr = texture(u_text, uv + vec2(off, 0.0)).r;
    float mb = texture(u_text, uv - vec2(off, 0.0)).r;
    float blur = texture(u_text_blur, v_uv).r;

    // ortadan dışa yanarak belirme
    float n = fbm2(v_uv * vec2(22.0, 12.0)) * 0.5 + abs(v_uv.x - 0.5) * 1.5;
    float rv = u_reveal * 1.35;
    float rev = smoothstep(n - 0.05, n + 0.01, rv);
    float burn = (smoothstep(n - 0.07, n - 0.01, rv) - smoothstep(n - 0.01, n + 0.03, rv));

    vec3 core = vec3(0.93, 0.86, 0.82) * vec3(mr, m, mb) * rev;
    vec3 halo = vec3(0.55, 0.012, 0.015) * blur * rev;
    vec3 ember = vec3(1.0, 0.22, 0.04) * burn * max(m, 0.4 * blur) * 3.0;
    float sy = abs(v_uv.y - 0.5);
    vec3 streak = vec3(0.9, 0.06, 0.03) * exp(-sy / 0.0035) * exp(-abs(v_uv.x - 0.5) / 0.3) * u_streak;
    frag = vec4((core * 1.3 + halo * 1.4 + ember) * u_bright + streak, 1.0);
}
