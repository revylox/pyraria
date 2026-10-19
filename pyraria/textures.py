"""Procedural pixel-art generation.

Everything is drawn at "art resolution" (one art pixel = 2x2 screen pixels,
like Terraria) and scaled up with nearest-neighbour filtering.
"""
import math
import zlib

import numpy as np
import pygame

from . import terrain_tex as TT
from . import tiles as T

ART = 2  # screen pixels per art pixel


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def rng_for(*key):
    return np.random.default_rng(zlib.crc32(repr(key).encode()))


def sh(c, f):
    return np.clip(np.asarray(c[:3], np.float32) * f, 0, 255)


def mix(a, b, k):
    a = np.asarray(a[:3], np.float32)
    b = np.asarray(b[:3], np.float32)
    return np.clip(a + (b - a) * k, 0, 255)


def to_surface(rgb, alpha=None, scale=ART):
    """rgb: (h, w, 3) float/uint8, alpha: (h, w) -> scaled pygame Surface."""
    h, w = rgb.shape[:2]
    a = np.full((h, w), 255, np.uint8) if alpha is None else \
        np.asarray(alpha, np.uint8)
    rgba = np.dstack([np.clip(rgb, 0, 255).astype(np.uint8), a])
    surf = pygame.image.frombuffer(np.ascontiguousarray(rgba).tobytes(),
                                   (w, h), "RGBA")
    if scale != 1:
        surf = pygame.transform.scale(surf, (w * scale, h * scale))
    return surf.convert_alpha() if pygame.display.get_surface() else surf


def template(rows, palette, scale=ART):
    """Build a surface from a list of strings and a char->colour palette."""
    h, w = len(rows), max(len(r) for r in rows)
    rgb = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), np.uint8)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            if ch in palette:
                col = palette[ch]
                rgb[y, x] = col[:3]
                alpha[y, x] = col[3] if len(col) > 3 else 255
    return to_surface(rgb, alpha, scale)


def art_surface(w, h):
    return pygame.Surface((w, h), pygame.SRCALPHA)


def upscale(surf, k=ART):
    s = pygame.transform.scale(surf, (surf.get_width() * k,
                                      surf.get_height() * k))
    return s.convert_alpha() if pygame.display.get_surface() else s


def outline_surface(surf, color=(0, 0, 0)):
    """Add a 1 art-pixel outline around opaque pixels of an art surface."""
    w, h = surf.get_size()
    out = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    mask = pygame.mask.from_surface(surf)
    sil = mask.to_surface(setcolor=color + (255,), unsetcolor=(0, 0, 0, 0))
    for dx, dy in ((0, 1), (2, 1), (1, 0), (1, 2)):
        out.blit(sil, (dx, dy))
    out.blit(surf, (1, 1))
    return out


