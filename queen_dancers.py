"""QUEEN lyric video - üç özgün 3B anime dansçı: modeller, iskelet ve toon render.

Karakterler tamamen koddan üretilir (hazır model yok) ve özgün tasarımdır:
  AKA     kızıl ikiz kuyruk, siyah-kırmızı idol kıyafeti (soldaki)
  KIN     uzun platin saç, küçük taç, beyaz-altın idol elbisesi (ortadaki)
  MIDORI  nane yeşili küt saç + yan at kuyruğu, beyaz-yeşil kıyafet (sağdaki)

Render: moderngl + EGL (ekran kartı gerekmez). Cel shading (iki ton, yumuşak geçiş),
sahnenin vurgu rengiyle kenar ışığı, saçta toon parlaması, renkli ince dış çizgi
(ters kabuk yöntemi) ve zeminde yumuşak gölge. Yüz ifadeleri (göz kırpma, gülümseme,
açık ağız, ^^ gözler, göz kırpışı) koddan çizilen bir doku atlasından seçilir.

Birimler: metre benzeri; karakter boyu ~1.6. Y yukarı, karakter +Z'ye (kameraya) bakar,
karakterin solu +X'tedir.
"""
import math

import moderngl
import numpy as np
import skia

# ---------------------------------------------------------------- iskelet

# eklem: (ebeveyn, dinlenme konumu ebeveyne göre)
JOINTS = {
    "root": (None, (0.0, 0.0, 0.0)),
    "pelvis": ("root", (0.0, 0.78, 0.0)),
    "spine": ("pelvis", (0.0, 0.10, 0.0)),
    "chest": ("spine", (0.0, 0.14, 0.0)),
    "neck": ("chest", (0.0, 0.15, 0.0)),
    "head": ("neck", (0.0, 0.07, 0.0)),
    "shoulder_l": ("chest", (0.13, 0.10, 0.0)),
    "elbow_l": ("shoulder_l", (0.0, -0.22, 0.0)),
    "wrist_l": ("elbow_l", (0.0, -0.20, 0.0)),
    "shoulder_r": ("chest", (-0.13, 0.10, 0.0)),
    "elbow_r": ("shoulder_r", (0.0, -0.22, 0.0)),
    "wrist_r": ("elbow_r", (0.0, -0.20, 0.0)),
    "hip_l": ("pelvis", (0.075, -0.04, 0.0)),
    "knee_l": ("hip_l", (0.0, -0.35, 0.0)),
    "ankle_l": ("knee_l", (0.0, -0.35, 0.0)),
    "hip_r": ("pelvis", (-0.075, -0.04, 0.0)),
    "knee_r": ("hip_r", (0.0, -0.35, 0.0)),
    "ankle_r": ("knee_r", (0.0, -0.35, 0.0)),
}
JOINT_NAMES = list(JOINTS)
UPPER_ARM, FORE_ARM, THIGH, SHIN = 0.22, 0.20, 0.35, 0.35
HEAD_C = np.array([0.0, 0.135, 0.012])        # kafa merkezinin "head" eklemine göre yeri (kafa biriminde)
HEAD_R = np.array([0.125, 0.142, 0.12])
HEAD_S = 1.13                                  # kafa ve saçın gövdeye göre ölçeği (sevimli anime oranı)


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler(rx, ry, rz):
    """Derece: önce Z (yana eğilme), sonra X (öne eğilme), en son Y (dönme)."""
    return rot_y(math.radians(ry)) @ rot_x(math.radians(rx)) @ rot_z(math.radians(rz))


