"""World data container: tiles, walls, liquids, simulation and persistence."""
import json
import random
from collections import deque

import numpy as np

from . import tiles as T
from .config import CHUNK, DAY_LENGTH, NIGHT_LENGTH

# surface biome ids
FOREST, OCEAN, DESERT, SNOW, JUNGLE, CORRUPTION, DUNGEON, MUSHROOM, \
    UNDERGROUND, CAVERN, UNDERWORLD, SPACE = range(12)
BIOME_NAMES = ["Forest", "Ocean", "Desert", "Snow", "Jungle", "Corruption",
               "Dungeon", "Mushroom", "Underground", "Cavern", "Underworld",
               "Space"]

WATER, LAVA = 0, 1

_SOLID = T.SOLID
_TILES = T.TILES

# tiles that count towards biome detection
_CORRUPT_SET = np.zeros(T.NUM_TILES, bool)
for _t in (T.CORRUPT_GRASS, T.EBONSTONE, T.EBONSAND, T.PURPLE_ICE,
           T.PLANT_CORRUPT, T.TREE_EBON, T.DEMONITE_ORE):
    _CORRUPT_SET[_t] = True
_JUNGLE_SET = np.zeros(T.NUM_TILES, bool)
for _t in (T.JUNGLE_GRASS, T.PLANT_JUNGLE, T.TREE_JUNGLE, T.VINE_JUNGLE):
    _JUNGLE_SET[_t] = True
_SNOW_SET = np.zeros(T.NUM_TILES, bool)
for _t in (T.SNOW, T.ICE, T.TREE_BOREAL):
    _SNOW_SET[_t] = True
_DESERT_SET = np.zeros(T.NUM_TILES, bool)
for _t in (T.SAND, T.SANDSTONE, T.HARDENED_SAND, T.CACTUS):
    _DESERT_SET[_t] = True
_MUSH_SET = np.zeros(T.NUM_TILES, bool)
for _t in (T.MUSHROOM_GRASS, T.PLANT_MUSHROOM, T.TREE_MUSHROOM):
    _MUSH_SET[_t] = True
_DUNGEON_WALLS = np.zeros(T.NUM_WALLS, bool)
_DUNGEON_WALLS[T.DUNGEON_WALL] = True

_PLANT_FOR_GRASS = {
    T.GRASS: T.PLANT, T.CORRUPT_GRASS: T.PLANT_CORRUPT,
    T.JUNGLE_GRASS: T.PLANT_JUNGLE, T.MUSHROOM_GRASS: T.PLANT_MUSHROOM,
}
_GRASS_FOR_PLANT = {v: k for k, v in _PLANT_FOR_GRASS.items()}


def _pair(s):
    """(name, count) for a chest entry stored as a tuple, list or Stack."""
    if s is None:
        return None
    if hasattr(s, "name"):
        return (s.name, s.count)
    return (s[0], int(s[1]))


