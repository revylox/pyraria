"""Terraria-style world generator (Corruption world).

Generates oceans, forest, snow, desert, jungle, two Corruption patches with
chasms, glowing-mushroom caves, floating islands, the dungeon, ores,
liquids and the underworld.  Contains no items, chests, pots or NPCs.
"""
import random
from collections import deque

import numpy as np

from . import tiles as T
from .config import WORLD_SIZES
from .noise import fractal_1d, fractal_2d
from .world import (World, build_tree, FOREST, OCEAN, DESERT, SNOW, JUNGLE,
                    CORRUPTION, WATER, LAVA)


class _Gen:
    def __init__(self, name, size, seed, progress):
        self.W, self.H = WORLD_SIZES[size]
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        self.prng = random.Random(seed)
        self.progress = progress
        self.world = World(self.W, self.H, name, seed)
        self.tiles = self.world.tiles
        self.walls = self.world.walls
        self.SX = self.W / 4200.0
        self.SY = self.H / 1200.0
        self.area = self.SX * self.SY

    # ---------------------------------------------------------------- utils
    def disc(self, cx, cy, r):
        W, H = self.W, self.H
        x0, x1 = max(0, int(cx - r)), min(W, int(cx + r) + 2)
        y0, y1 = max(0, int(cy - r)), min(H, int(cy + r) + 2)
        if x0 >= x1 or y0 >= y1:
            return None, None
        xs = np.arange(x0, x1)[:, None] - cx
        ys = np.arange(y0, y1)[None, :] - cy
        return (slice(x0, x1), slice(y0, y1)), (xs * xs + ys * ys) <= r * r

    def carve(self, cx, cy, r, wall=None):
        sl, m = self.disc(cx, cy, r)
        if sl is None:
            return
        sub = self.tiles[sl]
        sub[m & T.NATURAL[sub]] = T.AIR
        if wall is not None:
            ws = self.walls[sl]
            ws[m] = wall

    def convert(self, cx, cy, r, tid, only=None):
        sl, m = self.disc(cx, cy, r)
        if sl is None:
            return
        sub = self.tiles[sl]
        ok = T.NATURAL[sub] if only is None else np.isin(sub, only)
        sub[m & ok & (sub != T.AIR)] = tid

    def runner(self, x, y, strength, steps, tid, replace):
        """Random-walk blob placer (like Terraria's TileRunner)."""
        prng = self.prng
        dx, dy = prng.uniform(-1, 1), prng.uniform(-1, 1)
        s = strength
        for _ in range(steps):
            sl, m = self.disc(x, y, s / 2)
            if sl is None:
                return
            sub = self.tiles[sl]
            sub[m & replace[sub]] = tid
            x += dx * 1.4
            y += dy * 1.4
            dx = max(-1, min(1, dx + prng.uniform(-0.5, 0.5)))
            dy = max(-1, min(1, dy + prng.uniform(-0.5, 0.5)))
            s *= prng.uniform(0.82, 1.02)
            if s < 1.2:
                break

    def say(self, msg, frac):
        self.progress(msg, frac)

    # ----------------------------------------------------------------- run
    STEPS = [
        ("Generating terrain", 0.05, "terrain"),
        ("Adding rocks in the dirt", 0.12, "patches"),
        ("Generating tunnels and caves", 0.18, "caves"),
        ("Generating surface caves", 0.26, "surface_caves"),
        ("Generating ice biome", 0.30, "snow_biome"),
        ("Generating jungle", 0.36, "jungle_biome"),
        ("Adding sand and building the desert", 0.42, "desert_biome"),
        ("Making the world evil", 0.48, "corruption"),
        ("Adding mushroom patches", 0.54, "mushroom_biomes"),
        ("Creating the underworld", 0.58, "underworld"),
        ("Shining up the ores", 0.64, "ores"),
        ("Smoothing the world", 0.70, "smooth"),
        ("Generating floating islands", 0.73, "floating_islands"),
        ("Building the dungeon", 0.76, "dungeon"),
        ("Settling liquids", 0.80, "liquids"),
        ("Planting grass", 0.86, "grass"),
        ("Growing trees", 0.90, "trees"),
        ("Planting weeds and vines", 0.94, "plants"),
        ("Placing corruption altars", 0.96, "altars"),
        ("Wrapping up", 0.98, "finish"),
    ]

    def steps(self):
        """Run the generator one pass at a time, yielding (message, fraction)
        before each pass.  Lets a single-threaded host (the browser build)
        redraw its progress screen between passes."""
        self.layout()
        for msg, frac, method in self.STEPS:
            self.say(msg, frac)
            yield msg, frac
            getattr(self, method)()
        self.say("Done", 1.0)

    def run(self):
        for _ in self.steps():
            pass
        return self.world

    # --------------------------------------------------------------- layout
    def layout(self):
        W, prng = self.W, self.prng
        self.dungeon_left = prng.random() < 0.5
        m = (lambda f: f) if self.dungeon_left else (lambda f: 1.0 - f)
        j = lambda: prng.uniform(-0.015, 0.015)
        self.ocean_w = int(250 * self.SX ** 0.5)
        self.snow = (int(m(0.21 + j()) * W), int(0.036 * W))
        self.jungle = (int(m(0.81 + j()) * W), int(0.06 * W))
        slots = [m(0.335 + j()), m(0.595 + j()), m(0.705 + j())]
        di = prng.randrange(3)
        self.desert = (int(slots[di] * W), int(0.036 * W))
        self.corrupt = [(int(s * W), int(0.03 * W)) for i, s in
                        enumerate(slots) if i != di]
        b = np.full(W, FOREST, np.uint8)
        b[:self.ocean_w + 40] = OCEAN
        b[W - self.ocean_w - 40:] = OCEAN
        for (c, hw), bid in ((self.snow, SNOW), (self.jungle, JUNGLE),
                             (self.desert, DESERT)):
            b[max(0, c - hw):c + hw] = bid
        for c, hw in self.corrupt:
            b[max(0, c - hw):c + hw] = CORRUPTION
        self.biome = b

    # -------------------------------------------------------------- terrain
    def terrain(self):
        W, H, rng, prng = self.W, self.H, self.rng, self.prng
        base = int(H * 0.25)
        self.base = base
        h = (base + fractal_1d(W, 280, 5, rng) * 26 * self.SY +
             fractal_1d(W, 36, 3, rng) * 5 * self.SY)
        # a few mountains
        for _ in range(int(7 * self.SX)):
            c = prng.randint(self.ocean_w + 150, W - self.ocean_w - 150)
            if abs(c - W // 2) < 120:
                continue
            wdt = prng.randint(30, 90)
            hgt = prng.randint(14, 40) * self.SY
            xs = np.arange(max(0, c - wdt), min(W, c + wdt))
            k = np.cos((xs - c) / wdt * np.pi / 2) ** 2
            h[xs] -= hgt * k
        # desert dunes: smoother and a bit higher
        c, hw = self.desert
        xs = np.arange(max(0, c - hw - 40), min(W, c + hw + 40))
        k = np.clip(1 - (np.abs(xs - c) - hw) / 40, 0, 1)
        dunes = base - 4 + np.sin(xs / 23.0) * 4 + fractal_1d(len(xs), 60, 2,
                                                             rng) * 5
        h[xs] = h[xs] * (1 - k) + dunes * k
        # flatten spawn
        c = W // 2
        xs = np.arange(c - 40, c + 40)
        k = np.clip(1 - np.abs(xs - c) / 40, 0, 1) ** 0.5
        h[xs] = h[xs] * (1 - k) + h[c - 40:c + 40].mean() * k
        # oceans
        sea = base + 3
        self.sea_y = sea
        ow = self.ocean_w
        depth = 46 * self.SY
        for side in (0, 1):
            for i in range(ow + 60):
                x = i if side == 0 else W - 1 - i
                if i < ow:
                    d = (ow - i) / ow
                    floor = sea - 2 + depth * min(1.0, d * 1.5) ** 1.3
                    h[x] = floor + fractal_1d(1, 1, 1, rng)[0] * 0.5
                else:
                    k = (i - ow) / 60.0
                    h[x] = (sea - 2) * (1 - k) + h[x] * k
        self.h = np.round(h).astype(np.int32)
        self.world.surface = self.h.copy()
        hh = self.h[:, None]
        yy = np.arange(H)[None, :]
        solid = yy >= hh
        self.rock = (self.world.cavern_y - 10 +
                     fractal_1d(W, 70, 3, rng) * 14).astype(np.int32)
        self.tiles[solid] = T.DIRT
        self.tiles[(yy >= self.rock[:, None]) & solid] = T.STONE
        # beaches
        for side in (0, 1):
            xs = np.arange(0, ow + 60) if side == 0 else \
                np.arange(W - ow - 60, W)
            for x in xs:
                d = 18 + int(6 * np.sin(x * 0.1))
                y0 = self.h[x]
                self.tiles[x, y0:y0 + d] = T.SAND
        # background walls just below the surface down to the underground line
        wall_bottom = self.world.underground_y + \
            (fractal_1d(W, 30, 2, rng) * 5 + 3).astype(np.int32)
        wmask = (yy >= hh + 4) & (yy < wall_bottom[:, None])
        ocean = np.zeros(W, bool)
        ocean[:ow + 20] = True
        ocean[W - ow - 20:] = True
        wmask &= ~ocean[:, None]
        self.walls[wmask] = T.DIRT_WALL

    def patches(self):
        W, H, rng = self.W, self.H, self.rng
        n = fractal_2d(W, H, 22, 3, rng)
        yy = np.arange(H)[None, :]
        hh = self.h[:, None]
        t = self.tiles
        t[(t == T.DIRT) & (n > 0.34) & (yy > hh + 5)] = T.STONE
        t[(t == T.STONE) & (n < -0.40)] = T.DIRT
        n2 = fractal_2d(W, H, 14, 2, rng)
        t[(t == T.DIRT) & (n2 > 0.48) & (yy < hh + 28)] = T.CLAY
        t[(t == T.STONE) & (n2 < -0.58) &
          (yy > self.world.cavern_y)] = T.SILT
        self._n2 = n2

    def caves(self):
        W, H, rng = self.W, self.H, self.rng
        w = self.world
        yy = np.arange(H)
        ug, cv, uw = w.underground_y, w.cavern_y, w.underworld_y
        dep = np.clip((yy - (ug - 50)) / float(cv - ug + 50), 0, 1)
        dep2 = np.clip((yy - cv) / float(uw - cv), 0, 1)
        t1 = np.abs(fractal_2d(W, H, 64, 3, rng, stretch=1.4))
        tunnel = t1 < (0.02 + 0.06 * dep)[None, :]
        del t1
        t2 = np.abs(fractal_2d(W, H, 46, 3, rng))
        tunnel |= t2 < (0.05 * dep * (0.4 + dep2))[None, :]
        del t2
        blob = fractal_2d(W, H, 30, 3, rng)
        tunnel |= blob > (0.56 - 0.24 * dep2 - 0.06 * dep)[None, :]
        del blob
        hh = self.h[:, None]
        tunnel &= (yy[None, :] >= hh + 10) & (yy[None, :] < uw - 6)
        ocean = np.zeros(W, bool)
        ocean[:self.ocean_w + 30] = True
        ocean[W - self.ocean_w - 30:] = True
        tunnel &= ~(ocean[:, None] & (yy[None, :] < self.sea_y + 60))
        self.tiles[tunnel & T.NATURAL[self.tiles]] = T.AIR
        # worm caves (Terraria-style random walkers of varying width)
        prng = self.prng
        for _ in range(int(220 * self.area)):
            x = float(prng.randint(self.ocean_w + 60, W - self.ocean_w - 60))
            y = float(prng.randint(ug - 20, uw - 40))
            ang = prng.uniform(0, 6.283)
            r = prng.uniform(1.5, 3.5)
            for _ in range(prng.randint(40, 200)):
                if y < self.h[int(x)] + 12:
                    break
                self.carve(x, y, r)
                x += np.cos(ang) * 1.2
                y += np.sin(ang) * 0.8
                ang += prng.uniform(-0.35, 0.35)
                r = max(1.4, min(5.5, r + prng.uniform(-0.4, 0.4)))
                if not (60 < x < W - 60 and y < uw - 10):
                    break

    def _wobble(self, n, amp, scale=40):
        return fractal_1d(n, scale, 3, self.rng) * amp

    def surface_caves(self):
        prng = self.prng
        W = self.W
        for _ in range(int(32 * self.SX)):
            x = prng.randint(self.ocean_w + 80, W - self.ocean_w - 80)
            if abs(x - W // 2) < 60:
                continue
            y = float(self.h[x])
            ang = prng.uniform(0.6, 1.3) * (1 if prng.random() < .5 else -1)
            r = prng.uniform(1.8, 3.2)
            xf = float(x)
            for step in range(prng.randint(30, 110)):
                self.carve(xf, y, r)
                xf += np.cos(ang) * 0.9 * np.sign(ang)
                y += abs(np.sin(ang)) * 0.9 + 0.25
                ang += prng.uniform(-0.25, 0.25)
                r = max(1.6, min(4.0, r + prng.uniform(-0.3, 0.3)))

    # --------------------------------------------------------------- biomes
    def _region(self, c, hw, pad):
        x0 = max(0, c - hw - pad)
        x1 = min(self.W, c + hw + pad)
        return x0, x1

    def snow_biome(self):
        c, hw = self.snow
        w = self.world
        bottom = int(w.cavern_y + (w.underworld_y - w.cavern_y) * 0.55)
        x0, x1 = self._region(c, int(hw * 1.7), 20)
        xs = np.arange(x0, x1)[:, None]
        yy = np.arange(self.H)[None, :]
        hh = self.h[x0:x1, None]
        prog = np.clip((yy - hh) / float(bottom - self.base), 0, 1)
        edge = self._n2[x0:x1] * 8
        wl_, wr_ = self._wobble(self.H, 26)[None, :], \
            self._wobble(self.H, 26)[None, :]
        spread = hw * (1 + 0.65 * prog)
        mask = (xs - c > -spread + wl_ + edge) & \
            (xs - c < spread + wr_ + edge) & \
            (yy >= hh - 1) & (yy < bottom + edge * 2 +
                              self._wobble(x1 - x0, 20)[:, None])
        t = self.tiles[x0:x1]
        wl = self.walls[x0:x1]
        n = fractal_2d(x1 - x0, self.H, 12, 2, self.rng)
        t[mask & np.isin(t, (T.DIRT, T.GRASS, T.CLAY, T.SAND))] = T.SNOW
        deep = mask & (yy > hh + 25)
        t[deep & (t == T.STONE) & (n > -0.25)] = T.ICE
        t[deep & (t == T.SNOW) & (n > 0.35)] = T.ICE
        t[deep & (t == T.SILT)] = T.SNOW
        wl[mask & (wl == T.DIRT_WALL)] = T.SNOW_WALL
        cave = mask & (t == T.AIR) & (yy > w.underground_y)
        wl[cave & (n > -0.1)] = T.ICE_WALL
        wl[cave & (n <= -0.1)] = T.SNOW_WALL
        self.snow_mask = (x0, mask)

    def jungle_biome(self):
        c, hw = self.jungle
        w = self.world
        x0, x1 = self._region(c, int(hw * 1.4), 20)
        xs = np.arange(x0, x1)[:, None]
        yy = np.arange(self.H)[None, :]
        hh = self.h[x0:x1, None]
        prog = np.clip((yy - hh) / float(w.underworld_y - self.base), 0, 1)
        edge = self._n2[x0:x1] * 8
        wl_, wr_ = self._wobble(self.H, 34)[None, :], \
            self._wobble(self.H, 34)[None, :]
        spread = hw * (1 + 0.3 * prog)
        mask = (xs - c > -spread + wl_ + edge) & \
            (xs - c < spread + wr_ + edge) & \
            (yy >= hh - 1) & (yy < w.underworld_y - 20 + edge * 2)
        t = self.tiles[x0:x1]
        wl = self.walls[x0:x1]
        n = fractal_2d(x1 - x0, self.H, 18, 3, self.rng)
        # extra open jungle caves
        extra = mask & (yy > hh + 30) & (n > 0.3) & T.NATURAL[t]
        t[extra] = T.AIR
        t[mask & np.isin(t, (T.DIRT, T.GRASS, T.CLAY, T.SAND, T.SILT))] = \
            T.MUD
        t[mask & (t == T.STONE) & (self._n2[x0:x1] < 0.25)] = T.MUD
        wl[mask & (wl == T.DIRT_WALL)] = T.MUD_WALL
        wl[mask & (t == T.AIR) & (yy > w.underground_y) & (n > -0.35)] = \
            T.MUD_WALL
        self.jungle_mask = (x0, mask)

    def desert_biome(self):
        c, hw = self.desert
        w = self.world
        H = self.H
        x0, x1 = self._region(c, hw, 30)
        xs = np.arange(x0, x1)[:, None]
        yy = np.arange(H)[None, :]
        hh = self.h[x0:x1, None]
        edge = self._n2[x0:x1] * 10
        dx = np.abs(xs - c)
        depth = 40 * np.clip(1 - dx / (hw + 1.0), 0, 1) ** 0.5 + 6
        t = self.tiles[x0:x1]
        wl = self.walls[x0:x1]
        top = (dx < hw + edge) & (yy >= hh) & (yy < hh + depth)
        t[top & T.NATURAL[t]] = T.SAND
        t[top & (t == T.AIR) & (yy < hh + 12)] = T.SAND
        wl[top] = T.NO_WALL
        # underground desert: a big oval of sandstone / hardened sand
        cy = w.underground_y + (w.cavern_y - w.underground_y) * 0.9
        rx, ry = hw * 1.15, (w.cavern_y - w.underground_y) * 1.45
        ell = ((xs - c) / rx) ** 2 + ((yy - cy) / ry) ** 2 + edge / 60 < 1.0
        ell &= yy > hh + 20
        n = fractal_2d(x1 - x0, H, 10, 2, self.rng)
        fill = ell & (t != T.AIR)
        t[fill & (yy < cy - ry * 0.35 + n * 8)] = T.HARDENED_SAND
        t[fill & (yy >= cy - ry * 0.35 + n * 8)] = T.SANDSTONE
        # connect the surface sand to the oval
        link = (dx < hw * 0.8 + edge) & (yy >= hh + depth) & \
            (yy < cy - ry * 0.6) & T.NATURAL[t]
        t[link] = T.HARDENED_SAND
        # desert caves - long horizontal tunnels
        cav = np.abs(fractal_2d(x1 - x0, H, 22, 3, self.rng, stretch=2.5))
        holes = ell & ((cav < 0.05) | (n > 0.45)) & \
            (yy > cy - ry * 0.75)
        t[holes] = T.AIR
        wmask = ell & (t == T.AIR)
        wl[wmask & (yy < cy - ry * 0.3)] = T.HARDENED_SAND_WALL
        wl[wmask & (yy >= cy - ry * 0.3)] = T.SANDSTONE_WALL

    def corruption(self):
        prng = self.prng
        w = self.world
        H = self.H
        self.chasm_bottoms = []
        for c, hw in self.corrupt:
            x0, x1 = self._region(c, hw, 25)
            xs = np.arange(x0, x1)[:, None]
            yy = np.arange(H)[None, :]
            hh = self.h[x0:x1, None]
            edge = self._n2[x0:x1] * 12
            dx = np.abs(xs - c) / float(hw)
            bottom = hh + (w.cavern_y - self.base + 40) * np.clip(
                1 - dx ** 2, 0, 1)
            mask = (np.abs(xs - c) < hw + edge) & (yy >= hh - 2) & \
                (yy < bottom + edge)
            t = self.tiles[x0:x1]
            wl = self.walls[x0:x1]
            t[mask & (t == T.GRASS)] = T.CORRUPT_GRASS
            t[mask & (t == T.STONE)] = T.EBONSTONE
            t[mask & (t == T.SAND)] = T.EBONSAND
            t[mask & (t == T.ICE)] = T.PURPLE_ICE
            t[mask & (t == T.DIRT) & (self._n2[x0:x1] > 0.2) &
              (yy > hh + 8)] = T.EBONSTONE
            wl[mask & (wl == T.DIRT_WALL)] = T.CORRUPT_WALL
            # chasms
            n = max(3, int(2 * hw / 44))
            for i in range(n):
                cx = c - hw * 0.8 + i * (1.6 * hw / (n - 1)) + \
                    prng.uniform(-6, 6)
                self._chasm(cx)

    def _chasm(self, cx):
        prng = self.prng
        w = self.world
        x = float(cx)
        xi = int(x)
        y = float(self.h[xi] - 3)
        surf = self.h[xi]
        length = int((w.cavern_y - surf) * prng.uniform(0.55, 1.0)) + 25
        rb = prng.uniform(2.4, 4.2)
        for step in range(length):
            r = rb * (1 + 0.35 * np.sin(step / 6.0 + cx))
            if step < 6:
                r += 1.2
            self.convert(x, y, r + 5.5, T.EBONSTONE,
                         only=(T.STONE, T.DIRT, T.CLAY, T.GRASS, T.SAND,
                               T.CORRUPT_GRASS, T.SILT, T.SNOW, T.MUD))
            self.carve(x, y, r, wall=T.EBONSTONE_WALL
                       if y > surf + 10 else None)
            y += 1
            x += prng.gauss(0, 0.45)
            x = max(cx - 7, min(cx + 7, x))
        # pocket at the bottom
        rx = prng.randint(9, 16)
        for k in range(-rx, rx + 1):
            r = 4.5 * (1 - (k / (rx + 1)) ** 2) + 1.5
            self.convert(x + k, y, r + 4, T.EBONSTONE,
                         only=(T.STONE, T.DIRT, T.CLAY, T.SILT, T.MUD,
                               T.SNOW, T.SAND))
        for k in range(-rx, rx + 1):
            r = 4.5 * (1 - (k / (rx + 1)) ** 2) + 1.5
            self.carve(x + k, y, r, wall=T.EBONSTONE_WALL)
        self.chasm_bottoms.append((int(x), int(y), rx))
        # demonite veins near the bottom
        for _ in range(prng.randint(3, 6)):
            self.runner(x + prng.uniform(-rx - 6, rx + 6),
                        y + prng.uniform(-8, 8), prng.uniform(3, 5),
                        prng.randint(3, 7), T.DEMONITE_ORE,
                        _mask(T.EBONSTONE))

    def mushroom_biomes(self):
        prng = self.prng
        w = self.world
        W, H = self.W, self.H
        self.mushroom_areas = []
        avoid = [self.snow, self.jungle, self.desert]
        n = max(1, int(2 * self.SX))
        tries = 0
        while len(self.mushroom_areas) < n and tries < 200:
            tries += 1
            x = prng.randint(self.ocean_w + 200, W - self.ocean_w - 200)
            if any(abs(x - c) < hw * 1.6 + 60 for c, hw in avoid):
                continue
            if any(abs(x - a[0]) < 200 for a in self.mushroom_areas):
                continue
            y = int(w.cavern_y + (w.underworld_y - w.cavern_y) *
                    prng.uniform(0.25, 0.6))
            rx, ry = prng.randint(34, 50), prng.randint(20, 28)
            self.mushroom_areas.append((x, y, rx, ry))
            x0, x1 = max(0, x - rx - 4), min(W, x + rx + 5)
            y0, y1 = max(0, y - ry - 4), min(H, y + ry + 5)
            xs = np.arange(x0, x1)[:, None]
            ys = np.arange(y0, y1)[None, :]
            n2 = fractal_2d(x1 - x0, y1 - y0, 9, 2, self.rng)
            d = ((xs - x) / rx) ** 2 + ((ys - y) / ry) ** 2 + n2 * 0.25
            t = self.tiles[x0:x1, y0:y1]
            wl = self.walls[x0:x1, y0:y1]
            t[(d < 1.0) & T.NATURAL[t]] = T.MUD
            t[(d < 1.0) & (t == T.AIR)] = T.MUD
            hole = (d < 0.62) & (n2 > -0.35)
            t[hole] = T.AIR
            wl[hole | ((d < 0.8) & (t == T.AIR))] = T.MUSHROOM_WALL

    def underworld(self):
        W, H, rng = self.W, self.H, self.rng
        w = self.world
        uw = w.underworld_y
        S = self.SY
        yy = np.arange(H)[None, :]
        top_edge = (uw - 4 + fractal_1d(W, 40, 2, rng) * 6)[:, None]
        t, wl = self.tiles, self.walls
        region = yy >= top_edge
        t[region] = T.ASH
        wl[region] = T.NO_WALL
        ceil = (uw + 28 * S + fractal_1d(W, 60, 3, rng) * 14 * S)[:, None]
        floor = (H - 46 * S + fractal_1d(W, 90, 3, rng) * 26 * S)[:, None]
        cav = (yy > ceil) & (yy < floor)
        isl = fractal_2d(W, H - uw, 22, 3, rng)
        full = np.zeros((W, H), np.float32)
        full[:, uw:] = isl
        cav &= ~(full > 0.42)
        t[cav] = T.AIR
        self.lava_level = int(H - 50 * S)
        hs = fractal_2d(W, H - uw, 6, 2, rng)
        fullh = np.zeros((W, H), np.float32)
        fullh[:, uw:] = hs
        t[(t == T.ASH) & (fullh > 0.42) & (yy > uw + 8)] = T.HELLSTONE
        t[:, H - 3:] = T.ASH
        # transition: some stone/ash mixing above the underworld
        mix = (yy >= uw - 25) & (yy < top_edge) & (self._n2 > 0.2)
        t[mix & T.NATURAL[t] & (t != T.AIR)] = T.ASH

    def ores(self):
        prng = self.prng
        w = self.world
        W, H = self.W, self.H
        A = self.area
        rep = _mask(T.STONE, T.DIRT, T.MUD, T.ICE, T.SNOW, T.CLAY, T.SILT,
                    T.SANDSTONE, T.HARDENED_SAND)
        c1 = T.COPPER_ORE if prng.random() < .5 else T.TIN_ORE
        c2 = T.IRON_ORE if prng.random() < .5 else T.LEAD_ORE
        c3 = T.SILVER_ORE if prng.random() < .5 else T.TUNGSTEN_ORE
        c4 = T.GOLD_ORE if prng.random() < .5 else T.PLATINUM_ORE
        top = self.base - 30
        plans = [
            (c1, int(1000 * A), top, w.cavern_y + 80, (3, 5.5), (4, 9)),
            (c2, int(800 * A), w.underground_y - 30, w.underworld_y, (3, 5.5),
             (4, 9)),
            (c3, int(560 * A), w.underground_y, w.underworld_y, (3, 5),
             (4, 8)),
            (c4, int(400 * A), w.cavern_y - 40, w.underworld_y, (3, 5),
             (3, 7)),
        ]
        for tid, count, y0, y1, st, steps in plans:
            for _ in range(count):
                x = prng.randint(50, W - 50)
                y = prng.randint(max(0, y0), min(H - 1, y1))
                if not T.NATURAL[self.tiles[x, y]] or y < self.h[x] + 2:
                    continue
                self.runner(x, y, prng.uniform(*st), prng.randint(*steps),
                            tid, rep)
        # corruption demonite sprinkled deeper
        for c, hw in self.corrupt:
            for _ in range(int(25 * A)):
                x = prng.randint(c - hw, c + hw)
                y = prng.randint(self.h[x] + 25, w.cavern_y + 30)
                self.runner(x, y, prng.uniform(2.5, 4), prng.randint(3, 6),
                            T.DEMONITE_ORE, _mask(T.EBONSTONE))
        # sprinkle a little hellstone up the transition
        hell = _mask(T.ASH)
        for _ in range(int(500 * A)):
            x = prng.randint(50, W - 50)
            y = prng.randint(w.underworld_y, H - 5)
            self.runner(x, y, prng.uniform(3, 6), prng.randint(3, 7),
                        T.HELLSTONE, hell)

    def smooth(self):
        t = self.tiles
        s = T.SOLID[t]
        n = np.zeros(t.shape, np.int8)
        n[1:, :] += s[:-1, :]
        n[:-1, :] += s[1:, :]
        n[:, 1:] += s[:, :-1]
        n[:, :-1] += s[:, 1:]
        lone = s & (n <= 1) & T.NATURAL[t]
        t[lone] = T.AIR
        hole = (~s) & (n == 4) & (t == T.AIR)
        hole[:, -1] = False
        below = np.zeros_like(t)
        below[:, :-1] = t[:, 1:]
        t[hole] = below[hole]
        t[hole & ~T.SOLID[t]] = T.DIRT

    def floating_islands(self):
        prng = self.prng
        W = self.W
        w = self.world
        n = max(2, int(3.2 * self.SX))
        placed = []
        tries = 0
        while len(placed) < n and tries < 300:
            tries += 1
            x = prng.randint(int(W * 0.12), int(W * 0.88))
            if abs(x - W // 2) < 160 or any(abs(x - p) < 300 for p in placed):
                continue
            placed.append(x)
            y = int(w.space_y + prng.uniform(25, 70) * self.SY)
            rw = prng.randint(16, 26)
            ry = prng.randint(8, 12)
            for dx in range(-rw, rw + 1):
                k = 1 - (dx / (rw + 1)) ** 2
                th = int(ry * k ** 0.6) + prng.randint(0, 1)
                top = y + int(2 * (1 - k)) + prng.randint(0, 1)
                for yy in range(top, top + th):
                    self.tiles[x + dx, yy] = T.CLOUD
                if abs(dx) < rw * 0.78:
                    dd = max(1, int(5 * k))
                    for yy in range(top - 1, top - 1 + dd):
                        self.tiles[x + dx, yy] = T.DIRT
                    self.walls[x + dx, top + dd:top + dd + max(0, th - dd - 3)
                               ] = T.NO_WALL

    def dungeon(self):
        prng = self.prng
        W = self.W
        left = self.dungeon_left
        dx = self.ocean_w + int(70 * self.SX)
        bx = dx if left else W - dx - 26
        gy = int(self.h[bx:bx + 26].min())
        inward = 1 if left else -1
        rects = []          # interior rectangles (x0, y0, x1, y1)
        # entrance hall + tower
        rects.append((bx + 4, gy - 16, bx + 22, gy + 2))
        rects.append((bx + 9, gy - 30, bx + 17, gy - 16))
        # door opening facing the world centre
        door_x = bx + 22 if left else bx
        rects.append((door_x - 1, gy - 4, door_x + 4, gy + 2) if left else
                     (door_x - 4, gy - 4, door_x + 2, gy + 2))
        # zig-zag descent
        cx, cy = bx + 13, gy + 2
        depth_total = int(220 * self.SY)
        rooms = []
        d = inward
        while cy < gy + depth_total:
            ln = prng.randint(22, 36)
            rects.append((cx - 3, cy, cx + 3, cy + ln))
            cy += ln
            hl = prng.randint(30, 60)
            x2 = cx + d * hl
            rects.append((min(cx, x2) - 3, cy - 6, max(cx, x2) + 3, cy))
            if prng.random() < 0.6:
                rw, rh = prng.randint(14, 22), prng.randint(10, 14)
                rooms.append((x2 - rw // 2, cy - rh, x2 + rw // 2, cy))
            cx = x2
            d = -d if prng.random() < 0.7 else d
        rects.extend(rooms)
        t, wl = self.tiles, self.walls
        # thick outer bricks first
        for x0, y0, x1, y1 in rects:
            xa, xb = max(1, x0 - 5), min(W - 1, x1 + 5)
            ya, yb = max(1, y0 - 5), y1 + 5
            t[xa:xb, ya:yb] = T.DUNGEON_BRICK
            wl[xa:xb, ya:yb] = T.NO_WALL
            self.world.liquid[xa:xb, ya:yb] = 0
        for x0, y0, x1, y1 in rects:
            t[x0:x1, y0:y1] = T.AIR
            wl[x0 - 1:x1 + 1, y0 - 1:y1 + 1] = T.DUNGEON_WALL
        # clear the outside of the entrance so it can be reached
        if left:
            t[bx + 27:bx + 34, gy - 4:gy] = T.AIR
        else:
            t[bx - 8:bx - 1, gy - 4:gy] = T.AIR
        # platforms across vertical shafts
        for x0, y0, x1, y1 in rects:
            if y1 - y0 > x1 - x0 + 6:
                for py in range(y0 + 8, y1 - 2, 9):
                    for px in range(x0, x1):
                        t[px, py] = T.PLATFORM
        # clear the sky above the tower
        t[bx - 2:bx + 28, :gy - 35] = np.where(
            T.NATURAL[t[bx - 2:bx + 28, :gy - 35]], T.AIR,
            t[bx - 2:bx + 28, :gy - 35])
        self.dungeon_x = (bx, bx + 26)

    # -------------------------------------------------------------- liquids
    def liquids(self):
        w = self.world
        W, H = self.W, self.H
        liq, lt, t = w.liquid, w.ltype, self.tiles
        yy = np.arange(H)[None, :]
        ocean = np.zeros(W, bool)
        ocean[:self.ocean_w] = True
        ocean[W - self.ocean_w:] = True
        m = ocean[:, None] & (yy >= self.sea_y) & (yy < self.sea_y + 120) & \
            (t == T.AIR)
        liq[m] = 255
        lt[m] = WATER
        # underworld lava
        m = (yy >= self.lava_level) & (yy >= w.underworld_y) & (t == T.AIR)
        liq[m] = 255
        lt[m] = LAVA
        prng = self.prng
        A = self.area
        for _ in range(int(900 * A)):
            x = prng.randint(60, W - 60)
            y = prng.randint(w.underground_y, w.underworld_y - 30)
            self._pool(x, y, WATER, prng.randint(150, 2500))
        for _ in range(int(110 * A)):
            x = prng.randint(60, W - 60)
            y = prng.randint((w.cavern_y + w.underworld_y) // 2,
                             w.underworld_y - 10)
            self._pool(x, y, LAVA, prng.randint(80, 500))
        # a few surface ponds
        for _ in range(int(14 * self.SX)):
            x = prng.randint(self.ocean_w + 100, W - self.ocean_w - 100)
            self._pool(x, int(self.h[x]) - 1, WATER, prng.randint(30, 160),
                       max_rise=3)

    def _pool(self, x, y, ltype, max_cells, max_rise=6):
        t = self.tiles
        liq = self.world.liquid
        if t[x, y] != T.AIR or liq[x, y]:
            return
        H = self.H
        while y + 1 < H and t[x, y + 1] == T.AIR:
            y += 1
        if y >= H - 2:
            return
        level = y - self.prng.randint(1, max_rise)
        seen = {(x, y)}
        q = deque([(x, y)])
        while q:
            cx, cy = q.popleft()
            for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy + 1),
                           (cx, cy - 1)):
                if (nx, ny) in seen or ny < level:
                    continue
                if not (1 <= nx < self.W - 1 and 0 <= ny < H - 1):
                    return
                if T.SOLID[t[nx, ny]] or liq[nx, ny]:
                    continue
                if t[nx, ny] != T.AIR:
                    return
                seen.add((nx, ny))
                if len(seen) > max_cells:
                    return
                q.append((nx, ny))
        xs, ys = zip(*seen)
        liq[list(xs), list(ys)] = 255
        self.world.ltype[list(xs), list(ys)] = ltype

    # ---------------------------------------------------------- decoration
    def grass(self):
        t = self.tiles
        liq = self.world.liquid
        H = self.H
        w = self.world
        open_ = (~T.SOLID[t]) & (liq == 0)
        exp = np.zeros(t.shape, bool)
        exp[:, 1:] |= open_[:, :-1]
        exp[:, :-1] |= open_[:, 1:]
        exp[1:, :] |= open_[:-1, :]
        exp[:-1, :] |= open_[1:, :]
        yy = np.arange(H)[None, :]
        near = (yy < w.underground_y) & (yy < self.h[:, None] + 22)
        t[(t == T.DIRT) & exp & near] = T.GRASS
        # corruption
        for c, hw in self.corrupt:
            x0, x1 = self._region(c, hw, 25)
            sub = t[x0:x1]
            hh = self.h[x0:x1, None]
            sub[(sub == T.GRASS) & (np.abs(np.arange(x0, x1)[:, None] - c) <
                                    hw + 8) & (yy < hh + 140)] = \
                T.CORRUPT_GRASS
        x0, mask = self.jungle_mask
        sub = t[x0:x0 + mask.shape[0]]
        e = exp[x0:x0 + mask.shape[0]]
        sub[(sub == T.MUD) & e & mask] = T.JUNGLE_GRASS
        sub[(sub == T.GRASS) & mask] = T.JUNGLE_GRASS
        for (x, y, rx, ry) in self.mushroom_areas:
            xa, xb = max(0, x - rx - 4), min(self.W, x + rx + 5)
            ya, yb = max(0, y - ry - 4), min(H, y + ry + 5)
            sub = t[xa:xb, ya:yb]
            sub[(sub == T.MUD) & exp[xa:xb, ya:yb]] = T.MUSHROOM_GRASS

    def trees(self):
        prng = self.prng
        w = self.world
        t = self.tiles
        W = self.W
        solid_cols = T.SOLID[t]
        ground = solid_cols.argmax(axis=1)
        x = 60
        dx0, dx1 = self.dungeon_x
        while x < W - 60:
            gy = int(ground[x])
            g = int(t[x, gy])
            if dx0 - 6 <= x <= dx1 + 6 or abs(x - W // 2) < 3:
                x += 1
                continue
            kind, chance, hmin, hmax = None, 0, 0, 0
            biome = self.biome[x]
            if g == T.GRASS:
                kind, chance, hmin, hmax = T.TREE, 0.42, 7, 16
            elif g == T.CORRUPT_GRASS:
                kind, chance, hmin, hmax = T.TREE_EBON, 0.40, 7, 15
            elif g == T.JUNGLE_GRASS:
                kind, chance, hmin, hmax = T.TREE_JUNGLE, 0.55, 10, 22
            elif g == T.SNOW and biome == SNOW:
                kind, chance, hmin, hmax = T.TREE_BOREAL, 0.35, 6, 13
            elif g == T.SAND and biome == OCEAN and \
                    w.liquid[x, gy - 1] == 0:
                kind, chance, hmin, hmax = T.TREE_PALM, 0.12, 8, 14
            elif g == T.SAND and biome == DESERT:
                kind, chance, hmin, hmax = T.CACTUS, 0.08, 3, 6
            if kind is None or prng.random() > chance:
                x += 1
                continue
            if not (int(ground[x - 1]) == gy and int(ground[x + 1]) == gy):
                x += 1
                continue
            height = prng.randint(hmin, hmax)
            if gy - height - 4 < 2 or \
                    (T.SOLID[t[x - 1:x + 2, gy - height - 4:gy]]).any() or \
                    w.liquid[x, gy - height:gy].any():
                x += 1
                continue
            if kind == T.CACTUS:
                self._cactus(x, gy - 1, height)
            else:
                build_tree(w, x, gy - 1, height, kind, prng)
            x += prng.randint(3, 7) if kind != T.TREE_PALM else 12
        # giant glowing mushrooms in the mushroom caves
        for (mx, my, rx, ry) in self.mushroom_areas:
            for xx in range(mx - rx, mx + rx, 3):
                for yy in range(my - ry, my + ry):
                    if t[xx, yy] == T.MUSHROOM_GRASS and t[xx, yy - 1] == \
                            T.AIR and prng.random() < 0.25:
                        hgt = prng.randint(4, 8)
                        if not T.SOLID[t[xx - 1:xx + 2,
                                         yy - hgt - 3:yy]].any():
                            build_tree(w, xx, yy - 1, hgt, T.TREE_MUSHROOM,
                                       prng)
                        break

    def _cactus(self, x, y, height):
        t, f = self.tiles, self.world.frame
        for i in range(height):
            yy = y - i
            fr = T.TR_TRUNK
            if i == height - 1:
                fr = T.TR_TOP
            elif i == 1 and height > 3:
                fr = T.TR_BRANCH_L if self.prng.random() < .5 else \
                    T.TR_BRANCH_R
            t[x, yy] = T.CACTUS
            f[x, yy] = fr

    def plants(self):
        t, f = self.tiles, self.world.frame
        w = self.world
        H = self.H
        rng = self.rng
        prng = self.prng
        above_air = np.zeros(t.shape, bool)
        above_air[:, 1:] = (t[:, :-1] == T.AIR) & (w.liquid[:, :-1] == 0)
        for g, p, chance in ((T.GRASS, T.PLANT, 0.55),
                             (T.CORRUPT_GRASS, T.PLANT_CORRUPT, 0.5),
                             (T.JUNGLE_GRASS, T.PLANT_JUNGLE, 0.7),
                             (T.MUSHROOM_GRASS, T.PLANT_MUSHROOM, 0.35)):
            xs, ys = np.nonzero((t == g) & above_air)
            keep = rng.random(len(xs)) < chance
            xs, ys = xs[keep], ys[keep] - 1
            t[xs, ys] = p
            f[xs, ys] = rng.integers(0, 6, len(xs))
        # vines
        below_air = np.zeros(t.shape, bool)
        below_air[:, :-1] = (t[:, 1:] == T.AIR) & (w.liquid[:, 1:] == 0)
        for g, v, chance, mx in ((T.GRASS, T.VINE, 0.3, 7),
                                 (T.JUNGLE_GRASS, T.VINE_JUNGLE, 0.55, 12)):
            xs, ys = np.nonzero((t == g) & below_air)
            for x, y in zip(xs.tolist(), ys.tolist()):
                if prng.random() > chance:
                    continue
                for k in range(1, prng.randint(2, mx)):
                    if y + k >= H - 1 or t[x, y + k] != T.AIR or \
                            w.liquid[x, y + k]:
                        break
                    t[x, y + k] = v

    def altars(self):
        prng = self.prng
        w = self.world
        for (x, y, rx) in self.chasm_bottoms:
            for _ in range(20):
                ax = x + prng.randint(-rx, rx - 3)
                ay = y
                while ay < self.H - 2 and not T.SOLID[self.tiles[ax, ay + 1]]:
                    ay += 1
                if w.multi_fits(ax, ay - 1, T.DEMON_ALTAR):
                    for dx in range(3):
                        for dy in range(2):
                            self.tiles[ax + dx, ay - 1 + dy] = T.DEMON_ALTAR
                            w.frame[ax + dx, ay - 1 + dy] = dy * 8 + dx
                    break

    def finish(self):
        w = self.world
        W = self.W
        w.biome = self.biome
        x = W // 2
        t = self.tiles
        col = T.SOLID[t[x]]
        gy = int(col.argmax())
        for yy in range(gy - 4, gy):
            if not T.SOLID[t[x, yy]]:
                t[x, yy] = T.AIR
        w.spawn = (x, gy - 3)
        w.recompute_sky()
        w.dirty.clear()


def _mask(*tids):
    m = np.zeros(T.NUM_TILES, bool)
    for tid in tids:
        m[tid] = True
    return m


def generate(name, size="Small", seed=None, progress=None):
    if seed is None:
        seed = random.randrange(1, 2 ** 31)
    progress = progress or (lambda msg, frac: None)
    return _Gen(name, size, seed, progress).run()


def generate_steps(name, size="Small", seed=None):
    """Generator version: yields (message, fraction) between passes and
    returns the finished World (as StopIteration.value)."""
    if seed is None:
        seed = random.randrange(1, 2 ** 31)
    gen = _Gen(name, size, seed, lambda msg, frac: None)
    yield from gen.steps()
    return gen.world