# ---------------------------------------------------------------------------
# Assets container
# ---------------------------------------------------------------------------
class Assets:
    """All generated graphics. Must be created after the display exists."""

    def __init__(self):
        self.tile = {}      # tid -> [mask][variant] Surface 16x16
        self.wall = {}      # wid -> [mask][variant]
        self.build_blocks()
        self.build_walls()
        self.build_special()
        self.build_trees()
        self.build_furniture()
        self.build_misc()

    # ------------------------------------------------------------ blocks
    def build_blocks(self):
        """16x16 full-resolution block textures: 16 edge masks x 3 variants
        for every block type."""
        self.block_icon = {}
        for d in T.TILES:
            if d.kind != "block":
                continue
            bases = [TT.block_art(d, rng_for("tile", d.id, v))
                     for v in range(3)]
            masks = []
            for m in range(16):
                vs = []
                for v in range(3):
                    rgb, alpha = TT.apply_edges(bases[v][0], bases[v][1], m,
                                                d, rng_for("edge", d.id, v, m))
                    vs.append(to_surface(rgb, alpha, 1))
                masks.append(vs)
            self.tile[d.id] = masks
            rgb, alpha = TT.apply_edges(bases[0][0], bases[0][1], 0, d,
                                        rng_for("icon", d.id))
            self.block_icon[d.id] = to_surface(rgb, alpha, 2)

    def build_walls(self):
        self.wall_icon = {}
        for w in T.WALLS[1:]:
            bases = [TT.wall_art(w, rng_for("wall", w.id, v))
                     for v in range(3)]
            self.wall[w.id] = [[to_surface(TT.wall_edges(bases[v], m,
                                                         w.color), None, 1)
                                for v in range(3)] for m in range(16)]
            self.wall_icon[w.id] = to_surface(
                TT.wall_edges(bases[0], 0, w.color), None, 2)

    # ----------------------------------------------------------- special
    def build_special(self):
        # platforms: index = left_connected | right_connected << 1
        wood = T.TILES[T.PLATFORM].color
        self.platform = []
        for m in range(4):
            art = np.zeros((8, 8, 3), np.float32)
            alpha = np.zeros((8, 8), np.float32)
            art[0:3, :] = wood
            art[0, :] = sh(wood, 1.15)
            art[2, :] = sh(wood, 0.7)
            alpha[0:3, :] = 255
            for x in (1, 5):
                art[1, x] = sh(wood, 0.75)
            if not m & 1:      # left end bracket
                art[3:5, 1] = sh(wood, 0.6)
                alpha[3:5, 1] = 255
                alpha[0, 0] = 0
            if not m & 2:
                art[3:5, 6] = sh(wood, 0.6)
                alpha[3:5, 6] = 255
                alpha[0, 7] = 0
            self.platform.append(to_surface(art, alpha))
        self.platform_icon = pygame.transform.scale(self.platform[0], (32, 32))

        tp = {"y": (255, 220, 60), "Y": (255, 250, 150), "W": (255, 255, 240),
              "o": (240, 120, 30), "w": (150, 100, 60), "d": (100, 64, 40)}
        torch = ["...o....",
                 "..oyo...",
                 "..yYy...",
                 "..yWy...",
                 "...w....",
                 "...w....",
                 "...d....",
                 "...d...."]
        self.torch_icon = template(torch, tp, 3)
        # placed / held torches: the stick is static (baked into chunks),
        # the flame is drawn every frame from FLAME_FRAMES so it flickers
        base = template(["." * 8] * 4 + torch[4:], tp)
        self.torch = [base, base, base, base]
        # leaning versions for wall-side torches
        left = pygame.Surface((16, 16), pygame.SRCALPHA)
        left.blit(pygame.transform.rotate(base, -18), (-2, -1))
        right = pygame.Surface((16, 16), pygame.SRCALPHA)
        right.blit(pygame.transform.rotate(base, 18), (2, -1))
        self.torch[T.TORCH_LEFT] = left
        self.torch[T.TORCH_RIGHT] = right
        self.torch_flames = [template(f, tp) for f in FLAME_FRAMES]
        fw, fh = self.torch_flames[0].get_size()
        # where each torch frame's flame goes: its bottom centre sits on the
        # top of the stick
        self.flame_offset = []
        for stick in self.torch:
            ys = [y for y in range(16) for x in range(16)
                  if stick.get_at((x, y)).a]
            top = min(ys)
            xs = [x for x in range(16) if stick.get_at((x, top)).a]
            cx = (min(xs) + max(xs) + 1) / 2
            self.flame_offset.append((round(cx - fw / 2), top - fh))
        self.anim_tick = 0           # set by the renderer every frame

        # seams drawn where a block touches a block of another material
        self.seams = []
        for m in range(16):
            surf = pygame.Surface((16, 16), pygame.SRCALPHA)
            for bit, rect in ((1, (0, 0, 16, 1)), (2, (15, 0, 1, 16)),
                              (4, (0, 15, 16, 1)), (8, (0, 0, 1, 16))):
                if m & bit:
                    surf.fill((0, 0, 0, 95), rect)
            self.seams.append(surf)
        # crack overlays (three mining stages, each adds more fractures)
        self.cracks = []
        surf = pygame.Surface((16, 16), pygame.SRCALPHA)
        rng = rng_for("crack")
        for stage in range(3):
            for _ in range(2 + stage):
                x, y = 7.5 + rng.uniform(-2, 2), 7.5 + rng.uniform(-2, 2)
                a = rng.uniform(0, math.tau)
                for _k in range(int(rng.integers(3, 6))):
                    nx = max(0, min(15, x + math.cos(a) * 2.5))
                    ny = max(0, min(15, y + math.sin(a) * 2.5))
                    pygame.draw.line(surf, (18, 12, 8, 200), (x, y), (nx, ny))
                    x, y = nx, ny
                    a += rng.uniform(-0.9, 0.9)
            self.cracks.append(surf.copy())

        # plants (6 variants each)
        self.plant = {}
        for tid in (T.PLANT, T.PLANT_CORRUPT, T.PLANT_JUNGLE,
                    T.PLANT_MUSHROOM):
            self.plant[tid] = [self._plant_art(tid, v) for v in range(6)]
        self.vine = {}
        for tid in (T.VINE, T.VINE_JUNGLE):
            self.vine[tid] = [self._vine_art(tid, v) for v in range(4)]
        sap = art_surface(8, 8)
        pygame.draw.line(sap, (90, 140, 60), (3, 7), (3, 3))
        pygame.draw.rect(sap, (80, 190, 70), (1, 2, 2, 2))
        pygame.draw.rect(sap, (80, 190, 70), (4, 1, 2, 2))
        pygame.draw.rect(sap, (60, 160, 60), (3, 0, 1, 2))
        self.sapling = upscale(sap)

    def _plant_art(self, tid, v):
        rng = rng_for("plant", tid, v)
        s = art_surface(8, 8)
        if tid == T.PLANT:
            greens = [(40, 160, 50), (70, 200, 70), (30, 130, 45)]
            for i in range(rng.integers(3, 5)):
                x = int(rng.integers(0, 8))
                h = int(rng.integers(2, 6))
                col = greens[i % 3]
                pygame.draw.line(s, col, (x, 7), (x + int(rng.integers(-1, 2)),
                                                  7 - h))
            if v >= 4:
                fc = [(240, 60, 60), (250, 220, 60), (180, 90, 240),
                      (255, 255, 255)][int(rng.integers(0, 4))]
                fx = int(rng.integers(2, 6))
                pygame.draw.line(s, (60, 170, 60), (fx, 7), (fx, 3))
                s.fill(fc, (fx - 1, 2, 3, 1))
                s.fill(fc, (fx, 1, 1, 3))
                s.fill((255, 240, 150), (fx, 2, 1, 1))
        elif tid == T.PLANT_CORRUPT:
            cols = [(110, 90, 170), (150, 130, 210), (80, 60, 120)]
            for i in range(rng.integers(3, 5)):
                x = int(rng.integers(0, 8))
                h = int(rng.integers(2, 7))
                pygame.draw.line(s, cols[i % 3], (x, 7),
                                 (x + int(rng.integers(-2, 3)), 7 - h))
            if v >= 4:
                pygame.draw.rect(s, (90, 70, 140), (2, 3, 4, 2))
                pygame.draw.rect(s, (160, 140, 220), (3, 3, 2, 1))
                pygame.draw.line(s, (200, 190, 220), (4, 5), (4, 7))
        elif tid == T.PLANT_JUNGLE:
            cols = [(110, 200, 30), (70, 160, 30), (150, 230, 60)]
            for i in range(rng.integers(2, 4)):
                x = int(rng.integers(1, 7))
                h = int(rng.integers(3, 7))
                c = cols[i % 3]
                pygame.draw.line(s, c, (x, 7), (x, 7 - h))
                pygame.draw.line(s, c, (x, 7 - h), (x + (1 if i % 2 else -1) *
                                                    2, 8 - h))
        else:  # glowing mushroom
            x = int(rng.integers(1, 5))
            pygame.draw.line(s, (200, 210, 240), (x + 1, 7), (x + 1, 4))
            pygame.draw.rect(s, (70, 110, 255), (x, 2, 3, 2))
            s.fill((150, 190, 255), (x + 1, 2, 1, 1))
            if v % 2:
                pygame.draw.line(s, (200, 210, 240), (6, 7), (6, 6))
                s.fill((70, 110, 255), (5, 5, 3, 1))
        return upscale(s)

    def _vine_art(self, tid, v):
        rng = rng_for("vine", tid, v)
        s = art_surface(8, 8)
        c = T.TILES[tid].color
        dark = tuple(int(k * 0.7) for k in c)
        x = 3 + int(rng.integers(-1, 2))
        pts = [(x + (1 if (y + v) % 4 < 2 else 0), y) for y in range(8)]
        for (px, py) in pts:
            s.fill(c, (px, py, 1, 1))
        for _ in range(2):
            ly = int(rng.integers(0, 7))
            lx = pts[ly][0] + (1 if rng.random() < .5 else -2)
            s.fill(c, (lx, ly, 2, 1))
            s.fill(dark, (lx, ly + 1, 2, 1))
        return upscale(s)

    # ------------------------------------------------------------- trees
    def build_trees(self):
        self.trunk = {}
        self.canopy = {}
        self.branch = {}
        self.root = {}
        for tid in (T.TREE, T.TREE_EBON, T.TREE_JUNGLE, T.TREE_BOREAL,
                    T.TREE_PALM, T.TREE_MUSHROOM):
            d = T.TILES[tid]
            kind = {T.TREE_PALM: "palm", T.TREE_MUSHROOM: "mushroom"}.get(
                tid, "tree")
            self.trunk[tid] = [to_surface(*TT.bark(
                d.color, rng_for("trunk", tid, v), kind), 1) for v in range(3)]
            self.canopy[tid] = [self._canopy(tid, d.accent, v)
                                for v in range(3)]
            self.branch[tid] = [self._branch(tid, d.accent, side)
                                for side in (0, 1)]
            self.root[tid] = [to_surface(*TT.root(d.color, side), 1)
                              for side in (0, 1)]
        # cactus
        cg = T.TILES[T.CACTUS].color
        art = np.zeros((8, 8, 3), np.float32)
        alpha = np.zeros((8, 8), np.float32)
        art[:, 1:7] = cg
        art[:, 1] = art[:, 6] = sh(cg, 0.6)
        art[:, 3] = sh(cg, 1.25)
        alpha[:, 1:7] = 255
        for y in (1, 5):
            art[y, 2] = (230, 230, 190)
            art[y + 1, 5] = (230, 230, 190)
        self.cactus = to_surface(art, alpha)
        top = art.copy()
        ta = alpha.copy()
        ta[0, 1] = ta[0, 6] = 0
        ta[1, 1] = ta[1, 6] = 0
        top[1, 2] = top[1, 5] = sh(cg, 0.6)
        top[0, 2:6] = sh(cg, 0.6)
        self.cactus_top = to_surface(top, ta)
        arm = art_surface(8, 16)
        # arm sprite (for the right side): goes out then up
        pygame.draw.rect(arm, sh(cg, 0.6), (0, 9, 6, 5))
        pygame.draw.rect(arm, cg, (0, 10, 5, 3))
        pygame.draw.rect(arm, sh(cg, 0.6), (2, 2, 5, 12))
        pygame.draw.rect(arm, cg, (3, 3, 3, 10))
        pygame.draw.line(arm, sh(cg, 1.25), (4, 3), (4, 11))
        arm_s = upscale(arm)
        self.cactus_arm = [pygame.transform.flip(arm_s, True, False), arm_s]

    def _leaf_blob(self, w, h, centers, pal, rng):
        """Draw overlapping circles with outline, shading and leaf noise."""
        s = art_surface(w, h)
        dark, mid, light, outline = pal
        for (cx, cy, r) in centers:
            pygame.draw.circle(s, outline, (cx, cy), r + 1)
        for (cx, cy, r) in centers:
            pygame.draw.circle(s, dark, (cx, cy), r)
        for (cx, cy, r) in centers:
            pygame.draw.circle(s, mid, (cx - 1, cy - 1), max(1, r - 1))
        for (cx, cy, r) in centers:
            pygame.draw.circle(s, light, (cx - r // 3, cy - r // 3),
                               max(1, r // 3))
        # leaf noise
        px = pygame.surfarray.pixels3d(s)
        pa = pygame.surfarray.pixels_alpha(s)
        ys = rng.integers(0, h, w * h // 6)
        xs = rng.integers(0, w, w * h // 6)
        for x, y in zip(xs, ys):
            if pa[x, y] and tuple(px[x, y]) in (tuple(mid), tuple(light)):
                px[x, y] = dark if rng.random() < 0.6 else light
        del px, pa
        return s

    def _canopy(self, tid, accent, v):
        rng = rng_for("canopy", tid, v)
        a = np.asarray(accent, np.float32)
        if tid in (T.TREE, T.TREE_EBON, T.TREE_JUNGLE):
            if tid == T.TREE_JUNGLE:
                w, h, big = 52, 44, 12
            else:
                w, h, big = 42, 38, 10
            cx0, cy0 = w // 2, h // 2 + 1
            centers = [(cx0, cy0, big)]
            n = 7 if tid != T.TREE_JUNGLE else 9
            for i in range(n):
                ang = math.pi + (i + rng.uniform(-0.3, 0.3)) * math.pi / (n - 1)
                r = int(rng.integers(5, 8)) + (1 if tid == T.TREE_JUNGLE else 0)
                dist = big - r // 3 + rng.uniform(-1, 2)
                cx = int(cx0 + math.cos(ang) * dist * 1.25)
                cy = int(cy0 + math.sin(ang) * dist * 0.95)
                cx = max(r + 1, min(w - r - 2, cx))
                cy = max(r + 1, min(h - r - 2, cy))
                centers.append((cx, cy, r))
            for side in (-1, 1):
                r = int(rng.integers(5, 7))
                centers.append((cx0 + side * (big - 1), cy0 + 5, r))
            centers.append((cx0, h - 9, 7))
            pal = (tuple(sh(a, 0.72).astype(int)), tuple(a.astype(int)),
                   tuple(sh(a, 1.3).astype(int)),
                   tuple(sh(a, 0.42).astype(int)))
            s = self._leaf_blob(w, h, centers, pal, rng)
        elif tid == T.TREE_BOREAL:
            w, h = 30, 44
            s = art_surface(w, h)
            dark = tuple(sh(a, 0.75).astype(int))
            mid = tuple(a.astype(int))
            out = tuple(sh(a, 0.45).astype(int))
            for i in range(4):
                top = 2 + i * 9
                half = 6 + i * 3
                pts = [(w // 2, top), (w // 2 + half, top + 14),
                       (w // 2 - half, top + 14)]
                pygame.draw.polygon(s, out, pts)
                pts2 = [(w // 2, top + 1), (w // 2 + half - 2, top + 13),
                        (w // 2 - half + 2, top + 13)]
                pygame.draw.polygon(s, dark, pts2)
                pygame.draw.polygon(s, mid, [(w // 2, top + 2),
                                             (w // 2 + 2, top + 12),
                                             (w // 2 - half + 3, top + 12)])
                # snow on the slope
                for k in range(half - 1):
                    sx = w // 2 - k
                    sy = top + 1 + int(k * 14 / half)
                    if rng.random() < 0.75:
                        s.fill((240, 248, 255), (sx, sy, 1, 1))
                        s.fill((240, 248, 255), (w // 2 + k, sy, 1, 1))
        elif tid == T.TREE_PALM:
            w, h = 44, 26
            s = art_surface(w, h)
            cx, cy = w // 2, 10
            out = tuple(sh(a, 0.45).astype(int))
            for ang in (-170, -140, -110, -70, -40, -10, 200, 20):
                r = math.radians(ang)
                pts = []
                for k in range(16):
                    t = k / 15
                    px = cx + math.cos(r) * t * 20
                    py = cy - math.sin(r) * t * 9 + (t ** 2) * 12
                    pts.append((px, py))
                pygame.draw.lines(s, out, False, pts, 4)
                pygame.draw.lines(s, tuple(a.astype(int)), False, pts, 2)
                pygame.draw.lines(s, tuple(sh(a, 1.3).astype(int)), False,
                                  pts[:8], 1)
            pygame.draw.circle(s, (110, 80, 40), (cx - 2, cy + 3), 2)
            pygame.draw.circle(s, (110, 80, 40), (cx + 2, cy + 3), 2)
        else:  # mushroom cap
            w, h = 36, 18
            s = art_surface(w, h)
            col = tuple(a.astype(int))
            pygame.draw.ellipse(s, tuple(sh(a, 0.5).astype(int)),
                                (0, 0, w, h * 2 - 6))
            pygame.draw.ellipse(s, col, (1, 1, w - 2, h * 2 - 8))
            s.fill((0, 0, 0, 0), (0, h - 3, w, h))
            pygame.draw.rect(s, tuple(sh(a, 0.6).astype(int)),
                             (2, h - 4, w - 4, 2))
            for _ in range(6):
                x = int(rng.integers(4, w - 6))
                y = int(rng.integers(3, h - 7))
                s.fill((170, 200, 255), (x, y, 2, 2))
        return upscale(s)

    def _branch(self, tid, accent, side):
        a = np.asarray(accent, np.float32)
        rng = rng_for("branch", tid, side)
        s = art_surface(14, 12)
        trunkc = T.TILES[tid].color
        pygame.draw.line(s, sh(trunkc, 0.8), (13, 8), (7, 6), 2)
        if tid == T.TREE_BOREAL:
            pal = (tuple(sh(a, 0.75).astype(int)), tuple(a.astype(int)),
                   (240, 248, 255), tuple(sh(a, 0.45).astype(int)))
        else:
            pal = (tuple(sh(a, 0.72).astype(int)), tuple(a.astype(int)),
                   tuple(sh(a, 1.3).astype(int)),
                   tuple(sh(a, 0.42).astype(int)))
        leaf = self._leaf_blob(14, 12, [(5, 5, 4), (8, 4, 3), (4, 7, 3)], pal,
                               rng)
        s.blit(leaf, (0, 0))
        s = upscale(s)
        return s if side == 0 else pygame.transform.flip(s, True, False)

    # --------------------------------------------------------- furniture
    def build_furniture(self):
        self.furniture = {}
        wood = (168, 122, 82)
        wd = tuple(sh(wood, 0.6).astype(int))
        wl = tuple(sh(wood, 1.15).astype(int))
        # work bench 2x1
        s = art_surface(16, 8)
        pygame.draw.rect(s, wd, (0, 1, 16, 3))
        pygame.draw.rect(s, wood, (1, 1, 14, 2))
        s.fill(wl, (1, 1, 14, 1))
        for x in (1, 13):
            pygame.draw.rect(s, wd, (x, 4, 2, 4))
            s.fill(wood, (x, 4, 1, 4))
        pygame.draw.line(s, wd, (3, 5), (12, 5))
        self.furniture[T.WORKBENCH] = upscale(s)
        # furnace 3x2
        s = art_surface(24, 16)
        st, sd, sl = (124, 124, 130), (70, 70, 76), (160, 160, 168)
        pygame.draw.ellipse(s, sd, (1, 0, 22, 26))
        pygame.draw.ellipse(s, st, (2, 1, 20, 24))
        s.fill((0, 0, 0, 0), (0, 15, 24, 12))
        pygame.draw.rect(s, sd, (1, 13, 22, 3))
        pygame.draw.rect(s, st, (2, 13, 20, 2))
        for (x, y) in ((5, 4), (14, 3), (9, 8), (17, 9), (4, 10)):
            pygame.draw.line(s, sd, (x, y), (x + 3, y))
            pygame.draw.line(s, sl, (x, y + 1), (x + 3, y + 1))
        pygame.draw.rect(s, sd, (8, 8, 8, 7))
        pygame.draw.rect(s, (255, 120, 30), (9, 9, 6, 6))
        pygame.draw.rect(s, (255, 210, 60), (10, 11, 4, 4))
        s.fill((255, 250, 200), (11, 13, 2, 2))
        self.furniture[T.FURNACE] = upscale(s)
        # chest 2x2
        s = art_surface(16, 16)
        gold, gd = (230, 190, 60), (150, 110, 30)
        pygame.draw.rect(s, wd, (0, 3, 16, 13))
        pygame.draw.rect(s, wood, (1, 4, 14, 11))
        pygame.draw.rect(s, wl, (1, 4, 14, 1))
        pygame.draw.rect(s, wd, (0, 8, 16, 1))
        for x in (1, 13):
            pygame.draw.rect(s, gold, (x, 4, 2, 11))
            pygame.draw.line(s, gd, (x + 1, 4), (x + 1, 14))
        pygame.draw.rect(s, gd, (6, 7, 4, 4))
        pygame.draw.rect(s, gold, (7, 8, 2, 2))
        pygame.draw.rect(s, wd, (1, 2, 14, 2))
        self.furniture[T.CHEST] = upscale(s)
        # door 1x3 closed / open
        s = art_surface(8, 24)
        pygame.draw.rect(s, wd, (1, 0, 6, 24))
        pygame.draw.rect(s, wood, (2, 1, 4, 22))
        for y in (7, 15):
            pygame.draw.line(s, wd, (2, y), (5, y))
            pygame.draw.line(s, wl, (2, y + 1), (5, y + 1))
        pygame.draw.line(s, wl, (2, 1), (2, 22))
        s.fill((230, 190, 60), (5, 11, 1, 2))
        self.furniture[T.DOOR_CLOSED] = upscale(s)
        s = art_surface(8, 24)
        pygame.draw.rect(s, wd, (0, 0, 2, 24))
        pygame.draw.polygon(s, wd, [(1, 0), (7, 2), (7, 22), (1, 24)])
        pygame.draw.polygon(s, wood, [(2, 1), (6, 3), (6, 21), (2, 23)])
        pygame.draw.line(s, wl, (2, 2), (2, 21))
        self.furniture[T.DOOR_OPEN] = upscale(s)
        # demon altar 3x2
        s = art_surface(24, 16)
        dk, md, lt = (50, 36, 70), (96, 72, 130), (150, 120, 200)
        pygame.draw.polygon(s, dk, [(0, 16), (3, 8), (8, 9), (12, 3), (16, 9),
                                    (21, 8), (24, 16)])
        pygame.draw.polygon(s, md, [(2, 15), (4, 9), (9, 10), (12, 5),
                                    (15, 10), (20, 9), (22, 15)])
        pygame.draw.line(s, lt, (12, 5), (9, 10))
        pygame.draw.line(s, lt, (4, 9), (3, 14))
        for x in (5, 12, 19):
            s.fill((210, 80, 255), (x, 11, 1, 1))
        pygame.draw.polygon(s, dk, [(1, 8), (3, 2), (5, 8)])
        pygame.draw.polygon(s, dk, [(19, 8), (21, 2), (23, 8)])
        self.furniture[T.DEMON_ALTAR] = upscale(s)
        self.furniture_icon = {}
        for tid, surf in self.furniture.items():
            w, h = surf.get_size()
            k = min(36 / w, 36 / h, 1.0)
            self.furniture_icon[tid] = pygame.transform.scale(
                surf, (max(1, int(w * k)), max(1, int(h * k))))

    # --------------------------------------------------------------- misc
    def build_misc(self):
        self.white = pygame.Surface((16, 16))
        self.white.fill((255, 255, 255))

    def flame(self, x=0, y=0):
        """Current flame frame of the torch at tile (x, y); every torch
        flickers through FLAME_SEQ with its own phase."""
        i = self.anim_tick // FLAME_TICKS + (x * 7 + y * 13) % len(FLAME_SEQ)
        return self.torch_flames[FLAME_SEQ[i % len(FLAME_SEQ)]]


# ---------------------------------------------------------------------------
# Torch flame animation (5x5 art, bottom row rests on the stick)
# ---------------------------------------------------------------------------
FLAME_FRAMES = [
    [".....",
     "..o..",
     ".oyo.",
     ".yYy.",
     ".yWy."],
    [".....",
     "...o.",
     "..yo.",
     ".yYy.",
     ".yWy."],
    ["...o.",
     "..oy.",
     ".oYo.",
     ".yYy.",
     ".yWy."],
    ["..o..",
     "..y..",
     ".oYo.",
     ".yYy.",
     ".yWy."],
    [".o...",
     ".yo..",
     ".oYo.",
     ".yYy.",
     ".yWy."],
    [".....",
     ".o...",
     ".oy..",
     ".yYy.",
     ".yWy."],
    [".....",
     ".....",
     ".oyo.",
     "oyYyo",
     ".yWy."],
]
# frame order: the tip sways and stretches irregularly, like a real flame
FLAME_SEQ = [0, 3, 0, 1, 2, 1, 0, 6, 0, 5, 4, 5, 0, 3, 2, 1, 0, 5, 0, 6]
FLAME_TICKS = 5          # render frames per flame frame


# ---------------------------------------------------------------------------
# Pixel-art templates for items and UI
# ---------------------------------------------------------------------------
BAR = [
    "................",
    "................",
    "................",
    "................",
    "....oooooooo....",
    "...oHHHHHHHHo...",
    "..oHOOOOOOOOOo..",
    ".oHOOOOOOOOOOdo.",
    ".oOOOOOOOOOOddo.",
    ".oddddddddddddo.",
    "..oooooooooooo..",
    "................",
]
ORE_CHUNK = [
    "............",
    "....ooooo...",
    "...oSSHSSo..",
    "..oSOOSSSSo.",
    ".oSSOOSSOSo.",
    ".oSSSSSOOSo.",
    ".oSOSSSOSSo.",
    "..oSSSSSSo..",
    "...oooooo...",
]
ACORN = [
    "............",
    ".....w......",
    "...oooooo...",
    "..oddddddo..",
    "..oDDDDDDo..",
    "...oBBBBo...",
    "...oBHBBo...",
    "...oBBBBo...",
    "....oBBo....",
    ".....oo.....",
]
CACTUS_ITEM = [
    "............",
    ".....oo.....",
    "....oGGo....",
    "....oGLo.o..",
    ".o..oGLooGo.",
    "oGo.oGLoGGo.",
    "oGGooGLGGo..",
    ".oGGGGLoo...",
    "..ooGGLo....",
    "....oGLo....",
    "....oGGo....",
    ".....oo.....",
]
HEART = [
    "..ooo.ooo..",
    ".oRRRoRRRo.",
    "oRHHRRRRRRo",
    "oRHRRRRRRRo",
    "oRRRRRRRRdo",
    ".oRRRRRRdo.",
    "..oRRRRdo..",
    "...oRRdo...",
    "....odo....",
    ".....o.....",
]
STAR = [
    ".....o.....",
    "....oHo....",
    "....oBo....",
    "oooHBBBoooo",
    "oHBBBBBBBBo",
    ".oBBBBBBBo.",
    "..oBBBBBo..",
    "..oBBoBBo..",
    ".oBBo.oBBo.",
    ".oBo...oBo.",
    ".oo.....oo.",
]
CURSOR = [
    "oo..........",
    "oHoo........",
    "oHOOoo......",
    ".oHOOOoo....",
    ".oHOOOOOoo..",
    "..oHOOOOOOo.",
    "..oHOOOOoo..",
    "...oHOOOo...",
    "...oHOoOOo..",
    "....oo.oOOo.",
    "........oOo.",
    ".........o..",
]
BUBBLE = [
    "..oooo..",
    ".oWWBBo.",
    "oWBBBBBo",
    "oBBBBBBo",
    "oBBBBBBo",
    "oBBBBBdo",
    ".oBBBdo.",
    "..oooo..",
]
SHIELD = [
    "oooooooooooo",
    "oHHHHHHHHHHo",
    "oHSSSSSSSSdo",
    "oHSSSSSSSSdo",
    "oHSSSSSSSSdo",
    "oHSSSSSSSSdo",
    ".oSSSSSSSdo.",
    ".oSSSSSSSdo.",
    "..oSSSSSdo..",
    "...oSSSdo...",
    "....oSdo....",
    ".....oo.....",
]
TRASH = [
    "....oooo....",
    ".oooooooooo.",
    ".oHHHHHHHHo.",
    ".oooooooooo.",
    "..oSSdSSdo..",
    "..oSSdSSdo..",
    "..oSSdSSdo..",
    "..oSSdSSdo..",
    "..oSSdSSdo..",
    "..oSSdSSdo..",
    "...oooooo...",
]


def metal_palette(c):
    c = np.asarray(c, np.float32)
    return {"o": tuple(sh(c, 0.42).astype(int)),
            "O": tuple(c.astype(int)),
            "H": tuple(sh(c, 1.35).astype(int)),
            "d": tuple(sh(c, 0.7).astype(int)),
            "W": tuple(c.astype(int)),
            "w": (150, 104, 62), "g": (180, 140, 60)}


# ---------------------------------------------------------------------------
# Procedural tool sprites (handle + head, outlined like Terraria item art)
# ---------------------------------------------------------------------------
WOOD_HANDLE = (150, 104, 62)
WOOD_HANDLE_DARK = (104, 70, 40)


def _handle(s, a, b):
    pygame.draw.line(s, WOOD_HANDLE_DARK, a, b, 3)
    pygame.draw.line(s, WOOD_HANDLE, a, (b[0], b[1]), 1)


def tool_art(kind, metal):
    metal = np.asarray(metal, np.float32)
    mid = tuple(int(v) for v in metal)
    hi = tuple(int(v) for v in sh(metal, 1.35))
    lo = tuple(int(v) for v in sh(metal, 0.72))
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    if kind == "pickaxe":
        _handle(s, (2, 13), (10, 5))
        cx, cy = 3.5, 12.5
        for y in range(16):
            for x in range(16):
                dx, dy = x + 0.5 - cx, cy - (y + 0.5)
                d = math.hypot(dx, dy)
                ang = math.degrees(math.atan2(dy, dx))
                if 7.6 <= d <= 10.4 and -6 <= ang <= 96:
                    col = hi if d > 9.5 else (lo if d < 8.4 else mid)
                    s.set_at((x, y), col)
    elif kind == "axe":
        _handle(s, (2, 13), (11, 4))
        pts = [(7, 3), (9, 0), (14, 1), (15, 5), (12, 8), (9, 6)]
        pygame.draw.polygon(s, mid, pts)
        pygame.draw.lines(s, hi, False, [(9, 0), (14, 1), (15, 5)])
        pygame.draw.line(s, lo, (9, 6), (12, 8))
        _handle(s, (8, 7), (11, 4))
    elif kind == "hammer":
        _handle(s, (2, 13), (9, 6))
        c = (10.5, 4.5)
        u = (0.7071, 0.7071)
        v = (0.7071, -0.7071)
        pts = []
        for su, sv in ((-5, -2.6), (5, -2.6), (5, 2.6), (-5, 2.6)):
            pts.append((c[0] + u[0] * su + v[0] * sv,
                        c[1] + u[1] * su + v[1] * sv))
        pygame.draw.polygon(s, mid, pts)
        pygame.draw.line(s, hi, pts[0], pts[3])
        pygame.draw.line(s, lo, pts[1], pts[2])
    elif kind == "sword":
        pygame.draw.line(s, lo, (5, 10), (13, 2), 3)
        pygame.draw.line(s, mid, (5, 10), (13, 2), 2)
        pygame.draw.line(s, hi, (6, 9), (13, 2), 1)
        pygame.draw.line(s, (170, 130, 60), (3, 8), (7, 12), 2)
        _handle(s, (2, 13), (5, 10))
    out = outline_surface(s, (36, 22, 14))
    return upscale(out)
