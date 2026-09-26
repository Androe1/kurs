#version 330
// Işık huzmesinde süzülen toz: her parçacık huzmenin içindeyse ve gölgede değilse parlar.
#include "common.glsl"

uniform mat4 u_viewproj;
uniform float u_time;
uniform vec3 u_spot_pos;
uniform vec3 u_spot_dir;
uniform vec2 u_spot_cos;
uniform vec3 u_spot_col;
uniform sampler2DShadow u_shadow;
uniform mat4 u_light_vp;
uniform float u_light_gain;
uniform float u_px;             // 1 m uzaklıkta parçacık boyu (piksel)
uniform vec3 u_center;
uniform vec3 u_extent;

in vec4 in_seed;                // rastgele konum (0..1)^3 + faz
out vec3 v_col;

void main() {
    vec3 s = in_seed.xyz;
    float ph = in_seed.w;
    // yavaşça aşağı süzülen, kıvrılan toz
    vec3 p = u_center + (s - 0.5) * u_extent;
    p.y = u_center.y - 0.5 * u_extent.y + mod(s.y * u_extent.y - u_time * (0.018 + 0.02 * ph), u_extent.y);
    p.x += 0.05 * sin(u_time * (0.3 + 0.4 * ph) + ph * 40.0);
    p.z += 0.05 * cos(u_time * (0.25 + 0.3 * ph) + ph * 17.0);

    vec3 d = p - u_spot_pos;
    float dist = length(d);
    float cone = smoothstep(u_spot_cos.x, u_spot_cos.y, dot(d / dist, u_spot_dir));
    vec4 c = u_light_vp * vec4(p, 1.0);
    vec3 q = c.xyz / c.w * 0.5 + 0.5;
    float sh = texture(u_shadow, vec3(q.xy, q.z - 0.002));
    float twinkle = 0.55 + 0.45 * sin(u_time * (2.0 + 3.0 * ph) + ph * 60.0);
    v_col = u_spot_col * cone * sh * twinkle * (6.0 / (dist + 1.0)) * 0.9 * u_light_gain;

    gl_Position = u_viewproj * vec4(p, 1.0);
    gl_PointSize = clamp(u_px * (0.6 + 0.8 * ph) / gl_Position.w, 1.0, 6.0);
}
