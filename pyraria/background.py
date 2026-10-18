"""Sky, sun/moon, stars, clouds, parallax biome backgrounds and the
underground backdrop."""
import math
import random

import numpy as np
import pygame

from .config import SCREEN_W, SCREEN_H, DAY_LENGTH, NIGHT_LENGTH
from .noise import fractal_1d
from . import terrain_tex as TT
from .textures import rng_for, upscale, to_surface
from .world import (FOREST, OCEAN, DESERT, SNOW, JUNGLE, CORRUPTION,
                    DUNGEON, MUSHROOM, UNDERGROUND, CAVERN, UNDERWORLD)

LAYER_W = 1600

# sky colours (top, horizon) at full daylight per biome
SKY_DAY = {
    FOREST: ((74, 128, 222), (150, 196, 250)),
    OCEAN: ((70, 130, 225), (160, 205, 252)),
    DESERT: ((110, 150, 220), (225, 210, 170)),
    SNOW: ((120, 160, 220), (215, 230, 250)),
    JUNGLE: ((70, 140, 170), (150, 210, 180)),
    CORRUPTION: ((92, 84, 140), (170, 150, 190)),
}
SKY_NIGHT = ((6, 9, 30), (22, 34, 76))
SKY_DUSK = ((60, 70, 140), (250, 150, 90))


