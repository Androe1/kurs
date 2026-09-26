#version 330
// Yalnızca derinlik: spot ışığın gölge haritası ve ortam kapanması (AO) haritaları
uniform mat4 u_viewproj;
in vec3 in_pos;
void main() {
    gl_Position = u_viewproj * vec4(in_pos, 1.0);
}
