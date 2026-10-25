"""SCP tarzı amblem geometrisi (birim yarıçap, y yukarı). Saf Python: hem 2D çizim (scp_intro.py)
hem de tesis kapısındaki 3D amblem (blender/scp_cinematic.py) aynı vektörden üretilir.

  dış halka   r 0.80-1.00, 120° aralıkla üç eşit parça (parçalar arasında 30° boşluk)
  oklar       halkadaki boşluklarda, merkeze bakan üç eşit ok (90°, 210°, 330°)
  iç halka    r 0.21-0.30, kesintisiz
"""
import math

ARROW_ANGLES = (90.0, 210.0, 330.0)
RING_IN, RING_OUT, GAP_DEG = 0.80, 1.00, 30.0
INNER_IN, INNER_OUT = 0.21, 0.30
SHAFT_OUT, SHAFT_IN, SHAFT_HALF = 0.97, 0.56, 0.062
HEAD_BASE, HEAD_HALF, HEAD_TIP = 0.60, 0.165, 0.36


def _pt(r, deg):
    a = math.radians(deg)
    return (r * math.cos(a), r * math.sin(a))


def arc(a0, a1, r_in, r_out, n=64):
    """Halka parçası: dış yay a0->a1, iç yay a1->a0 (kapalı çokgen, saat yönü tersine)."""
    outer = [_pt(r_out, a0 + (a1 - a0) * i / n) for i in range(n + 1)]
    inner = [_pt(r_in, a1 - (a1 - a0) * i / n) for i in range(n + 1)]
    return outer + inner


def arrow(deg):
    """Merkeze bakan ok: gövde + üçgen uç; deg doğrultusunda, uç merkeze yakın."""
    a = math.radians(deg)
    ux, uy = math.cos(a), math.sin(a)       # dışa doğru birim vektör
    px, py = -uy, ux                        # dik birim vektör

    def p(r, s):
        return (ux * r + px * s, uy * r + py * s)

    return [p(SHAFT_OUT, -SHAFT_HALF), p(SHAFT_OUT, SHAFT_HALF), p(HEAD_BASE, SHAFT_HALF),
            p(HEAD_BASE, HEAD_HALF), p(HEAD_TIP, 0.0), p(HEAD_BASE, -HEAD_HALF), p(HEAD_BASE, -SHAFT_HALF)]


def ring_arcs():
    """Dış halkanın üç eşit parçası (her biri 120 - GAP derece)."""
    half = GAP_DEG / 2
    return [arc(a + half, a + 120 - half, RING_IN, RING_OUT) for a in ARROW_ANGLES]


def shapes():
    """Dolu çokgenler (halka parçaları + oklar) ve iç halka yarıçapları."""
    return {"polygons": ring_arcs() + [arrow(a) for a in ARROW_ANGLES], "inner_ring": (INNER_IN, INNER_OUT)}


def check():
    """Simetri doğrulaması: parçalar ve oklar 120° döndürmede birbirinin aynısı olmalı."""
    def rot(poly, deg):
        c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
        return [(x * c - y * s, x * s + y * c) for x, y in poly]

    arcs, arrows = ring_arcs(), [arrow(a) for a in ARROW_ANGLES]
    for group in (arcs, arrows):
        for k in (1, 2):
            a, b = rot(group[0], 120 * k), group[k]
            err = max(math.hypot(x0 - x1, y0 - y1) for (x0, y0), (x1, y1) in zip(a, b))
            assert err < 1e-9, err
    return True


if __name__ == "__main__":
    print("simetri:", check())