def _lerp(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


KEY = (255, 0, 255)


class Layer:
    """A horizontally tiling silhouette. Stored cropped to its opaque rows
    and converted to colour-keyed surfaces, which blit much faster than
    per-pixel alpha."""

    def __init__(self, surf, parallax, base_y, fill):
        bound = surf.get_bounding_rect()
        self.top = bound.top
        self.full_h = surf.get_height()
        self.surf = surf.subsurface((0, bound.top, surf.get_width(),
                                     surf.get_height() - bound.top)).copy()
        self.parallax = parallax
        self.base_y = base_y
        self.fill = fill
        self.tinted = {}

    def get(self, tint):
        s = self.tinted.get(tint)
        if s is None:
            t = self.surf.copy()
            t.fill(tint + (255,), special_flags=pygame.BLEND_RGBA_MULT)
            s = pygame.Surface(t.get_size())
            if pygame.display.get_surface():
                s = s.convert()
            s.fill(KEY)
            s.blit(t, (0, 0))
            s.set_colorkey(KEY, pygame.RLEACCEL)
            if len(self.tinted) > 8:
                self.tinted.clear()
            self.tinted[tint] = s
        return s


def _ridge(n, scale, amp, rng, base):
    return base + fractal_1d(n, scale, 4, rng) * amp


def _make_layer(kind, depth, seed):
    """Procedural silhouette layer (art resolution, scaled x2)."""
    rng = np.random.default_rng(seed)
    prng = random.Random(seed)
    w, h = LAYER_W // 2, 220
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    if kind == CORRUPTION:
        cols = [(112, 98, 150), (84, 70, 118), (58, 46, 84)]
    elif kind == DESERT:
        cols = [(222, 196, 140), (206, 172, 108), (182, 146, 86)]
    elif kind == SNOW:
        cols = [(196, 214, 238), (150, 178, 210), (110, 140, 176)]
    elif kind == JUNGLE:
        cols = [(70, 128, 90), (44, 104, 58), (28, 78, 40)]
    elif kind == OCEAN:
        cols = [(120, 160, 196), (66, 132, 96), (40, 104, 60)]
    else:
        cols = [(112, 160, 180), (62, 128, 84), (40, 100, 58)]
    col = cols[depth]
    dark = tuple(int(c * 0.8) for c in col)
    base = [70, 110, 140][depth]
    amp = [50, 26, 18][depth]
    scale = [120, 70, 50][depth]
    if kind == DESERT:
        amp = [26, 18, 12][depth]
        scale = [160, 100, 70][depth]
    if kind == OCEAN and depth == 0:
        # far sea horizon
        pygame.draw.rect(s, (70, 120, 190), (0, 150, w, h - 150))
        pygame.draw.rect(s, (110, 160, 220), (0, 150, w, 2))
        return Layer(upscale(s), 0.1, 0, (70, 120, 190))
    ridge = _ridge(w + 1, scale, amp, rng, base)
    # make it tile seamlessly
    blend = np.linspace(0, 1, 60)
    ridge[-60:] = ridge[-60:] * (1 - blend) + ridge[:60] * blend
    if kind == SNOW and depth == 0:
        ridge = base + np.abs(fractal_1d(w + 1, 60, 3, rng)) * -90 + 30
        ridge[-60:] = ridge[-60:] * (1 - blend) + ridge[:60] * blend
    ridge = [float(v) for v in ridge]
    pts = [(x, ridge[x]) for x in range(w)] + [(w, h), (0, h)]
    pygame.draw.polygon(s, col, pts)
    # decorations on the ridge
    if depth >= 1 or kind in (CORRUPTION, JUNGLE):
        x = prng.randint(0, 20)
        while x < w - 8:
            y = ridge[x]
            if kind in (FOREST, OCEAN, DUNGEON):
                r = prng.randint(4, 8) + depth * 2
                pygame.draw.line(s, dark, (x, y), (x, y - r - 2), 2)
                pygame.draw.circle(s, col, (x, y - r - 2), r)
                pygame.draw.circle(s, col, (x - r // 2, y - r), r - 1)
                pygame.draw.circle(s, col, (x + r // 2, y - r), r - 1)
                x += prng.randint(6, 26)
            elif kind == CORRUPTION:
                hgt = prng.randint(10, 26) + depth * 6
                pygame.draw.line(s, col, (x, y), (x, y - hgt), 2)
                for k in range(prng.randint(2, 4)):
                    by = y - hgt * prng.uniform(0.4, 0.9)
                    d = prng.choice((-1, 1))
                    pygame.draw.line(s, col, (x, by),
                                     (x + d * prng.randint(4, 9),
                                      by - prng.randint(3, 8)), 1)
                if depth == 0 and prng.random() < 0.3:
                    pygame.draw.polygon(s, col, [(x - 6, y), (x, y - 50),
                                                 (x + 6, y)])
                x += prng.randint(8, 30)
            elif kind == SNOW:
                hgt = prng.randint(12, 24) + depth * 4
                pygame.draw.polygon(s, col, [(x - hgt // 3, y), (x, y - hgt),
                                             (x + hgt // 3, y)])
                x += prng.randint(6, 18)
            elif kind == JUNGLE:
                r = prng.randint(8, 14) + depth * 2
                pygame.draw.circle(s, col, (x, y - r // 2), r)
                pygame.draw.line(s, dark, (x, y), (x, y + 4), 2)
                x += prng.randint(6, 16)
            elif kind == DESERT:
                if prng.random() < 0.15 and depth == 2:
                    hgt = prng.randint(8, 14)
                    pygame.draw.line(s, (90, 130, 70), (x, y), (x, y - hgt), 3)
                    pygame.draw.line(s, (90, 130, 70), (x - 3, y - hgt // 2),
                                     (x - 3, y - hgt // 2 - 4), 2)
                x += prng.randint(20, 50)
            else:
                x += 20
    # fog gradient: darker lower down (RGB only, keeps the alpha binary)
    fog = pygame.Surface((w, h))
    for y in range(h):
        k = max(0.0, (y - base) / (h - base))
        v = int(255 * (1 - 0.16 * k))
        fog.fill((v, v, v), (0, y, w, 1))
    s.blit(fog, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    big = upscale(s)
    parallax = [0.12, 0.22, 0.34][depth]
    return Layer(big, parallax, 0, tuple(int(c * 0.85) for c in col))


class Background:
    def __init__(self, seed=1):
        self.seed = seed
        self.layers = {}
        self.biome = FOREST
        self.prev_biome = FOREST
        self.fade = 1.0
        self.under_kind = UNDERGROUND
        self.stars = [(random.random(), random.random() * 0.75,
                       random.random() * math.tau, random.choice((1, 2, 2, 3)))
                      for _ in range(160)]
        self.clouds = []
        rng = random.Random(seed)
        for i in range(10):
            self.clouds.append([rng.random() * SCREEN_W * 2,
                                rng.uniform(20, 260),
                                rng.uniform(0.1, 0.4),
                                self._cloud_sprite(rng, i)])
        self.sky_cache = {}
        self.backdrops = {}
        self.sun = self._sun()
        self.moon = self._moon()
        self.time = 0

    # ----------------------------------------------------------- sprites
    @staticmethod
    def _cloud_sprite(rng, i):
        w, h = rng.randint(40, 80), rng.randint(14, 24)
        s = pygame.Surface((w, h + 6), pygame.SRCALPHA)
        circles = []
        for _ in range(rng.randint(4, 7)):
            r = rng.randint(5, h // 2 + 2)
            circles.append((rng.randint(r, w - r), rng.randint(h // 2,
                                                               h - r // 2 + 2),
                            r))
        for cx, cy, r in circles:
            pygame.draw.circle(s, (205, 215, 235), (cx, cy + 2), r)
        for cx, cy, r in circles:
            pygame.draw.circle(s, (250, 252, 255), (cx, cy), r)
        return upscale(s)

    @staticmethod
    def _sun():
        s = pygame.Surface((40, 40), pygame.SRCALPHA)
        for r, a in ((20, 30), (16, 50), (12, 255)):
            pygame.draw.circle(s, (255, 240, 150, a), (20, 20), r)
        pygame.draw.circle(s, (255, 255, 220), (20, 20), 9)
        return upscale(s)

    @staticmethod
    def _moon():
        s = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(s, (225, 228, 235), (12, 12), 10)
        for (x, y, r) in ((8, 9, 2), (14, 14, 3), (15, 7, 1), (9, 15, 1)):
            pygame.draw.circle(s, (190, 192, 205), (x, y), r)
        return upscale(s)

    # ---------------------------------------------------------- biomes
    def set_biome(self, biome):
        sky_biome = biome if biome in SKY_DAY else FOREST
        if biome == DUNGEON:
            sky_biome = FOREST
        if sky_biome != self.biome:
            self.prev_biome = self.biome
            self.biome = sky_biome
            self.fade = 0.0
        if biome in (UNDERGROUND, CAVERN, UNDERWORLD, MUSHROOM, SNOW, JUNGLE,
                     DESERT, CORRUPTION, DUNGEON, FOREST, OCEAN):
            self.under_kind = biome

    def _layers_for(self, biome):
        if biome not in self.layers:
            self.layers[biome] = [_make_layer(biome, d, self.seed * 31 + d +
                                              biome * 7) for d in range(3)]
        return self.layers[biome]

    # ------------------------------------------------------------- sky
    def _sky_colors(self, world, biome):
        hrs = world.clock_hours()
        day = SKY_DAY.get(biome, SKY_DAY[FOREST])
        if 6.5 <= hrs < 17.5:
            k = 0.0
            dusk = 0.0
        elif 4.5 <= hrs < 6.5:
            t = (hrs - 4.5) / 2.0
            k, dusk = 1 - t, math.sin(t * math.pi)
        elif 17.5 <= hrs < 19.5:
            t = (hrs - 17.5) / 2.0
            k, dusk = t, math.sin(t * math.pi)
        else:
            k, dusk = 1.0, 0.0
        top = _lerp(day[0], SKY_NIGHT[0], k)
        bot = _lerp(day[1], SKY_NIGHT[1], k)
        top = _lerp(top, SKY_DUSK[0], dusk * 0.5)
        bot = _lerp(bot, SKY_DUSK[1], dusk * 0.8)
        return top, bot, k

    def _gradient(self, top, bot):
        key = (top, bot)
        s = self.sky_cache.get(key)
        if s is None:
            g = pygame.Surface((1, 64))
            for y in range(64):
                g.set_at((0, y), _lerp(top, bot, y / 63))
            s = pygame.transform.smoothscale(g, (SCREEN_W, SCREEN_H))
            if len(self.sky_cache) > 40:
                self.sky_cache.clear()
            self.sky_cache[key] = s
        return s

    def update(self):
        self.time += 1
        if self.fade < 1:
            self.fade = min(1.0, self.fade + 1 / 60)
        for c in self.clouds:
            c[0] += c[2] * 0.4

    def draw_sky(self, screen, camx, camy, world):
        top, bot, night = self._sky_colors(world, self.biome)
        if self.fade < 1:
            pt, pb, _ = self._sky_colors(world, self.prev_biome)
            top = _lerp(pt, top, self.fade)
            bot = _lerp(pb, bot, self.fade)
        # space: darken towards the top of the world
        space_px = world.space_y * 16 * 1.6
        sp = max(0.0, min(1.0, 1 - (camy + SCREEN_H / 2) / max(1, space_px)))
        if sp > 0:
            top = _lerp(top, (4, 6, 20), sp)
            bot = _lerp(bot, (30, 40, 80), sp * 0.7)
        q = lambda c: tuple(v // 4 * 4 for v in c)
        screen.blit(self._gradient(q(top), q(bot)), (0, 0))
        star_alpha = max(night, sp)
        if star_alpha > 0.05:
            for (sx, sy, ph, size) in self.stars:
                tw = 0.6 + 0.4 * math.sin(self.time * 0.05 + ph)
                v = int(255 * star_alpha * tw)
                x = int((sx * SCREEN_W * 1.3 - camx * 0.02) % SCREEN_W)
                y = int(sy * SCREEN_H)
                screen.fill((v, v, min(255, v + 20)), (x, y, size, size))
        # sun & moon on an arc
        if world.is_day:
            p = world.time / DAY_LENGTH
            img = self.sun
        else:
            p = (world.time - DAY_LENGTH) / NIGHT_LENGTH
            img = self.moon
        x = -60 + p * (SCREEN_W + 120)
        y = SCREEN_H * 0.62 - math.sin(p * math.pi) * SCREEN_H * 0.52
        y += max(0, (camy - world.underground_y * 16 + SCREEN_H) * 0.0)
        screen.blit(img, (x - img.get_width() / 2, y - img.get_height() / 2))
        return night

    def draw_layers(self, screen, camx, camy, world, night):
        light = world.sun_color()
        tint = tuple(max(28, min(255, int(c * 255))) // 8 * 8 for c in light)
        # clouds
        for cx, cy, sp, spr in self.clouds:
            x = (cx - camx * sp * 0.3) % (SCREEN_W + 400) - 200
            y = cy - (camy - world.surface[min(world.w - 1,
                                               max(0, int(camx // 16)))] *
                      16) * 0.05
            spr2 = spr.copy()
            spr2.fill(tint + (220,), special_flags=pygame.BLEND_RGBA_MULT)
            screen.blit(spr2, (x, y))
        anchor = world.surface[min(world.w - 1, max(0, int(
            (camx + SCREEN_W / 2) // 16)))] * 16
        if self.fade < 1:
            self._draw_biome_layers(screen, camx, camy, anchor,
                                    self.prev_biome, tint, 255)
            self._draw_biome_layers(screen, camx, camy, anchor, self.biome,
                                    tint, int(255 * self.fade))
        else:
            self._draw_biome_layers(screen, camx, camy, anchor, self.biome,
                                    tint, 255)

    def _draw_biome_layers(self, screen, camx, camy, anchor, biome, tint,
                           alpha):
        layers = self._layers_for(biome)
        for d, layer in enumerate(layers):
            surf = layer.get(tint)
            if alpha < 255:
                surf = surf.copy()
                surf.set_alpha(alpha)
            # vertical: layers sit around the surface line, moving slowly
            k = [0.1, 0.2, 0.3][d]
            ridge_px = [140, 220, 280][d]
            base = SCREEN_H * 0.5 - ridge_px + [-110, -60, -15][d] + \
                (anchor - (camy + SCREEN_H / 2)) * k
            if base > SCREEN_H:
                continue
            w = surf.get_width()
            x = -((camx * layer.parallax) % w)
            while x < SCREEN_W:
                screen.blit(surf, (x, base + layer.top))
                x += w
            bottom = base + layer.full_h
            if bottom < SCREEN_H:
                fc = tuple(int(c * t / 255) for c, t in zip(layer.fill, tint))
                if alpha < 255:
                    tmp = pygame.Surface((SCREEN_W, int(SCREEN_H - bottom) +
                                          1))
                    tmp.fill(fc)
                    tmp.set_alpha(alpha)
                    screen.blit(tmp, (0, bottom))
                else:
                    screen.fill(fc, (0, bottom, SCREEN_W, SCREEN_H - bottom))

    # -------------------------------------------------------- underground
    def _backdrop(self, kind, layer):
        key = (kind, layer)
        if key in self.backdrops:
            return self.backdrops[key]
        base = {
            "dirt": (74, 52, 38), "rock": (56, 52, 50), "hell": (96, 34, 24),
        }[layer]
        tints = {SNOW: (1.15, 1.25, 1.45), JUNGLE: (0.75, 1.1, 0.7),
                 DESERT: (1.3, 1.1, 0.8), CORRUPTION: (0.95, 0.8, 1.25),
                 MUSHROOM: (0.6, 0.75, 1.5), DUNGEON: (0.6, 0.7, 1.3)}
        t = tints.get(kind, (1, 1, 1)) if layer != "hell" else (1, 1, 1)
        col = tuple(min(255, int(c * k)) for c, k in zip(base, t))
        rng = rng_for("backdrop", kind, layer)
        surf = to_surface(TT.backdrop(col, rng, 64), None, 1)
        self.backdrops[key] = surf
        return surf

    def draw_backdrop(self, ws, camx, camy, world):
        ug = world.underground_y * 16
        top = ug - camy
        if top >= SCREEN_H:
            return
        cav = world.cavern_y * 16 - camy
        hell = world.underworld_y * 16 - camy
        kind = self.under_kind
        bands = ((top, cav, "dirt"), (cav, hell, "rock"),
                 (hell, SCREEN_H + 64, "hell"))
        for y0, y1, layer in bands:
            y0c, y1c = max(0, y0), min(SCREEN_H, y1)
            if y0c >= y1c:
                continue
            tex = self._backdrop(kind, layer)
            tw, th = tex.get_size()
            ox = -(camx % tw)
            oy = y0 + ((y0c - y0) // th) * th
            clip = ws.get_clip()
            ws.set_clip(pygame.Rect(0, y0c, SCREEN_W, y1c - y0c))
            y = oy
            while y < y1c:
                x = ox
                while x < SCREEN_W:
                    ws.blit(tex, (x, y))
                    x += tw
                y += th
            # separator band at the top of each layer
            if 0 <= y0 < SCREEN_H:
                ws.fill((24, 18, 14), (0, y0, SCREEN_W, 4))
            ws.set_clip(clip)
