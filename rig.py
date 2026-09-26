"""Roblox R6 karakterleri için basit 3B iskelet ve OpenGL render'ı.

Roblox Studio'dan "Export Selection" ile alınan .obj dosyası okunur. R6
gövdesi 6 parçadır (2 bacak, 2 kol, gövde, kafa); aksesuarlar (Handle
grupları) en yakın parçaya bağlanır. Her parça kendi ekleminden döndürülür,
böylece koşma, zıplama gibi pozlar verilebilir.

Render, ekran kartı gerektirmeyen OpenGL (moderngl + EGL) ile yapılır ve
şeffaf arka planlı RGBA görüntü döndürür.
"""
import math
from pathlib import Path

import moderngl
import numpy as np
import skia

PARTS = ("right_leg", "left_leg", "right_arm", "left_arm", "torso", "head")


def load_obj(path):
    """.obj dosyasını grup grup (konum, uv, normal) üçgen dizilerine çevirir."""
    v, vt, vn, groups, cur = [], [], [], {}, None
    for line in open(path):
        p = line.split()
        if not p:
            continue
        if p[0] == "v":
            v.append([float(x) for x in p[1:4]])
        elif p[0] == "vt":
            vt.append([float(x) for x in p[1:3]])
        elif p[0] == "vn":
            vn.append([float(x) for x in p[1:4]])
        elif p[0] == "g":
            cur = p[1]
            groups.setdefault(cur, [])
        elif p[0] == "f":
            corners = [[int(x) if x else 0 for x in q.split("/")] for q in p[1:]]
            for k in range(1, len(corners) - 1):              # çokgenleri üçgenle
                groups[cur].extend([corners[0], corners[k], corners[k + 1]])
    v, vt, vn = np.array(v), np.array(vt), np.array(vn)
    out = {}
    for name, idx in groups.items():
        idx = np.array(idx) - 1
        out[name] = (v[idx[:, 0]], vt[idx[:, 1]], vn[idx[:, 2]])
    return out


class R6Character:
    """Parçalara ayrılmış, eklemlerinden döndürülebilen R6 karakteri."""

    def __init__(self, folder):
        folder = Path(folder)
        obj = next(folder.glob("*.obj"))
        groups = load_obj(obj)
        body = [g for g in groups if not g.startswith("Handle")]
        body.sort(key=lambda g: int("".join(ch for ch in g if ch.isdigit()) or 0))
        # Studio'nun dışa aktarma sırası: 1-2 bacak, 3-4 kol, 5 gövde, 6 kafa
        named = dict(zip(PARTS, body))
        # Yere ve karakterin merkezine göre koordinatları sıfırla; yüz -Z'ye bakar
        torso = groups[named["torso"]][0]
        center = np.array([(torso[:, 0].min() + torso[:, 0].max()) / 2, 0.0,
                           (torso[:, 2].min() + torso[:, 2].max()) / 2])
        self.meshes = {}
        for part, group in named.items():
            pos, uv, nrm = groups[group]
            self.meshes[part] = [(pos - center, uv, nrm)]
        # Aksesuarlar: merkezine en yakın parçaya bağlanır (saç/şapka kafaya, sırt eşyası gövdeye)
        for name, (pos, uv, nrm) in groups.items():
            if not name.startswith("Handle"):
                continue
            mid = (pos.min(0) + pos.max(0)) / 2 - center
            part = min(("head", "torso"), key=lambda p: np.linalg.norm(
                mid - self._mid(self.meshes[p])))
            self.meshes[part].append((pos - center, uv, nrm))
        t = self._bounds("torso")
        self.pivots = {
            "torso": np.array([0, t[0][1], 0]),          # kalça hizası: eğilince bacaklar yerinde kalır
            "head": np.array([0, t[1][1], 0]),
        }
        for side in ("right", "left"):
            a, l = self._bounds(f"{side}_arm"), self._bounds(f"{side}_leg")
            self.pivots[f"{side}_arm"] = np.array([(a[0][0] + a[1][0]) / 2, a[1][1] - 0.5, (a[0][2] + a[1][2]) / 2])
            self.pivots[f"{side}_leg"] = np.array([(l[0][0] + l[1][0]) / 2, l[1][1], (l[0][2] + l[1][2]) / 2])
        self.texture_path = folder / "Handle1_diff.png"
        self.height = max(np.vstack([m[0] for m in self.meshes[p]])[:, 1].max() for p in self.meshes)

    @staticmethod
    def _mid(meshes):
        pos = np.vstack([m[0] for m in meshes])
        return (pos.min(0) + pos.max(0)) / 2

    def _bounds(self, part):
        pos = self.meshes[part][0][0]          # yalnızca vücut parçası (aksesuarlar hariç)
        return pos.min(0), pos.max(0)


def rot(axis, angle):
    c, s = math.cos(angle), math.sin(angle)
    if axis == "x":
        return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(x=0.0, y=0.0, z=0.0):
    return rot("y", y) @ rot("x", x) @ rot("z", z)


_VERT = """
#version 330
uniform mat4 mvp;
uniform mat3 nmat;
in vec3 in_pos;
in vec2 in_uv;
in vec3 in_n;
out vec2 uv;
out vec3 n;
void main() {
    gl_Position = mvp * vec4(in_pos, 1.0);
    uv = in_uv;
    n = normalize(nmat * in_n);
}
"""

