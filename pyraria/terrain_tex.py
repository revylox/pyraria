"""High-detail terrain textures: every tile is a full 16x16 pixel image.

Each material is built from a few layers:
  * a low-frequency tint field (periodic value noise) for large variation,
  * a height field that is embossed with a top-left light so clods, stones,
    bricks and planks get highlights and shadows,
  * fine grain / speckles and material features (ore nuggets, wood grain,
    ice streaks, glowing hellstone veins ...),
  * quantisation to a small number of shades so it stays pixel art.
Exposed sides get a two-pixel rim and rounded corners; grassy tiles grow
individual blades over their exposed edges.
"""
import math

import numpy as np

N = 16
_YS, _XS = np.mgrid[0:N, 0:N].astype(np.float32)
_YC, _XC = _YS + 0.5, _XS + 0.5


# ---------------------------------------------------------------------------
# primitives
# ---------------------------------------------------------------------------
def vnoise(rng, cells, size=N):
    """Smooth periodic value noise in [0, 1] of shape (size, size)."""
    g = rng.random((cells, cells)).astype(np.float32)
    t = np.arange(size, dtype=np.float32) * (cells / size)
    i0 = t.astype(np.int32) % cells
    i1 = (i0 + 1) % cells
    f = t - np.floor(t)
    f = f * f * (3 - 2 * f)
    top = g[i0][:, i0] * (1 - f)[None, :] + g[i0][:, i1] * f[None, :]
    bot = g[i1][:, i0] * (1 - f)[None, :] + g[i1][:, i1] * f[None, :]
    return top * (1 - f)[:, None] + bot * f[:, None]


def emboss(h, k):
    """Lighting factor for a height field lit from the top-left."""
    return 1.0 + k * (h - np.roll(np.roll(h, 1, 0), 1, 1))


def quant(f, step=0.05):
    return np.round(f / step) * step


def paint(color, f):
    c = np.asarray(color[:3], np.float32)
    return np.clip(c[None, None, :] * f[..., None], 0, 255)


def blend(rgb, color, k):
    """Mix rgb (h,w,3) towards colour by per-pixel factor k (h,w)."""
    c = np.asarray(color[:3], np.float32)
    k = np.clip(k, 0, 1)[..., None]
    return rgb * (1 - k) + c[None, None, :] * k


def voronoi(rng, n):
    """Periodic Voronoi: (region id, distance-to-border) for n seeds."""
    pts = rng.random((n, 2)).astype(np.float32) * N
    dx = np.abs(_XC[..., None] - pts[:, 0])
    dx = np.minimum(dx, N - dx)
    dy = np.abs(_YC[..., None] - pts[:, 1])
    dy = np.minimum(dy, N - dy)
    d = np.sqrt(dx * dx + dy * dy)
    s = np.sort(d, axis=2)
    return d.argmin(axis=2), s[..., 1] - s[..., 0]


def _grain(rng, f, dark=0.86, light=1.08, pd=0.10, pl=0.08):
    g = rng.random((N, N))
    f = f.copy()
    f[g < pd] *= dark
    f[g > 1 - pl] *= light
    return f


# ---------------------------------------------------------------------------
# materials -> (rgb (16,16,3) float, alpha (16,16) float)
# ---------------------------------------------------------------------------
def dirt(color, rng, clods=0.35):
    low = vnoise(rng, 3)
    f = 0.9 + 0.16 * low
    h = np.clip((vnoise(rng, 6) * 0.7 + vnoise(rng, 8) * 0.3 - 0.45) * 4,
                0, 1)
    f = f * emboss(h, clods) + h * 0.05
    f = _grain(rng, f)
    for _ in range(rng.integers(3, 6)):          # small pebbles
        x, y = (int(v) for v in rng.integers(0, N, 2))
        w = int(rng.integers(1, 3))
        for i in range(w):
            f[y, (x + i) % N] = 1.18 if i == 0 else 1.1
            f[(y + 1) % N, (x + i) % N] = 0.74
    return paint(color, quant(f)), None


