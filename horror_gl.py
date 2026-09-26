"""Korku teaser'ı - moderngl render hattı (EGL ile ekransız; ekran kartı gerekmez, llvmpipe yeter).

Kare başına geçişler:
  1. gölge      : gül + düşen yapraklar + sıvı, spot ışığın gözünden derinlik
  2. yansıma    : sahne zemine göre aynalanıp yarım çözünürlükte çizilir
  3. ana        : zemin (dalgalanan kan), gül, sıvı, toz; 4x MSAA, HDR
  4. hacim      : spot ışık huzmesi (gölge haritasıyla ışık gölgeleri), yarım çözünürlük
  5. gözler / yazı, bloom, ton eşleme, film greni, vinyet
"""
import math
from pathlib import Path

import moderngl
import numpy as np

SHADERS = Path(__file__).parent / "shaders"


def load_shader(name):
    out = []
    for line in (SHADERS / name).read_text().splitlines():
        if line.startswith("#include"):
            out.append((SHADERS / line.split('"')[1]).read_text())
        else:
            out.append(line)
    return "\n".join(out)


# ---------------------------------------------------------------- matrisler

def look_at(eye, target, up=(0.0, 1.0, 0.0)):
    eye, target, up = (np.asarray(v, float) for v in (eye, target, up))
    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


def perspective(fovy_deg, aspect, near, far):
    t = 1 / math.tan(math.radians(fovy_deg) / 2)
    m = np.zeros((4, 4))
    m[0, 0], m[1, 1] = t / aspect, t
    m[2, 2], m[2, 3] = (far + near) / (near - far), 2 * far * near / (near - far)
    m[3, 2] = -1
    return m


def ortho(r, near, far):
    m = np.eye(4)
    m[0, 0] = m[1, 1] = 1 / r
    m[2, 2], m[2, 3] = -2 / (far - near), -(far + near) / (far - near)
    return m


def mat(m):
    return np.ascontiguousarray(np.asarray(m, "f4").T).tobytes()


def fibonacci_dirs(n):
    i = np.arange(n) + 0.5
    phi = np.arccos(1 - 2 * i / n)
    th = math.pi * (1 + 5 ** 0.5) * i
    return np.stack([np.cos(th) * np.sin(phi), np.cos(phi), np.sin(th) * np.sin(phi)], -1)


def vec4s(rows, n):
    """(k, 4) diziyi n elemanlı vec4 uniform dizisine (sıfırla doldurarak) çevirir."""
    out = np.zeros((n, 4), "f4")
    rows = np.asarray(rows, "f4").reshape(-1, 4)[:n]
    out[:len(rows)] = rows
    return out.tobytes(), len(rows)


VERTEX_FMT = "3f 3f 2f 4f 2f"
VERTEX_ATTRS = ("in_pos", "in_nrm", "in_uv", "in_info", "in_extra")
FULLSCREEN = ("floor", "liquid", "volume", "bloom_down", "bloom_up", "composite", "post", "eyes", "title")


