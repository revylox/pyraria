"""World map: minimap frame, overlay map and the fullscreen map (M)."""
import numpy as np
import pygame

from . import tiles as T
from .config import SCREEN_W as SW, SCREEN_H as SH, SETTINGS

WATER = np.array([30, 70, 200], np.uint8)
LAVA = np.array([250, 90, 10], np.uint8)


def region_colors(world, x0, y0, w, h, reveal_all=False):
    """Map colours for a tile rectangle -> uint8 (w, h, 3)."""
    out = np.zeros((w, h, 3), np.uint8)
    xa, xb = max(0, x0), min(world.w, x0 + w)
    ya, yb = max(0, y0), min(world.h, y0 + h)
    if xa >= xb or ya >= yb:
        return out
    tiles = world.tiles[xa:xb, ya:yb]
    walls = world.walls[xa:xb, ya:yb]
    liq = world.liquid[xa:xb, ya:yb]
    ys = np.arange(ya, yb)
    bg = np.empty((yb - ya, 3), np.uint8)
    # sky gradient and depth layers
    k = np.clip(ys / max(1, world.underground_y), 0, 1)[:, None]
    bg[:] = (np.array([60, 110, 220]) * (1 - k) +
             np.array([150, 195, 250]) * k).astype(np.uint8)
    bg[ys >= world.underground_y] = (88, 62, 46)
    bg[ys >= world.cavern_y] = (70, 62, 58)
    bg[ys >= world.underworld_y] = (52, 18, 16)
    reg = np.broadcast_to(bg[None, :, :], (xb - xa, yb - ya, 3)).copy()
    wm = walls > 0
    reg[wm] = T.WALL_MAP_COLOR[walls[wm]]
    tm = T.TILE_ON_MAP[tiles]
    reg[tm] = T.TILE_MAP_COLOR[tiles[tm]]
    lq = liq > 0
    if lq.any():
        lava = lq & (world.ltype[xa:xb, ya:yb] == 1)
        reg[lq & ~lava] = (reg[lq & ~lava] * 0.35 + WATER * 0.65).astype(
            np.uint8)
        reg[lava] = LAVA
    if not reveal_all:
        reg[~world.explored[xa:xb, ya:yb]] = (8, 10, 18)
    out[xa - x0:xb - x0, ya - y0:yb - y0] = reg
    return out