def cobble(color, rng, seeds=6, mortar=0.58, bevel=0.55, tint=(0.88, 1.08)):
    rid, edge = voronoi(rng, seeds)
    t = rng.uniform(*tint, seeds)[rid]
    h = np.clip(edge, 0, 2.6) / 2.6
    f = t * emboss(h, bevel) * (0.95 + 0.1 * vnoise(rng, 8))
    f = _grain(rng, f, 0.9, 1.06, 0.08, 0.06)
    f[edge < 0.85] = mortar
    # a hairline crack or two
    for _ in range(rng.integers(0, 3)):
        x, y = rng.uniform(0, N, 2)
        a = rng.uniform(0, math.tau)
        for _k in range(int(rng.integers(3, 6))):
            xi, yi = int(x) % N, int(y) % N
            if edge[yi, xi] > 1.4:
                f[yi, xi] = 0.72
            x += math.cos(a)
            y += math.sin(a)
            a += rng.uniform(-0.6, 0.6)
    return paint(color, quant(f)), None


def sand(color, rng):
    ripple = np.sin((_YS * 0.95 + _XS * 0.3 + 4 * vnoise(rng, 2)) * 1.25)
    f = 1 + 0.08 * (vnoise(rng, 4) - 0.5) + 0.035 * ripple
    g = rng.random((N, N))
    f[g < 0.14] *= 0.88
    f[g > 0.9] *= 1.08
    f[g < 0.025] *= 0.82
    return paint(color, quant(f, 0.04)), None


def strata(color, rng):
    v = _YS + 3.2 * vnoise(rng, 2) + 1.2 * vnoise(rng, 4)
    band = (np.floor(v / 3) % 4).astype(np.int32)
    levels = np.array([1.07, 0.99, 0.88, 0.96], np.float32)
    f = levels[band]
    f = f * emboss(band.astype(np.float32) * -0.25, 0.6)
    f *= 0.96 + 0.08 * vnoise(rng, 8)
    for _ in range(rng.integers(2, 5)):             # pits
        x, y = (int(v) for v in rng.integers(0, N, 2))
        f[y, x] = 0.7
        f[(y + 1) % N, x] = 1.12
    return paint(color, quant(f)), None


def snow(color, rng):
    h = vnoise(rng, 4) * 0.7 + vnoise(rng, 8) * 0.3
    f = (0.95 + 0.06 * h) * emboss(h, 0.5)
    rgb = paint(color, quant(f, 0.03))
    rgb = blend(rgb, (150, 178, 226), (1.0 - f) * 3.2)
    g = rng.random((N, N))
    rgb[g > 0.965] = (255, 255, 255)
    return rgb, None


def ice(color, rng):
    f = 1.0 + 0.06 * (vnoise(rng, 3) - 0.5)
    rgb = paint(color, f)
    d = (_XS - _YS * 0.75 + 5 * vnoise(rng, 2)) % 9
    rgb = blend(rgb, (255, 255, 255), np.where(d < 1.1, 0.6, np.where(
        d < 2.3, 0.28, 0.0)))
    rgb = np.where((d > 5.0)[..., None] & (d < 6.2)[..., None], rgb * 0.9,
                   rgb)
    # a crack
    x, y = rng.uniform(2, 14, 2)
    a = rng.uniform(0, math.tau)
    dark = np.asarray(color, np.float32) * 0.72
    for _ in range(int(rng.integers(4, 8))):
        xi, yi = int(x) % N, int(y) % N
        rgb[yi, xi] = dark
        rgb[(yi + 1) % N, xi] = blend(rgb[(yi + 1) % N, xi][None, None],
                                      (255, 255, 255), np.array([[0.4]]))[0, 0]
        x += math.cos(a)
        y += math.sin(a)
        a += rng.uniform(-0.7, 0.7)
    g = rng.random((N, N))
    rgb[g > 0.975] = (255, 255, 255)
    return rgb, np.full((N, N), 238, np.float32)


def ore(color, accent, rng):
    rgb, _ = cobble(color, rng, seeds=5)
    acc = np.asarray(accent, np.float32)
    dark = np.asarray(color, np.float32) * 0.5
    for _ in range(int(rng.integers(3, 5))):
        cx, cy = rng.uniform(2.5, 13.5, 2)
        r = rng.uniform(1.5, 2.5)
        d = np.hypot(_XC - cx, _YC - cy)
        ins = d <= r
        ring = (d > r) & (d <= r + 0.85)
        shade = 1.22 - 0.32 * ((_XC - cx) + (_YC - cy)) / r
        shade = quant(shade, 0.08)
        rgb[ring] = dark
        rgb[ins] = np.clip(acc[None, :] * shade[ins][:, None], 0, 255)
        hx, hy = int(cx - r * 0.45), int(cy - r * 0.45)
        if 0 <= hx < N and 0 <= hy < N:
            rgb[hy, hx] = np.clip(acc * 1.5 + 40, 0, 255)
    return rgb, None