class Renderer:
    def __init__(self, width, height, samples=4, n_dust=1400, seed=3):
        self.W, self.H = width, height
        self.ctx = moderngl.create_standalone_context(backend="egl")
        ctx = self.ctx
        self.prog = {}
        self._program("rose", "rose.vert", "rose.frag")
        self._program("depth", "depth.vert", "depth.frag")
        self._program("dust", "dust.vert", "dust.frag")
        for name in FULLSCREEN:
            self._program(name, "fullscreen.vert", f"{name}.frag")
        self.prog["ao"] = ctx.program(vertex_shader=load_shader("ao_gather.vert"), varyings=["out_ao"])

        quad = ctx.buffer(np.array([-1, -1, 1, -1, -1, 1, 1, 1], "f4").tobytes())
        self.quad = {n: ctx.vertex_array(self.prog[n], [(quad, "2f", "in_pos")]) for n in FULLSCREEN}

        rng = np.random.default_rng(seed)
        seeds = rng.random((n_dust, 4)).astype("f4")
        self.dust_vao = ctx.vertex_array(self.prog["dust"], [(ctx.buffer(seeds.tobytes()), "4f", "in_seed")])
        self.n_dust = n_dust

        # gölge haritası (spot ışık)
        self.shadow_size = 2048
        self.shadow_tex = ctx.depth_texture((self.shadow_size,) * 2)
        self.shadow_tex.compare_func = "<="
        self.shadow_tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.shadow_fbo = ctx.framebuffer(depth_attachment=self.shadow_tex)

        # ortam kapanması atlası: 48 yön, 8x6 karo
        self.ao_dirs = fibonacci_dirs(48)
        self.ao_grid = (8, 6)
        self.ao_tile = 256
        self.ao_tex = ctx.depth_texture((self.ao_grid[0] * self.ao_tile, self.ao_grid[1] * self.ao_tile))
        self.ao_tex.compare_func = ""
        self.ao_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.ao_fbo = ctx.framebuffer(depth_attachment=self.ao_tex)

        W, H = width, height
        hw, hh = W // 2, H // 2
        # ana HDR hedef (MSAA; ikinci çıktı normal + kimlik G-buffer'ı) ve çözülmüş kopyaları
        rb_col = ctx.renderbuffer((W, H), 4, samples=samples, dtype="f2")
        rb_g = ctx.renderbuffer((W, H), 4, samples=samples, dtype="f2")
        rb_d = ctx.depth_renderbuffer((W, H), samples=samples)
        self.msaa = ctx.framebuffer(color_attachments=[rb_col, rb_g], depth_attachment=rb_d)
        self.hdr = self._tex((W, H))
        self.gbuf = self._tex((W, H))
        self.gbuf.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.hdr_depth = ctx.depth_texture((W, H))
        self.hdr_depth.compare_func = ""
        self.hdr_fbo = ctx.framebuffer(color_attachments=[self.hdr, self.gbuf], depth_attachment=self.hdr_depth)
        # zemindeki yansıma (yarım çözünürlük)
        self.refl = self._tex((hw, hh))
        self.refl_fbo = ctx.framebuffer(color_attachments=[self.refl], depth_attachment=ctx.depth_renderbuffer((hw, hh)))
        # ışık huzmesi (yarım çözünürlük) ve yansımadaki huzme
        self.vol = self._tex((hw, hh))
        self.vol_fbo = ctx.framebuffer(color_attachments=[self.vol])
        # birleşik HDR (gözler ve yazı da buraya çizilir)
        self.comp = self._tex((W, H))
        self.comp_fbo = ctx.framebuffer(color_attachments=[self.comp])
        # bloom zinciri
        self.bloom = []
        w, h = hw, hh
        for _ in range(6):
            t = self._tex((max(w, 1), max(h, 1)))
            self.bloom.append((t, ctx.framebuffer(color_attachments=[t])))
            w, h = w // 2, h // 2
        self.out = ctx.texture((W, H), 4)
        self.out_fbo = ctx.framebuffer(color_attachments=[self.out])

        self._kuwahara_kernel()
        self.text_tex = None
        self.rose_vbo = None
        self.rose_vao = {}
        self.n_vertices = 0

    def _kuwahara_kernel(self, radius=3.4, n_sectors=8, sharp=4.0):
        """Genelleştirilmiş Kuwahara: disk içi örnek konumları ve her örneğin 8 dilime ağırlıkları."""
        pts = [(x, y) for y in range(-4, 5) for x in range(-4, 5) if x * x + y * y <= radius * radius]
        pts = sorted(pts, key=lambda p: p[0] ** 2 + p[1] ** 2)[:37]
        offs = np.array(pts, "f4")
        w = np.zeros((len(pts), n_sectors), "f4")
        for i, (x, y) in enumerate(pts):
            g = math.exp(-(x * x + y * y) / (2 * (radius * 0.6) ** 2))
            if x == 0 and y == 0:
                w[i] = g / n_sectors
                continue
            a = math.atan2(y, x)
            for k in range(n_sectors):
                c = math.cos(a - 2 * math.pi * k / n_sectors)
                w[i, k] = g * max(c, 0.0) ** sharp
        prog = self.prog["composite"]
        prog["u_koff"].write(offs.tobytes())
        prog["u_kw0"].write(np.ascontiguousarray(w[:, :4]).tobytes())
        prog["u_kw1"].write(np.ascontiguousarray(w[:, 4:]).tobytes())

    def _tex(self, size):
        t = self.ctx.texture(size, 4, dtype="f2")
        t.filter = (moderngl.LINEAR, moderngl.LINEAR)
        t.repeat_x = t.repeat_y = False
        return t

    def _program(self, name, vs, fs):
        self.prog[name] = self.ctx.program(vertex_shader=load_shader(vs), fragment_shader=load_shader(fs))

    def set_uniforms(self, name, **values):
        prog = self.prog[name]
        for k, v in values.items():
            if k not in prog:
                continue
            if isinstance(v, (bytes, bytearray)):
                prog[k].write(v)
            else:
                prog[k].value = v

    # ------------------------------------------------------------ gül köşeleri

    def upload_mesh(self, verts, tri):
        """verts: (n, 14) float32 (konum, normal, uv, info, extra); tri: (m, 3) int32."""
        data = np.ascontiguousarray(verts, "f4").tobytes()
        if self.rose_vbo is None or self.rose_vbo.size != len(data):
            self.rose_vbo = self.ctx.buffer(data, dynamic=True)
            self.rose_ibo = self.ctx.buffer(np.ascontiguousarray(tri, "i4").tobytes())
            self.rose_vao = {
                "rose": self.ctx.vertex_array(self.prog["rose"], [(self.rose_vbo, VERTEX_FMT, *VERTEX_ATTRS)],
                                              self.rose_ibo),
                "depth": self.ctx.vertex_array(self.prog["depth"],
                                               [(self.rose_vbo, "3f 44x", "in_pos")], self.rose_ibo),
                "ao": self.ctx.vertex_array(self.prog["ao"], [(self.rose_vbo, "3f 3f 32x", "in_pos", "in_nrm")]),
            }
            self.ao_out = self.ctx.buffer(reserve=len(verts) * 8)
        else:
            self.rose_vbo.write(data)
        self.n_vertices = len(verts)

    def bake_ao(self, center, radius, offset=0.004):
        """Yüklü köşeler için iki yüzlü ortam kapanması: (n, 2)."""
        ctx = self.ctx
        cols, rows = self.ao_grid
        center = np.asarray(center, float)
        vps = []
        self.ao_fbo.use()
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.BLEND)
        self.ao_fbo.clear(depth=1.0)
        proj = ortho(radius, 0.0, 2 * radius)
        for j, d in enumerate(self.ao_dirs):
            up = (0, 1, 0) if abs(d[1]) < 0.95 else (1, 0, 0)
            vp = proj @ look_at(center + d * radius, center, up)
            vps.append(vp)
            x, y = j % cols, j // cols
            self.ao_fbo.viewport = (x * self.ao_tile, y * self.ao_tile, self.ao_tile, self.ao_tile)
            self.prog["depth"]["u_viewproj"].write(mat(vp))
            self.rose_vao["depth"].render()
        self.ao_fbo.viewport = (0, 0, cols * self.ao_tile, rows * self.ao_tile)
        prog = self.prog["ao"]
        prog["u_vp"].write(b"".join(mat(m) for m in vps))
        prog["u_dirs"].write(np.ascontiguousarray(self.ao_dirs, "f4").tobytes())
        prog["u_grid"].value = (float(cols), float(rows))
        prog["u_offset"].value = offset
        self.ao_tex.use(0)
        prog["u_atlas"].value = 0
        self.rose_vao["ao"].transform(self.ao_out, mode=moderngl.POINTS, vertices=self.n_vertices)
        return np.frombuffer(self.ao_out.read(), "f4").reshape(-1, 2).copy()

    def set_eye_image(self, rgba, pupils, pupil_r, center, ref_per_unit, aux=None, lids=None):
        """Şeytani göz çizimi (H, W, 4) uint8, kapak verileri ve çizim düzlemindeki ölçüler."""
        h, w = rgba.shape[:2]
        if aux is not None:
            ta = self.ctx.texture((w, h), 4, np.ascontiguousarray(aux[::-1]).tobytes())
            ta.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tl = self.ctx.texture((w, 1), 4, np.ascontiguousarray(lids, "f4").tobytes(), dtype="f4")
            tl.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tl.repeat_x = tl.repeat_y = False
            self.eye_aux, self.eye_lids = ta, tl
        t = self.ctx.texture((w, h), 4, np.ascontiguousarray(rgba[::-1]).tobytes())
        t.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        t.build_mipmaps()
        t.repeat_x = t.repeat_y = False
        self.eye_tex = t
        prog = self.prog["eyes"]
        prog["u_img_size"].value = (float(w), float(h))
        prog["u_center"].value = tuple(float(v) for v in center)
        prog["u_ref_per_unit"].value = float(ref_per_unit)
        prog["u_pupils"].value = (*map(float, pupils[0]), *map(float, pupils[1]))
        prog["u_pupil_r"].value = float(pupil_r)

    def set_text(self, sharp, blurred):
        """COMING SOON maskeleri (H, W) float32 0..1, üst satır görüntünün üstü."""
        def tex(a):
            t = self.ctx.texture((a.shape[1], a.shape[0]), 1, np.ascontiguousarray(a[::-1], "f4").tobytes(), dtype="f4")
            t.filter = (moderngl.LINEAR, moderngl.LINEAR)
            return t
        self.text_tex = (tex(sharp), tex(blurred))

    # ------------------------------------------------------------ kare

    def render(self, st):
        """st: sahne durumu (horror_scene.Scene.state). Dönüş: (H, W, 3) uint8."""
        ctx = self.ctx
        W, H = self.W, self.H
        cam = st["camera"]
        view = look_at(cam["eye"], cam["target"], cam.get("up", (0, 1, 0)))
        proj = perspective(cam["fov"], W / H, 0.03, 60.0)
        vp = proj @ view
        inv_vp = np.linalg.inv(vp)
        lights = st["lights"]
        light_vp = lights["light_vp"]
        view3 = np.ascontiguousarray(view[:3, :3].T.astype("f4")).tobytes()   # mat3 (sütun düzeni)
        common = dict(u_spot_pos=tuple(lights["spot_pos"]), u_spot_dir=tuple(lights["spot_dir"]),
                      u_spot_cos=tuple(lights["spot_cos"]), u_spot_col=tuple(lights["spot_col"]),
                      u_light_vp=mat(light_vp), u_back_dir=tuple(lights["back_dir"]),
                      u_back_col=tuple(lights["back_col"]), u_light_gain=float(lights["gain"]),
                      u_time=float(st["t"]), u_shadow=1, u_view3=view3,
                      u_toon=float(st.get("toon", 1.0)))
        scene_on = st.get("scene_on", True)
        liq = st["liquid"]

        if scene_on:
            if st.get("mesh") is not None:
                self.upload_mesh(*st["mesh"])
            # 1. gölge haritası: gül + sıvı
            self.shadow_fbo.use()
            self.shadow_fbo.clear(depth=1.0)
            ctx.enable(moderngl.DEPTH_TEST)
            ctx.disable(moderngl.BLEND)
            ctx.polygon_offset = (1.5, 4.0)
            self.prog["depth"]["u_viewproj"].write(mat(light_vp))
            if self.n_vertices:
                self.rose_vao["depth"].render()
            ctx.polygon_offset = (0.0, 0.0)
            self._liquid(liq, 2, light_vp, np.linalg.inv(light_vp), lights["spot_pos"],
                         (self.shadow_size, self.shadow_size), common)

            # 2. yansıma: aynalanmış gül + sıvı + huzme
            self.refl_fbo.use()
            self.refl_fbo.clear(0, 0, 0, 1, depth=1.0)
            self.shadow_tex.use(1)
            self._rose(vp, 1, cam["eye"], st, common)
            self._liquid(liq, 1, vp, inv_vp, cam["eye"], (W // 2, H // 2), common)

            # 3. ana geçiş
            self.msaa.use()
            self.msaa.clear(0, 0, 0, 1, depth=1.0)
            ctx.enable(moderngl.DEPTH_TEST)
            ctx.disable(moderngl.BLEND)
            self.refl.use(2)
            self.shadow_tex.use(1)
            rip, n_rip = vec4s(st["ripples"][:, :4], 32)
            rip2, _ = vec4s(st["ripples"][:, 4:8], 32)
            self.set_uniforms("floor", u_viewproj=mat(vp), u_inv_viewproj=mat(inv_vp), u_res=(float(W), float(H)),
                              u_ripples=rip, u_ripples2=rip2, u_nripples=n_rip, u_refl=2,
                              u_refl_gain=float(st.get("refl_gain", 1.0)),
                              u_beam_refl=float(st.get("beam_refl", 1.0)),
                              u_ripple_ink=float(st.get("ripple_ink", 1.0)), **common)
            self.quad["floor"].render(moderngl.TRIANGLE_STRIP)
            self._rose(vp, 0, cam["eye"], st, common)
            self._liquid(liq, 0, vp, inv_vp, cam["eye"], (W, H), common)
            # toz
            ctx.enable(moderngl.BLEND | moderngl.PROGRAM_POINT_SIZE)
            ctx.blend_func = moderngl.ONE, moderngl.ONE
            ctx.depth_mask = False
            dust = st["dust"]
            self.set_uniforms("dust", u_viewproj=mat(vp), u_px=float(dust["px"]), u_center=tuple(dust["center"]),
                              u_extent=tuple(dust["extent"]), **common)
            self.shadow_tex.use(1)
            self.dust_vao.render(moderngl.POINTS, vertices=int(self.n_dust * dust["amount"]))
            ctx.depth_mask = True
            ctx.disable(moderngl.BLEND)
            ctx.copy_framebuffer(self.hdr_fbo, self.msaa)

            # 4. hacimsel ışık (yarım çözünürlük)
            ctx.disable(moderngl.DEPTH_TEST)
            self.vol_fbo.use()
            self.vol_fbo.clear(0, 0, 0, 1)
            self.hdr_depth.use(3)
            self.shadow_tex.use(1)
            self.set_uniforms("volume", u_inv_viewproj=mat(inv_vp), u_depth=3, u_mirror=0,
                              u_density=float(st["fog"]), **common)
            self.quad["volume"].render(moderngl.TRIANGLE_STRIP)
        else:
            self.hdr_fbo.use()
            self.hdr_fbo.clear(0, 0, 0, 0, depth=1.0)
            self.vol_fbo.use()
            self.vol_fbo.clear(0, 0, 0, 1)

        # 5. birleştirme + gözler + yazı
        ctx.disable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.BLEND)
        self.comp_fbo.use()
        self.hdr.use(0)
        self.vol.use(4)
        self.hdr_depth.use(3)
        self.gbuf.use(2)
        style = st.get("style", {})
        self.set_uniforms("composite", u_hdr=0, u_vol=4, u_depth=3, u_gbuf=2, u_vol_texel=(2.0 / W, 2.0 / H),
                          u_res=(float(W), float(H)), u_near=0.03, u_far=60.0, u_time=float(st["t"]),
                          u_ink=float(style.get("ink", 1.0)) if scene_on else 0.0,
                          u_paint=float(style.get("paint", 1.0)) if scene_on else 0.0)
        self.quad["composite"].render(moderngl.TRIANGLE_STRIP)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.ONE, moderngl.ONE
        eyes = st.get("eyes")
        if eyes:
            self.eye_tex.use(8)
            self.eye_aux.use(9)
            self.eye_lids.use(10)
            self.set_uniforms("eyes", u_img=8, u_aux=9, u_lids=10, u_res=(float(W), float(H)),
                              u_time=float(st["t"]), **eyes)
            self.quad["eyes"].render(moderngl.TRIANGLE_STRIP)
        title = st.get("title")
        if title and self.text_tex:
            self.text_tex[0].use(5)
            self.text_tex[1].use(6)
            self.set_uniforms("title", u_text=5, u_text_blur=6, u_time=float(st["t"]), **title)
            self.quad["title"].render(moderngl.TRIANGLE_STRIP)
        ctx.disable(moderngl.BLEND)

        # 6. bloom
        post = st["post"]
        src, texel = self.comp, (1.0 / W, 1.0 / H)
        for i, (t, fbo) in enumerate(self.bloom):
            fbo.use()
            src.use(0)
            self.set_uniforms("bloom_down", u_src=0, u_texel=texel, u_threshold=float(post["bloom_threshold"]),
                              u_first=int(i == 0))
            self.quad["bloom_down"].render(moderngl.TRIANGLE_STRIP)
            src, texel = t, (1.0 / t.width, 1.0 / t.height)
        ctx.enable(moderngl.BLEND)
        ctx.blend_func = moderngl.ONE, moderngl.ONE
        for i in range(len(self.bloom) - 1, 0, -1):
            t, _ = self.bloom[i]
            _, fbo = self.bloom[i - 1]
            fbo.use()
            t.use(0)
            self.set_uniforms("bloom_up", u_src=0, u_texel=(1.0 / t.width, 1.0 / t.height), u_weight=1.0)
            self.quad["bloom_up"].render(moderngl.TRIANGLE_STRIP)
        ctx.disable(moderngl.BLEND)

        # 7. son işlem
        self.out_fbo.use()
        self.comp.use(0)
        self.bloom[0][0].use(7)
        self.set_uniforms("post", u_comp=0, u_bloom=7, u_res=(float(W), float(H)), u_time=float(st["t"]),
                          u_exposure=float(post["exposure"]), u_bloom_amt=float(post["bloom"]),
                          u_ca=float(post["ca"]), u_blur=tuple(post["blur"]), u_grain=float(post["grain"]),
                          u_vignette=float(post["vignette"]), u_flash=float(post["flash"]),
                          u_fade=float(post["fade"]), u_bars=float(post["bars"]))
        self.quad["post"].render(moderngl.TRIANGLE_STRIP)
        data = self.out_fbo.read(components=3)
        return np.frombuffer(data, np.uint8).reshape(H, W, 3)[::-1]

    # ------------------------------------------------------------ yardımcı geçişler

    def _rose(self, vp, mirror, eye, st, common):
        if not self.n_vertices:
            return
        ctx = self.ctx
        ctx.enable(moderngl.DEPTH_TEST)
        ctx.disable(moderngl.BLEND)
        self.shadow_tex.use(1)
        self.set_uniforms("rose", u_viewproj=mat(vp), u_mirror=float(mirror), u_eye=tuple(eye),
                          u_amb=tuple(st["lights"]["amb"]), u_floor_glow=float(st["lights"]["floor_glow"]), **common)
        self.rose_vao["rose"].render()

    def _liquid(self, liq, mode, vp, inv_vp, eye, res, common):
        if liq is None:
            return
        ctx = self.ctx
        caps, n_caps = vec4s(liq["caps"], 14)
        blobs, n_blobs = vec4s(liq["blobs"], 28)
        if n_caps < 2 and n_blobs == 0 and liq["drop"][3] <= 0:
            return
        ctx.enable(moderngl.DEPTH_TEST)
        if mode == 2:
            ctx.disable(moderngl.BLEND)
        else:
            ctx.enable(moderngl.BLEND)
            ctx.blend_func = moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA
        self.shadow_tex.use(1)
        self.set_uniforms("liquid", u_mode=mode, u_viewproj=mat(vp), u_inv_viewproj=mat(inv_vp),
                          u_eye=tuple(float(v) for v in eye), u_res=(float(res[0]), float(res[1])),
                          u_caps=caps, u_ncaps=n_caps, u_blobs=blobs, u_nblobs=n_blobs,
                          u_drop=tuple(liq["drop"]), u_drop_shape=tuple(liq["drop_shape"]),
                          u_bmin=tuple(liq["bmin"]), u_bmax=tuple(liq["bmax"]), u_blend=float(liq["blend"]),
                          u_ridge=float(liq.get("ridge", 0.0)),
                          **common)
        self.quad["liquid"].render(moderngl.TRIANGLE_STRIP)
        ctx.disable(moderngl.BLEND)
