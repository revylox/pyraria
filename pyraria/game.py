"""In-game state: simulation, input, camera and drawing."""
import json
import math
import random

import pygame

from . import config as C
from . import lighting
from . import tiles as T
from . import webstore
from .background import Background
from .entities import (ItemEntity, FallingBlock, Particle, FloatText,
                       pickup_text)
from .items import ITEMS
from .minimap import MapUI
from .renderer import Renderer
from .ui import UI
from .world import BIOME_NAMES

SW, SH = C.SCREEN_W, C.SCREEN_H

KEYMAP = {
    "left": (pygame.K_a, pygame.K_LEFT),
    "right": (pygame.K_d, pygame.K_RIGHT),
    "jump": (pygame.K_SPACE, pygame.K_w, pygame.K_UP),
    "down": (pygame.K_s, pygame.K_DOWN),
}


class Game:
    def __init__(self, app, world, player, world_path, player_path):
        self.app = app
        self.screen = app.screen
        self.assets = app.assets
        self.text = app.text
        self.audio = app.audio
        self.world = world
        self.player = player
        self.world_path = world_path
        self.player_path = player_path
        self.bg = Background(world.seed)
        self.renderer = Renderer(world, self.assets, self.bg)
        self.ui = UI(self)
        self.map = MapUI(self)
        self.entities = []
        self.particles = []
        self.texts = []
        self.camx = self.camy = 0.0
        self.biome = 0
        self.fps = 0.0
        self.autosave_timer = 0
        self.exit_requested = False
        self.was_wet = False
        self.chat = None             # text being typed, or None
        self._plant_colors = {}
        world.on_drop = self.drop_item
        world.on_fall = self._on_fall
        world.dirty.clear()
        player.spawn_at(world)
        self._update_camera(snap=True)
        self.biome = world.detect_biome(int(player.cx // 16),
                                        int(player.cy // 16))
        self.bg.set_biome(self.biome)
        self.bg.fade = 1.0
        self.ui.message(f"{player.name} has joined {world.name}.",
                        (255, 240, 150))
        self.ui.message("Esc: inventory   M: map   Tab: minimap mode",
                        (200, 200, 220))

    # ------------------------------------------------------------ helpers
    def sound(self, name):
        self.audio.play(name)

    def drop_item(self, name, count, px, py, vx=None, delay=0):
        if count <= 0:
            return
        self.entities.append(ItemEntity(name, count, px, py, vx=vx,
                                        pickup_delay=delay))

    def _on_fall(self, tid, x, y):
        self.entities.append(FallingBlock(tid, x, y))

    def on_pickup(self, name, count):
        self.sound("grab")
        for ft in self.texts:
            if ft.key == name and ft.life > 20:
                ft.count += count
                ft.text, ft.color = pickup_text(name, ft.count)
                ft.life = ft.max_life
                ft.y = self.player.y - 10
                ft.vy = -2.0
                return
        label, color = pickup_text(name, count)
        ft = FloatText(label, self.player.cx, self.player.y - 10, color,
                       size=20, key=name)
        ft.count = count
        self.texts.append(ft)

    def toggle_fullscreen(self):
        C.SETTINGS["fullscreen"] = not C.SETTINGS["fullscreen"]
        try:
            pygame.display.toggle_fullscreen()
        except Exception:
            pass
        C.save_settings(C.SETTINGS)

    # ---------------------------------------------------------------- save
    def save(self):
        try:
            self.world.save(self.world_path)
            with open(self.player_path, "w", encoding="utf-8") as f:
                json.dump(self.player.to_json(), f)
        except OSError as e:
            self.ui.message(f"Save failed: {e}", (255, 120, 120))
            return
        if not (webstore.persist(self.world_path) and
                webstore.persist(self.player_path)):
            self.ui.message("Browser storage is full - this save will be "
                            "lost when the page is closed.", (255, 160, 120))

    def save_and_exit(self):
        self.ui.close_inventory()
        self.save()
        self.exit_requested = True

    # --------------------------------------------------------------- input
    def mouse_world(self):
        mx, my = pygame.mouse.get_pos()
        return mx + self.camx, my + self.camy

    def handle_event(self, e):
        if self.map.full_open:
            if e.type == pygame.KEYDOWN and e.key in (pygame.K_m,
                                                      pygame.K_ESCAPE):
                self.map.close_full()
            else:
                self.map.full_event(e)
            return
        ui = self.ui
        inv = self.player.inv
        if self.chat is not None:
            self._chat_event(e)
            if e.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
                return
        if e.type == pygame.KEYDOWN:
            k = e.key
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.chat = ""
                pygame.key.start_text_input()
            elif k == pygame.K_ESCAPE:
                if ui.wardrobe_open:
                    ui.wardrobe_open = False
                elif ui.settings_open:
                    ui.close_settings()
                else:
                    ui.toggle_inventory()
            elif k == pygame.K_k:
                ui.wardrobe_open = not ui.wardrobe_open
            elif k == pygame.K_m:
                self.map.open_full()
            elif k == pygame.K_TAB:
                self.map.cycle_mode()
            elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                self.map.zoom_minimap(1)
            elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.map.zoom_minimap(-1)
            elif k == pygame.K_F10:
                C.SETTINGS["show_fps"] = not C.SETTINGS["show_fps"]
            elif k == pygame.K_F11:
                self.toggle_fullscreen()
            elif k == pygame.K_t:
                self._throw_held()
            elif pygame.K_1 <= k <= pygame.K_9:
                inv.selected = k - pygame.K_1
            elif k == pygame.K_0:
                inv.selected = 9
        elif e.type == pygame.MOUSEWHEEL:
            if ui.handle_wheel(e.y, pygame.mouse.get_pos()):
                return
            inv.selected = (inv.selected - e.y) % 10
        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button in (1, 3):
                mods = pygame.key.get_mods()
                if ui.handle_click(e.button, e.pos, mods):
                    return
                if ui.inventory_open and inv.mouse and e.button == 1:
                    self._throw_mouse_item()
                    return
                if e.button == 3:
                    self._interact()

    def _chat_event(self, e):
        if e.type == pygame.KEYDOWN:
            if e.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                msg = self.chat.strip()
                if msg:
                    self.ui.message(f"<{self.player.name}> {msg}")
                self.chat = None
                pygame.key.stop_text_input()
            elif e.key == pygame.K_ESCAPE:
                self.chat = None
                pygame.key.stop_text_input()
            elif e.key == pygame.K_BACKSPACE:
                self.chat = self.chat[:-1]
        elif e.type == pygame.TEXTINPUT and len(self.chat) < 120:
            self.chat += e.text

    def _throw_held(self):
        inv = self.player.inv
        s = inv.held
        if s:
            p = self.player
            self.drop_item(s.name, s.count, p.cx + p.dir * 8, p.cy - 6,
                           vx=p.dir * 4, delay=90)
            inv.main[inv.selected] = None

    def _throw_mouse_item(self):
        inv = self.player.inv
        p = self.player
        mx, _ = self.mouse_world()
        d = 1 if mx > p.cx else -1
        self.drop_item(inv.mouse.name, inv.mouse.count, p.cx + d * 8,
                       p.cy - 6, vx=d * 4, delay=90)
        inv.mouse = None

    def _interact(self):
        p = self.player
        if p.dead:
            return
        mx, my = self.mouse_world()
        tx, ty = int(mx // 16), int(my // 16)
        if not p.in_reach(tx, ty):
            return
        tid = self.world.get(tx, ty)
        if tid in (T.DOOR_CLOSED, T.DOOR_OPEN):
            if tid == T.DOOR_OPEN:
                x0, y0 = self.world.multi_origin(tx, ty)
                if pygame.Rect(x0 * 16, y0 * 16, 16, 48).colliderect(p.rect()):
                    return
            self.world.toggle_door(tx, ty)
            self.sound("door_open" if tid == T.DOOR_CLOSED else "door_close")
        elif tid == T.CHEST:
            pos = self.world.multi_origin(tx, ty)
            if self.ui.chest == pos:
                self.ui.chest = None
                self.sound("close")
            else:
                self.ui.open_chest(pos)

    # -------------------------------------------------------------- update
    def update(self):
        world, p, ui = self.world, self.player, self.ui
        world.tick_count += 1
        world.time = (world.time + 1) % (C.DAY_LENGTH + C.NIGHT_LENGTH)
        keys_down = pygame.key.get_pressed()
        typing_blocked = self.map.full_open or ui.settings_open or \
            ui.wardrobe_open or self.chat is not None
        keys = {name: (not typing_blocked) and any(keys_down[k] for k in ks)
                for name, ks in KEYMAP.items()}
        mouse = pygame.mouse.get_pressed()
        mpos = pygame.mouse.get_pos()
        ui.update(mpos, mouse)
        blocked = typing_blocked or ui.mouse_over_ui(mpos) or \
            (ui.inventory_open and p.inv.mouse is not None)
        p.update(world, keys, self.mouse_world(), mouse[0], blocked)
        self._handle_player_events()
        # splash
        if p.wet != self.was_wet and not p.dead:
            self.sound("splash")
            for _ in range(10):
                self.particles.append(Particle(
                    p.cx + random.uniform(-10, 10), p.y + p.h - 8,
                    (120, 170, 255), vy=random.uniform(-4, -1), size=4))
        self.was_wet = p.wet
        world.process_updates()
        world.update_liquids()
        world.random_updates(int(p.cx // 16), int(p.cy // 16), 40)
        # damage decay on partially mined tiles
        if world.tick_count % 60 == 0:
            for key in list(world.damage):
                d = world.damage[key]
                d[1] += 1
                if d[1] > 5:
                    del world.damage[key]
        for e in self.entities:
            e.update(world, p, self)
        self.entities = [e for e in self.entities if not e.dead]
        if len(self.entities) > 400:
            self.entities = self.entities[-400:]
        self._spawn_embers()
        for prt in self.particles:
            prt.update(world, p, self)
        self.particles = [q for q in self.particles if not q.dead]
        for t in self.texts:
            t.update()
        self.texts = [t for t in self.texts if not t.dead]
        if world.tick_count % 30 == 0:
            self.biome = world.detect_biome(int(p.cx // 16), int(p.cy // 16))
            self.bg.set_biome(self.biome)
        self.bg.update()
        self._update_camera()
        # autosave
        self.autosave_timer += 1
        mins = C.SETTINGS.get("autosave_minutes", 5)
        if mins and self.autosave_timer >= mins * 60 * 60:
            self.autosave_timer = 0
            self.save()
            ui.message("Autosaved.", (180, 180, 200))

    def _handle_player_events(self):
        p = self.player
        for kind, data in p.events:
            if kind == "dig":
                tx, ty, tid = data
                if tid == "wall":
                    col = T.WALLS[self.world.walls[tx, ty]].color \
                        if self.world.walls[tx, ty] else (100, 80, 60)
                    snd = "dig"
                else:
                    d = T.TILES[tid]
                    col = d.dust
                    snd = d.sound if d.sound in ("dig", "tink", "grass") \
                        else "dig"
                self.sound(snd)
                for _ in range(4):
                    self.particles.append(Particle(
                        tx * 16 + random.uniform(2, 14),
                        ty * 16 + random.uniform(2, 14), col))
            elif kind == "break":
                tx, ty, tid = data[:3]
                frame = data[3] if len(data) > 3 else 0
                self._break_particles(tx, ty, tid, frame)
            elif kind == "swing":
                if ITEMS[data].kind == "weapon":
                    self.sound(random.choice(("sword_1", "sword_2")))
            elif kind == "place":
                self.sound("place")
            elif kind == "tink":
                self.sound("tink")
            elif kind == "hurt":
                self.sound("hurt")
                self.texts.append(FloatText(str(data), p.cx, p.y - 4,
                                            (255, 70, 70), size=24, life=60))
            elif kind == "death":
                self.sound("death")
                self.ui.message(f"{p.name} {data}.", (225, 25, 25))
                self.ui.close_inventory(silent=True)
            elif kind == "message":
                if not self.ui.messages or self.ui.messages[-1][0] != data:
                    self.ui.message(data, (255, 255, 255))
        p.events.clear()

    def _sprite_colors(self, tid, frame):
        """Opaque colours of a plant/vine sprite (cached), for particles."""
        key = (tid, frame % 6)
        cols = self._plant_colors.get(key)
        if cols is None:
            A = self.assets
            if T.TILES[tid].kind == "plant":
                spr = A.plant[tid][frame % 6]
            else:
                spr = A.vine[tid][0]
            w, h = spr.get_size()
            cols = [tuple(spr.get_at((x, y)))[:3] for x in range(0, w, 2)
                    for y in range(0, h, 2) if spr.get_at((x, y))[3] > 0]
            self._plant_colors[key] = cols or [T.TILES[tid].dust]
        return cols

    def _break_particles(self, tx, ty, tid, frame):
        d = T.TILES[tid]
        if d.kind in ("plant", "vine"):
            # leafy burst: bits in the plant's own colours (petals too)
            cols = self._sprite_colors(tid, frame)
            for _ in range(12):
                c = random.choice(cols)
                k = random.uniform(0.8, 1.15)
                self.particles.append(Particle(
                    tx * 16 + random.uniform(2, 14),
                    ty * 16 + random.uniform(4, 15),
                    tuple(min(255, int(v * k)) for v in c),
                    vx=random.uniform(-1.8, 1.8),
                    vy=random.uniform(-3.2, -0.8),
                    life=random.randint(22, 40),
                    size=random.choice((2, 2, 4)), grav=0.12))
            return
        for _ in range(8):
            self.particles.append(Particle(
                tx * 16 + random.uniform(0, 16),
                ty * 16 + random.uniform(0, 16), d.dust))

    def _update_camera(self, snap=False):
        p = self.player
        tx = p.cx - SW / 2
        ty = p.cy - SH / 2
        if snap:
            self.camx, self.camy = tx, ty
        else:
            self.camx += (tx - self.camx) * 0.5
            self.camy += (ty - self.camy) * 0.5
        w = self.world
        self.camx = max(0, min(w.w * 16 - SW, self.camx))
        self.camy = max(0, min(w.h * 16 - SH, self.camy))

    # ---------------------------------------------------------------- draw
    def draw(self):
        screen = self.screen
        if self.map.full_open:
            self.map.draw_full(screen, self.text)
            self._draw_cursor(screen)
            return
        world, p = self.world, self.player
        camx, camy = int(self.camx), int(self.camy)
        night = self.bg.draw_sky(screen, camx, camy, world)
        if camy < world.underground_y * 16:
            self.bg.draw_layers(screen, camx, camy, world, night)
        hand = p.held_light()
        self.renderer.draw(screen, camx, camy, p, self.entities,
                           self.particles, self._dynamic_lights(),
                           [(hand[0], hand[1] - 6)] if hand else [])
        self._draw_target(screen, camx, camy)
        for t in self.texts:
            t.draw(screen, camx, camy, self.text)
        self.ui.draw_breath(screen, p, camx, camy)
        mpos = pygame.mouse.get_pos()
        self.map.draw_minimap(screen)
        self.ui.draw(screen, mpos)
        if p.dead:
            self.text.draw(screen, "You were slain...", (SW // 2, SH // 2 - 40),
                           48, (225, 25, 25), anchor="center")
            self.text.draw(screen, str(math.ceil(p.respawn / 60)),
                           (SW // 2, SH // 2 + 10), 36, (225, 25, 25),
                           anchor="center")
        if C.SETTINGS.get("show_fps"):
            self.text.draw(screen, f"{self.fps:.0f} FPS   "
                           f"{BIOME_NAMES[self.biome]}   "
                           f"x {int(p.cx // 16)}  y {int(p.cy // 16)}",
                           (SW // 2, SH - 6), 16, anchor="midbottom")
        if self.chat is not None:
            box = pygame.Rect(16, SH - 34, 620, 28)
            bg = pygame.Surface(box.size, pygame.SRCALPHA)
            pygame.draw.rect(bg, (20, 24, 60, 190), bg.get_rect(),
                             border_radius=5)
            screen.blit(bg, box)
            caret = "|" if (self.world.tick_count // 30) % 2 == 0 else ""
            self.text.draw(screen, self.chat + caret, (box.x + 8, box.y + 4),
                           18)
        self.ui.draw_overlay(screen, mpos)
        self._draw_cursor(screen)

    def _spawn_embers(self):
        """Torches now and then give off a small rising, glowing ember."""
        sources = list(self.renderer.visible_torches)
        hand = self.player.held_light()
        if hand:
            sources.append((hand[0], hand[1] - 6))
        for (x, y) in sources:
            if random.random() < 0.02:
                self.particles.append(Particle(
                    x + random.uniform(-2, 2), y + random.uniform(-2, 1),
                    random.choice(((255, 190, 70), (255, 140, 40),
                                   (255, 230, 140))),
                    vx=random.uniform(-0.3, 0.3),
                    vy=random.uniform(-1.0, -0.4),
                    life=random.randint(25, 50), size=2, grav=-0.004,
                    glow=True))

    def _dynamic_lights(self):
        """Light sources that aren't tiles: a torch in the player's hand and
        torches lying on the ground (both glow, as in Terraria)."""
        lights = []
        hand = self.player.held_light()
        if hand:
            lights.append((hand[0], hand[1], lighting.TORCH_LIGHT))
        for e in self.entities:
            if isinstance(e, ItemEntity) and e.name == "Torch":
                lights.append((e.x, e.y, lighting.TORCH_LIGHT))
        return lights

    def _draw_target(self, screen, camx, camy):
        p = self.player
        if p.dead or self.ui.inventory_open and \
                self.ui.mouse_over_ui(pygame.mouse.get_pos()):
            return
        held = p.inv.held
        if not held:
            return
        mx, my = self.mouse_world()
        tx, ty = int(mx // 16), int(my // 16)
        if not p.in_reach(tx, ty):
            return
        r = pygame.Rect(tx * 16 - camx, ty * 16 - camy, 16, 16)
        s = pygame.Surface((16, 16), pygame.SRCALPHA)
        pygame.draw.rect(s, (255, 255, 255, 90), s.get_rect(), 1)
        screen.blit(s, r)

    def _draw_cursor(self, screen):
        cur = self.app.cursor
        mx, my = pygame.mouse.get_pos()
        screen.blit(cur, (mx - 2, my - 2))
