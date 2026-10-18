"""Sound effects: small synthesised ones plus audio files from sounds/."""
import os
import sys

import numpy as np
import pygame

RATE = 44100
SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")
# sound name -> file name (without extension) in SOUND_DIR
FILE_SOUNDS = {"door_open": "door_open", "door_close": "door_close"}
# used when a file is missing or can't be decoded
FALLBACK = {"door_open": "open", "door_close": "close"}


def _env(n, attack=0.005, decay=None):
    t = np.arange(n) / RATE
    e = np.minimum(1.0, t / max(attack, 1e-4))
    if decay:
        e *= np.exp(-t / decay)
    return e


def _to_sound(wave, vol=0.5):
    w = np.clip(wave * vol, -1, 1)
    data = (w * 32767).astype(np.int16)
    stereo = np.ascontiguousarray(np.column_stack([data, data]))
    return pygame.sndarray.make_sound(stereo)


class Audio:
    def __init__(self, volume=0.6):
        self.ok = False
        self.sounds = {}
        self.volume = volume
        try:
            pygame.mixer.pre_init(RATE, -16, 2, 512)
            pygame.mixer.init(RATE, -16, 2, 512)
            self.ok = pygame.mixer.get_init() is not None
        except pygame.error:
            self.ok = False
        if self.ok:
            try:
                self._build()
            except Exception:       # pragma: no cover - audio is optional
                self.ok = False

    def _build(self):
        rng = np.random.default_rng(3)
        n = int(RATE * 0.09)
        noise = rng.uniform(-1, 1, n)
        # dig: low filtered noise burst
        lp = np.convolve(noise, np.ones(14) / 14, mode="same")
        self.sounds["dig"] = _to_sound(lp * _env(n, decay=0.03) * 2.2, 0.45)
        # tink: metallic ping
        t = np.arange(int(RATE * 0.12)) / RATE
        tink = (np.sin(t * 2 * np.pi * 1900) + 0.5 *
                np.sin(t * 2 * np.pi * 2900)) * np.exp(-t / 0.03)
        self.sounds["tink"] = _to_sound(tink, 0.25)
        # grass rustle
        hp = noise - np.convolve(noise, np.ones(4) / 4, mode="same")
        self.sounds["grass"] = _to_sound(hp * _env(n, decay=0.025) * 1.5,
                                         0.35)
        # place: thump
        t = np.arange(int(RATE * 0.07)) / RATE
        thump = np.sin(t * 2 * np.pi * (180 - t * 900)) * np.exp(-t / 0.02)
        self.sounds["place"] = _to_sound(thump + lp[:len(t)] * 0.3, 0.5)
        # grab: short pop
        t = np.arange(int(RATE * 0.06)) / RATE
        pop = np.sin(t * 2 * np.pi * (500 + t * 6000)) * np.exp(-t / 0.02)
        self.sounds["grab"] = _to_sound(pop, 0.3)
        # menu tick
        t = np.arange(int(RATE * 0.04)) / RATE
        self.sounds["menu"] = _to_sound(np.sin(t * 2 * np.pi * 900) *
                                        np.exp(-t / 0.01), 0.3)
        # hurt
        t = np.arange(int(RATE * 0.18)) / RATE
        hurt = np.sin(t * 2 * np.pi * (260 - t * 600)) * np.exp(-t / 0.06)
        self.sounds["hurt"] = _to_sound(hurt + rng.uniform(-0.2, 0.2, len(t))
                                        * np.exp(-t / 0.03), 0.5)
        # swing whoosh
        n2 = int(RATE * 0.12)
        wn = np.convolve(rng.uniform(-1, 1, n2), np.ones(6) / 6, mode="same")
        env = np.sin(np.linspace(0, np.pi, n2))
        self.sounds["swing"] = _to_sound(wn * env * 1.5, 0.18)
        # door / chest
        t = np.arange(int(RATE * 0.15)) / RATE
        creak = np.sin(t * 2 * np.pi * (300 + 80 * np.sin(t * 60))) * \
            np.exp(-t / 0.05)
        self.sounds["open"] = _to_sound(creak, 0.3)
        self.sounds["close"] = _to_sound(creak[::-1] * np.exp(-t / 0.05), 0.3)
        # splash
        n3 = int(RATE * 0.25)
        sp = np.convolve(rng.uniform(-1, 1, n3), np.ones(8) / 8, mode="same")
        self.sounds["splash"] = _to_sound(sp * _env(n3, 0.01, 0.07) * 2, 0.35)
        self.sounds["death"] = _to_sound(
            np.sin(np.arange(int(RATE * 0.6)) / RATE * 2 * np.pi * 110) *
            np.exp(-np.arange(int(RATE * 0.6)) / RATE / 0.2), 0.5)
        self._load_files()
        self.set_volume(self.volume)

    def set_volume(self, v):
        self.volume = v
        for s in self.sounds.values():
            s.set_volume(v)

    def _load_files(self):
        # browsers (pygbag build) only get the .ogg copies
        exts = (".ogg", ".wav") if sys.platform == "emscripten" else \
            (".wav", ".ogg")
        for name, base in FILE_SOUNDS.items():
            for ext in exts:
                path = os.path.join(SOUND_DIR, base + ext)
                if not os.path.exists(path):
                    continue
                try:
                    self.sounds[name] = pygame.mixer.Sound(path)
                    break
                except pygame.error:
                    continue

    def play(self, name):
        if self.ok and self.volume > 0:
            s = self.sounds.get(name) or self.sounds.get(FALLBACK.get(name))
            if s:
                s.play()
