"""The player: physics, stats, item use and drawing."""
import math

import pygame

from . import config as C
from . import tiles as T
from .inventory import Inventory
from .customskins import make_gfx
from .items import ITEMS, STARTER_ITEMS, held_sprite
from .playergfx import PlayerGfx, IDLE, JUMP, LEG_FRAMES
from .world import WATER, LAVA

_SOLID = T.SOLID


class Player:
    def __init__(self, name="Player", look=None):
        self.name = name
        self.look = look or {}
        self.gfx = make_gfx(self.look)
        self.inv = Inventory()
        self.w, self.h = C.PLAYER_W, C.PLAYER_H
        self.x = self.y = 0.0
        self.vx = self.vy = 0.0
        self.dir = 1
        self.on_ground = False
        self.jump_timer = 0
        self.jump_held = False
        self.life_max = 100
        self.life = 100
        self.mana_max = 20
        self.mana = 20
        self.breath = C.BREATH_MAX
        self.immune = 0
        self.dead = False
        self.respawn = 0
        self.fall_start = None
        self.regen_time = 0
        self.regen_acc = 0.0
        self.mana_acc = 0.0
        self.buffs = {}            # name -> ticks remaining
        self.wet = False
        self.in_lava = False
        self.head_wet = False
        # animation
        self.walk_frame = 0.0
        self.item_anim = 0
        self.item_time = 0
        self.use_item = None
        self.use_anim_max = 1
        self.use_target = None
        self.mouse_was_down = False
        self.stats = {"deaths": 0}
        self.events = []           # (kind, payload) consumed by the game

    def set_look(self, look):
        """Change appearance (skin preset or custom colours)."""
        self.look = dict(look)
        self.gfx = make_gfx(self.look)

    # ---------------------------------------------------------- creation
    @classmethod
    def new(cls, name, look):
        p = cls(name, look)
        if C.STARTER_KIT:
            for n, c in STARTER_ITEMS:
                p.inv.add(n, c)
        return p

    def to_json(self):
        return {"name": self.name, "look": self.look,
                "life_max": self.life_max, "mana_max": self.mana_max,
                "inventory": self.inv.to_json(), "stats": self.stats}

    @classmethod
    def from_json(cls, d):
        p = cls(d.get("name", "Player"), d.get("look", {}))
        p.life_max = d.get("life_max", 100)
        p.mana_max = d.get("mana_max", 20)
        p.life = p.life_max
        p.mana = p.mana_max
        p.inv = Inventory.from_json(d.get("inventory", {}))
        p.stats = d.get("stats", {"deaths": 0})
        return p

    # ------------------------------------------------------------ helpers
    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    def rect(self):
        return pygame.Rect(int(self.x), int(self.y), self.w, self.h)

    def spawn_at(self, world):
        sx, sy = world.spawn
        if not world.valid_spawn():
            sy = world.find_spawn_y(sx)
            world.spawn = (sx, sy)
        self.x = sx * 16 + 8 - self.w / 2
        self.y = (sy + 3) * 16 - self.h
        self.vx = self.vy = 0
        self.fall_start = None

    def defense(self):
        return self.inv.defense()

    def in_reach(self, tx, ty):
        x0 = int(self.x // 16) - C.TILE_RANGE_X
        x1 = int((self.x + self.w) // 16) + C.TILE_RANGE_X
        y0 = int(self.y // 16) - C.TILE_RANGE_Y
        y1 = int((self.y + self.h) // 16) + C.TILE_RANGE_Y
        return x0 <= tx <= x1 and y0 <= ty <= y1

    # ---------------------------------------------------------- collision
    def _collide(self, world, x, y, falling=False, prev_bottom=None,
                 drop=False):
        """True if the box at (x, y) overlaps solid tiles."""
        x0 = int(x // 16)
        x1 = int((x + self.w - 0.001) // 16)
        y0 = int(y // 16)
        y1 = int((y + self.h - 0.001) // 16)
        tiles = world.tiles
        W, H = world.w, world.h
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                if tx < 0 or tx >= W or ty < 0 or ty >= H:
                    return True
                t = tiles[tx, ty]
                if _SOLID[t]:
                    return True
                if falling and not drop and t == T.PLATFORM and \
                        prev_bottom is not None and prev_bottom <= ty * 16 \
                        and y + self.h > ty * 16:
                    return True
                if falling and not drop and prev_bottom is not None and \
                        prev_bottom <= ty * 16 and \
                        t == T.WORKBENCH and int(world.frame[tx, ty]) >> 3 == 0:
                    return True
        return False

    def _move(self, world, drop):
        # ---- horizontal
        dx = self.vx
        if dx:
            nx = self.x + dx
            if self._collide(world, nx, self.y):
                stepped = False
                if self.on_ground or self.wet:
                    # auto step up one tile
                    for up in range(1, 17):
                        if not self._collide(world, nx, self.y - up):
                            if up <= 16 and self.on_ground:
                                self.x = nx
                                self.y -= up
                                stepped = True
                            break
                if not stepped:
                    if dx > 0:
                        edge = (int((nx + self.w) // 16)) * 16
                        self.x = edge - self.w - 0.01
                    else:
                        edge = (int(nx // 16) + 1) * 16
                        self.x = edge + 0.01
                    if self._collide(world, self.x, self.y):
                        self.x -= dx if abs(dx) < 1 else math.copysign(1, dx)
                    self.vx = 0
            else:
                self.x = nx
        # ---- vertical
        dy = self.vy
        prev_bottom = self.y + self.h
        ny = self.y + dy
        self.on_ground = False
        if self._collide(world, self.x, ny, falling=dy > 0,
                         prev_bottom=prev_bottom, drop=drop):
            if dy > 0:
                ty = int((ny + self.h) // 16)
                self.y = ty * 16 - self.h
                self.on_ground = True
            else:
                ty = int(ny // 16) + 1
                self.y = ty * 16 + 0.01
                self.jump_timer = 0
            self.vy = 0
        else:
            self.y = ny
        # world edges
        lo = C.WORLD_EDGE * 16
        hi = (world.w - C.WORLD_EDGE) * 16 - self.w
        if self.x < lo:
            self.x, self.vx = lo, 0
        elif self.x > hi:
            self.x, self.vx = hi, 0
        if self.y < 0:
            self.y, self.vy = 0, 0

    def _liquid_state(self, world):
        x0 = int(self.x // 16)
        x1 = int((self.x + self.w - 1) // 16)
        y0 = int((self.y + 8) // 16)
        y1 = int((self.y + self.h - 2) // 16)
        wet = lava = False
        for tx in range(x0, x1 + 1):
            for ty in range(y0, y1 + 1):
                if 0 <= tx < world.w and 0 <= ty < world.h:
                    a = world.liquid[tx, ty]
                    if a:
                        surface = (ty + 1) * 16 - a / 255 * 16
                        if surface < self.y + self.h - 2:
                            if world.ltype[tx, ty] == LAVA:
                                lava = True
                            else:
                                wet = True
        hx, hy = int(self.cx // 16), int((self.y + 6) // 16)
        head = False
        if 0 <= hx < world.w and 0 <= hy < world.h:
            a = world.liquid[hx, hy]
            if a and (hy + 1) * 16 - a / 255 * 16 < self.y + 6:
                head = world.ltype[hx, hy] == WATER
        return wet or lava, lava, head

    # ------------------------------------------------------------- damage
    def hurt(self, dmg, source="", knock_dir=0, ignore_defense=False):
        if self.dead or (self.immune > 0 and not ignore_defense):
            return
        if not ignore_defense:
            dmg = max(1, int(dmg - self.defense() * 0.5))
        self.life -= dmg
        self.regen_time = 0
        self.events.append(("hurt", dmg))
        if not ignore_defense:
            self.immune = C.IMMUNE_TICKS
            if knock_dir:
                self.vx = knock_dir * 4
                self.vy = -4
        if self.life <= 0:
            self.life = 0
            self.die(source)

    def die(self, source):
        self.dead = True
        self.respawn = C.RESPAWN_TICKS
        self.stats["deaths"] = self.stats.get("deaths", 0) + 1
        self.events.append(("death", source))
        self.item_anim = 0

    # ------------------------------------------------------------- update
    def update(self, world, keys, mouse_world, mouse_down, ui_blocked):
        if self.dead:
            self.respawn -= 1
            if self.respawn <= 0:
                self.dead = False
                self.life = self.life_max
                self.mana = self.mana_max
                self.breath = C.BREATH_MAX
                self.buffs.clear()
                self.spawn_at(world)
                self.immune = 120
            return
        left = keys.get("left")
        right = keys.get("right")
        jump = keys.get("jump")
        down = keys.get("down")
        self.wet, self.in_lava, self.head_wet = self._liquid_state(world)
        space = self.y < world.space_y * 16
        # ---- horizontal movement
        max_run = C.MAX_RUN * (0.5 if self.wet else 1.0)
        accel = C.RUN_ACCEL * (0.5 if self.wet else 1.0)
        if left and not right:
            if self.vx > -max_run:
                self.vx -= accel + (C.RUN_SLOWDOWN if self.vx > 0 else 0)
            self.vx = max(self.vx, -max_run) if self.vx < -max_run else \
                self.vx
            if not self.item_anim:
                self.dir = -1
        elif right and not left:
            if self.vx < max_run:
                self.vx += accel + (C.RUN_SLOWDOWN if self.vx < 0 else 0)
            if not self.item_anim:
                self.dir = 1
        else:
            slow = C.RUN_SLOWDOWN if self.on_ground else C.RUN_SLOWDOWN * 0.5
            if self.vx > slow:
                self.vx -= slow
            elif self.vx < -slow:
                self.vx += slow
            else:
                self.vx = 0
        if self.vx > max_run * 1.0001:
            self.vx = max(max_run, self.vx - C.RUN_SLOWDOWN)
        if self.vx < -max_run * 1.0001:
            self.vx = min(-max_run, self.vx + C.RUN_SLOWDOWN)
        # ---- jumping / swimming
        jump_speed = C.JUMP_SPEED
        if jump and not self.jump_held:
            if self.on_ground or self.wet:
                self.vy = -jump_speed * (0.75 if self.wet and
                                         not self.on_ground else 1)
                self.jump_timer = C.JUMP_HEIGHT if not self.wet else 8
        if jump and self.jump_timer > 0:
            self.vy = min(self.vy, -jump_speed * (0.75 if self.wet else 1))
            self.jump_timer -= 1
        elif not jump:
            self.jump_timer = 0
        self.jump_held = jump
        # ---- gravity
        g = C.GRAVITY
        max_fall = C.MAX_FALL
        if self.wet:
            g *= 0.5
            max_fall = 5.0
        if space:
            g *= 0.35
        if self.jump_timer == 0:
            self.vy += g
        self.vy = min(self.vy, max_fall)
        # ---- move
        was_ground = self.on_ground
        self._move(world, drop=down)
        # ---- fall damage
        if self.wet or self.vy < 0:
            self.fall_start = None
        elif not self.on_ground and self.fall_start is None:
            self.fall_start = self.y
        if self.on_ground and not was_ground:
            if self.fall_start is not None:
                tiles = (self.y - self.fall_start) / 16
                if tiles > C.FALL_DAMAGE_TILES and not space:
                    dmg = int((tiles - C.FALL_DAMAGE_TILES) * 10)
                    self.hurt(dmg, "fell to their death", ignore_defense=True)
                    self.immune = max(self.immune, 20)
                self.events.append(("land", None))
            self.fall_start = None
        if self.on_ground:
            self.fall_start = None
        # ---- liquids
        if self.in_lava:
            self.buffs["On Fire!"] = 420
            self.hurt(40, "tried to swim in lava")
        if self.head_wet:
            if world.tick_count % 7 == 0:
                self.breath -= 1
                if self.breath <= 0:
                    self.breath = 0
                    self.life -= 2
                    self.regen_time = 0
                    if self.life <= 0:
                        self.life = 0
                        self.die("drowned")
                        return
        elif self.breath < C.BREATH_MAX:
            self.breath = min(C.BREATH_MAX, self.breath + 3)
        # ---- buffs
        for name in list(self.buffs):
            self.buffs[name] -= 1
            if name == "On Fire!" and world.tick_count % 20 == 0:
                if self.wet and not self.in_lava:
                    self.buffs[name] = 0
                else:
                    self.life -= 2
                    self.regen_time = 0
                    if self.life <= 0:
                        self.life = 0
                        self.die("burned to death")
                        return
            if self.buffs.get(name, 0) <= 0:
                self.buffs.pop(name, None)
        # ---- regeneration
        self.regen_time += 1
        if self.life < self.life_max and "On Fire!" not in self.buffs:
            t = self.regen_time
            rate = 0.0 if t < 300 else min(4.0, 0.6 + (t - 300) / 500)
            if abs(self.vx) < 0.1 and self.on_ground:
                rate *= 1.5
            self.regen_acc += rate / 60
            if self.regen_acc >= 1:
                n = int(self.regen_acc)
                self.life = min(self.life_max, self.life + n)
                self.regen_acc -= n
        if self.mana < self.mana_max:
            self.mana_acc += 0.12
            if self.mana_acc >= 1:
                self.mana = min(self.mana_max, self.mana + int(self.mana_acc))
                self.mana_acc %= 1
        if self.immune > 0:
            self.immune -= 1
        # ---- animation
        if self.on_ground and abs(self.vx) > 0.1:
            self.walk_frame = (self.walk_frame + abs(self.vx) * 0.12) % \
                LEG_FRAMES
        elif self.on_ground:
            self.walk_frame = 0
        # ---- item use
        self._update_item(world, mouse_world, mouse_down and not ui_blocked)

    # ----------------------------------------------------------- item use
    def _update_item(self, world, mouse_world, mouse_down):
        inv = self.inv
        stack = inv.held
        fresh = mouse_down and not self.mouse_was_down
        self.mouse_was_down = mouse_down
        if self.item_anim == 0:
            self.use_item = None
            if stack and mouse_down and (stack.item.auto_reuse or fresh or
                                         stack.item.kind in ("tool",)):
                it = stack.item
                self.use_item = stack.name
                self.item_anim = it.use_anim
                self.use_anim_max = it.use_anim
                self.item_time = 0
                self.dir = 1 if mouse_world[0] >= self.cx else -1
                self.events.append(("swing", it.name))
        if self.item_anim > 0:
            if self.use_item is None or inv.held is None or \
                    inv.held.name != self.use_item:
                # switched items mid-swing: finish the animation only
                self.item_anim -= 1
                return
            if self.item_time <= 0:
                it = ITEMS[self.use_item]
                self.item_time = it.use_time
                if mouse_down or self.item_anim == self.use_anim_max:
                    self._act(world, it, mouse_world)
            self.item_time -= 1
            self.item_anim -= 1

    def _act(self, world, it, mouse_world):
        tx, ty = int(mouse_world[0] // 16), int(mouse_world[1] // 16)
        if not world.in_bounds(tx, ty):
            return
        reach = self.in_reach(tx, ty)
        if it.pick or it.axe:
            if not reach:
                return
            tid = world.get(tx, ty)
            d = T.TILES[tid]
            if tid == T.AIR:
                return
            if it.axe and d.kind in ("tree", "cactus"):
                self._hit_tile(world, tx, ty, it.axe * d.mult)
            elif it.pick and d.kind not in ("tree", "cactus"):
                if not world.can_mine(tx, ty):
                    self.events.append(("tink", (tx, ty)))
                    return
                if it.pick < d.min_pick:
                    self.events.append(("tink", (tx, ty)))
                    self.events.append(("message",
                                        "Your pickaxe is not strong enough"))
                    return
                self._hit_tile(world, tx, ty, it.pick * d.mult)
            elif d.kind in ("plant", "vine"):
                self._hit_tile(world, tx, ty, 100)
            return
        if it.hammer:
            if not reach:
                return
            tid = world.get(tx, ty)
            if T.TILES[tid].kind in ("plant", "vine"):
                self._hit_tile(world, tx, ty, 100)
                return
            if world.walls[tx, ty] and (tid == T.AIR or not _SOLID[tid]):
                if not any(world.walls[nx, ny] == 0 for nx, ny in
                           ((tx - 1, ty), (tx + 1, ty), (tx, ty - 1),
                            (tx, ty + 1)) if world.in_bounds(nx, ny)):
                    return
                dmg = world.wall_damage.get((tx, ty), 0) + it.hammer * 1.5
                self.events.append(("dig", (tx, ty, "wall")))
                if dmg >= 100:
                    world.kill_wall(tx, ty)
                else:
                    world.wall_damage[(tx, ty)] = dmg
            return
        if it.kind == "weapon":
            # cut grass in front of the player
            for dx in range(1, 3):
                gx = int((self.cx + self.dir * dx * 14) // 16)
                for gy in (int(self.cy // 16), int((self.y + self.h - 4) // 16)):
                    tid = world.get(gx, gy)
                    if T.TILES[tid].kind in ("plant", "vine"):
                        frame = int(world.frame[gx, gy])
                        world.kill_tile(gx, gy)
                        self.events.append(("break", (gx, gy, tid, frame)))
            return
        if not reach:
            return
        if it.place_tile is not None:
            if self._place_tile(world, it, tx, ty):
                self.inv.consume_selected()
                self.events.append(("place", (tx, ty)))
        elif it.place_wall is not None:
            if world.walls[tx, ty] == 0 and self._wall_supported(world, tx,
                                                                  ty):
                world.set_wall(tx, ty, it.place_wall)
                self.inv.consume_selected()
                self.events.append(("place", (tx, ty)))

    def _hit_tile(self, world, tx, ty, power):
        key = (tx, ty)
        dmg = world.damage.get(key, [0, 0])[0] + power
        tid = world.get(tx, ty)
        frame = int(world.frame[tx, ty])
        self.events.append(("dig", (tx, ty, tid)))
        if dmg >= 100:
            world.damage.pop(key, None)
            world.kill_tile(tx, ty)
            self.events.append(("break", (tx, ty, tid, frame)))
        else:
            world.damage[key] = [dmg, 0]

    def _overlaps_player(self, tx, ty, w=1, h=1):
        r = pygame.Rect(tx * 16, ty * 16, w * 16, h * 16)
        return r.colliderect(self.rect())

    def _wall_supported(self, world, tx, ty):
        for nx, ny in ((tx - 1, ty), (tx + 1, ty), (tx, ty - 1), (tx, ty + 1)):
            if world.in_bounds(nx, ny) and (world.walls[nx, ny] or
                                            world.get(nx, ny) != T.AIR):
                return True
        return world.get(tx, ty) != T.AIR

    def _place_tile(self, world, it, tx, ty):
        tid = it.place_tile
        d = T.TILES[tid]
        cur = world.get(tx, ty)
        if d.kind == "furniture":
            w, h = d.size
            x0 = tx - (w - 1) // 2
            y0 = ty - (h - 1) if tid != T.DOOR_CLOSED else ty - 1
            if not world.multi_fits(x0, y0, tid):
                return False
            if (d.solid or tid == T.DOOR_CLOSED) and \
                    self._overlaps_player(x0, y0, w, h):
                return False
            world.place_multi(x0, y0, tid)
            return True
        if not T.REPLACEABLE[cur]:
            return False
        if d.kind == "torch":
            if world.liquid[tx, ty] and world.ltype[tx, ty] == WATER:
                return False
            if world.solid(tx, ty + 1):
                f = T.TORCH_GROUND
            elif world.solid(tx - 1, ty):
                f = T.TORCH_LEFT
            elif world.solid(tx + 1, ty):
                f = T.TORCH_RIGHT
            elif world.walls[tx, ty]:
                f = T.TORCH_WALL
            else:
                return False
            world.set_tile(tx, ty, tid, f)
            return True
        if d.kind == "sapling":
            if world.get(tx, ty + 1) not in T.GRASS_TILES + (T.SNOW, T.SAND):
                return False
            world.set_tile(tx, ty, tid)
            return True
        # blocks and platforms need something next to them
        support = world.walls[tx, ty] > 0
        for nx, ny in ((tx - 1, ty), (tx + 1, ty), (tx, ty - 1), (tx, ty + 1)):
            n = world.get(nx, ny)
            if _SOLID[n] or n == T.PLATFORM or (world.in_bounds(nx, ny) and
                                                world.walls[nx, ny]):
                support = True
        if not support:
            return False
        if d.solid and self._overlaps_player(tx, ty):
            return False
        world.set_tile(tx, ty, tid)
        return True

    # ------------------------------------------------------------- drawing
    def draw(self, surf, camx, camy, assets):
        if self.dead:
            return
        if self.immune > 0 and (self.immune // 4) % 2 == 0 and \
                self.immune < C.IMMUNE_TICKS + 1:
            return
        # pose
        if not self.on_ground and not self.wet:
            legs = JUMP
        elif self.on_ground and abs(self.vx) > 0.1:
            legs = int(self.walk_frame) % LEG_FRAMES
        else:
            legs = IDLE
        swing = 0.0
        if legs < LEG_FRAMES:
            swing = math.sin(self.walk_frame / LEG_FRAMES * math.tau) * 28
        front, back = 8 + swing, 8 - swing
        if legs == JUMP:
            front, back = 150, 40
        item_draw = None
        if self.item_anim > 0 and self.use_item:
            it = ITEMS[self.use_item]
            p = 1 - self.item_anim / max(1, self.use_anim_max)
            if it.use_style == "stab":
                front = 90
                thrust = math.sin(p * math.pi) * 10
                item_draw = (it, 90, thrust)
            else:
                front = 175 - 150 * p
                item_draw = (it, front, 0)
        held = self.inv.held
        holding_torch = item_draw is None and held is not None and \
            held.name == "Torch"
        if holding_torch:
            front = 80                      # torch held out in front
        frame = self.gfx.frame(legs, front, back, walk=self.walk_frame)
        # local canvas (facing right), then flip for left
        canvas = pygame.Surface((140, 140), pygame.SRCALPHA)
        ox, oy = 70 - 36, 70 + 21 - 72
        if item_draw and item_draw[0].kind not in ("tool", "weapon"):
            canvas.blit(frame, (ox, oy))
            self._draw_item(canvas, ox, oy, item_draw, assets)
        else:
            canvas.blit(frame, (ox, oy))
            if item_draw:
                self._draw_item(canvas, ox, oy, item_draw, assets)
        if holding_torch:
            hx, hy = PlayerGfx.hand_pos(front)
            spr = assets.torch[0]
            canvas.blit(spr, (ox + (hx + 8) * 2 - 8, oy + (hy + 8) * 2 - 13))
        if self.dir < 0:
            canvas = pygame.transform.flip(canvas, True, False)
        surf.blit(canvas, (round(self.cx - 70 - camx),
                           round(self.y + self.h / 2 - 70 - camy)))

    def held_light(self):
        """Pixel position of the light from a torch in hand, or None."""
        held = self.inv.held
        if self.dead or held is None or held.name != "Torch" or \
                self.head_wet:
            return None
        return (self.cx + self.dir * 13, self.cy - 8)

    def _draw_item(self, canvas, ox, oy, item_draw, assets):
        it, angle, thrust = item_draw
        spr = held_sprite(it.name, assets)
        hx, hy = PlayerGfx.hand_pos(angle)
        hx = ox + (hx + 8) * 2
        hy = oy + (hy + 8) * 2
        a = math.radians(angle)
        dx, dy = math.sin(a), math.cos(a)
        hx += dx * thrust
        hy += dy * thrust
        theta = math.degrees(math.atan2(-dy, dx))
        if it.kind in ("tool", "weapon"):
            rot = pygame.transform.rotate(spr, theta - 45)
            # handle is the bottom-left corner of the icon
            w, h = spr.get_size()
            vx, vy = -w / 2 + 3, h / 2 - 3
            r = math.radians(theta - 45)
            rx = vx * math.cos(r) + vy * math.sin(r)
            ry = -vx * math.sin(r) + vy * math.cos(r)
            canvas.blit(rot, (hx - rx - rot.get_width() / 2,
                              hy - ry - rot.get_height() / 2))
        else:
            canvas.blit(spr, (hx - spr.get_width() / 2 + dx * 6,
                              hy - spr.get_height() / 2 + dy * 6))