def brick(color, rng, mortar=0.5):
    f = np.ones((N, N), np.float32)
    noise = 0.95 + 0.1 * vnoise(rng, 8)
    for row in range(4):
        y0 = row * 4
        off = 0 if row % 2 == 0 else 4
        for b in range(2):
            x0 = off + b * 8
            t = rng.uniform(0.88, 1.1)
            for dx in range(7):
                x = (x0 + dx) % N
                for dy in range(3):
                    k = t * noise[y0 + dy, x]
                    if dy == 0:
                        k *= 1.16
                    elif dy == 2:
                        k *= 0.86
                    if dx == 0:
                        k *= 1.07
                    elif dx == 6:
                        k *= 0.88
                    f[y0 + dy, x] = k
            f[y0:y0 + 3, (x0 + 7) % N] = mortar
        f[y0 + 3, :] = mortar
    f = _grain(rng, f, 0.92, 1.05, 0.06, 0.05)
    return paint(color, quant(f)), None


def planks(color, rng):
    f = np.ones((N, N), np.float32)
    for p in range(4):
        y0 = p * 4
        t = rng.uniform(0.9, 1.08)
        grain = vnoise(rng, 4)[0]          # 1-D grain along x
        for y in range(y0, y0 + 3):
            for x in range(N):
                g = grain[(x + y * 3) % N]
                k = t * (0.9 if g > 0.62 else 1.04 if g < 0.25 else 1.0)
                f[y, x] = k
        f[y0, :] *= 1.13
        f[y0 + 2, :] *= 0.94
        f[y0 + 3, :] = 0.58
        jx = int(rng.integers(1, N - 1))
        f[y0:y0 + 3, jx] = 0.66
        f[y0:y0 + 3, (jx + 1) % N] *= 1.08
        if rng.random() < 0.35:                    # knot
            kx = int(rng.integers(2, N - 3))
            f[y0 + 1, kx:kx + 2] = 0.7
            f[y0 + 2, kx] *= 0.85
    return paint(color, quant(f)), None


def hellstone(color, accent, rng):
    rid, edge = voronoi(rng, 6)
    h = np.clip(edge, 0, 2.6) / 2.6
    f = rng.uniform(0.85, 1.15, 6)[rid] * emboss(h, 0.6)
    rgb = paint(color, quant(f))
    glow = np.clip(1.6 - edge, 0, 1)
    rgb = blend(rgb, accent, glow * 1.2)
    rgb = blend(rgb, (255, 236, 150), np.clip(0.8 - edge, 0, 1) * 1.1)
    return rgb, None


def obsidian(color, rng):
    rid, edge = voronoi(rng, 5)
    ang = rng.uniform(0, math.tau, 5)[rid]
    f = 0.85 + 0.35 * (np.cos(ang) * (_XS / N) + np.sin(ang) * (_YS / N))
    f = quant(f, 0.07)
    rgb = paint(color, f)
    rgb = blend(rgb, (150, 112, 220), np.clip((f - 1.05) * 3, 0, 0.7))
    rgb[edge < 0.7] = np.asarray(color, np.float32) * 0.55
    g = rng.random((N, N))
    rgb[g > 0.98] = (190, 160, 240)
    return rgb, None


def cloud(color, rng):
    h = vnoise(rng, 3) * 0.7 + vnoise(rng, 6) * 0.3
    f = (0.96 + 0.06 * h) * emboss(h, 0.7)
    rgb = paint(color, quant(f, 0.03))
    rgb = blend(rgb, (176, 192, 228), (1.0 - f) * 3.5)
    return rgb, None


def glass(color, rng):
    rgb = np.empty((N, N, 3), np.float32)
    rgb[:] = color
    alpha = np.full((N, N), 64, np.float32)
    s = _XS + _YS
    for lo, hi, a in ((5, 7, 175), (8, 9, 120), (19, 20, 120)):
        m = (s >= lo) & (s < hi)
        rgb[m] = (255, 255, 255)
        alpha[m] = a
    return rgb, alpha


