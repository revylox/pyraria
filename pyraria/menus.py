"""Title screen, player / world selection and creation, world generation
progress and loading screens."""
import json
import math
import os
import random
import re
import threading
import pygame

from . import config as C
from .background import _make_layer, Background
from .player import Player
from .playergfx import PlayerGfx, LEG_FRAMES
from .world import World, FOREST
from . import tiles as T
from . import webstore
from . import worldgen

SW, SH = C.SCREEN_W, C.SCREEN_H
YELLOW = (255, 235, 100)
WHITE = (255, 255, 255)


def _safe_name(name):
    s = re.sub(r"[^A-Za-z0-9_\- ]", "", name).strip() or "unnamed"
    return s.replace(" ", "_")


# ---------------------------------------------------------------------------
# shared menu background (scrolling forest, like Terraria's title screen)
# ---------------------------------------------------------------------------
class MenuBackground:
    def __init__(self):
        self.layers = [_make_layer(FOREST, d, 77 + d) for d in range(3)]
        self.bg = Background(5)
        self.t = 0.0
        g = pygame.Surface((1, 64))
        for y in range(64):
            k = y / 63
            g.set_at((0, y), (int(74 + (150 - 74) * k),
                              int(128 + (196 - 128) * k),
                              int(222 + (250 - 222) * k)))
        self.sky = pygame.transform.smoothscale(g, (SW, SH))

    def draw(self, screen, assets):
        self.t += 0.6
        screen.blit(self.sky, (0, 0))
        for c in self.bg.clouds:
            x = (c[0] + self.t * c[2] * 0.5) % (SW + 400) - 200
            screen.blit(c[3], (x, c[1] * 0.6))
        sun = self.bg.sun
        screen.blit(sun, (SW * 0.78, 60))
        for d, layer in enumerate(self.layers):
            surf = layer.get((255, 255, 255))
            w = surf.get_width()
            x = -((self.t * layer.parallax * 2) % w)
            base = SH * 0.42 + d * 40
            while x < SW:
                screen.blit(surf, (x, base + layer.top))
                x += w
            bottom = base + layer.full_h
            if bottom < SH:
                screen.fill(layer.fill, (0, bottom, SW, SH - bottom))
        # tile ground strip at the bottom
        tx = assets.tile
        off = int(self.t * 0.7) % 16
        for i in range(SW // 16 + 2):
            x = i * 16 - off
            screen.blit(tx[T.GRASS][2 | 8 | 4][i % 3], (x, SH - 64))
            for j in range(1, 4):
                screen.blit(tx[T.DIRT][15][(i + j) % 3], (x, SH - 64 + j * 16))


def draw_logo(screen, text, t, y=110):
    key = "_logo"
    img = text.cache.get(key)
    if img is None:
        f = pygame.font.Font(None, 150)
        base = f.render("Pyraria", True, (255, 255, 255))
        w, h = base.get_size()
        grad = pygame.Surface((w, h), pygame.SRCALPHA)
        for yy in range(h):
            k = yy / h
            if k < 0.42:
                c = (int(110 - 40 * k), int(220 - 60 * k), int(70 - 20 * k))
            else:
                c = (int(170 - 60 * (k - .42)), int(120 - 40 * (k - .42)),
                     int(70 - 30 * (k - .42)))
            grad.fill(c, (0, yy, w, 1))
        grad.blit(base, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        mask = pygame.mask.from_surface(base)
        sil = mask.to_surface(setcolor=(40, 26, 16, 255),
                              unsetcolor=(0, 0, 0, 0))
        img = pygame.Surface((w + 12, h + 14), pygame.SRCALPHA)
        for dx in range(-5, 6, 1):
            for dy in range(-5, 8, 1):
                if dx * dx + dy * dy <= 30:
                    img.blit(sil, (6 + dx, 6 + dy))
        img.blit(grad, (6, 6))
        text.cache[key] = img
    ang = math.sin(t * 0.02) * 2.5
    sc = 1.0 + math.sin(t * 0.031) * 0.03
    rot = pygame.transform.rotozoom(img, ang, sc)
    screen.blit(rot, rot.get_rect(center=(SW // 2, y)))


class Menu:
    """Base class for simple text menus."""
    title = ""

    def __init__(self, app):
        self.app = app
        self.text = app.text
        self.items = []         # (label, callback)
        self.hover = -1
        self.t = 0

    def item_rects(self, y0=300, gap=56, size=40):
        rects = []
        y = y0
        for label, _ in self.items:
            img = self.text.render(label, size)
            rects.append(img.get_rect(midtop=(SW // 2, y)))
            y += gap
        return rects

    def handle_event(self, e):
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in enumerate(self.item_rects()):
                if r.collidepoint(e.pos):
                    self.app.audio.play("menu")
                    self.items[i][1]()
                    return
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.back()

    def back(self):
        pass

    def update(self):
        self.t += 1
        pos = pygame.mouse.get_pos()
        hov = next((i for i, r in enumerate(self.item_rects())
                    if r.collidepoint(pos)), -1)
        # tick when the cursor reaches a different option (silent on the
        # first frame so entering a menu under the cursor makes no sound)
        if hov != self.hover:
            if hov != -1 and self.t > 1:
                self.app.audio.play("menu_tick")
            self.hover = hov

    def draw(self, screen):
        self.app.menu_bg.draw(screen, self.app.assets)
        if self.title:
            self.text.draw(screen, self.title, (SW // 2, 200), 44,
                           anchor="midtop")
        mpos = pygame.mouse.get_pos()
        for (label, _), r in zip(self.items, self.item_rects()):
            hov = r.collidepoint(mpos)
            img = self.text.render(label, 40, YELLOW if hov else WHITE)
            if hov:
                img = pygame.transform.rotozoom(img, 0, 1.08)
            screen.blit(img, img.get_rect(center=r.center))


class TitleMenu(Menu):
    def __init__(self, app):
        super().__init__(app)
        self.items = [("Single Player", lambda: app.set_state(
            PlayerSelect(app))),
            ("Settings", lambda: app.set_state(SettingsMenu(app)))]
        if not webstore.WEB:          # a browser tab can't be "exited"
            self.items.append(("Exit", app.quit))

    def draw(self, screen):
        super().draw(screen)
        draw_logo(screen, self.text, self.t)
        self.text.draw(screen, "v1.0  -  a Terraria-style sandbox in Python",
                       (10, SH - 8), 16, anchor="bottomleft")


class SettingsMenu(Menu):
    def __init__(self, app):
        super().__init__(app)
        self._build()

    def _build(self):
        s = C.SETTINGS
        self.items = [
            (f"Lighting: {'Color' if s['lighting'] == 'color' else 'Retro'}",
             lambda: self._toggle("lighting")),
            (f"Fullscreen: {'On' if s['fullscreen'] else 'Off'}",
             lambda: self._toggle("fullscreen")),
            (f"Minimap: {s['minimap'].title()}",
             lambda: self._toggle("minimap")),
            (f"Volume: {int(s['volume'] * 100)}%",
             lambda: self._toggle("volume")),
            (f"Autosave: {s['autosave_minutes']} min" if
             s['autosave_minutes'] else "Autosave: Off",
             lambda: self._toggle("autosave")),
            ("Back", self.back)]

    def _toggle(self, key):
        s = C.SETTINGS
        if key == "lighting":
            s["lighting"] = "retro" if s["lighting"] == "color" else "color"
        elif key == "fullscreen":
            s["fullscreen"] = not s["fullscreen"]
            try:
                pygame.display.toggle_fullscreen()
            except Exception:
                pass
        elif key == "minimap":
            order = ["frame", "overlay", "off"]
            s["minimap"] = order[(order.index(s["minimap"]) + 1) % 3]
        elif key == "volume":
            v = round(s["volume"] + 0.2, 1)
            s["volume"] = 0.0 if v > 1.0 else v
            self.app.audio.set_volume(s["volume"])
        elif key == "autosave":
            opts = [0, 2, 5, 10]
            cur = s.get("autosave_minutes", 5)
            s["autosave_minutes"] = opts[(opts.index(cur) + 1) % 4] \
                if cur in opts else 5
        C.save_settings(s)
        self._build()

    def back(self):
        self.app.set_state(TitleMenu(self.app))

    def draw(self, screen):
        self.title = "Settings"
        super().draw(screen)


# ---------------------------------------------------------------------------
# list menus (players / worlds)
# ---------------------------------------------------------------------------
class ListMenu:
    title = ""

    def __init__(self, app):
        self.app = app
        self.text = app.text
        self.entries = []        # dicts with "label", "sub", "path"
        self.scroll = 0
        self.confirm = None
        self.t = 0
        self.refresh()

    def refresh(self):
        pass

    def panel(self):
        return pygame.Rect(SW // 2 - 300, 150, 600, 400)

    def row_rects(self):
        p = self.panel()
        rects = []
        for i in range(len(self.entries)):
            j = i - self.scroll
            if 0 <= j < 5:
                rects.append((i, pygame.Rect(p.x + 14, p.y + 14 + j * 76,
                                             p.w - 28, 68)))
        return rects

    def buttons(self):
        p = self.panel()
        return [("New", pygame.Rect(p.x, p.bottom + 20, 180, 44)),
                ("Back", pygame.Rect(p.right - 180, p.bottom + 20, 180, 44))]

    def handle_event(self, e):
        if self.confirm:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                yes, no = self._confirm_rects()
                if yes.collidepoint(e.pos):
                    self.app.audio.play("menu")
                    self.delete(self.confirm)
                    self.confirm = None
                    self.refresh()
                elif no.collidepoint(e.pos):
                    self.app.audio.play("menu")
                    self.confirm = None
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.confirm = None
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for i, r in self.row_rects():
                if r.collidepoint(e.pos):
                    self.app.audio.play("menu")
                    dr = pygame.Rect(r.right - 40, r.y + 20, 28, 28)
                    if dr.collidepoint(e.pos):
                        self.confirm = self.entries[i]
                    else:
                        self.choose(self.entries[i])
                    return
            for label, r in self.buttons():
                if r.collidepoint(e.pos):
                    self.app.audio.play("menu")
                    if label == "New":
                        self.new()
                    else:
                        self.back()
                    return
        elif e.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, min(max(0, len(self.entries) - 5),
                                     self.scroll - e.y))
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            self.back()

    def _confirm_rects(self):
        return (pygame.Rect(SW // 2 - 130, SH // 2 + 20, 110, 44),
                pygame.Rect(SW // 2 + 20, SH // 2 + 20, 110, 44))

    def update(self):
        self.t += 1

    def draw_entry_icon(self, screen, entry, rect):
        pass

    def draw(self, screen):
        self.app.menu_bg.draw(screen, self.app.assets)
        self.text.draw(screen, self.title, (SW // 2, 100), 40,
                       anchor="midtop")
        p = self.panel()
        bg = pygame.Surface(p.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (33, 43, 99, 220), bg.get_rect(),
                         border_radius=12)
        pygame.draw.rect(bg, (90, 110, 190), bg.get_rect(), 3,
                         border_radius=12)
        screen.blit(bg, p)
        mpos = pygame.mouse.get_pos()
        if not self.entries:
            self.text.draw(screen, "Nothing here yet - click New",
                           p.center, 24, (200, 200, 220), anchor="center")
        for i, r in self.row_rects():
            e = self.entries[i]
            hov = r.collidepoint(mpos)
            pygame.draw.rect(screen, (73, 94, 171) if hov else (63, 82, 151),
                             r, border_radius=8)
            pygame.draw.rect(screen, (120, 140, 220), r, 2, border_radius=8)
            self.draw_entry_icon(screen, e, r)
            self.text.draw(screen, e["label"], (r.x + 80, r.y + 8), 26,
                           YELLOW if hov else WHITE)
            self.text.draw(screen, e.get("sub", ""), (r.x + 80, r.y + 38),
                           16, (200, 205, 230))
            dr = pygame.Rect(r.right - 40, r.y + 20, 28, 28)
            pygame.draw.rect(screen, (150, 50, 50) if dr.collidepoint(mpos)
                             else (110, 40, 40), dr, border_radius=5)
            self.text.draw(screen, "X", dr.center, 18, anchor="center")
        for label, r in self.buttons():
            hov = r.collidepoint(mpos)
            pygame.draw.rect(screen, (73, 94, 171) if hov else (53, 70, 140),
                             r, border_radius=8)
            pygame.draw.rect(screen, (120, 140, 220), r, 2, border_radius=8)
            self.text.draw(screen, label, r.center, 26,
                           YELLOW if hov else WHITE, anchor="center")
        if self.confirm:
            shade = pygame.Surface((SW, SH), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 160))
            screen.blit(shade, (0, 0))
            self.text.draw(screen, f"Delete {self.confirm['label']}?",
                           (SW // 2, SH // 2 - 30), 32, anchor="center")
            for label, r in zip(("Delete", "Cancel"), self._confirm_rects()):
                hov = r.collidepoint(mpos)
                pygame.draw.rect(screen, (130, 50, 50) if label == "Delete"
                                 else (53, 70, 140), r, border_radius=8)
                self.text.draw(screen, label, r.center, 24,
                               YELLOW if hov else WHITE, anchor="center")


class PlayerSelect(ListMenu):
    title = "Select Player"

    def refresh(self):
        self.entries = []
        os.makedirs(C.PLAYER_DIR, exist_ok=True)
        for fn in sorted(os.listdir(C.PLAYER_DIR)):
            if fn.endswith(".json"):
                path = os.path.join(C.PLAYER_DIR, fn)
                try:
                    with open(path, encoding="utf-8") as f:
                        d = json.load(f)
                except (OSError, ValueError):
                    continue
                gfx = PlayerGfx()
                self.entries.append({
                    "label": d.get("name", fn[:-5]),
                    "sub": f"{d.get('life_max', 100)} HP   "
                           f"{d.get('mana_max', 20)} Mana   "
                           f"Deaths: {d.get('stats', {}).get('deaths', 0)}",
                    "path": path, "icon": gfx.preview(1)})

    def draw_entry_icon(self, screen, e, r):
        icon = e["icon"]
        screen.blit(icon, icon.get_rect(center=(r.x + 40, r.centery - 4)))

    def choose(self, e):
        self.app.player_path = e["path"]
        self.app.set_state(WorldSelect(self.app))

    def new(self):
        self.app.set_state(PlayerCreate(self.app))

    def back(self):
        self.app.set_state(TitleMenu(self.app))

    def delete(self, e):
        try:
            os.remove(e["path"])
        except OSError:
            pass
        webstore.forget(e["path"])


class WorldSelect(ListMenu):
    title = "Select World"

    def refresh(self):
        self.entries = []
        os.makedirs(C.WORLD_DIR, exist_ok=True)
        for fn in sorted(os.listdir(C.WORLD_DIR)):
            if fn.endswith(".wld.npz"):
                path = os.path.join(C.WORLD_DIR, fn)
                try:
                    meta = World.read_meta(path)
                except Exception:
                    continue
                size = {4200: "Small", 6400: "Medium", 8400: "Large"}.get(
                    meta["w"], f"{meta['w']}x{meta['h']}")
                self.entries.append({
                    "label": meta["name"],
                    "sub": f"{size}   Corruption   Seed {meta['seed']}",
                    "path": path})

    def draw_entry_icon(self, screen, e, r):
        ic = pygame.Rect(r.x + 14, r.y + 10, 50, 48)
        pygame.draw.rect(screen, (100, 150, 230), ic, border_radius=6)
        pygame.draw.rect(screen, (60, 160, 60), (ic.x, ic.y + 26, 50, 6))
        pygame.draw.rect(screen, (130, 90, 60), (ic.x, ic.y + 32, 50, 16),
                         border_bottom_left_radius=6,
                         border_bottom_right_radius=6)
        pygame.draw.rect(screen, (130, 110, 190), (ic.x + 30, ic.y + 26, 12,
                                                   22))

    def choose(self, e):
        self.app.set_state(LoadingScreen(self.app, e["path"]))

    def new(self):
        self.app.set_state(WorldCreate(self.app))

    def back(self):
        self.app.set_state(PlayerSelect(self.app))

    def delete(self, e):
        try:
            os.remove(e["path"])
        except OSError:
            pass
        webstore.forget(e["path"])


# ---------------------------------------------------------------------------
# creation screens
# ---------------------------------------------------------------------------
class TextField:
    def __init__(self, value="", limit=20):
        self.value = value
        self.limit = limit

    def handle(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_BACKSPACE:
                self.value = self.value[:-1]
                return True
        elif e.type == pygame.TEXTINPUT:
            if len(self.value) < self.limit and e.text.isprintable():
                self.value += e.text
                return True
        return False


class PlayerCreate:
    """Name your character (everyone plays the same hero sprite)."""

    def __init__(self, app):
        self.app = app
        self.text = app.text
        self.name = TextField("", 16)
        self.gfx = PlayerGfx()
        self.t = 0
        pygame.key.start_text_input()

    def _rects(self):
        return {"name": pygame.Rect(SW // 2 - 200, 470, 400, 46),
                "create": pygame.Rect(SW // 2 - 200, 550, 190, 50),
                "back": pygame.Rect(SW // 2 + 10, 550, 190, 50)}

    def handle_event(self, e):
        if self.name.handle(e):
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            r = self._rects()
            if r["create"].collidepoint(e.pos):
                self.app.audio.play("menu")
                self.create()
            elif r["back"].collidepoint(e.pos):
                self.app.audio.play("menu")
                self.back()
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_RETURN:
                self.create()
            elif e.key == pygame.K_ESCAPE:
                self.back()

    def create(self):
        name = self.name.value.strip()
        if not name:
            return
        p = Player.new(name)
        os.makedirs(C.PLAYER_DIR, exist_ok=True)
        path = os.path.join(C.PLAYER_DIR, _safe_name(name) + ".json")
        n = 2
        while os.path.exists(path):
            path = os.path.join(C.PLAYER_DIR, f"{_safe_name(name)}_{n}.json")
            n += 1
        with open(path, "w", encoding="utf-8") as f:
            json.dump(p.to_json(), f)
        webstore.persist(path)
        pygame.key.stop_text_input()
        self.app.set_state(PlayerSelect(self.app))

    def back(self):
        pygame.key.stop_text_input()
        self.app.set_state(PlayerSelect(self.app))

    def update(self):
        self.t += 1

    def draw(self, screen):
        self.app.menu_bg.draw(screen, self.app.assets)
        self.text.draw(screen, "Create Player", (SW // 2, 60), 40,
                       anchor="midtop")
        mpos = pygame.mouse.get_pos()
        panel = pygame.Rect(SW // 2 - 140, 130, 280, 310)
        pygame.draw.rect(screen, (33, 43, 99), panel, border_radius=10)
        pygame.draw.rect(screen, (90, 110, 190), panel, 3, border_radius=10)
        legs = (self.t // 6) % LEG_FRAMES
        frame = self.gfx.frame(legs, 0, 0)
        big = pygame.transform.scale(frame, (frame.get_width() * 3,
                                             frame.get_height() * 3))
        screen.blit(big, big.get_rect(center=(panel.centerx,
                                              panel.centery + 10)))
        r = self._rects()
        nr = r["name"]
        self.text.draw(screen, "Name", (nr.x, nr.y - 24), 18,
                       (210, 215, 240))
        pygame.draw.rect(screen, (63, 82, 151), nr, border_radius=8)
        pygame.draw.rect(screen, YELLOW, nr, 2, border_radius=8)
        caret = "|" if (self.t // 30) % 2 == 0 else ""
        label = self.name.value
        if label or caret:
            self.text.draw(screen, label + caret, (nr.x + 12, nr.y + 11), 24)
        if not label:
            self.text.draw(screen, "Type a name...", (nr.x + 22, nr.y + 13),
                           20, (170, 175, 200))
        for key, text in (("create", "Create"), ("back", "Back")):
            rect = r[key]
            hov = rect.collidepoint(mpos)
            pygame.draw.rect(screen, (73, 94, 171) if hov else (53, 70, 140),
                             rect, border_radius=8)
            pygame.draw.rect(screen, (120, 140, 220), rect, 2,
                             border_radius=8)
            self.text.draw(screen, text, rect.center, 26,
                           YELLOW if hov else WHITE, anchor="center")


class WorldCreate:
    SIZES = ["Small", "Medium"] if webstore.WEB else ["Small", "Medium",
                                                      "Large"]

    def __init__(self, app):
        self.app = app
        self.text = app.text
        self.name = TextField("", 24)
        self.seed = TextField("", 10)
        self.size = 0
        self.focus = "name"
        self.t = 0
        pygame.key.start_text_input()

    def _rects(self):
        cx = SW // 2
        return {
            "name": pygame.Rect(cx - 220, 200, 440, 46),
            "size": pygame.Rect(cx - 220, 290, 440, 46),
            "evil": pygame.Rect(cx - 220, 360, 440, 46),
            "seed": pygame.Rect(cx - 220, 450, 440, 46),
            "create": pygame.Rect(cx - 220, 540, 210, 50),
            "back": pygame.Rect(cx + 10, 540, 210, 50),
        }

    def handle_event(self, e):
        if e.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.back()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
                self.create()
                return
            if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
                self.focus = "seed" if self.focus == "name" else "name"
                return
            field = self.name if self.focus == "name" else self.seed
            if self.focus == "seed" and e.type == pygame.TEXTINPUT and \
                    not e.text.isdigit():
                return
            field.handle(e)
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            r = self._rects()
            if r["name"].collidepoint(e.pos):
                self.focus = "name"
            elif r["seed"].collidepoint(e.pos):
                self.focus = "seed"
            elif r["size"].collidepoint(e.pos):
                self.size = (self.size + 1) % len(self.SIZES)
                self.app.audio.play("menu")
            elif r["create"].collidepoint(e.pos):
                self.app.audio.play("menu")
                self.create()
            elif r["back"].collidepoint(e.pos):
                self.app.audio.play("menu")
                self.back()

    def create(self):
        name = self.name.value.strip()
        if not name:
            self.focus = "name"
            return
        seed = int(self.seed.value) if self.seed.value else \
            random.randrange(1, 2 ** 31)
        pygame.key.stop_text_input()
        self.app.set_state(GeneratingScreen(self.app, name,
                                            self.SIZES[self.size], seed))

    def back(self):
        pygame.key.stop_text_input()
        self.app.set_state(WorldSelect(self.app))

    def update(self):
        self.t += 1

    def draw(self, screen):
        self.app.menu_bg.draw(screen, self.app.assets)
        self.text.draw(screen, "Create World", (SW // 2, 100), 40,
                       anchor="midtop")
        mpos = pygame.mouse.get_pos()
        r = self._rects()
        caret = "|" if (self.t // 30) % 2 == 0 else ""
        for key, label in (("name", "World Name"), ("seed", "Seed (optional)")):
            rect = r[key]
            self.text.draw(screen, label, (rect.x, rect.y - 24), 18,
                           (210, 215, 240))
            focused = self.focus == key
            pygame.draw.rect(screen, (63, 82, 151), rect, border_radius=8)
            pygame.draw.rect(screen, YELLOW if focused else (120, 140, 220),
                             rect, 2, border_radius=8)
            val = (self.name if key == "name" else self.seed).value
            self.text.draw(screen, val + (caret if focused else ""),
                           (rect.x + 12, rect.y + 11), 24)
        for key, label in (("size", f"Size: {self.SIZES[self.size]}"),
                           ("evil", "World Evil: Corruption"),
                           ("create", "Create"), ("back", "Back")):
            rect = r[key]
            hov = rect.collidepoint(mpos) and key != "evil"
            col = (110, 80, 150) if key == "evil" else \
                ((73, 94, 171) if hov else (53, 70, 140))
            pygame.draw.rect(screen, col, rect, border_radius=8)
            pygame.draw.rect(screen, (120, 140, 220), rect, 2,
                             border_radius=8)
            self.text.draw(screen, label, rect.center, 26,
                           YELLOW if hov else WHITE, anchor="center")
        sizes = {"Small": "4200 x 1200", "Medium": "6400 x 1800",
                 "Large": "8400 x 2400"}
        self.text.draw(screen, sizes[self.SIZES[self.size]] + " tiles",
                       (r["size"].right + 14, r["size"].y + 12), 18,
                       (210, 215, 240))


# ---------------------------------------------------------------------------
# generation / loading
# ---------------------------------------------------------------------------
class GeneratingScreen:
    def __init__(self, app, name, size, seed):
        self.app = app
        self.text = app.text
        self.msg = "Starting"
        self.frac = 0.0
        self.done = None
        self.error = None
        self.t = 0
        self.name = name
        if webstore.WEB:
            # no threads in the browser: run one generation pass per frame
            self.steps = self._run_steps(name, size, seed)
        else:
            self.steps = None
            self.thread = threading.Thread(target=self._run,
                                           args=(name, size, seed),
                                           daemon=True)
            self.thread.start()

    def _progress(self, msg, frac):
        self.msg, self.frac = msg, frac

    def _run_steps(self, name, size, seed):
        gen = worldgen.generate_steps(name, size, seed)
        while True:
            try:
                self._progress(*next(gen))
            except StopIteration as stop:
                world = stop.value
                break
            yield
        self._progress("Saving world", 1.0)
        yield
        self._save(world)

    def _save(self, world):
        os.makedirs(C.WORLD_DIR, exist_ok=True)
        base = _safe_name(world.name)
        path = os.path.join(C.WORLD_DIR, base + ".wld.npz")
        n = 2
        while os.path.exists(path):
            path = os.path.join(C.WORLD_DIR, f"{base}_{n}.wld.npz")
            n += 1
        world.save(path)
        webstore.persist(path)
        self.done = (world, path)

    def _run(self, name, size, seed):
        try:
            world = worldgen.generate(name, size, seed, self._progress)
            self._progress("Saving world", 1.0)
            self._save(world)
        except Exception as e:  # pragma: no cover
            import traceback
            traceback.print_exc()
            self.error = str(e)

    def handle_event(self, e):
        if self.error and e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.set_state(WorldSelect(self.app))

    def update(self):
        self.t += 1
        if self.steps is not None and not self.done and not self.error \
                and self.t > 2:
            try:
                next(self.steps)
            except StopIteration:
                pass
            except Exception as e:  # pragma: no cover
                import traceback
                traceback.print_exc()
                self.error = str(e)
        if self.done:
            world, path = self.done
            self.app.start_game(world, path)

    def draw(self, screen):
        self.app.menu_bg.draw(screen, self.app.assets)
        shade = pygame.Surface((SW, SH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 90))
        screen.blit(shade, (0, 0))
        if self.error:
            self.text.draw(screen, "World generation failed: " + self.error,
                           (SW // 2, SH // 2), 24, (255, 120, 120),
                           anchor="center")
            return
        self.text.draw(screen, self.msg + "." * ((self.t // 20) % 4),
                       (SW // 2, SH // 2 - 50), 32, anchor="center")
        bar = pygame.Rect(SW // 2 - 250, SH // 2, 500, 28)
        pygame.draw.rect(screen, (20, 24, 60), bar, border_radius=8)
        fill = bar.inflate(-6, -6)
        fill.w = int(fill.w * self.frac)
        pygame.draw.rect(screen, (90, 200, 90), fill, border_radius=6)
        pygame.draw.rect(screen, (120, 140, 220), bar, 2, border_radius=8)
        self.text.draw(screen, f"{int(self.frac * 100)}%", bar.center, 20,
                       anchor="center")


class LoadingScreen:
    def __init__(self, app, path):
        self.app = app
        self.text = app.text
        self.path = path
        self.done = None
        self.error = None
        self.t = 0
        if not webstore.WEB:
            threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        try:
            self.done = World.load(self.path)
        except Exception as e:  # pragma: no cover
            self.error = str(e)

    def handle_event(self, e):
        if self.error and e.type in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            self.app.set_state(WorldSelect(self.app))

    def update(self):
        self.t += 1
        if webstore.WEB and self.t == 3 and not self.done:
            self._run()               # after the "Loading" text was shown
        if self.done:
            self.app.start_game(self.done, self.path)

    def draw(self, screen):
        self.app.menu_bg.draw(screen, self.app.assets)
        msg = ("Failed to load world: " + self.error) if self.error else \
            "Loading world" + "." * ((self.t // 20) % 4)
        self.text.draw(screen, msg, (SW // 2, SH // 2), 32,
                       (255, 120, 120) if self.error else WHITE,
                       anchor="center")