def bone_basis(direction, hint):
    """Yerel -Y eksenini 'direction'a çeviren dönüş; yerel +Z 'hint'e olabildiğince yakın."""
    y = -np.asarray(direction, float)
    y /= np.linalg.norm(y) + 1e-12
    z = np.asarray(hint, float) - y * np.dot(hint, y)
    if np.linalg.norm(z) < 1e-4:
        alt = np.array([0.0, 0.0, 1.0]) if abs(y[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        z = alt - y * np.dot(alt, y)
    z /= np.linalg.norm(z)
    x = np.cross(y, z)
    return np.stack([x, y, z], axis=1)


def two_bone(root, target, l1, l2, pole):
    """İki kemikli IK: kök, hedef ve dirsek/diz yönü -> (orta eklem konumu, uç konumu)."""
    d_vec = target - root
    d = float(np.linalg.norm(d_vec))
    d = min(max(d, 0.04), l1 + l2 - 1e-3)
    u = d_vec / (np.linalg.norm(d_vec) + 1e-12)
    v = pole - u * np.dot(pole, u)
    if np.linalg.norm(v) < 1e-5:
        v = np.array([0.0, 0.0, 1.0]) - u * u[2]
    v /= np.linalg.norm(v) + 1e-12
    ca = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    sa = math.sqrt(max(0.0, 1 - ca * ca))
    mid = root + l1 * (ca * u + sa * v)
    end = root + d * u
    return mid, end


def solve_skeleton(pose):
    """Poz -> her eklemin dünya dönüşü (3x3) ve konumu (3,).

    pose anahtarları:
      root (x, y, z), yaw (derece), pelvis/spine/chest/neck/head (rx, ry, rz derece),
      hand_l/hand_r: el hedefi göğüs uzayında, elbow_l/elbow_r: dirsek yönü (göğüs uzayı),
      foot_l/foot_r: ayak bileği hedefi kök uzayında (yaw uygulanmadan), knee_l/knee_r: diz yönü.
    """
    Rw, Pw = {}, {}
    yaw = rot_y(math.radians(pose.get("yaw", 0.0)))
    Rw["root"], Pw["root"] = yaw, np.asarray(pose.get("root", (0, 0, 0)), float)
    for j in ("pelvis", "spine", "chest", "neck", "head"):
        parent, off = JOINTS[j]
        Pw[j] = Pw[parent] + Rw[parent] @ np.asarray(off)
        if j == "pelvis":
            Pw[j] = Pw[j] + yaw @ np.array([0.0, pose.get("bounce", 0.0), 0.0])
        Rw[j] = Rw[parent] @ euler(*pose.get(j, (0, 0, 0)))
    for s in ("l", "r"):
        sign = 1 if s == "l" else -1
        sh = f"shoulder_{s}"
        Pw[sh] = Pw["chest"] + Rw["chest"] @ np.asarray(JOINTS[sh][1])
        target = Pw["chest"] + Rw["chest"] @ np.asarray(pose.get(f"hand_{s}", (0.18 * sign, -0.3, 0.03)))
        pole = Rw["chest"] @ np.asarray(pose.get(f"elbow_{s}", (0.3 * sign, -0.2, -1.0)), float)
        elbow, hand = two_bone(Pw[sh], target, UPPER_ARM, FORE_ARM, pole)
        fwd = Rw["chest"] @ np.array([0.0, 0.0, 1.0])
        Rw[sh] = bone_basis(elbow - Pw[sh], -pole)
        Pw[f"elbow_{s}"] = elbow
        Rw[f"elbow_{s}"] = bone_basis(hand - elbow, fwd - pole * 0.5)
        Pw[f"wrist_{s}"] = hand
        Rw[f"wrist_{s}"] = Rw[f"elbow_{s}"]
        hp = f"hip_{s}"
        Pw[hp] = Pw["pelvis"] + Rw["pelvis"] @ np.asarray(JOINTS[hp][1])
        foot = Pw["root"] + yaw @ np.asarray(pose.get(f"foot_{s}", (0.09 * sign, 0.06, 0.0)))
        kpole = yaw @ np.asarray(pose.get(f"knee_{s}", (0.15 * sign, 0.0, 1.0)), float)
        knee, ank = two_bone(Pw[hp], foot, THIGH, SHIN, kpole)
        Rw[hp] = bone_basis(knee - Pw[hp], kpole)
        Pw[f"knee_{s}"] = knee
        Rw[f"knee_{s}"] = bone_basis(ank - knee, kpole)
        Pw[f"ankle_{s}"] = ank
        Rw[f"ankle_{s}"] = yaw @ rot_x(math.radians(pose.get(f"toe_{s}", 0.0)))
    return Rw, Pw


# ---------------------------------------------------------------- ağ (mesh) yapıcılar

class Mesh:
    def __init__(self, V, F, C, UV=None, N=None):
        self.V = np.asarray(V, np.float32)
        self.F = np.asarray(F, np.int32)
        C = np.asarray(C, np.float32)
        self.C = np.broadcast_to(C, self.V.shape).astype(np.float32) if C.ndim == 1 else C
        self.UV = np.zeros((len(self.V), 2), np.float32) if UV is None else np.asarray(UV, np.float32)
        self.N = vertex_normals(self.V, self.F) if N is None else np.asarray(N, np.float32)

    def interleaved(self):
        return np.hstack([self.V, self.N, self.C, self.UV]).astype("f4")


def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V, dtype=np.float64)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return (N / (np.linalg.norm(N, axis=1, keepdims=True) + 1e-12)).astype(np.float32)


def merge(meshes):
    V, F, C, UV, off = [], [], [], [], 0
    for m in meshes:
        V.append(m.V)
        F.append(m.F + off)
        C.append(m.C)
        UV.append(m.UV)
        off += len(m.V)
    out = Mesh(np.vstack(V), np.vstack(F), np.vstack(C), np.vstack(UV), N=np.vstack([m.N for m in meshes]))
    return out


def grid_faces(rows, cols, closed=True):
    """rows x cols ızgara (her satır bir halka) için üçgenler; dış yüz saat yönünün tersine."""
    F = []
    cc = cols if closed else cols - 1
    for i in range(rows - 1):
        for j in range(cc):
            a, b = i * cols + j, i * cols + (j + 1) % cols
            c_, d = (i + 1) * cols + j, (i + 1) * cols + (j + 1) % cols
            F += [(a, c_, b), (b, c_, d)]
    return np.array(F, np.int32)


def fix_winding(V, F, inside):
    """Yüz normali 'inside' noktalarından dışarı bakmıyorsa üçgeni ters çevirir."""
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    cen = V[F].mean(axis=1)
    flip = np.einsum("ij,ij->i", fn, cen - inside) < 0
    F = F.copy()
    F[flip] = F[flip][:, [0, 2, 1]]
    return F


def lathe(ys, rs, color, sides=20, sx=1.0, sz=1.0, center=(0.0, 0.0, 0.0), zshift=None):
    """Dönel yüzey: her y'de r yarıçaplı (x'te sx, z'de sz ölçekli) halka; uçlar kapalı."""
    ys, rs = np.asarray(ys, float), np.asarray(rs, float)
    a = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    V = []
    for i, (y, r) in enumerate(zip(ys, rs)):
        dz = zshift[i] if zshift is not None else 0.0
        V.append(np.stack([r * sx * np.sin(a), np.full(sides, y), r * sz * np.cos(a) + dz], 1))
    V = np.vstack(V)
    F = grid_faces(len(ys), sides)
    top, bot = len(V), len(V) + 1
    V = np.vstack([V, [[0, ys[0], 0], [0, ys[-1], 0]]])
    caps = [(top, j, (j + 1) % sides) for j in range(sides)]
    last = (len(ys) - 1) * sides
    caps += [(bot, last + (j + 1) % sides, last + j) for j in range(sides)]
    F = np.vstack([F, np.array(caps, np.int32)])
    V = V + np.asarray(center)
    axis = np.stack([np.full(len(F), center[0]), V[F].mean(axis=1)[:, 1], np.full(len(F), center[2])], 1)
    fn_cen = V[F].mean(axis=1)
    inside = np.where(np.abs(fn_cen[:, 1:2] - V[F][:, :, 1].mean(1, keepdims=True)) < 1e-9, axis, axis)
    F = fix_winding(V, F, inside)
    return Mesh(V, F, color)


def capsule(length, r0, r1, color, sides=16, rings=10, sx=1.0, sz=1.0, bulge=0.0):
    """Eklemden aşağı (-Y) uzanan, uçları yuvarlak konik kapsül."""
    ys, rs = [], []
    n = rings
    for k in range(4):                                    # üst yarım küre
        th = math.pi / 2 * (1 - k / 4)
        ys.append(r0 * math.sin(th) * 0.9)
        rs.append(r0 * math.cos(th))
    for k in range(n + 1):
        u = k / n
        ys.append(-length * u)
        rs.append(r0 + (r1 - r0) * u + bulge * math.sin(math.pi * u) * (1 - u))
    for k in range(1, 5):                                 # alt yarım küre
        th = math.pi / 2 * k / 4
        ys.append(-length - r1 * math.sin(th) * 0.9)
        rs.append(r1 * math.cos(th))
    rs[0] = 1e-4
    rs[-1] = 1e-4
    return lathe(ys, rs, color, sides=sides, sx=sx, sz=sz)


def ellipsoid(center, radii, color, sides=20, rings=14):
    ys, rs = [], []
    for k in range(rings + 1):
        th = math.pi * k / rings
        ys.append(radii[1] * math.cos(th))
        rs.append(max(math.sin(th), 1e-4))
    m = lathe(ys, rs, color, sides=sides, sx=radii[0], sz=radii[2])
    m.V += np.asarray(center, np.float32)
    return m


def ribbon(points, widths, normals, thickness, color):
    """Saç tutamı: yol boyunca genişliği değişen, kalınlığı olan kapalı şerit.
    points (k,3), widths (k,), normals (k,3) şeridin dışa baktığı yön."""
    P = np.asarray(points, float)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    Nn = np.asarray(normals, float)
    Nn = Nn - T * np.einsum("ij,ij->i", Nn, T)[:, None]
    Nn /= np.linalg.norm(Nn, axis=1, keepdims=True) + 1e-12
    B = np.cross(T, Nn)
    w = np.asarray(widths)[:, None] / 2
    th = np.asarray(thickness if np.ndim(thickness) else np.full(len(P), thickness))[:, None] / 2
    ring = [P + B * w + Nn * th, P - B * w + Nn * th, P - B * w - Nn * th, P + B * w - Nn * th]
    V = np.stack(ring, 1).reshape(-1, 3)
    F = grid_faces(len(P), 4)
    cap0 = [(0, 1, 2), (0, 2, 3)]
    e = (len(P) - 1) * 4
    cap1 = [(e, e + 2, e + 1), (e, e + 3, e + 2)]
    F = np.vstack([F, cap0, cap1])
    inside = np.repeat(P, 4, axis=0)[F].mean(axis=1)
    F = fix_winding(V, F, inside)
    return Mesh(V, F, color)


def tube(points, radii, color, sides=10):
    """Yol boyunca yarıçapı değişen boru (ikiz kuyruk, at kuyruğu)."""
    P = np.asarray(points, float)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    ref = np.array([0.0, 0.0, 1.0]) if abs(T[0][2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    Nn = []
    n = ref - T[0] * np.dot(ref, T[0])
    n /= np.linalg.norm(n)
    for t in T:                                           # paralel taşıma
        n = n - t * np.dot(n, t)
        n /= np.linalg.norm(n) + 1e-12
        Nn.append(n)
    Nn = np.array(Nn)
    B = np.cross(T, Nn)
    a = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    r = np.asarray(radii)[:, None, None]
    V = P[:, None, :] + r * (np.cos(a)[None, :, None] * Nn[:, None, :] + np.sin(a)[None, :, None] * B[:, None, :])
    V = V.reshape(-1, 3)
    F = grid_faces(len(P), sides)
    V = np.vstack([V, P[0], P[-1]])
    s0, s1 = len(V) - 2, len(V) - 1
    last = (len(P) - 1) * sides
    caps = [(s0, j, (j + 1) % sides) for j in range(sides)] + [(s1, last + j, last + (j + 1) % sides) for j in range(sides)]
    F = np.vstack([F, caps])
    centers = np.vstack([np.repeat(P, sides, axis=0), P[0], P[-1]])
    F = fix_winding(V, F, centers[F].mean(axis=1))
    return Mesh(V, F, color)


# ---------------------------------------------------------------- kafa ve yüz

def head_mesh(skin):
    """Anime kafası: üstü yuvarlak, alt yarısı çeneye doğru daralan elipsoit; ön yüzde düzlemsel UV."""
    m = ellipsoid((0, 0, 0), HEAD_R, skin, sides=32, rings=26)
    V = m.V.astype(float)
    y = V[:, 1] / HEAD_R[1]
    low = np.clip(-y, 0, 1)
    V[:, 0] *= 1 - 0.36 * low ** 1.5
    V[:, 2] *= 1 - 0.12 * low ** 1.5
    V[:, 2] += 0.02 * low ** 2                            # çene hafif önde
    V[:, 1] *= 1 + 0.06 * low
    m.V = (V + HEAD_C).astype(np.float32)
    m.N = vertex_normals(m.V, m.F)
    uv = np.stack([V[:, 0] / 0.25 + 0.5, V[:, 1] / 0.30 + 0.5], 1)
    m.UV = uv.astype(np.float32)
    return m


FACE_W = 512
EXPRESSIONS = ("smile", "blink", "open", "happy", "wink")


def face_atlas(eye_rgb, lash=(0.1, 0.06, 0.09), brow=None):
    """Yüz ifadesi atlası (5 hücre yan yana): gözler, kaşlar, ağız, allık. Şeffaf zemin."""
    n = len(EXPRESSIONS)
    surf = skia.Surface(FACE_W * n, FACE_W)
    brow = brow or lash

    def px(hx, hy):                                       # kafa koordinatı -> hücre pikseli
        return (hx / 0.25 + 0.5) * FACE_W, (0.5 - hy / 0.30) * FACE_W

    def paint(rgb, a=1.0, width=None, blur=0.0):
        p = skia.Paint(AntiAlias=True, Color4f=skia.Color4f(*rgb, a))
        if width:
            p.setStyle(skia.Paint.kStroke_Style)
            p.setStrokeWidth(width)
            p.setStrokeCap(skia.Paint.kRound_Cap)
        if blur:
            p.setMaskFilter(skia.MaskFilter.MakeBlur(skia.kNormal_BlurStyle, blur))
        return p

    iris_dark = tuple(c * 0.42 for c in eye_rgb)
    iris_light = tuple(min(1.0, c * 0.75 + 0.35) for c in eye_rgb)

    def open_eye(c, side):
        cx, cy = px(0.047 * side, -0.004)
        w, h = 84, 92
        rect = skia.Rect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)
        c.drawOval(rect, paint((1, 1, 1)))
        ir = skia.Rect(cx - 30, cy - 36, cx + 30, cy + 44)
        shader = skia.GradientShader.MakeLinear([skia.Point(cx, ir.top()), skia.Point(cx, ir.bottom())],
                                                [skia.Color4f(*iris_dark, 1).toColor(),
                                                 skia.Color4f(*eye_rgb, 1).toColor(),
                                                 skia.Color4f(*iris_light, 1).toColor()], [0.0, 0.55, 1.0])
        pi = skia.Paint(AntiAlias=True, Shader=shader)
        c.save()
        c.clipRect(rect)
        c.drawOval(ir, pi)
        c.drawOval(skia.Rect(cx - 12, cy - 12, cx + 12, cy + 22), paint(tuple(k * 0.25 for k in eye_rgb)))
        c.drawOval(ir, paint(tuple(k * 0.3 for k in eye_rgb), width=4))
        c.restore()
        c.drawCircle(cx - 13 * side, cy - 16, 12, paint((1, 1, 1)))
        c.drawCircle(cx + 11 * side, cy + 20, 6, paint((1, 1, 1), 0.9))
        # üst kirpik: kalın kavis, dış köşede küçük kıvrım
        path = skia.Path()
        path.moveTo(cx - 46 * side, cy - 20)
        path.quadTo(cx - 4 * side, cy - 62, cx + 44 * side, cy - 26)
        path.lineTo(cx + 56 * side, cy - 14)
        c.drawPath(path, paint(lash, width=11))
        low = skia.Path()
        low.moveTo(cx - 26 * side, cy + 47)
        low.quadTo(cx + 4 * side, cy + 54, cx + 30 * side, cy + 44)
        c.drawPath(low, paint(lash, 0.6, width=3.5))

    def closed_eye(c, side, happy):
        cx, cy = px(0.047 * side, -0.004)
        path = skia.Path()
        if happy:                                         # ^ ^
            path.moveTo(cx - 36, cy + 14)
            path.quadTo(cx, cy - 34, cx + 36, cy + 14)
        else:                                             # huzurlu kapalı göz
            path.moveTo(cx - 42, cy + 2)
            path.quadTo(cx, cy + 30, cx + 42, cy + 2)
        c.drawPath(path, paint(lash, width=10))

    def brows(c):
        for side in (-1, 1):
            cx, cy = px(0.05 * side, 0.052)
            path = skia.Path()
            path.moveTo(cx - 30 * side, cy + 6)
            path.quadTo(cx, cy - 8, cx + 34 * side, cy + 4)
            c.drawPath(path, paint(brow, 0.9, width=4))

    def mouth(c, kind):
        cx, cy = px(0.0, -0.088)
        if kind == "smile":
            path = skia.Path()
            path.moveTo(cx - 20, cy - 4)
            path.quadTo(cx, cy + 12, cx + 20, cy - 4)
            c.drawPath(path, paint((0.45, 0.15, 0.2), width=5))
        else:
            path = skia.Path()
            path.moveTo(cx - 24, cy - 8)
            path.lineTo(cx + 24, cy - 8)
            path.quadTo(cx + 22, cy + 30, cx, cy + 32)
            path.quadTo(cx - 22, cy + 30, cx - 24, cy - 8)
            c.drawPath(path, paint((0.5, 0.1, 0.16)))
            c.drawOval(skia.Rect(cx - 13, cy + 12, cx + 13, cy + 30), paint((0.95, 0.5, 0.55)))

    def cheeks(c):
        for side in (-1, 1):
            cx, cy = px(0.066 * side, -0.056)
            c.drawOval(skia.Rect(cx - 36, cy - 14, cx + 36, cy + 14), paint((1.0, 0.45, 0.5), 0.35, blur=9))
        cx, cy = px(0.004, -0.052)
        c.drawLine(cx, cy - 5, cx - 3, cy + 4, paint((0.8, 0.45, 0.45), 0.7, width=3))

    with surf as c:
        c.clear(skia.Color4f(0, 0, 0, 0))
        for k, name in enumerate(EXPRESSIONS):
            c.save()
            c.translate(k * FACE_W, 0)
            c.clipRect(skia.Rect(0, 0, FACE_W, FACE_W))
            cheeks(c)
            brows(c)
            if name in ("smile", "open"):
                open_eye(c, 1)
                open_eye(c, -1)
            elif name == "blink":
                closed_eye(c, 1, False)
                closed_eye(c, -1, False)
            elif name == "happy":
                closed_eye(c, 1, True)
                closed_eye(c, -1, True)
            elif name == "wink":
                open_eye(c, -1)
                closed_eye(c, 1, True)
            mouth(c, "smile" if name in ("smile", "blink", "wink") else "open")
            c.restore()
    img = surf.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
    return np.ascontiguousarray(img[::-1])                # GL: v=0 alt satır


# ---------------------------------------------------------------- karakter tasarımları

SKIN = (1.0, 0.89, 0.83)

DESIGNS = {
    "aka": dict(hair=(0.82, 0.1, 0.2), eyes=(0.92, 0.18, 0.3), top=(0.13, 0.12, 0.17), accent=(1.0, 0.22, 0.34),
                skirt=(0.88, 0.14, 0.26), hem=(0.13, 0.12, 0.17), socks=(0.12, 0.11, 0.15), shoes=(1.0, 0.24, 0.36),
                gloves=(0.13, 0.12, 0.17), style="twintail", rim=(1.0, 0.3, 0.4)),
    "kin": dict(hair=(1.0, 0.9, 0.66), eyes=(0.95, 0.62, 0.12), top=(0.98, 0.97, 0.95), accent=(1.0, 0.76, 0.22),
                skirt=(0.97, 0.96, 0.94), hem=(1.0, 0.76, 0.22), socks=(0.98, 0.97, 0.95), shoes=(1.0, 0.8, 0.3),
                gloves=(0.98, 0.97, 0.95), style="long", rim=(1.0, 0.85, 0.4)),
    "midori": dict(hair=(0.32, 0.88, 0.68), eyes=(0.16, 0.72, 0.5), top=(0.96, 0.98, 0.97), accent=(0.18, 0.82, 0.6),
                   skirt=(0.22, 0.78, 0.58), hem=(0.96, 0.98, 0.97), socks=(0.96, 0.98, 0.97), shoes=(0.2, 0.8, 0.6),
                   gloves=SKIN, style="bob", rim=(0.4, 1.0, 0.75)),
}


def shade(rgb, k):
    return tuple(min(1.0, c * k) for c in rgb)


def head_point(theta, phi, lift=0.0):
    """Kafa elipsoidi üstünde nokta (theta: tepeden açı, phi: önden +X'e açı), yüzeyden 'lift' dışarı."""
    d = np.array([math.sin(theta) * math.sin(phi), math.cos(theta), math.sin(theta) * math.cos(phi)])
    p = d * (HEAD_R + lift)
    return p + HEAD_C, d


def strand_path(th0, ph0, th1, ph1, n=9, lift0=0.012, lift1=0.02, drop=0.0):
    """Kafa yüzeyini izleyen saç tutamı yolu (+ ucunda aşağı sarkma)."""
    pts, nrm = [], []
    for k in range(n):
        u = k / (n - 1)
        th = th0 + (th1 - th0) * u
        ph = ph0 + (ph1 - ph0) * u
        p, d = head_point(th, ph, lift0 + (lift1 - lift0) * u)
        p = p + np.array([0.0, -drop * u ** 2, 0.0])
        pts.append(p)
        nrm.append(d)
    return np.array(pts), np.array(nrm)


def build_static_hair(des):
    """Kafaya sabit saç parçaları: kafatası kabuğu, perçem, yan tutamlar, aksesuarlar."""
    hair = des["hair"]
    parts = []
    cap = ellipsoid(HEAD_C + np.array([0, 0.01, -0.006]), HEAD_R * np.array([1.085, 1.075, 1.1]), hair,
                    sides=32, rings=24)
    cen = cap.V[cap.F].mean(axis=1) - HEAD_C
    front = cen[:, 2] > -0.01
    keep = ~((front & (cen[:, 1] < 0.075 - 0.25 * np.clip(np.abs(cen[:, 0]) - 0.09, 0, 1))) | (cen[:, 1] < -0.105))
    cap.F = cap.F[keep]
    parts.append(cap)
    # perçem: alında sivri uçlu tutamlar
    xs = np.linspace(-0.58, 0.58, 9)
    for i, ph in enumerate(xs):
        long = 0.1 if i % 2 else 0.0
        pts, nrm = strand_path(0.35, ph * 0.55, 1.33 + long, ph, n=9, lift0=0.014, lift1=0.02)
        w = 0.052 * (1 - np.linspace(0, 1, 9) ** 1.6) + 0.004
        parts.append(ribbon(pts, w, nrm, 0.012, hair))
    # ense/arka: tepeden aşağı inen tutamlar (arkadan kask gibi görünmesin)
    for k in range(9):
        ph = math.pi + (k - 4) * 0.3
        pts, nrm = strand_path(0.22, ph * 0.9 + math.pi * 0.1, 1.75, ph, n=10, lift0=0.016, lift1=0.024)
        w = 0.075 * (1 - np.linspace(0, 1, 10) ** 2.2) + 0.01
        parts.append(ribbon(pts, w, nrm, 0.014, hair))
    # yan tutamlar (yüzün iki yanında)
    for side in (-1, 1):
        pts, nrm = strand_path(0.6, side * 1.05, 1.62, side * 1.12, n=10, lift0=0.014, lift1=0.022, drop=0.07)
        w = 0.05 * (1 - np.linspace(0, 1, 10) ** 1.4) + 0.005
        parts.append(ribbon(pts, w, nrm, 0.014, hair))
    style = des["style"]
    if style == "long":                                    # taç
        gold = des["accent"]
        band = []
        for k in range(15):
            a = math.radians(-60 + 120 * k / 14)
            p, d = head_point(0.52, a, 0.018)
            band.append(p)
        band = np.array(band)
        parts.append(tube(band, np.full(len(band), 0.008), gold, sides=6))
        for k, (a, hgt) in enumerate(((-0.6, 0.05), (0.0, 0.075), (0.6, 0.05))):
            p, d = head_point(0.52, a, 0.018)
            tip = p + d * 0.02 + np.array([0, hgt, 0])
            parts.append(tube(np.array([p, (p + tip) / 2, tip]), np.array([0.014, 0.009, 0.002]), gold, sides=6))
            parts.append(ellipsoid(p + d * 0.012 + np.array([0, 0.012, 0]), (0.009, 0.009, 0.006),
                                   ((1.0, 0.2, 0.35), (0.3, 0.8, 1.0), (0.2, 0.95, 0.55))[k], sides=8, rings=6))
    elif style == "twintail":                               # kuyruk bağları (fiyonk)
        for side in (-1, 1):
            p, d = head_point(1.05, side * 1.95, 0.02)
            for lobe in (-1, 1):
                c = p + np.array([0, 0.02 * lobe, 0]) + d * 0.01
                parts.append(ellipsoid(c + np.array([0, 0.018 * lobe, 0]), (0.014, 0.024, 0.02), (0.1, 0.09, 0.13),
                                       sides=10, rings=8))
    elif style == "bob":                                    # yıldız toka
        p, d = head_point(0.95, 1.2, 0.02)
        parts.append(ellipsoid(p, (0.022, 0.022, 0.01), (1.0, 0.85, 0.3), sides=10, rings=6))
    return merge(parts)


# Fizikli saç zincirleri: (kafaya göre kök noktası, kafaya göre dinlenme yönü, boy, düğüm, yarıçap/genişlik, tür)
def hair_chains(des):
    style = des["style"]
    chains = []
    if style == "long":
        for k in range(9):
            ph = math.pi + (k - 4) * 0.3
            p, d = head_point(1.55, ph, 0.024)
            out = np.array([d[0] * 0.18, -1.0, d[2] * 0.12])
            chains.append(dict(anchor=p, rest=out / np.linalg.norm(out), length=0.64, nodes=8,
                               width=(0.11, 0.04), kind="ribbon", stiff=0.05))
        for side in (-1, 1):                              # önden omuza dökülen uzun tutamlar
            p, d = head_point(1.45, side * 1.35, 0.02)
            chains.append(dict(anchor=p, rest=np.array([side * 0.15, -1.0, 0.25]), length=0.5, nodes=7,
                               width=(0.05, 0.015), kind="ribbon", stiff=0.06))
    elif style == "twintail":
        for side in (-1, 1):
            p, d = head_point(1.05, side * 1.95, 0.03)
            chains.append(dict(anchor=p, rest=np.array([side * 0.3, -0.94, -0.12]), length=0.64, nodes=9,
                               radius=(0.04, 0.062, 0.008), kind="tube", stiff=0.035))
        for k in range(5):                                # ense
            ph = math.pi + (k - 2) * 0.4
            p, d = head_point(1.7, ph, 0.02)
            chains.append(dict(anchor=p, rest=np.array([d[0] * 0.2, -1.0, d[2] * 0.3]), length=0.16, nodes=4,
                               width=(0.06, 0.02), kind="ribbon", stiff=0.12))
    else:                                                 # küt saç + yan at kuyruğu
        for k in range(11):
            ph = math.radians(62 + k * 23.6)
            p, d = head_point(1.28, ph, 0.024)
            out = np.array([d[0] * 0.28, -1.0, d[2] * 0.28])
            chains.append(dict(anchor=p, rest=out / np.linalg.norm(out), length=0.19, nodes=4,
                               width=(0.07, 0.02), kind="ribbon", stiff=0.14))
        p, d = head_point(1.05, 1.95, 0.03)
        chains.append(dict(anchor=p, rest=np.array([0.28, -0.94, -0.14]), length=0.42, nodes=7,
                           radius=(0.03, 0.046, 0.006), kind="tube", stiff=0.04))
    for ch in chains:
        ch["anchor"] = np.asarray(ch["anchor"], float)
        r = np.asarray(ch["rest"], float)
        ch["rest"] = r / np.linalg.norm(r)
    return chains


SKIRT_RIBS, SKIRT_NODES = 18, 3
SKIRT_TOP = np.array([0.0, 0.1, 0.0])                     # pelvis'e göre bel halkası
SKIRT_R = (0.108, 0.088)


def skirt_rest():
    """Etek kaburgalarının pelvis uzayında kök noktaları ve dinlenme yönleri."""
    a = np.linspace(0, 2 * math.pi, SKIRT_RIBS, endpoint=False)
    anchors = np.stack([SKIRT_R[0] * np.sin(a), np.full_like(a, SKIRT_TOP[1]), SKIRT_R[1] * np.cos(a)], 1)
    outward = np.stack([np.sin(a), np.zeros_like(a), np.cos(a) * 0.85], 1)
    dirs = outward * math.sin(math.radians(28)) + np.array([0, -math.cos(math.radians(28)), 0])
    return anchors, dirs / np.linalg.norm(dirs, axis=1, keepdims=True), 0.2


def body_parts(des):
    """Eklemlere bağlı katı parçalar: [(eklem, mesh)] (mesh eklem uzayında)."""
    top, acc, skin = des["top"], des["accent"], SKIN
    parts = []
    parts.append(("pelvis", ellipsoid((0, 0.02, 0.0), (0.105, 0.085, 0.082), top)))
    parts.append(("spine", lathe([0.0, 0.05, 0.1, 0.15], [0.095, 0.088, 0.09, 0.1], top, sx=1.0, sz=0.78)))
    parts.append(("spine", lathe([0.02, 0.0], [0.104, 0.104], acc, sx=1.0, sz=0.8)))          # bel bandı
    parts.append(("chest", ellipsoid((0, 0.05, 0.0), (0.118, 0.1, 0.085), top)))
    parts.append(("chest", ellipsoid((0, 0.1, 0.0), (0.13, 0.05, 0.075), top)))                 # omuz hattı
    for side in (-1, 1):                                  # kurdele (göğüste fiyonk)
        parts.append(("chest", ellipsoid((0.028 * side, 0.1, 0.08), (0.026, 0.017, 0.012), acc, sides=10, rings=8)))
        parts.append(("chest", ellipsoid((0.012 * side, 0.07, 0.083), (0.008, 0.026, 0.006), acc, sides=8, rings=6)))
    parts.append(("chest", ellipsoid((0, 0.1, 0.086), (0.011, 0.011, 0.01), shade(acc, 0.8), sides=8, rings=6)))
    neck = capsule(0.1, 0.028, 0.028, skin, sides=12, rings=4)
    neck.V += np.array([0, 0.08, 0], np.float32)
    parts.append(("neck", neck))
    parts.append(("head", head_mesh(skin)))
    for s in ("l", "r"):
        parts.append((f"shoulder_{s}", ellipsoid((0, -0.02, 0), (0.05, 0.05, 0.048), top, sides=14, rings=10)))
        parts.append((f"shoulder_{s}", capsule(UPPER_ARM, 0.034, 0.029, skin, sides=12)))
        parts.append((f"elbow_{s}", capsule(FORE_ARM - 0.03, 0.029, 0.024, skin, sides=12)))
        glove = des["gloves"]
        parts.append((f"wrist_{s}", ellipsoid((0, -0.038, 0.004), (0.025, 0.046, 0.033), glove, sides=12, rings=10)))
        parts.append((f"wrist_{s}", ellipsoid((0, -0.006, 0.0), (0.026, 0.016, 0.028), shade(glove, 0.95),
                                               sides=10, rings=6)))
        parts.append((f"hip_{s}", capsule(THIGH, 0.058, 0.043, skin, sides=14)))
        socks = des["socks"]
        sock_len = 0.2 if des["style"] == "twintail" else 0.03
        if sock_len > 0.05:
            m = capsule(sock_len, 0.05, 0.045, socks, sides=14, rings=6)
            m.V[:, 1] -= THIGH - sock_len
            parts.append((f"hip_{s}", m))
        parts.append((f"knee_{s}", capsule(SHIN - 0.05, 0.044, 0.031, socks, sides=14, bulge=0.012)))
        parts.append((f"ankle_{s}", ellipsoid((0, -0.02, 0.035), (0.042, 0.04, 0.085), des["shoes"], sides=14, rings=10)))
        parts.append((f"ankle_{s}", ellipsoid((0, -0.052, 0.035), (0.044, 0.012, 0.088), (0.95, 0.95, 0.95), sides=14,
                                             rings=6)))
    return parts


# ---------------------------------------------------------------- dinamik ağlar

def chain_mesh(ch, pts, head_center, color):
    k = len(pts)
    u = np.linspace(0, 1, k)
    if ch["kind"] == "tube":
        r0, r1, r2 = ch["radius"]
        v = np.clip((u - 0.3) / 0.7, 0, 1)
        radii = np.where(u < 0.3, r0 + (r1 - r0) * np.sin(u / 0.3 * math.pi / 2), r1 + (r2 - r1) * v ** 2.2)
        return tube(pts, radii, color, sides=10)
    w0, w1 = ch["width"]
    widths = w0 + (w1 - w0) * u
    widths = widths * (1 - u ** 3) + 0.004
    out = pts - head_center
    out[:, 1] *= 0.3
    return ribbon(pts, widths, out, 0.012, color)


def skirt_mesh(nodes, des):
    """nodes: (kaburga, düğüm, 3) -> pileli etek yüzeyi (etek + etek ucu şeridi)."""
    R, N = nodes.shape[:2]
    rows = []
    for i in range(N - 1):                                # düğümler arası ara halkalar
        for t in np.linspace(0, 1, 3, endpoint=False):
            rows.append(nodes[:, i] * (1 - t) + nodes[:, i + 1] * t)
    rows.append(nodes[:, -1])
    rows = np.array(rows)                                 # (satır, kaburga, 3)
    center = rows.mean(axis=1, keepdims=True)
    # pile: her kaburganın arasına içeri çekilmiş bir sütun
    mid = (rows + np.roll(rows, -1, axis=1)) / 2
    mid = center + (mid - center) * 0.93
    grid = np.stack([rows, mid], axis=2).reshape(len(rows), R * 2, 3)
    V = grid.reshape(-1, 3)
    F = grid_faces(len(rows), R * 2)
    rr = np.repeat(np.arange(len(rows)), R * 2)
    hem = rr >= len(rows) - 2
    C = np.where(hem[:, None], np.asarray(des["hem"], np.float32), np.asarray(des["skirt"], np.float32))
    inside = np.repeat(center[:, 0], R * 2, axis=0)
    F = fix_winding(V, F, inside[F].mean(axis=1))
    return Mesh(V, F, C)


# ---------------------------------------------------------------- render

_VERT = """
#version 330
uniform mat4 model;
uniform mat4 viewproj;
uniform mat3 nmat;
in vec3 in_pos; in vec3 in_n; in vec3 in_col; in vec2 in_uv;
out vec3 v_n; out vec3 v_col; out vec2 v_uv; out vec3 v_obj; out vec3 v_world;
void main() {
    vec4 w = model * vec4(in_pos, 1.0);
    gl_Position = viewproj * w;
    v_n = nmat * in_n; v_col = in_col; v_uv = in_uv; v_obj = in_pos; v_world = w.xyz;
}
"""

_FRAG = """
#version 330
uniform vec3 light; uniform vec3 cam_pos; uniform vec3 rim_col; uniform float rim_k;
uniform vec3 shade_tint; uniform float spec_k; uniform int use_face; uniform sampler2D face;
uniform float face_cell; uniform float face_z; uniform float exposure;
in vec3 v_n; in vec3 v_col; in vec2 v_uv; in vec3 v_obj; in vec3 v_world;
out vec4 color;
void main() {
    vec3 n = normalize(v_n);
    if (!gl_FrontFacing) n = -n;
    vec3 V = normalize(cam_pos - v_world);
    vec3 base = v_col;
    float lit = smoothstep(-0.06, 0.1, dot(n, light));
    if (use_face == 1) {
        vec2 uv = vec2((face_cell + clamp(v_uv.x, 0.0, 1.0)) / 5.0, v_uv.y);
        vec4 f = texture(face, uv);
        float front = smoothstep(face_z, face_z + 0.03, v_obj.z);
        float inside = step(0.0, v_uv.x) * step(v_uv.x, 1.0) * step(0.0, v_uv.y) * step(v_uv.y, 1.0);
        base = mix(base, f.rgb, f.a * front * inside);
        lit = max(lit, 0.55);
    }
    vec3 c = mix(base * shade_tint, base, lit);
    float rim = pow(1.0 - max(dot(n, V), 0.0), 3.0) * rim_k;
    c += rim_col * rim;
    vec3 H = normalize(light + V);
    c += vec3(pow(max(dot(n, H), 0.0), 18.0) * spec_k);
    color = vec4(min(c * exposure, 1.0), 1.0);
}
"""

_OUT_VERT = """
#version 330
uniform mat4 model; uniform mat4 viewproj; uniform mat3 nmat; uniform float width; uniform vec3 cam_pos;
in vec3 in_pos; in vec3 in_n; in vec3 in_col;
out vec3 v_col;
void main() {
    vec4 w = model * vec4(in_pos, 1.0);
    vec3 n = normalize(nmat * in_n);
    w.xyz += n * width * length(cam_pos - w.xyz);
    gl_Position = viewproj * w;
    v_col = in_col;
}
"""

_OUT_FRAG = """
#version 330
uniform float dark; uniform vec3 tint;
in vec3 v_col;
out vec4 color;
void main() { color = vec4(mix(v_col * dark, tint, 0.2), 1.0); }
"""

_SHADOW_VERT = """
#version 330
uniform mat4 viewproj; uniform vec3 center; uniform vec2 radius;
in vec2 in_q;
out vec2 v_q;
void main() { v_q = in_q; gl_Position = viewproj * vec4(center + vec3(in_q.x * radius.x, 0.001, in_q.y * radius.y), 1.0); }
"""

_SHADOW_FRAG = """
#version 330
uniform float strength;
in vec2 v_q;
out vec4 color;
void main() { float r = length(v_q); float a = strength * (1.0 - smoothstep(0.35, 1.0, r)); color = vec4(0.0, 0.0, 0.0, a); }
"""


def perspective(fov_deg, aspect, near=0.1, far=100.0):
    f = 1 / math.tan(math.radians(fov_deg) / 2)
    return np.array([[f / aspect, 0, 0, 0], [0, f, 0, 0],
                     [0, 0, (far + near) / (near - far), 2 * far * near / (near - far)], [0, 0, -1, 0]])


def look_at(eye, target, up=(0, 1, 0)):
    eye, target, up = map(lambda v: np.asarray(v, float), (eye, target, up))
    f = target - eye
    f /= np.linalg.norm(f)
    s = np.cross(f, up)
    s /= np.linalg.norm(s)
    u = np.cross(s, f)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


class Dancer:
    """Bir dansçının statik parçaları, yüz dokusu ve fizik zincir tanımları."""

    def __init__(self, name):
        self.name = name
        self.des = DESIGNS[name]
        self.parts = body_parts(self.des)
        self.parts.append(("head", build_static_hair(self.des)))
        self.chains = hair_chains(self.des)
        self.face = face_atlas(self.des["eyes"], brow=shade(self.des["hair"], 0.45))
        self.skirt = skirt_rest()


class ToonRenderer:
    """Dansçıları şeffaf RGBA katmana çizer (moderngl + EGL)."""

    def __init__(self, width, height, samples=4):
        self.ctx = moderngl.create_standalone_context(backend="egl")
        self.w, self.h = width, height
        self.fbo = self.ctx.framebuffer(
            color_attachments=[self.ctx.renderbuffer((width, height), 4, samples=samples)],
            depth_attachment=self.ctx.depth_renderbuffer((width, height), samples=samples))
        self.resolve = self.ctx.simple_framebuffer((width, height), components=4)
        self.prog = self.ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        self.oprog = self.ctx.program(vertex_shader=_OUT_VERT, fragment_shader=_OUT_FRAG)
        self.sprog = self.ctx.program(vertex_shader=_SHADOW_VERT, fragment_shader=_SHADOW_FRAG)
        q = np.array([[-1, -1], [1, -1], [1, 1], [-1, -1], [1, 1], [-1, 1]], "f4")
        self.shadow_vao = self.ctx.vertex_array(self.sprog, [(self.ctx.buffer(q.tobytes()), "2f", "in_q")])
        self.static = {}
        self.faces = {}
        self.dyn = {}

    def _vaos(self, mesh, key=None, dynamic=False):
        data = mesh.interleaved()
        if dynamic and key in self.dyn:
            vbo, ibo, cap_v, cap_i, vao, ovao = self.dyn[key]
            if data.nbytes <= cap_v and mesh.F.nbytes <= cap_i:
                vbo.orphan(cap_v)
                vbo.write(data.tobytes())
                ibo.orphan(cap_i)
                ibo.write(mesh.F.astype("i4").tobytes())
                return vao, ovao, mesh.F.size
        cap_v, cap_i = data.nbytes * (2 if dynamic else 1), mesh.F.nbytes * (2 if dynamic else 1)
        vbo = self.ctx.buffer(reserve=cap_v, dynamic=dynamic)
        vbo.write(data.tobytes())
        ibo = self.ctx.buffer(reserve=cap_i, dynamic=dynamic)
        ibo.write(mesh.F.astype("i4").tobytes())
        fmt = [(vbo, "3f 3f 3f 2f", "in_pos", "in_n", "in_col", "in_uv")]
        vao = self.ctx.vertex_array(self.prog, fmt, index_buffer=ibo, index_element_size=4)
        ovao = self.ctx.vertex_array(self.oprog, [(vbo, "3f 3f 3f 8x", "in_pos", "in_n", "in_col")],
                                     index_buffer=ibo, index_element_size=4)
        if dynamic:
            self.dyn[key] = (vbo, ibo, cap_v, cap_i, vao, ovao)
        return vao, ovao, mesh.F.size

    def prepare(self, dancer):
        if dancer.name in self.static:
            return
        items = []
        for joint, mesh in dancer.parts:
            vao, ovao, n = self._vaos(mesh)
            is_head = joint == "head" and mesh.UV.any()
            items.append((joint, vao, ovao, n, is_head))
        self.static[dancer.name] = items
        tex = self.ctx.texture((dancer.face.shape[1], dancer.face.shape[0]), 4, dancer.face.tobytes())
        tex.build_mipmaps()
        tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        tex.repeat_x = tex.repeat_y = False
        self.faces[dancer.name] = tex

    def begin(self, view, proj, cam_pos, rim_col, rim_k=0.55, light=(-0.45, 0.75, 0.55), exposure=1.0):
        self.fbo.use()
        self.ctx.clear(0, 0, 0, 0)
        self.vp = proj @ view
        self.cam_pos = np.asarray(cam_pos, float)
        L = np.asarray(light, float)
        self.prog["light"].value = tuple(L / np.linalg.norm(L))
        self.prog["cam_pos"].value = tuple(self.cam_pos)
        self.prog["rim_col"].value = tuple(rim_col)
        self.prog["rim_k"].value = rim_k
        self.prog["exposure"].value = exposure
        self.prog["viewproj"].write(self.vp.T.astype("f4").tobytes())
        self.oprog["viewproj"].write(self.vp.T.astype("f4").tobytes())
        self.oprog["cam_pos"].value = tuple(self.cam_pos)
        self.sprog["viewproj"].write(self.vp.T.astype("f4").tobytes())

    def shadow(self, center, radius=(0.32, 0.2), strength=0.35):
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = (moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
        self.sprog["center"].value = tuple(center)
        self.sprog["radius"].value = tuple(radius)
        self.sprog["strength"].value = strength
        self.shadow_vao.render(moderngl.TRIANGLES)
        self.ctx.disable(moderngl.BLEND)

    def _draw(self, vao, ovao, n, model, face=None, face_cell=0.0, spec=0.0, outline=0.0016, tint=(0, 0, 0)):
        nmat = np.linalg.inv(model[:3, :3]).T
        mb = model.T.astype("f4").tobytes()
        nb = nmat.T.astype("f4").tobytes()
        self.ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        # dış çizgi: şişirilmiş kabuğun arka yüzleri
        self.ctx.front_face = "ccw"
        self.ctx.cull_face = "front"
        self.oprog["model"].write(mb)
        self.oprog["nmat"].write(nb)
        self.oprog["width"].value = outline
        self.oprog["dark"].value = 0.5
        self.oprog["tint"].value = tuple(tint)
        ovao.render(moderngl.TRIANGLES, vertices=n)
        self.ctx.cull_face = "back"
        self.ctx.disable(moderngl.CULL_FACE)
        self.prog["model"].write(mb)
        self.prog["nmat"].write(nb)
        self.prog["spec_k"].value = spec
        self.prog["shade_tint"].value = (0.74, 0.68, 0.82)
        if face is not None:
            face.use(0)
            self.prog["face"].value = 0
            self.prog["use_face"].value = 1
            self.prog["face_cell"].value = float(face_cell)
            self.prog["face_z"].value = 0.02
        else:
            self.prog["use_face"].value = 0
        vao.render(moderngl.TRIANGLES, vertices=n)

    def draw_dancer(self, dancer, Rw, Pw, face_cell, chain_pts, skirt_nodes, key):
        self.prepare(dancer)
        tex = self.faces[dancer.name]
        for joint, vao, ovao, n, is_head in self.static[dancer.name]:
            M = np.eye(4)
            M[:3, :3] = Rw[joint] * (HEAD_S if joint == "head" else 1.0)
            M[:3, 3] = Pw[joint]
            spec = 0.12 if joint == "head" and not is_head else 0.0
            self._draw(vao, ovao, n, M, face=tex if is_head else None, face_cell=face_cell, spec=spec)
        head_c = Pw["head"] + Rw["head"] @ HEAD_C * HEAD_S
        I = np.eye(4)
        for k, (ch, pts) in enumerate(zip(dancer.chains, chain_pts)):
            mesh = chain_mesh(ch, pts, head_c, dancer.des["hair"])
            vao, ovao, n = self._vaos(mesh, key=(key, "chain", k), dynamic=True)
            self._draw(vao, ovao, n, I, spec=0.1)
        if skirt_nodes is not None:
            mesh = skirt_mesh(skirt_nodes, dancer.des)
            vao, ovao, n = self._vaos(mesh, key=(key, "skirt"), dynamic=True)
            self._draw(vao, ovao, n, I)

    def finish(self):
        self.ctx.copy_framebuffer(self.resolve, self.fbo)
        data = np.frombuffer(self.resolve.read(components=4, alignment=1), np.uint8)
        return data.reshape(self.h, self.w, 4)[::-1].copy()


def rest_chains(dancer, Rw, Pw):
    """Zincirleri dinlenme şekliyle (fiziksiz) dünya uzayına yerleştirir."""
    out = []
    for ch in dancer.chains:
        a = Pw["head"] + Rw["head"] @ ch["anchor"] * HEAD_S
        d = Rw["head"] @ ch["rest"]
        seg = ch["length"] / (ch["nodes"] - 1)
        out.append(np.array([a + d * seg * i for i in range(ch["nodes"])]))
    return out


def rest_skirt(dancer, Rw, Pw):
    anchors, dirs, length = dancer.skirt
    A = Pw["pelvis"] + anchors @ Rw["pelvis"].T
    D = dirs @ Rw["pelvis"].T
    return np.stack([A + D * length * i / (SKIRT_NODES - 1) for i in range(SKIRT_NODES)], axis=1)