STYLE = {
    "speckle": lambda d, r: dirt(d.color, r),
    "grass": lambda d, r: dirt(d.color, r),
    "cobble": lambda d, r: cobble(d.color, r),
    "sand": lambda d, r: sand(d.color, r),
    "strata": lambda d, r: strata(d.color, r),
    "snow": lambda d, r: snow(d.color, r),
    "ice": lambda d, r: ice(d.color, r),
    "ore": lambda d, r: ore(d.color, d.accent, r),
    "brick": lambda d, r: brick(d.color, r),
    "planks": lambda d, r: planks(d.color, r),
    "hellstone": lambda d, r: hellstone(d.color, d.accent, r),
    "obsidian": lambda d, r: obsidian(d.color, r),
    "cloud": lambda d, r: cloud(d.color, r),
    "glass": lambda d, r: glass(d.color, r),
}


def block_art(tdef, rng):
    rgb, alpha = STYLE.get(tdef.style, STYLE["speckle"])(tdef, rng)
    if alpha is None:
        alpha = np.full((N, N), 255, np.float32)
    return rgb.astype(np.float32), alpha.astype(np.float32)


# ---------------------------------------------------------------------------
# edges
# ---------------------------------------------------------------------------
def _sides(mask):
    return (not mask & 1, not mask & 2, not mask & 4, not mask & 8)


def _side_index(side, depth, i):
    """(y, x) of the pixel at `depth` from exposed `side`, position i."""
    if side == 0:
        return depth, i
    if side == 1:
        return i, N - 1 - depth
    if side == 2:
        return N - 1 - depth, i
    return i, depth


def _round_corners(rgb, alpha, sides, outline, radius=3.0):
    top, right, bottom, left = sides
    for cond, cy, cx in ((top and left, 0, 0), (top and right, 0, 1),
                         (bottom and left, 1, 0), (bottom and right, 1, 1)):
        if not cond:
            continue
        for j in range(4):
            for i in range(4):
                d = math.hypot(radius - (i + 0.5), radius - (j + 0.5))
                y = j if cy == 0 else N - 1 - j
                x = i if cx == 0 else N - 1 - i
                if i >= radius or j >= radius:
                    continue
                if d > radius:
                    alpha[y, x] = 0
                elif d > radius - 1.0:
                    rgb[y, x] = outline


def apply_edges(rgb, alpha, mask, tdef, rng):
    rgb = rgb.copy()
    alpha = alpha.copy()
    sides = _sides(mask)
    base = np.asarray(tdef.color, np.float32)
    if tdef.style == "glass":
        for s, exp in enumerate(sides):
            if exp:
                for i in range(N):
                    y, x = _side_index(s, 0, i)
                    rgb[y, x] = (230, 242, 255)
                    alpha[y, x] = 215
                    y, x = _side_index(s, 1, i)
                    alpha[y, x] = max(alpha[y, x], 110)
        return rgb, alpha
    if tdef.style == "grass":
        g = np.asarray(tdef.accent, np.float32)
        outline = g * 0.55
        for s, exp in enumerate(sides):
            if not exp:
                continue
            for i in range(N):
                length = int(rng.integers(4, 7)) if s != 2 else \
                    int(rng.integers(2, 4))
                if rng.random() < 0.15 and s != 2:
                    length += 1
                for d in range(length):
                    y, x = _side_index(s, d, i)
                    if d == 0:
                        c = outline
                    elif d == 1:
                        c = g * (1.28 if (i + int(rng.integers(0, 3))) % 3
                                 else 1.14)
                    elif d == 2:
                        c = g * 1.06
                    elif d == length - 1:
                        c = g * 0.72
                    else:
                        c = g * 0.9
                    rgb[y, x] = np.clip(c, 0, 255)
                y, x = _side_index(s, length, i)
                if 0 <= y < N and 0 <= x < N:
                    rgb[y, x] *= 0.78          # shadow under the blades
        _round_corners(rgb, alpha, sides, outline)
        return rgb, alpha
    outline = base * (0.62 if tdef.style == "cloud" else 0.48)
    for s, exp in enumerate(sides):
        if not exp:
            continue
        for i in range(N):
            y, x = _side_index(s, 0, i)
            rgb[y, x] = outline
            y, x = _side_index(s, 1, i)
            rgb[y, x] *= 0.8
    _round_corners(rgb, alpha, sides, outline,
                   4.0 if tdef.style == "cloud" else 3.0)
    return rgb, alpha


