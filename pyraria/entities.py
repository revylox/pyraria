"""Dropped items, falling sand, dust particles and floating text."""
import math
import random

import pygame

from . import tiles as T
from .items import ITEMS, RARITY_COLORS, get_icon

_SOLID = T.SOLID
GRAB_RANGE = 84          # px, like Terraria's default item grab range


def _solid_at(world, px, py):
    tx, ty = int(px // 16), int(py // 16)
    if not world.in_bounds(tx, ty):
        return True
    t = world.tiles[tx, ty]
    return bool(_SOLID[t]) or (t == T.PLATFORM and py % 16 < 6)


class ItemEntity:
    def __init__(self, name, count, x, y, vx=None, vy=None, pickup_delay=0):
        self.name = name
        self.count = count
        self.x, self.y = x, y
        self.vx = random.uniform(-1.6, 1.6) if vx is None else vx
        self.vy = random.uniform(-2.6, -1.4) if vy is None else vy
        self.w = self.h = 14
        self.age = 0
        self.dead = False
        self.pickup_delay = pickup_delay

    def update(self, world, player, game):
        self.age += 1
        if self.pickup_delay > 0:
            self.pickup_delay -= 1
        dx = player.cx - self.x
        dy = player.cy - self.y
        dist = math.hypot(dx, dy)
        attract = (not player.dead and dist < GRAB_RANGE and
                   self.pickup_delay == 0 and
                   player.inv.room_for(self.name))
        if attract:
            sp = 6.0
            self.vx += (dx / max(dist, 1) * sp - self.vx) * 0.2
            self.vy += (dy / max(dist, 1) * sp - self.vy) * 0.2
            self.x += self.vx
            self.y += self.vy
            if dist < 18:
                left = player.inv.add(self.name, self.count)
                got = self.count - left
                if got:
                    game.on_pickup(self.name, got)
                self.count = left
                if left == 0:
                    self.dead = True
            return
        self.vy = min(self.vy + 0.1, 7)
        self.vx *= 0.95
        nx = self.x + self.vx
        if _solid_at(world, nx, self.y):
            self.vx = 0
        else:
            self.x = nx
        ny = self.y + self.vy
        if self.vy > 0 and _solid_at(world, self.x, ny + self.h / 2):
            self.vy = 0
            self.y = (int((ny + self.h / 2) // 16)) * 16 - self.h / 2
            self.vx *= 0.7
        elif self.vy < 0 and _solid_at(world, self.x, ny - self.h / 2):
            self.vy = 0
        else:
            self.y = ny
        tx, ty = int(self.x // 16), int(self.y // 16)
        if world.in_bounds(tx, ty) and world.liquid[tx, ty]:
            if world.ltype[tx, ty] == 1 and self.age > 2:
                self.dead = True          # lava destroys items
            else:
                self.vy = min(self.vy, 1.0)
        if self.age > 60 * 60 * 10:
            self.dead = True

    def draw(self, surf, camx, camy, assets):
        icon = get_icon(self.name, assets)
        w, h = icon.get_size()
        if max(w, h) > 24:
            k = 24 / max(w, h)
            icon = pygame.transform.scale(icon, (int(w * k), int(h * k)))
        bob = math.sin(self.age * 0.06) * 1.5
        surf.blit(icon, (self.x - icon.get_width() / 2 - camx,
                         self.y + self.h / 2 - icon.get_height() - camy +
                         bob + 2))


class FallingBlock:
    def __init__(self, tid, tx, ty):
        self.tid = tid
        self.x = tx * 16.0
        self.y = ty * 16.0
        self.vy = 0.0
        self.dead = False

    def update(self, world, player, game):
        self.vy = min(self.vy + 0.4, 10)
        ny = self.y + self.vy
        tx = int((self.x + 8) // 16)
        ty = int((ny + 16) // 16)
        below = world.get(tx, ty)
        if _SOLID[below] or below == T.PLATFORM or \
                T.TILES[below].kind in ("furniture", "tree"):
            cell = ty - 1
            cur = world.get(tx, cell)
            if T.REPLACEABLE[cur]:
                world.set_tile(tx, cell, self.tid)
            else:
                drop = T.TILES[self.tid].drop
                if drop:
                    game.drop_item(drop, 1, self.x + 8, self.y + 8)
            self.dead = True
            return
        self.y = ny
        if pygame.Rect(self.x, self.y, 16, 16).colliderect(player.rect()):
            if self.vy > 3:
                player.hurt(10, "was crushed by sand")
        if self.y > world.h * 16:
            self.dead = True

    def draw(self, surf, camx, camy, assets):
        tex = assets.tile[self.tid][0][0]
        surf.blit(tex, (self.x - camx, self.y - camy))


class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "color", "size", "grav",
                 "dead", "glow")

    def __init__(self, x, y, color, vx=None, vy=None, life=None, size=4,
                 grav=0.18, glow=False):
        self.x, self.y = x, y
        self.vx = random.uniform(-2, 2) if vx is None else vx
        self.vy = random.uniform(-3, 0) if vy is None else vy
        self.life = random.randint(20, 40) if life is None else life
        self.color = color
        self.size = size
        self.grav = grav
        self.dead = False
        self.glow = glow

    def update(self, world, player, game):
        self.vy += self.grav
        self.vx *= 0.97
        self.x += self.vx
        self.y += self.vy
        if _solid_at(world, self.x, self.y):
            self.vy *= -0.3
            self.vx *= 0.5
        self.life -= 1
        if self.life <= 0:
            self.dead = True

    def draw(self, surf, camx, camy, assets):
        s = self.size if self.life > 8 else max(1, self.size // 2)
        rect = (int(self.x - camx), int(self.y - camy), s, s)
        if self.glow:
            # emissive: added on top of the lit scene, fading out
            k = min(1.0, self.life / 20)
            surf.fill(tuple(int(c * k) for c in self.color), rect,
                      special_flags=pygame.BLEND_RGB_ADD)
        else:
            surf.fill(self.color, rect)


class FloatText:
    """Rising text above the player (pickups, damage numbers)."""

    def __init__(self, text, x, y, color, size=20, life=70, key=None):
        self.text = text
        self.x, self.y = x, y
        self.color = color
        self.size = size
        self.life = life
        self.max_life = life
        self.vy = -2.2
        self.key = key
        self.count = 0
        self.dead = False

    def update(self):
        self.y += self.vy
        self.vy *= 0.92
        self.life -= 1
        if self.life <= 0:
            self.dead = True

    def draw(self, surf, camx, camy, text):
        alpha = min(255, int(255 * self.life / (self.max_life * 0.4)))
        img = text.render(self.text, self.size, self.color)
        img.set_alpha(alpha)
        surf.blit(img, (self.x - img.get_width() / 2 - camx,
                        self.y - img.get_height() / 2 - camy))


def pickup_text(name, count):
    it = ITEMS[name]
    label = f"{name} ({count})" if count > 1 else name
    return label, RARITY_COLORS[it.rarity]
