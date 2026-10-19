"""World renderer: cached tile chunks, liquids, decorations and lighting."""
import numpy as np
import pygame

from . import lighting
from . import tiles as T
from .config import CHUNK, SCREEN_W, SCREEN_H, TILE, SETTINGS

CPX = CHUNK * TILE

# tile kind codes for fast dispatch
K_AIR, K_BLOCK, K_PLATFORM, K_TORCH, K_TREE, K_CACTUS, K_PLANT, K_VINE, \
    K_SAPLING, K_FURN = range(10)
_KIND_CODES = {"air": K_AIR, "block": K_BLOCK, "platform": K_PLATFORM,
               "torch": K_TORCH, "tree": K_TREE, "cactus": K_CACTUS,
               "plant": K_PLANT, "vine": K_VINE, "sapling": K_SAPLING,
               "furniture": K_FURN}
KIND = np.array([_KIND_CODES[t.kind] for t in T.TILES], np.uint8)
KIND_L = KIND.tolist()

WATER_COL = (38, 86, 214, 150)
WATER_TOP = (120, 170, 255, 190)
LAVA_COL = (255, 104, 18, 240)
LAVA_TOP = (255, 200, 80, 255)

PLATFORM_LINK = T.SOLID | (np.arange(T.NUM_TILES) == T.PLATFORM)


def _variants(xs, ys):
    return ((xs.astype(np.int64) * 73856093) ^
            (ys.astype(np.int64) * 19349663)) % 3