# ---------------------------------------------------------------------------
# walls
# ---------------------------------------------------------------------------
def wall_art(wdef, rng):
    st, c = wdef.style, wdef.color
    if st == "cobble":
        rgb, _ = cobble(c, rng, seeds=5, mortar=0.62, bevel=0.4)
    elif st == "brick":
        rgb, _ = brick(c, rng, mortar=0.6)
    elif st == "planks":
        rgb, _ = planks(c, rng)
    elif st == "snow":
        rgb, _ = snow(c, rng)
    elif st == "ice":
        rgb, _ = ice(c, rng)
    elif st == "strata":
        rgb, _ = strata(c, rng)
    else:
        rgb, _ = dirt(c, rng, clods=0.25)
    return rgb


def wall_edges(rgb, mask, color):
    rgb = rgb.copy()
    oc = np.asarray(color, np.float32) * 0.5
    for s, exp in enumerate(_sides(mask)):
        if exp:
            for i in range(N):
                y, x = _side_index(s, 0, i)
                rgb[y, x] = oc
                y, x = _side_index(s, 1, i)
                rgb[y, x] *= 0.78
    return rgb


# ---------------------------------------------------------------------------
# tree bark, roots, backdrop
# ---------------------------------------------------------------------------
def bark(color, rng, kind="tree"):
    c = np.asarray(color, np.float32)
    rgb = np.zeros((N, N, 3), np.float32)
    alpha = np.zeros((N, N), np.float32)
    x0, x1 = (4, 12) if kind == "mushroom" else (2, 14)
    w = x1 - x0
    xs = np.arange(x0, x1)
    # cylindrical shading: light on the left, dark on the right
    cyl = 1.12 - 0.34 * ((xs - x0) / (w - 1)) ** 1.4
    grooves = vnoise(rng, 4)
    for y in range(N):
        for k, x in enumerate(xs):
            f = cyl[k]
            if kind == "palm":
                if y % 6 in (0,):
                    f *= 0.72
                elif y % 6 == 1:
                    f *= 1.1
            elif kind == "mushroom":
                f *= 0.97 + 0.06 * ((x + y) % 3 == 0)
            else:
                g = grooves[y, (x * 3) % N]
                if g > 0.62:
                    f *= 0.74
                elif g < 0.22:
                    f *= 1.1
            rgb[y, x] = c * f
            alpha[y, x] = 255
    rgb[:, x0] = c * 0.5
    rgb[:, x1 - 1] = c * 0.45
    if kind == "tree" and rng.random() < 0.5:
        ky = int(rng.integers(3, 12))
        kx = int(rng.integers(x0 + 3, x1 - 4))
        rgb[ky, kx:kx + 2] = c * 0.55
        rgb[ky + 1, kx:kx + 2] = c * 0.7
        rgb[ky - 1, kx] = c * 1.15
    return np.clip(rgb, 0, 255), alpha


def root(color, side):
    c = np.asarray(color, np.float32)
    rgb = np.zeros((N, N, 3), np.float32)
    alpha = np.zeros((N, N), np.float32)
    for y in range(N):
        for x in range(N):
            # wedge rising towards the trunk side (right edge for side 0)
            top = 6 + (N - 1 - x) * 0.62
            if y >= top:
                f = 1.08 - 0.3 * (y - top) / max(1.0, N - top)
                rgb[y, x] = c * f
                alpha[y, x] = 255
                if y - top < 1.0:
                    rgb[y, x] = c * 0.5
    if side == 1:
        rgb = rgb[:, ::-1]
        alpha = alpha[:, ::-1]
    return rgb, alpha


def backdrop(color, rng, size=64):
    h = vnoise(rng, 4, size) * 0.6 + vnoise(rng, 8, size) * 0.3 + \
        vnoise(rng, 16, size) * 0.1
    rocks = np.clip((h - 0.42) * 3.5, 0, 1)
    f = (0.86 + 0.22 * h) * (1.0 + 0.45 * (rocks - np.roll(np.roll(
        rocks, 1, 0), 1, 1)))
    g = rng.random((size, size))
    f[g < 0.06] *= 0.85
    f[g > 0.96] *= 1.1
    f = quant(f, 0.05)
    c = np.asarray(color, np.float32)
    return np.clip(c[None, None, :] * f[..., None], 0, 255)