_FRAG = """
#version 330
uniform sampler2D tex;
uniform vec3 light;
uniform vec3 rim_dir;
uniform float rim;
in vec2 uv;
in vec3 n;
out vec4 color;
void main() {
    vec4 t = texture(tex, vec2(uv.x, 1.0 - uv.y));
    if (t.a < 0.4) discard;
    float d = max(dot(normalize(n), light), 0.0);
    vec3 c = t.rgb * (0.55 + 0.6 * d);
    c += rim * pow(max(dot(normalize(n), rim_dir), 0.0), 3.0);
    color = vec4(min(c, 1.0), 1.0);
}
"""


class Renderer:
    """Karakterleri şeffaf arka plana çizen OpenGL render'ı (ekran kartı gerekmez)."""

    def __init__(self, width, height, samples=4):
        self.ctx = moderngl.create_standalone_context(backend="egl")
        self.w, self.h = width, height
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.renderbuffer((width, height), 4, samples=samples)],
            depth_attachment=self.ctx.depth_renderbuffer((width, height), samples=samples))
        self.resolve = self.ctx.simple_framebuffer((width, height), components=4)
        self.prog = self.ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.cache = {}

    @staticmethod
    def _split(value):
        if isinstance(value, tuple):
            return value[0], np.asarray(value[1], float)
        return value, np.zeros(3)

    def _upload(self, character):
        if id(character) in self.cache:
            return self.cache[id(character)]
        img = skia.Image.open(str(character.texture_path)).toarray(colorType=skia.kRGBA_8888_ColorType)
        tex = self.ctx.texture((img.shape[1], img.shape[0]), 4, np.ascontiguousarray(img).tobytes())
        tex.build_mipmaps()
        tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        parts = {}
        for part, meshes in character.meshes.items():
            data = np.hstack([np.vstack([m[k] for m in meshes]) for k in range(3)]).astype("f4")
            vbo = self.ctx.buffer(data.tobytes())
            parts[part] = self.ctx.vertex_array(self.prog, [(vbo, "3f 2f 3f", "in_pos", "in_uv", "in_n")])
        self.cache[id(character)] = (tex, parts)
        return tex, parts

    def render(self, character, pose, root_rot, root_pos, view, fov=30.0, rim=0.35, squash=None):
        """Tek karakteri çizer; (h, w, 4) uint8 RGBA döndürür.

        pose: {parça: 3x3 dönüş} ya da {parça: (3x3 dönüş, kaydırma)}. Kaydırma
        gövde uzayında stud cinsindendir: Roblox'ta Motor6D'nin konumunu key'lemek
        gibi, kol omuzdan ayrılabilir / gövdeye girebilir, bacak gövdeye çekilebilir.
        root_rot/root_pos: karakterin dünyadaki duruşu; squash: gövde merkezinden
        (sx, sy, sz) ölçek (squash & stretch). view: 4x4 kamera matrisi.
        """
        tex, parts = self._upload(character)
        aspect = self.w / self.h
        f = 1 / math.tan(math.radians(fov) / 2)
        near, far = 0.1, 200.0
        proj = np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                         [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)],
                         [0, 0, -1, 0]])
        self.fbo.use()
        self.ctx.clear(0, 0, 0, 0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        tex.use(0)
        self.prog["tex"].value = 0
        light = np.array([-0.4, 0.7, 0.6])
        self.prog["light"].value = tuple(light / np.linalg.norm(light))
        rim_dir = np.array([0.6, 0.3, -0.7])
        self.prog["rim_dir"].value = tuple(rim_dir / np.linalg.norm(rim_dir))
        self.prog["rim"].value = rim
        S = np.diag(squash) if squash is not None else np.eye(3)
        S_inv = np.linalg.inv(S)
        center = (character.pivots["torso"] + character.pivots["head"]) / 2
        tr, tr_off = self._split(pose.get("torso", np.eye(3)))
        t = character.pivots["torso"]
        for part, vao in parts.items():
            local, off = self._split(pose.get(part, np.eye(3)))
            if part != "torso" and part in character.pivots:
                # parça kendi ekleminden döner, sonra gövdenin dönüşünü izler
                p = character.pivots[part]
                m3 = tr @ local
                offset = tr @ (p - t) + t - m3 @ p + tr @ off + tr_off
            else:
                m3 = local
                offset = t - m3 @ t + off
            # squash & stretch: gövde merkezinden ölçek
            m3s = S @ m3
            offset = S @ (offset - center) + center
            model = np.eye(4)
            model[:3, :3] = root_rot @ m3s
            model[:3, 3] = root_rot @ offset + root_pos
            mvp = proj @ view @ model
            self.prog["mvp"].write(mvp.T.astype("f4").tobytes())
            self.prog["nmat"].write((root_rot @ S_inv @ m3).T.astype("f4").tobytes())
            vao.render(moderngl.TRIANGLES)
        self.ctx.copy_framebuffer(self.resolve, self.fbo)
        data = np.frombuffer(self.resolve.read(components=4, alignment=1), np.uint8)
        return data.reshape(self.h, self.w, 4)[::-1].copy()


def look_at(eye, target, up=(0, 1, 0)):
    eye, target, up = map(np.asarray, (eye, target, up))
    f = target - eye
    f = f / np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m