class World:
    def __init__(self, w, h, name="World", seed=0):
        self.w, self.h = w, h
        self.name = name
        self.seed = seed
        self.tiles = np.zeros((w, h), np.uint16)
        self.frame = np.zeros((w, h), np.uint8)
        self.walls = np.zeros((w, h), np.uint8)
        self.liquid = np.zeros((w, h), np.uint8)
        self.ltype = np.zeros((w, h), np.uint8)
        self.explored = np.zeros((w, h), bool)
        self.surface = np.zeros(w, np.int32)
        self.biome = np.zeros(w, np.uint8)
        self.sky_top = np.zeros(w, np.int32)
        self.space_y = int(h * 0.06)
        self.underground_y = int(h * 0.31)
        self.cavern_y = int(h * 0.42)
        self.underworld_y = h - int(200 * h / 1200)
        self.spawn = (w // 2, int(h * 0.25))
        self.time = 13500            # 8:15 AM
        self.chests = {}             # (x, y) of top-left -> list of 40 stacks
        self.dirty = set()           # chunks whose tile layer must be redrawn
        self.liquid_dirty = set()    # chunks whose liquid layer must be redrawn
        self.active_liquid = set()
        self.updates = deque()
        self.damage = {}             # (x, y) -> [damage, idle ticks]
        self.wall_damage = {}
        self.tick_count = 0
        self.rng = random.Random(seed)
        # hooks assigned by the game
        self.on_drop = lambda name, count, px, py: None
        self.on_fall = lambda tid, x, y: None
        self.on_tile_changed = lambda x, y: None

    # ------------------------------------------------------------------ time
    @property
    def is_day(self):
        return self.time < DAY_LENGTH

    def clock_hours(self):
        if self.is_day:
            return (4.5 + 15.0 * self.time / DAY_LENGTH) % 24
        return (19.5 + 9.0 * (self.time - DAY_LENGTH) / NIGHT_LENGTH) % 24

    def sun_color(self):
        """Colour/intensity of skylight at the current time."""
        hrs = self.clock_hours()
        night = np.array([0.10, 0.12, 0.22], np.float32)
        day = np.array([1.0, 1.0, 1.0], np.float32)
        dusk = np.array([1.0, 0.70, 0.50], np.float32)
        if 4.5 <= hrs < 6.5:            # sunrise
            k = (hrs - 4.5) / 2.0
            c = night + (dusk - night) * min(1, k * 2) if k < 0.5 else \
                dusk + (day - dusk) * (k - 0.5) * 2
        elif 6.5 <= hrs < 17.5:
            c = day
        elif 17.5 <= hrs < 19.5:        # sunset
            k = (hrs - 17.5) / 2.0
            c = day + (dusk - day) * min(1, k * 2) if k < 0.5 else \
                dusk + (night - dusk) * (k - 0.5) * 2
        else:
            c = night
        return c

    # ----------------------------------------------------------------- access
    def in_bounds(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def get(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return int(self.tiles[x, y])
        return T.STONE

    def solid(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            return bool(_SOLID[self.tiles[x, y]])
        return True

    def tile_def(self, x, y):
        return _TILES[self.get(x, y)]

    # ------------------------------------------------------------- dirtiness
    def mark_dirty(self, x, y):
        cx, cy = x // CHUNK, y // CHUNK
        self.dirty.add((cx, cy))
        lx, ly = x % CHUNK, y % CHUNK
        if lx == 0:
            self.dirty.add((cx - 1, cy))
        elif lx == CHUNK - 1:
            self.dirty.add((cx + 1, cy))
        if ly == 0:
            self.dirty.add((cx, cy - 1))
        elif ly == CHUNK - 1:
            self.dirty.add((cx, cy + 1))

    def mark_liquid_dirty(self, x, y):
        self.liquid_dirty.add((x // CHUNK, y // CHUNK))

    # -------------------------------------------------------------- sunlight
    def recompute_sky(self):
        blocks = T.BLOCKS_SUN[self.tiles] | (self.walls > 0)
        has = blocks.any(axis=1)
        top = blocks.argmax(axis=1)
        self.sky_top = np.where(has, top, self.h).astype(np.int32)

    def update_sky_column(self, x):
        col = T.BLOCKS_SUN[self.tiles[x]] | (self.walls[x] > 0)
        idx = int(col.argmax())
        self.sky_top[x] = idx if col[idx] else self.h

    # -------------------------------------------------------------- mutation
    def set_tile(self, x, y, tid, frame=0, notify=True):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        self.tiles[x, y] = tid
        self.frame[x, y] = frame
        if _SOLID[tid] and self.liquid[x, y]:
            self.liquid[x, y] = 0
            self.mark_liquid_dirty(x, y)
        self.mark_dirty(x, y)
        self.update_sky_column(x)
        self.damage.pop((x, y), None)
        if notify:
            self._neighbours_changed(x, y)
            self.on_tile_changed(x, y)

    def set_wall(self, x, y, wid):
        if not (0 <= x < self.w and 0 <= y < self.h):
            return
        self.walls[x, y] = wid
        self.mark_dirty(x, y)
        self.update_sky_column(x)
        self.wall_damage.pop((x, y), None)
        self.updates.append((x, y))     # torches may lose their support

    def _neighbours_changed(self, x, y):
        for nx, ny in ((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y),
                       (x, y)):
            if 0 <= nx < self.w and 0 <= ny < self.h:
                self.updates.append((nx, ny))
                if self.liquid[nx, ny]:
                    self.active_liquid.add((nx, ny))
        # liquids above/side may now flow into (x, y)
        self.active_liquid.add((x, y))

    # ------------------------------------------------------ multi-tile logic
    def multi_origin(self, x, y):
        f = int(self.frame[x, y])
        return x - (f & 7), y - (f >> 3)

    def place_multi(self, x0, y0, tid):
        w, h = _TILES[tid].size
        for dx in range(w):
            for dy in range(h):
                self.set_tile(x0 + dx, y0 + dy, tid, dy * 8 + dx)
        if tid == T.CHEST and (x0, y0) not in self.chests:
            self.chests[(x0, y0)] = [None] * 40

    def multi_fits(self, x0, y0, tid):
        w, h = _TILES[tid].size
        if x0 < 0 or y0 < 0 or x0 + w > self.w or y0 + h > self.h:
            return False
        for dx in range(w):
            for dy in range(h):
                if not T.REPLACEABLE[self.tiles[x0 + dx, y0 + dy]]:
                    return False
                if self.liquid[x0 + dx, y0 + dy] > 100:
                    return False
        if tid in (T.DOOR_CLOSED, T.DOOR_OPEN):
            return self.solid(x0, y0 - 1) and self.solid(x0, y0 + h)
        for dx in range(w):
            if not self.solid(x0 + dx, y0 + h) and \
                    self.get(x0 + dx, y0 + h) != T.PLATFORM:
                return False
        return True

    def toggle_door(self, x, y):
        tid = self.get(x, y)
        if tid not in (T.DOOR_CLOSED, T.DOOR_OPEN):
            return False
        x0, y0 = self.multi_origin(x, y)
        new = T.DOOR_OPEN if tid == T.DOOR_CLOSED else T.DOOR_CLOSED
        for dy in range(3):
            self.tiles[x0, y0 + dy] = new
            self.mark_dirty(x0, y0 + dy)
        self.update_sky_column(x0)
        for dy in range(3):
            self._neighbours_changed(x0, y0 + dy)
        return True

    # --------------------------------------------------------- tile removal
    def can_mine(self, x, y):
        """Blocks holding up trees or furniture can't be mined (Terraria)."""
        tid = self.get(x, y)
        d = _TILES[tid]
        if not d.breakable or tid == T.AIR:
            return False
        above = self.get(x, y - 1)
        ad = _TILES[above]
        if d.kind in ("block", "platform"):
            if ad.kind in ("tree", "cactus", "sapling"):
                return False
            if ad.kind == "furniture" and above not in (T.DOOR_CLOSED,
                                                       T.DOOR_OPEN):
                return False
            below = self.get(x, y + 1)
            if below in (T.DOOR_CLOSED, T.DOOR_OPEN) and \
                    self.multi_origin(x, y + 1)[1] == y + 1:
                return False
            if above in (T.DOOR_CLOSED, T.DOOR_OPEN):
                return False
        if tid == T.CHEST:
            x0, y0 = self.multi_origin(x, y)
            items = self.chests.get((x0, y0))
            if items and any(s and _pair(s)[1] > 0 for s in items):
                return False
        return True

    def kill_tile(self, x, y, drop=True):
        """Destroy the tile at (x, y) with all side effects."""
        tid = self.get(x, y)
        if tid == T.AIR:
            return
        d = _TILES[tid]
        px, py = x * 16 + 8, y * 16 + 8
        if d.kind in ("tree", "cactus"):
            self._kill_tree(x, y, tid, drop)
            return
        if d.kind == "furniture":
            x0, y0 = self.multi_origin(x, y)
            w, h = d.size
            for dx in range(w):
                for dy in range(h):
                    if self.get(x0 + dx, y0 + dy) == tid:
                        self.set_tile(x0 + dx, y0 + dy, T.AIR)
            if tid == T.CHEST:
                items = self.chests.pop((x0, y0), None)
                if items and drop:
                    for st in items:
                        st = _pair(st)
                        if st:
                            self.on_drop(st[0], st[1], px, py)
            if drop and d.drop:
                self.on_drop(d.drop, 1, (x0 + w / 2) * 16, (y0 + h / 2) * 16)
            return
        self.set_tile(x, y, T.AIR)
        if drop and d.drop:
            self.on_drop(d.drop, 1, px, py)

    def _kill_tree(self, x, y, tid, drop):
        frame = int(self.frame[x, y])
        count = 0
        if frame in (T.TR_ROOT_L, T.TR_ROOT_R):
            self.set_tile(x, y, T.AIR)
            count = 1
        else:
            yy = y
            top_removed = False
            while yy >= 0 and self.get(x, yy) == tid and \
                    int(self.frame[x, yy]) not in (T.TR_ROOT_L, T.TR_ROOT_R):
                f = int(self.frame[x, yy])
                if f == T.TR_TOP:
                    top_removed = True
                    count += 4 if tid != T.CACTUS else 1
                if f in (T.TR_BRANCH_L, T.TR_BRANCH_R):
                    count += 1
                self.set_tile(x, yy, T.AIR)
                count += 1
                yy -= 1
            # removed the base -> roots go too
            if self.get(x, y + 1) != tid:
                for rx in (x - 1, x + 1):
                    if self.get(rx, y) == tid and int(self.frame[rx, y]) in \
                            (T.TR_ROOT_L, T.TR_ROOT_R):
                        self.set_tile(rx, y, T.AIR)
                        count += 1
            if drop and top_removed and tid in (T.TREE, T.TREE_EBON,
                                                T.TREE_JUNGLE, T.TREE_BOREAL):
                n = self.rng.randint(0, 2)
                if n:
                    self.on_drop("Acorn", n, x * 16 + 8, (yy + 1) * 16)
        d = _TILES[tid]
        if drop and d.drop:
            n = max(1, count // 2 + self.rng.randint(0, 2))
            self.on_drop(d.drop, n, x * 16 + 8, y * 16)

    def kill_wall(self, x, y, drop=True):
        wid = int(self.walls[x, y])
        if wid == 0:
            return
        self.set_wall(x, y, T.NO_WALL)
        wd = T.WALLS[wid]
        if drop and wd.drop:
            self.on_drop(wd.drop, 1, x * 16 + 8, y * 16 + 8)

    # ----------------------------------------------------- support / physics
    def process_updates(self, limit=400):
        n = 0
        seen = set()
        while self.updates and n < limit:
            x, y = self.updates.popleft()
            if (x, y) in seen:
                continue
            seen.add((x, y))
            n += 1
            self._check_support(x, y)

    def _check_support(self, x, y):
        tid = self.get(x, y)
        if tid == T.AIR:
            return
        d = _TILES[tid]
        kind = d.kind
        if kind == "block":
            if d.falls:
                below = self.get(x, y + 1)
                if not _SOLID[below] and _TILES[below].kind in (
                        "air", "plant", "vine", "torch") and y + 1 < self.h:
                    self.set_tile(x, y, T.AIR)
                    self.on_fall(tid, x, y)
            return
        if kind == "plant":
            g = _GRASS_FOR_PLANT.get(tid)
            below = self.get(x, y + 1)
            if below not in T.GRASS_TILES:
                self.set_tile(x, y, T.AIR)
            elif g is not None and below != g:
                self.set_tile(x, y, _PLANT_FOR_GRASS[below],
                              int(self.frame[x, y]))
        elif kind == "vine":
            above = self.get(x, y - 1)
            if not (above in T.GRASS_TILES or _TILES[above].kind == "vine"):
                self.set_tile(x, y, T.AIR)
        elif kind == "sapling":
            if self.get(x, y + 1) not in T.GRASS_TILES and \
                    self.get(x, y + 1) not in (T.SNOW, T.SAND):
                self.kill_tile(x, y)
        elif kind == "torch":
            if not (self.walls[x, y] or self.solid(x - 1, y) or
                    self.solid(x + 1, y) or self.solid(x, y + 1)):
                self.kill_tile(x, y)
        elif kind in ("tree", "cactus"):
            f = int(self.frame[x, y])
            if f in (T.TR_ROOT_L, T.TR_ROOT_R):
                if not self.solid(x, y + 1):
                    self.set_tile(x, y, T.AIR)
                return
            below = self.get(x, y + 1)
            if below != tid and not _SOLID[below]:
                self.kill_tile(x, y)
        elif kind == "furniture":
            x0, y0 = self.multi_origin(x, y)
            w, h = d.size
            ok = True
            for dx in range(w):
                for dy in range(h):
                    if self.get(x0 + dx, y0 + dy) != tid:
                        ok = False
            if ok:
                if tid in (T.DOOR_CLOSED, T.DOOR_OPEN):
                    ok = self.solid(x0, y0 - 1) and self.solid(x0, y0 + h)
                else:
                    for dx in range(w):
                        b = self.get(x0 + dx, y0 + h)
                        if not (_SOLID[b] or b == T.PLATFORM):
                            ok = False
            if not ok and d.breakable:
                self.kill_tile(x, y)
        elif kind == "platform":
            pass

    # ---------------------------------------------------------------- liquids
    def update_liquids(self, budget=1600):
        if not self.active_liquid:
            return
        cells = self.active_liquid
        self.active_liquid = set()
        if len(cells) > budget:
            ordered = sorted(cells, key=lambda c: -c[1])
            work, rest = ordered[:budget], ordered[budget:]
            self.active_liquid.update(rest)
        else:
            work = sorted(cells, key=lambda c: -c[1])
        liq, lt, tiles = self.liquid, self.ltype, self.tiles
        W, H = self.w, self.h
        lava_tick = self.tick_count % 3 == 0
        act = self.active_liquid
        for x, y in work:
            if not (1 <= x < W - 1 and 0 <= y < H - 1):
                continue
            a = int(liq[x, y])
            if a == 0:
                continue
            t = int(lt[x, y])
            if t == LAVA and not lava_tick:
                act.add((x, y))
                continue
            changed = False
            # ---- fall
            if not _SOLID[tiles[x, y + 1]]:
                b = int(liq[x, y + 1])
                if b and int(lt[x, y + 1]) != t:
                    self._mix(x, y + 1)
                    liq[x, y] = 0
                    self.mark_liquid_dirty(x, y)
                    continue
                if b < 255:
                    f = min(a, 255 - b)
                    liq[x, y + 1] = b + f
                    lt[x, y + 1] = t
                    a -= f
                    liq[x, y] = a
                    changed = True
                    act.add((x, y + 1))
                    self.mark_liquid_dirty(x, y + 1)
            # ---- spread
            if a > 0:
                nbrs = []
                for nx in (x - 1, x + 1):
                    if _SOLID[tiles[nx, y]]:
                        continue
                    nb = int(liq[nx, y])
                    if nb and int(lt[nx, y]) != t:
                        self._mix(nx, y)
                        continue
                    nbrs.append((nx, nb))
                if nbrs:
                    total = a + sum(n for _, n in nbrs)
                    cnt = len(nbrs) + 1
                    avg = total // cnt
                    rem = total - avg * cnt
                    if any(abs(n - avg) > 1 for _, n in nbrs) or \
                            abs(a - (avg + rem)) > 1:
                        for nx, nb in nbrs:
                            liq[nx, y] = avg
                            lt[nx, y] = t
                            act.add((nx, y))
                            self.mark_liquid_dirty(nx, y)
                        a = avg + rem
                        liq[x, y] = a
                        changed = True
                if a <= 3 and _SOLID[tiles[x, y + 1]]:
                    liq[x, y] = 0
                    a = 0
                    changed = True
            if changed:
                self.mark_liquid_dirty(x, y)
                act.add((x, y))
                act.add((x, y - 1))
                # torches are washed away
                if _TILES[int(tiles[x, y])].kind == "torch" and t == WATER:
                    self.kill_tile(x, y)

    def _mix(self, x, y):
        """Water meets lava -> obsidian."""
        self.liquid[x, y] = 0
        self.mark_liquid_dirty(x, y)
        if T.REPLACEABLE[self.tiles[x, y]]:
            self.set_tile(x, y, T.OBSIDIAN)

    # --------------------------------------------------------- random ticks
    def random_updates(self, cx, cy, n=60):
        rng = self.rng
        tiles = self.tiles
        for _ in range(n):
            x = cx + rng.randint(-90, 90)
            y = cy + rng.randint(-60, 60)
            if not (2 <= x < self.w - 2 and 2 <= y < self.h - 2):
                continue
            tid = int(tiles[x, y])
            if tid in (T.DIRT, T.MUD):
                # grass spreads onto exposed dirt / mud
                if self._exposed(x, y):
                    for dx, dy in ((-1, -1), (0, -1), (1, -1), (-1, 0),
                                   (1, 0), (-1, 1), (0, 1), (1, 1)):
                        g = int(tiles[x + dx, y + dy])
                        if tid == T.DIRT and g in (T.GRASS, T.CORRUPT_GRASS):
                            self.set_tile(x, y, g)
                            break
                        if tid == T.MUD and g in (T.JUNGLE_GRASS,
                                                  T.MUSHROOM_GRASS):
                            self.set_tile(x, y, g)
                            break
            elif tid in T.GRASS_TILES:
                above = int(tiles[x, y - 1])
                if above == T.AIR and self.liquid[x, y - 1] == 0 and \
                        rng.random() < 0.3:
                    self.set_tile(x, y - 1, _PLANT_FOR_GRASS[tid],
                                  rng.randint(0, 5))
                below = int(tiles[x, y + 1])
                if below == T.AIR and tid in (T.GRASS, T.JUNGLE_GRASS) and \
                        rng.random() < 0.1:
                    self.set_tile(x, y + 1, T.VINE if tid == T.GRASS
                                  else T.VINE_JUNGLE)
                # corruption slowly spreads through grass
                if tid == T.CORRUPT_GRASS and rng.random() < 0.15:
                    nx, ny = x + rng.randint(-3, 3), y + rng.randint(-3, 3)
                    if self.get(nx, ny) == T.GRASS:
                        self.set_tile(nx, ny, T.CORRUPT_GRASS)
            elif _TILES[tid].kind == "vine":
                if int(tiles[x, y + 1]) == T.AIR and rng.random() < 0.3:
                    length = 1
                    yy = y
                    while _TILES[self.get(x, yy - 1)].kind == "vine":
                        yy -= 1
                        length += 1
                    if length < 10:
                        self.set_tile(x, y + 1, tid)
            elif tid == T.SAPLING:
                if rng.random() < 0.12:
                    self.grow_tree_from_sapling(x, y)

    def _exposed(self, x, y):
        t = self.tiles
        return (not _SOLID[t[x, y - 1]] or not _SOLID[t[x, y + 1]] or
                not _SOLID[t[x - 1, y]] or not _SOLID[t[x + 1, y]])

    def grow_tree_from_sapling(self, x, y):
        ground = self.get(x, y + 1)
        kind = {T.GRASS: T.TREE, T.CORRUPT_GRASS: T.TREE_EBON,
                T.JUNGLE_GRASS: T.TREE_JUNGLE, T.SNOW: T.TREE_BOREAL,
                T.SAND: T.TREE_PALM, T.MUSHROOM_GRASS: T.TREE_MUSHROOM
                }.get(ground)
        if kind is None:
            return False
        height = self.rng.randint(6, 13)
        for yy in range(y - height - 3, y + 1):
            for xx in (x - 1, x, x + 1):
                if xx == x and yy == y:
                    continue
                if not T.REPLACEABLE[self.get(xx, yy)] and \
                        self.get(xx, yy) != T.SAPLING:
                    return False
        self.tiles[x, y] = T.AIR
        build_tree(self, x, y, height, kind, self.rng)
        return True

    # ------------------------------------------------------------- biomes
    def detect_biome(self, tx, ty):
        """Terraria-style biome detection by counting nearby tiles."""
        if ty < self.space_y:
            return SPACE
        if ty >= self.underworld_y:
            return UNDERWORLD
        x0, x1 = max(0, tx - 50), min(self.w, tx + 50)
        y0, y1 = max(0, ty - 35), min(self.h, ty + 35)
        reg = self.tiles[x0:x1, y0:y1]
        counts = np.bincount(reg.ravel(), minlength=T.NUM_TILES)
        corrupt = int(counts[_CORRUPT_SET].sum())
        jungle = int(counts[_JUNGLE_SET].sum())
        snow = int(counts[_SNOW_SET].sum())
        desert = int(counts[_DESERT_SET].sum())
        mush = int(counts[_MUSH_SET].sum())
        if self.walls[max(0, min(self.w - 1, tx)),
                      max(0, min(self.h - 1, ty))] == T.DUNGEON_WALL:
            return DUNGEON
        if mush > 100:
            return MUSHROOM
        if corrupt > 200:
            return CORRUPTION
        if jungle > 140:
            return JUNGLE
        if snow > 500:
            return SNOW
        if desert > 800:
            return DESERT
        if ty < self.underground_y:
            if tx < 380 or tx > self.w - 380:
                return OCEAN
            return FOREST
        if ty < self.cavern_y:
            return UNDERGROUND
        return CAVERN

    # --------------------------------------------------------------- spawn
    def find_spawn_y(self, x):
        y = max(1, self.space_y)
        while y < self.h - 4:
            if self.solid(x, y + 3) and not self.solid(x, y) and \
                    not self.solid(x, y + 1) and not self.solid(x, y + 2) and \
                    self.liquid[x, y + 2] == 0:
                return y
            y += 1
        return self.spawn[1]

    def valid_spawn(self):
        x, y = self.spawn
        for dy in range(3):
            if self.solid(x, y + dy):
                return False
        return True

    # ------------------------------------------------------------ persistence
    def save(self, path):
        chests = {f"{x},{y}": [list(_pair(s)) if s else None for s in items]
                  for (x, y), items in self.chests.items()}
        meta = dict(name=self.name, seed=self.seed, w=self.w, h=self.h,
                    spawn=list(self.spawn), time=self.time,
                    space_y=self.space_y, underground_y=self.underground_y,
                    cavern_y=self.cavern_y, underworld_y=self.underworld_y,
                    chests=chests, version=1)
        tmp = path + ".tmp.npz"
        np.savez_compressed(
            tmp, tiles=self.tiles, frame=self.frame, walls=self.walls,
            liquid=self.liquid, ltype=self.ltype,
            explored=np.packbits(self.explored, axis=None),
            surface=self.surface, biome=self.biome,
            meta=np.frombuffer(json.dumps(meta).encode(), dtype=np.uint8))
        import os
        os.replace(tmp, path)

    @classmethod
    def load(cls, path):
        data = np.load(path)
        meta = json.loads(bytes(data["meta"]).decode())
        w = cls(meta["w"], meta["h"], meta["name"], meta["seed"])
        w.tiles = data["tiles"].astype(np.uint16)
        w.frame = data["frame"]
        w.walls = data["walls"]
        w.liquid = data["liquid"]
        w.ltype = data["ltype"]
        w.explored = np.unpackbits(data["explored"])[:w.w * w.h] \
            .reshape(w.w, w.h).astype(bool)
        w.surface = data["surface"]
        w.biome = data["biome"]
        w.spawn = tuple(meta["spawn"])
        w.time = meta["time"]
        w.space_y = meta["space_y"]
        w.underground_y = meta["underground_y"]
        w.cavern_y = meta["cavern_y"]
        w.underworld_y = meta["underworld_y"]
        for key, items in meta.get("chests", {}).items():
            x, y = map(int, key.split(","))
            w.chests[(x, y)] = [tuple(s) if s else None for s in items]
        w.recompute_sky()
        return w

    @staticmethod
    def read_meta(path):
        data = np.load(path)
        return json.loads(bytes(data["meta"]).decode())


# ---------------------------------------------------------------------------
# Tree builder (shared by world generation and sapling growth)
# ---------------------------------------------------------------------------
def build_tree(world, x, y, height, kind, rng):
    """Build a tree whose base trunk tile is at (x, y)."""
    tiles, frame = world.tiles, world.frame
    for i in range(height):
        yy = y - i
        f = T.TR_TRUNK
        if i == height - 1:
            f = T.TR_TOP
        elif 2 <= i < height - 2 and kind not in (T.TREE_PALM,
                                                  T.TREE_MUSHROOM):
            r = rng.random()
            if r < 0.14:
                f = T.TR_BRANCH_L
            elif r < 0.28:
                f = T.TR_BRANCH_R
        tiles[x, yy] = kind
        frame[x, yy] = f
        world.mark_dirty(x, yy)
    if kind not in (T.TREE_PALM, T.TREE_MUSHROOM):
        for rx, rf in ((x - 1, T.TR_ROOT_L), (x + 1, T.TR_ROOT_R)):
            if 0 <= rx < world.w and tiles[rx, y] == T.AIR and \
                    _SOLID[tiles[rx, y + 1]] and rng.random() < 0.55:
                tiles[rx, y] = kind
                frame[rx, y] = rf
                world.mark_dirty(rx, y)