class MapUI:
    def __init__(self, game):
        self.game = game
        self.zoom = 1.6           # minimap pixels per tile
        self.frame_rect = pygame.Rect(SW - 246, 80, 226, 190)
        self.mini_img = None
        self.mini_timer = 0
        self.full_open = False
        self.full_img = None
        self.full_scaled = {}
        self.full_zoom = 1.0
        self.center = (0.0, 0.0)
        self.dragging = None
        self.overlay_zoom = 3.0
        self.frame_surf = self._make_frame()

    def _make_frame(self):
        r = self.frame_rect
        s = pygame.Surface((r.w + 12, r.h + 12), pygame.SRCALPHA)
        gold, dark, light = (190, 150, 70), (90, 62, 28), (240, 210, 130)
        pygame.draw.rect(s, dark, s.get_rect(), border_radius=8)
        pygame.draw.rect(s, gold, s.get_rect().inflate(-4, -4), 3,
                         border_radius=7)
        pygame.draw.rect(s, light, s.get_rect().inflate(-4, -4), 1,
                         border_radius=7)
        s.fill((0, 0, 0, 0), pygame.Rect(6, 6, r.w, r.h))
        for cx, cy in ((6, 6), (r.w + 6, 6), (6, r.h + 6), (r.w + 6, r.h + 6)):
            pygame.draw.circle(s, gold, (cx, cy), 6)
            pygame.draw.circle(s, light, (cx - 1, cy - 1), 2)
        return s

    # ------------------------------------------------------------ minimap
    def draw_minimap(self, screen):
        mode = SETTINGS.get("minimap", "frame")
        if mode == "off":
            return
        p = self.game.player
        world = self.game.world
        if mode == "frame":
            r = self.frame_rect
            z = self.zoom
            w, h = int(r.w / z) + 1, int(r.h / z) + 1
            self.mini_timer -= 1
            if self.mini_img is None or self.mini_timer <= 0:
                x0 = int(p.cx // 16) - w // 2
                y0 = int(p.cy // 16) - h // 2
                col = region_colors(world, x0, y0, w, h)
                surf = pygame.surfarray.make_surface(col)
                self.mini_img = pygame.transform.scale(
                    surf, (int(w * z), int(h * z)))
                self.mini_origin = (x0, y0)
                self.mini_timer = 8
            screen.fill((8, 10, 18), r)
            screen.blit(self.mini_img, r.topleft, (0, 0, r.w, r.h))
            screen.blit(self.frame_surf, (r.x - 6, r.y - 6))
            head = self.game.player.gfx.head_icon()
            hx = r.x + (p.cx / 16 - self.mini_origin[0]) * z
            hy = r.y + (p.cy / 16 - self.mini_origin[1]) * z
            if r.collidepoint(hx, hy):
                screen.blit(head, head.get_rect(center=(hx, hy)))
        else:  # overlay
            z = self.overlay_zoom
            w, h = int(SW / z) + 1, int(SH / z) + 1
            self.mini_timer -= 1
            if self.mini_img is None or self.mini_timer <= 0 or \
                    self.mini_img.get_width() < SW:
                x0 = int(p.cx // 16) - w // 2
                y0 = int(p.cy // 16) - h // 2
                col = region_colors(world, x0, y0, w, h)
                surf = pygame.surfarray.make_surface(col)
                surf.set_colorkey((8, 10, 18))
                self.mini_img = pygame.transform.scale(
                    surf, (int(w * z), int(h * z)))
                self.mini_img.set_alpha(150)
                self.mini_origin = (x0, y0)
                self.mini_timer = 8
            screen.blit(self.mini_img, (0, 0))
            head = self.game.player.gfx.head_icon()
            screen.blit(head, head.get_rect(center=(SW // 2, SH // 2)))

    def zoom_minimap(self, d):
        if SETTINGS.get("minimap") == "overlay":
            self.overlay_zoom = max(1.0, min(8.0, self.overlay_zoom * (
                1.25 if d > 0 else 0.8)))
        else:
            self.zoom = max(0.5, min(8.0, self.zoom * (1.25 if d > 0
                                                       else 0.8)))
        self.mini_img = None

    def cycle_mode(self):
        order = ["frame", "overlay", "off"]
        cur = SETTINGS.get("minimap", "frame")
        SETTINGS["minimap"] = order[(order.index(cur) + 1) % 3]
        self.mini_img = None

    # ---------------------------------------------------------- full map
    def open_full(self):
        world = self.game.world
        p = self.game.player
        col = region_colors(world, 0, 0, world.w, world.h)
        self.full_img = pygame.surfarray.make_surface(col)
        self.full_scaled = {}
        self.full_open = True
        self.center = (p.cx / 16, p.cy / 16)
        self.full_zoom = 2.0

    def close_full(self):
        self.full_open = False
        self.full_img = None
        self.full_scaled = {}

    def full_event(self, e):
        if e.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            old = self.full_zoom
            self.full_zoom = max(0.25, min(8.0, self.full_zoom *
                                           (1.25 if e.y > 0 else 0.8)))
            # zoom towards the mouse
            cx, cy = self.center
            wx = cx + (mx - SW / 2) / old
            wy = cy + (my - SH / 2) / old
            self.center = (wx - (mx - SW / 2) / self.full_zoom,
                           wy - (my - SH / 2) / self.full_zoom)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (1, 3):
            self.dragging = (e.pos, self.center)
        elif e.type == pygame.MOUSEBUTTONUP and e.button in (1, 3):
            self.dragging = None
        elif e.type == pygame.MOUSEMOTION and self.dragging:
            (sx, sy), (cx, cy) = self.dragging
            self.center = (cx - (e.pos[0] - sx) / self.full_zoom,
                           cy - (e.pos[1] - sy) / self.full_zoom)

    def draw_full(self, screen, text):
        world = self.game.world
        p = self.game.player
        screen.fill((10, 12, 24))
        z = self.full_zoom
        cx, cy = self.center
        cx = max(0, min(world.w, cx))
        cy = max(0, min(world.h, cy))
        self.center = (cx, cy)
        # visible tile rect
        tw, th = SW / z, SH / z
        x0, y0 = cx - tw / 2, cy - th / 2
        if z >= 1:
            sx0, sy0 = int(max(0, x0)), int(max(0, y0))
            sx1 = int(min(world.w, x0 + tw + 2))
            sy1 = int(min(world.h, y0 + th + 2))
            if sx1 > sx0 and sy1 > sy0:
                sub = self.full_img.subsurface((sx0, sy0, sx1 - sx0,
                                                sy1 - sy0))
                img = pygame.transform.scale(sub, (int((sx1 - sx0) * z),
                                                   int((sy1 - sy0) * z)))
                screen.blit(img, ((sx0 - x0) * z, (sy0 - y0) * z))
        else:
            key = round(z, 3)
            img = self.full_scaled.get(key)
            if img is None:
                img = pygame.transform.smoothscale(
                    self.full_img, (max(1, int(world.w * z)),
                                    max(1, int(world.h * z))))
                self.full_scaled = {key: img}
            screen.blit(img, (-x0 * z, -y0 * z))
        # spawn and player markers
        sx, sy = world.spawn
        spx, spy = (sx - x0) * z, (sy + 1 - y0) * z
        pygame.draw.polygon(screen, (40, 30, 20), [(spx - 9, spy + 9),
                                                   (spx, spy - 8),
                                                   (spx + 9, spy + 9)])
        pygame.draw.polygon(screen, (230, 200, 120), [(spx - 7, spy + 8),
                                                      (spx, spy - 5),
                                                      (spx + 7, spy + 8)])
        head = p.gfx.head_icon()
        screen.blit(head, head.get_rect(center=((p.cx / 16 - x0) * z,
                                                (p.cy / 16 - y0) * z)))
        # border frame
        pygame.draw.rect(screen, (190, 150, 70), screen.get_rect(), 6)
        pygame.draw.rect(screen, (90, 62, 28), screen.get_rect(), 2)
        # hovered tile name
        mx, my = pygame.mouse.get_pos()
        hx, hy = int(x0 + mx / z), int(y0 + my / z)
        label = None
        if world.in_bounds(hx, hy) and world.explored[hx, hy]:
            t = world.get(hx, hy)
            if T.TILE_ON_MAP[t]:
                label = T.TILES[t].name
            elif world.liquid[hx, hy]:
                label = "Lava" if world.ltype[hx, hy] else "Water"
            elif world.walls[hx, hy]:
                label = T.WALLS[world.walls[hx, hy]].name
        if label:
            text.draw(screen, label, (mx + 16, my + 8), 20)
        text.draw(screen, "Map  -  drag to pan, scroll to zoom, M / Esc to "
                  "close", (SW // 2, SH - 12), 18, anchor="midbottom")
