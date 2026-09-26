#version 330
// Karanlıkta beliren ve kapakları açılan iki şeytani göz: kullanıcının çizimi doku olarak kullanılır.
// Önce gözler kapalıdır: yalnızca kaş / diken darbeleri ve kirpikli kapalı kapak çizgisi görünür.
// Sonra üst kapak hızla, alt kapak biraz gecikmeyle açılır; göz akı ve göz bebekleri ortaya çıkar,
// kapak konturları (göz akına yakın darbeler) belirir. Çizgiler saniyede 12 kez hafifçe "kaynar".
#include "common.glsl"

uniform sampler2D u_img;        // çizim (düz alfa, sRGB)
uniform vec2 u_img_size;        // çizimin piksel boyutu
uniform vec2 u_center;          // çizimde ekran ortasına gelen nokta (piksel)
uniform float u_ref_per_unit;   // ekran yüksekliği birimi başına çizim pikseli
uniform vec4 u_pupils;          // iki göz bebeğinin çizimdeki merkezi (x0, y0, x1, y1)
uniform float u_pupil_r;        // çizimdeki göz bebeği yarıçapı (piksel)
uniform sampler2D u_aux;        // R: göz akına yakın mürekkep (kapak konturu), G: göz akı maskesi
uniform sampler2D u_lids;       // her sütun: göz akı üstü, altı, kapalı kapak çizgisi (satır), geçerlilik
uniform float u_lid_up;         // üst kapak açıklığı (0 kapalı .. 1 açık)
uniform float u_lid_lo;         // alt kapak açıklığı
uniform float u_show;           // kapalı gözlerin karanlıktan belirmesi
uniform float u_near_vis;       // kapak konturlarının görünürlüğü

uniform vec2 u_res;
uniform float u_time;
uniform float u_open;           // dikey açıklık (0 kapalı, 1 tam açık; >1 aşma)
uniform float u_pupil;          // göz bebeği ölçeği (1 = çizimdeki boy)
uniform vec2 u_look;            // göz bebeği kayması (çizim pikseli)
uniform vec2 u_shake;           // ekran kayması (ekran yüksekliği birimi)
uniform float u_rot;
uniform float u_zoom;
uniform float u_glow;
uniform float u_reveal;         // darbelerin gözden dışa belirme yarıçapı
uniform float u_squint;

in vec2 v_uv;
out vec4 frag;

vec3 toLinear(vec3 c) { return pow(c, vec3(2.2)); }