class Renderer:
    def __init__(self, world, assets, background):
        self.world = world
        self.assets = assets
        self.bg = background
        self.cache = {}
        self.lcache = {}
        self.lcache_age = {}
        self.world_surf = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        self.light = None
        self.light_origin = (0, 0)
        self.frame = 0
        self.margin = 24       # tiles beyond the screen that still cast light
        self.visible_torches = []

    # ---------------------------------------------------------------- cache
    def invalidate(self):
        self.cache.clear()
        self.lcache.clear()

    def _pad(self, arr, x0, y0, fill):
        W, H = self.world.w, self.world.h
        n = CHUNK + 2
        out = np.full((n, n), fill, arr.dtype)
        xa, xb = max(0, x0 - 1), min(W, x0 + CHUNK + 1)
        ya, yb = max(0, y0 - 1), min(H, y0 + CHUNK + 1)
        if xa < xb and ya < yb:
            out[xa - (x0 - 1):xb - (x0 - 1), ya - (y0 - 1):yb - (y0 - 1)] = \
                arr[xa:xb, ya:yb]
        return out

    def render_chunk(self, cx, cy):
        world, A = self.world, self.assets
        x0, y0 = cx * CHUNK, cy * CHUNK
        surf = pygame.Surface((CPX, CPX), pygame.SRCALPHA)
        tp = self._pad(world.tiles, x0, y0, T.STONE)
        wp = self._pad(world.walls, x0, y0, 0)
        merge = T.MERGE[tp]
        tiles = tp[1:-1, 1:-1]
        walls = wp[1:-1, 1:-1]
        frames = world.frame[x0:x0 + CHUNK, y0:y0 + CHUNK]
        tmask = (merge[1:-1, :-2].astype(np.uint8) |
                 (merge[2:, 1:-1].astype(np.uint8) << 1) |
                 (merge[1:-1, 2:].astype(np.uint8) << 2) |
                 (merge[:-2, 1:-1].astype(np.uint8) << 3))
        grp = T.GROUP[tp]
        gc = grp[1:-1, 1:-1]
        dmask = ((merge[1:-1, :-2] & (grp[1:-1, :-2] != gc)).astype(np.uint8) |
                 ((merge[2:, 1:-1] & (grp[2:, 1:-1] != gc)).astype(np.uint8)
                  << 1) |
                 ((merge[1:-1, 2:] & (grp[1:-1, 2:] != gc)).astype(np.uint8)
                  << 2) |
                 ((merge[:-2, 1:-1] & (grp[:-2, 1:-1] != gc)).astype(np.uint8)
                  << 3))
        wh = wp > 0
        wmask = (wh[1:-1, :-2].astype(np.uint8) |
                 (wh[2:, 1:-1].astype(np.uint8) << 1) |
                 (wh[1:-1, 2:].astype(np.uint8) << 2) |
                 (wh[:-2, 1:-1].astype(np.uint8) << 3))
        blits = []
        # walls (skip ones fully hidden behind surrounded blocks)
        hidden = T.MERGE[tiles] & (tmask == 15)
        xs, ys = np.nonzero((walls > 0) & ~hidden)
        if len(xs):
            var = _variants(xs + x0, ys + y0).tolist()
            wl = walls[xs, ys].tolist()
            wm = wmask[xs, ys].tolist()
            wall_tex = A.wall
            for x, y, w, m, v in zip(xs.tolist(), ys.tolist(), wl, wm, var):
                blits.append((wall_tex[w][m][v], (x * 16, y * 16)))
        # tiles
        xs, ys = np.nonzero(tiles > 0)
        if len(xs):
            var = _variants(xs + x0, ys + y0).tolist()
            tl = tiles[xs, ys].tolist()
            tm = tmask[xs, ys].tolist()
            fr = frames[xs, ys].tolist()
            dm = dmask[xs, ys].tolist()
            link = PLATFORM_LINK[tp]
            tile_tex = A.tile
            seams = A.seams
            for x, y, t, m, f, v, d in zip(xs.tolist(), ys.tolist(), tl, tm,
                                           fr, var, dm):
                k = KIND_L[t]
                pos = (x * 16, y * 16)
                if k == K_BLOCK:
                    blits.append((tile_tex[t][m][v], pos))
                    if d:
                        blits.append((seams[d], pos))
                elif k == K_PLATFORM:
                    pm = int(link[x, y + 1]) | (int(link[x + 2, y + 1]) << 1)
                    blits.append((A.platform[pm], pos))
                elif k == K_TORCH:
                    blits.append((A.torch[f & 3], pos))
                elif k == K_TREE:
                    if f == T.TR_ROOT_L:
                        blits.append((A.root[t][0], pos))
                    elif f == T.TR_ROOT_R:
                        blits.append((A.root[t][1], pos))
                    else:
                        blits.append((A.trunk[t][v], pos))
                elif k == K_CACTUS:
                    blits.append((A.cactus_top if f == T.TR_TOP else A.cactus,
                                  pos))
                elif k == K_PLANT:
                    blits.append((A.plant[t][f % 6], pos))
                elif k == K_VINE:
                    blits.append((A.vine[t][(x + y + x0) % 4], pos))
                elif k == K_SAPLING:
                    blits.append((A.sapling, pos))
                elif k == K_FURN:
                    spr = A.furniture.get(t)
                    if spr is not None:
                        fx, fy = f & 7, f >> 3
                        blits.append((spr, pos, (fx * 16, fy * 16, 16, 16)))
        surf.blits(blits, doreturn=False)
        return surf

    def render_liquid(self, cx, cy):
        world = self.world
        x0, y0 = cx * CHUNK, cy * CHUNK
        liq = world.liquid[x0:x0 + CHUNK, y0:y0 + CHUNK]
        if not liq.any():
            return None
        lt = world.ltype[x0:x0 + CHUNK, y0:y0 + CHUNK]
        above = np.zeros_like(liq)
        if y0 > 0:
            above[:, 0] = world.liquid[x0:x0 + CHUNK, y0 - 1]
        above[:, 1:] = liq[:, :-1]
        surf = pygame.Surface((CPX, CPX), pygame.SRCALPHA)
        xs, ys = np.nonzero(liq)
        for x, y, a, ab, t in zip(xs.tolist(), ys.tolist(),
                                  liq[xs, ys].tolist(), above[xs, ys].tolist(),
                                  lt[xs, ys].tolist()):
            px, py = x * 16, y * 16
            if ab:
                surf.fill(LAVA_COL if t else WATER_COL, (px, py, 16, 16))
            else:
                h = max(2, round(a * 16 / 255))
                surf.fill(LAVA_COL if t else WATER_COL,
                          (px, py + 16 - h, 16, h))
                surf.fill(LAVA_TOP if t else WATER_TOP,
                          (px, py + 16 - h, 16, 2))
        return surf

    def _get_chunk(self, key, budget):
        surf = self.cache.get(key)
        if surf is None or key in self.world.dirty:
            if surf is not None and budget[0] <= 0:
                return surf
            surf = self.render_chunk(*key)
            self.cache[key] = surf
            self.world.dirty.discard(key)
            budget[0] -= 1
        return surf

    def _get_liquid(self, key):
        if key in self.world.liquid_dirty:
            last = self.lcache_age.get(key, -99)
            if self.frame - last >= 3 or key not in self.lcache:
                self.lcache[key] = self.render_liquid(*key)
                self.lcache_age[key] = self.frame
                self.world.liquid_dirty.discard(key)
        elif key not in self.lcache:
            self.lcache[key] = self.render_liquid(*key)
            self.lcache_age[key] = self.frame
        return self.lcache[key]

    def _trim_cache(self, cx0, cy0, cx1, cy1):
        if len(self.cache) > 110:
            for key in list(self.cache):
                if not (cx0 - 3 <= key[0] <= cx1 + 3 and
                        cy0 - 3 <= key[1] <= cy1 + 3):
                    del self.cache[key]
                    self.lcache.pop(key, None)

    # ----------------------------------------------------------------- draw
    def draw(self, screen, camx, camy, player, entities, particles,
             lights=()):
        self.frame += 1
        world = self.world
        self.assets.anim_tick = world.tick_count
        ws = self.world_surf
        ws.fill((0, 0, 0, 0))
        icx, icy = int(camx), int(camy)
        # underground backdrop (behind everything, lit by the light map)
        self.bg.draw_backdrop(ws, icx, icy, world)
        cx0, cy0 = icx // CPX, icy // CPX
        cx1 = (icx + SCREEN_W) // CPX
        cy1 = (icy + SCREEN_H) // CPX
        budget = [6]
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                if cx < 0 or cy < 0 or cx * CHUNK >= world.w or \
                        cy * CHUNK >= world.h:
                    continue
                ws.blit(self._get_chunk((cx, cy), budget),
                        (cx * CPX - icx, cy * CPX - icy))
        # prefetch one chunk around the view
        if budget[0] > 3:
            for cx, cy in ((cx0 - 1, cy0), (cx1 + 1, cy0), (cx0, cy1 + 1),
                           (cx0 - 1, cy1), (cx1 + 1, cy1), (cx1, cy0 - 1)):
                if 0 <= cx * CHUNK < world.w and 0 <= cy * CHUNK < world.h \
                        and (cx, cy) not in self.cache:
                    self.cache[(cx, cy)] = self.render_chunk(cx, cy)
                    break
        self._trim_cache(cx0, cy0, cx1, cy1)
        self._draw_tree_decor(ws, icx, icy)
        self._draw_cracks(ws, icx, icy)
        self._draw_flames(ws, icx, icy)
        for e in entities:
            e.draw(ws, icx, icy, self.assets)
        player.draw(ws, icx, icy, self.assets)
        for p in particles:
            if not p.glow:
                p.draw(ws, icx, icy, self.assets)
        for cy in range(cy0, cy1 + 1):
            for cx in range(cx0, cx1 + 1):
                if cx < 0 or cy < 0 or cx * CHUNK >= world.w or \
                        cy * CHUNK >= world.h:
                    continue
                ls = self._get_liquid((cx, cy))
                if ls is not None:
                    ws.blit(ls, (cx * CPX - icx, cy * CPX - icy))
        self._apply_light(ws, icx, icy, lights)
        screen.blit(ws, (0, 0))
        for p in particles:
            if p.glow:
                p.draw(screen, icx, icy, self.assets)

    def _draw_flames(self, ws, icx, icy):
        """Animated flames of the placed torches on screen (the sticks are
        part of the cached chunks).  Drawn before lighting, so they sit
        behind the player and take the torch's own warm light."""
        world, A = self.world, self.assets
        x0, y0 = max(0, icx // 16 - 1), max(0, icy // 16 - 1)
        x1 = min(world.w, (icx + SCREEN_W) // 16 + 2)
        y1 = min(world.h, (icy + SCREEN_H) // 16 + 2)
        xs, ys = np.nonzero(world.tiles[x0:x1, y0:y1] == T.TORCH)
        frames = world.frame[x0:x1, y0:y1]
        torches = []
        for x, y in zip(xs.tolist(), ys.tolist()):
            f = int(frames[x, y]) & 3
            tx, ty = x + x0, y + y0
            ox, oy = A.flame_offset[f]
            ws.blit(A.flame(tx, ty), (tx * 16 + ox - icx, ty * 16 + oy - icy))
            dx = -2 if f == T.TORCH_LEFT else 2 if f == T.TORCH_RIGHT else 0
            torches.append((tx * 16 + 8 + dx, ty * 16 + 3))
        self.visible_torches = torches      # ember sources

    def _draw_tree_decor(self, ws, icx, icy):
        world, A = self.world, self.assets
        x0 = max(0, icx // 16 - 4)
        y0 = max(0, icy // 16 - 2)
        x1 = min(world.w, (icx + SCREEN_W) // 16 + 5)
        y1 = min(world.h, (icy + SCREEN_H) // 16 + 8)
        reg = world.tiles[x0:x1, y0:y1]
        tree = T.IS_TREE[reg]
        if not tree.any():
            return
        fr = world.frame[x0:x1, y0:y1]
        xs, ys = np.nonzero(tree & ((fr == T.TR_TOP) | (fr == T.TR_BRANCH_L) |
                                    (fr == T.TR_BRANCH_R)))
        for x, y in zip(xs.tolist(), ys.tolist()):
            tid = int(reg[x, y])
            f = int(fr[x, y])
            wx, wy = (x + x0) * 16, (y + y0) * 16
            if tid == T.CACTUS:
                if f in (T.TR_BRANCH_L, T.TR_BRANCH_R):
                    side = 0 if f == T.TR_BRANCH_L else 1
                    spr = A.cactus_arm[side]
                    ox = -16 if side == 0 else 16
                    ws.blit(spr, (wx + ox - icx, wy - 16 - icy))
                continue
            if f == T.TR_TOP:
                v = (x + x0) % 3
                spr = A.canopy[tid][v]
                sw, shh = spr.get_size()
                oy = 6 if tid != T.TREE_MUSHROOM else 0
                ws.blit(spr, (wx + 8 - sw // 2 - icx, wy + oy - shh + 6 - icy))
            else:
                side = 0 if f == T.TR_BRANCH_L else 1
                spr = A.branch[tid][side]
                ox = -spr.get_width() + 6 if side == 0 else 10
                ws.blit(spr, (wx + ox - icx, wy - 8 - icy))

    def _draw_cracks(self, ws, icx, icy):
        A = self.assets
        for (x, y), (dmg, _) in self.world.damage.items():
            stage = min(2, int(dmg / 34))
            ws.blit(A.cracks[stage], (x * 16 - icx, y * 16 - icy))

    def _apply_light(self, ws, icx, icy, lights=()):
        world = self.world
        tx0, ty0 = icx // 16, icy // 16
        nx, ny = SCREEN_W // 16 + 2, SCREEN_H // 16 + 2
        m = self.margin
        sun = world.sun_color()
        light = lighting.compute(world, tx0 - m, ty0 - m, nx + 2 * m,
                                 ny + 2 * m, sun, lights)
        vis = light[m:m + nx, m:m + ny]
        self.light = light
        self.light_origin = (tx0 - m, ty0 - m)
        # reveal the map
        xa, ya = max(0, tx0), max(0, ty0)
        xb, yb = min(world.w, tx0 + nx), min(world.h, ty0 + ny)
        if xa < xb and ya < yb:
            lit = vis[xa - tx0:xb - tx0, ya - ty0:yb - ty0].max(axis=2) > 0.05
            world.explored[xa:xb, ya:yb] |= lit
        # one extra tile on every side so the interpolated map covers the
        # whole screen; smoothscale maps source pixel i to dest i*16 exactly
        # when scaling to (n - 1) * 16, so sample points sit on tile centres
        ext = light[m - 1:m + nx + 1, m - 1:m + ny + 1]
        arr = (np.clip(ext, 0, 1) * 255).astype(np.uint8)    # linear
        small = pygame.surfarray.make_surface(arr)
        n2, m2 = arr.shape[0], arr.shape[1]
        if SETTINGS.get("lighting", "color") == "retro":
            big = pygame.transform.scale(small, (n2 * 16, m2 * 16))
            off = 0
        else:
            big = pygame.transform.smoothscale(small, ((n2 - 1) * 16,
                                                       (m2 - 1) * 16))
            off = 8
        ws.blit(big, ((tx0 - 1) * 16 - icx + off, (ty0 - 1) * 16 - icy + off),
                special_flags=pygame.BLEND_RGB_MULT)

    def light_at(self, px, py):
        """Light colour at a world pixel (from the last computed map)."""
        if self.light is None:
            return (1.0, 1.0, 1.0)
        ox, oy = self.light_origin
        tx, ty = int(px // 16) - ox, int(py // 16) - oy
        if 0 <= tx < self.light.shape[0] and 0 <= ty < self.light.shape[1]:
            return tuple(float(v) for v in self.light[tx, ty])
        return (0.0, 0.0, 0.0)
