"""Application shell: window, main loop and state switching.

The main loop is async so the same code runs on the desktop and in the
browser (pygbag), where control must be handed back to the page every frame.
"""
import asyncio
import json
import os
import sys

import pygame

from . import config as C
from . import webstore
from .audio import Audio
from .text import Text
from . import textures as TX

WEB = webstore.WEB
TICK_MS = 1000.0 / C.FPS


def _open_window():
    size = (C.SCREEN_W, C.SCREEN_H)
    if WEB:
        return pygame.display.set_mode(size)
    flags = pygame.SCALED | pygame.RESIZABLE
    if C.SETTINGS.get("fullscreen"):
        flags |= pygame.FULLSCREEN
    for args, kw in (((size, flags), {"vsync": 1}),
                     ((size, pygame.SCALED), {}),
                     ((size,), {})):
        try:
            return pygame.display.set_mode(*args, **kw)
        except Exception:
            continue
    raise SystemExit("could not open a window")


class App:
    def __init__(self):
        if WEB:
            webstore.restore_all()            # bring back browser saves
            C.SETTINGS.update(C.load_settings())
        os.makedirs(C.WORLD_DIR, exist_ok=True)
        os.makedirs(C.PLAYER_DIR, exist_ok=True)
        pygame.init()
        self.screen = _open_window()
        pygame.display.set_caption(C.TITLE)
        self.screen.fill((0, 0, 0))
        self.text = Text()
        self.text.draw(self.screen, "Generating textures...",
                       (C.SCREEN_W // 2, C.SCREEN_H // 2), 28,
                       anchor="center")
        pygame.display.flip()
        self.audio = Audio(C.SETTINGS.get("volume", 0.6))
        self.assets = TX.Assets()
        self.cursor = TX.template(TX.CURSOR, {"o": (40, 10, 10),
                                              "O": (255, 96, 70),
                                              "H": (255, 190, 170)})
        pygame.mouse.set_visible(False)
        from .menus import MenuBackground, TitleMenu
        self.menu_bg = MenuBackground()
        self.clock = pygame.time.Clock()
        self.player_path = None
        self.running = True
        self.state = TitleMenu(self)

    def set_state(self, state):
        self.state = state

    def quit(self):
        self.running = False

    def start_game(self, world, world_path):
        from .game import Game
        from .player import Player
        with open(self.player_path, encoding="utf-8") as f:
            player = Player.from_json(json.load(f))
        self.set_state(GameState(self, Game(self, world, player, world_path,
                                            self.player_path)))

    def _frame(self, acc):
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                if isinstance(self.state, GameState):
                    self.state.game.save()
                self.running = False
                return acc
            self.state.handle_event(e)
        if WEB and isinstance(self.state, GameState):
            # the browser decides the frame rate: run the simulation on a
            # fixed 60 Hz clock (at most 2 ticks per frame to stay responsive)
            acc = min(acc + self.clock.tick(), 50.0)
            ticks = 0
            while acc >= TICK_MS and ticks < 2:
                self.state.update()
                acc -= TICK_MS
                ticks += 1
        else:
            if WEB:
                self.clock.tick()
            self.state.update()
        self.state.draw(self.screen)
        if not isinstance(self.state, GameState):
            mx, my = pygame.mouse.get_pos()
            self.screen.blit(self.cursor, (mx - 2, my - 2))
        pygame.display.flip()
        if not WEB:
            self.clock.tick(C.FPS)
        return acc

    async def run_async(self):
        acc = TICK_MS
        while self.running:
            acc = self._frame(acc)
            await asyncio.sleep(0)
        if not WEB:
            pygame.quit()

    def run(self):
        asyncio.run(self.run_async())


class GameState:
    """Adapter running the Game at a fixed 60 Hz tick."""

    def __init__(self, app, game):
        self.app = app
        self.game = game

    def handle_event(self, e):
        self.game.handle_event(e)

    def update(self):
        self.game.fps = self.app.clock.get_fps()
        self.game.update()
        if self.game.exit_requested:
            from .menus import TitleMenu
            self.app.set_state(TitleMenu(self.app))

    def draw(self, screen):
        self.game.draw()


def handle_cli():
    """Desktop-only command line tools. Returns True if one ran."""
    args = sys.argv[1:]
    if args[:1] == ["--export-skin"] and len(args) >= 2:
        from .customskins import export_template
        name = " ".join(args[1:])
        try:
            print("Wrote", export_template(name))
        except ValueError as e:
            print(e)
            sys.exit(1)
        return True
    return False


async def main_async():
    await App().run_async()


def main():
    if WEB or not handle_cli():
        asyncio.run(main_async())