void main() {
    float boil = floor(u_time * 12.0);
    vec2 p = (gl_FragCoord.xy - 0.5 * u_res) / u_res.y;
    p -= u_shake;
    float cr = cos(u_rot), sr = sin(u_rot);
    p = mat2(cr, sr, -sr, cr) * p / u_zoom;

    // ekran -> çizim pikseli; açılışta kısa bir dikey esneme (u_open), sonda kısılma
    vec2 X = vec2(u_center.x + p.x * u_ref_per_unit, u_center.y - p.y * u_ref_per_unit);
    float open = max(u_open * (1.0 - 0.12 * u_squint), 0.015);
    X = vec2(X.x, u_center.y + (X.y - u_center.y) / open);
    // el çizimi titreşimi
    vec2 wob = (vec2(vnoise2(X * 0.012 + boil * 1.3), vnoise2(X * 0.012 + 7.7 + boil * 2.1)) - 0.5) * 2.4;
    vec2 uv = (X + wob) / u_img_size;

    vec4 c = texture(u_img, vec2(uv.x, 1.0 - uv.y));
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) c = vec4(0.0);
    float lum = dot(c.rgb, vec3(0.3333));
    float wht = smoothstep(0.55, 0.85, lum);
    float sclera = c.a * wht;
    float ink = c.a * (1.0 - wht);

    // kapaklar: her sütunda göz akının üst/alt sınırı ile kapalı kapak çizgisi arasında
    vec4 lid = texture(u_lids, vec2((X.x + 0.5) / u_img_size.x, 0.5));
    float valid = lid.w * step(0.0, X.x) * step(X.x, u_img_size.x);
    float squ = 0.35 * u_squint;
    float yU = mix(lid.z, lid.x, clamp(u_lid_up - squ, 0.0, 1.2));
    float yL = mix(lid.z, lid.y, clamp(u_lid_lo - 0.4 * squ, 0.0, 1.2));
    float aperture = valid * smoothstep(yU - 1.2, yU + 1.2, X.y) * (1.0 - smoothstep(yL - 1.2, yL + 1.2, X.y));
    sclera *= aperture;

    // darbeler: uzaktakiler (kaş, dikenler) gözden dışa sürünerek belirir; göz akına yakın olanlar
    // (kapak konturu) kapaklar açılırken ortaya çıkar
    vec4 ax = texture(u_aux, vec2(uv.x, 1.0 - uv.y));
    int side = (X.x < u_center.x) ? 0 : 1;
    vec2 eyeC = (side == 0) ? u_pupils.xy : u_pupils.zw;
    float d = length((X - eyeC) / vec2(330.0, 210.0));
    float far = ink * (1.0 - ax.r) * (1.0 - smoothstep(u_reveal - 0.25, u_reveal, d));
    float nearInk = ink * ax.r * u_near_vis;
    ink = max(far, nearInk);
    // kapak çizgileri (kapalıyken birleşip kalın, kirpikli bir çizgi olur); açılınca kaybolur
    float lidVis = valid * u_show * (1.0 - smoothstep(0.7, 1.0, min(u_lid_up - squ, u_lid_lo)));
    float jit = (vnoise2(vec2(X.x * 0.05, boil)) - 0.5) * 2.0;
    float wU = 6.0 + 6.0 * (1.0 - clamp(u_lid_up, 0.0, 1.0));
    float lineU = 1.0 - smoothstep(wU * 0.5, wU * 0.5 + 1.6, abs(X.y - yU + jit));
    float lineL = 1.0 - smoothstep(2.2, 3.8, abs(X.y - yL + jit * 0.5));
    // kapalı gözün aşağı bakan kirpikleri
    float cell = floor(X.x / 21.0);
    float fx = (fract(X.x / 21.0) - 0.5) * 21.0 + (hash11(cell * 3.1 + float(side)) - 0.5) * 8.0;
    float down = X.y - yL;
    float lashLen = 9.0 + 9.0 * hash11(cell * 1.7 + 4.0);
    float slope = (side == 0) ? -0.5 : 0.5;
    float lash = (1.0 - smoothstep(1.2, 2.6, abs(fx - down * slope))) * step(0.0, down) * (1.0 - smoothstep(lashLen * 0.6, lashLen, down));
    lash *= 1.0 - smoothstep(0.05, 0.35, u_lid_up);
    float lidInk = clamp(max(lineU, lineL * 0.85) + lash * 0.9, 0.0, 1.0) * lidVis;
    // kuru fırça greni
    float grain = vnoise2(X * 0.9 + boil * 3.0);
    ink *= smoothstep(0.1, 0.45, ink + (grain - 0.5) * 0.35);

    vec3 inkCol = toLinear(c.rgb) * 3.2 + vec3(0.02, 0.0, 0.0);
    vec3 lidCol = vec3(0.26, 0.01, 0.014);
    vec3 white = vec3(0.96, 0.93, 0.9) * u_glow;
    vec3 col = vec3(0.0);
    col = mix(col, white, sclera);
    col = mix(col, inkCol, clamp(ink, 0.0, 1.0));

    // göz bebeği: simsiyah iç, koyu kızıl kenar
    vec2 pc = eyeC + u_look;
    float r = length(X - pc);
    float R = u_pupil_r * u_pupil;
    float disk = 1.0 - smoothstep(R - 1.2, R + 0.8, r);
    vec3 pupilCol = mix(vec3(0.0), vec3(0.12, 0.004, 0.006), smoothstep(R * 0.45, R * 0.85, r));
    col = mix(col, pupilCol, disk * sclera * aperture);
    col = mix(col, lidCol, lidInk);

    // arkada çok sönük kızıl hale
    float halo = exp(-length((X - eyeC) / vec2(420.0, 260.0)) * 2.0);
    col += vec3(0.05, 0.0015, 0.003) * halo * u_show * (0.4 + 0.6 * clamp(u_lid_up, 0.0, 1.0)) * (1.0 - sclera);

    frag = vec4(col, 1.0);
}
