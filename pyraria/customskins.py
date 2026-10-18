"""Sprite-sheet skins loaded from PNG files in the ``skins/`` folder.

Drop ``<Name>.png`` into ``skins/`` and it appears in the Wardrobe and the
character creator.  The image is used pixel for pixel.  Supported layouts:

* a single character image (one frame), or
* an animation strip of equally sized frames, stacked vertically (the
  layout Terraria uses for town NPC sheets) or horizontally.

Without a sidecar file the frame size is guessed (character frames are
about 1.4 times taller than wide) and multi-frame sheets use the Terraria
NPC convention: frame 0 standing, frame 1 airborne, frames 2-15 walking,
facing left.  An optional ``<Name>.json`` overrides any of this::

    {"frame_width": 40, "frame_height": 56, "layout": "vertical",
     "idle": 0, "jump": 1, "walk": [2, 3, 4, 5, 6, 7, 8, 9],
     "facing": "left", "scale": 1}
"""
import json
import os

import pygame

from . import config as C
from .playergfx import (CW, CH, IDLE, JUMP, LEG_FRAMES, O, SKINS,
                        PlayerGfx)

SKIN_DIR = os.path.join(C.ROOT_DIR, "skins")
FEET_Y = (O + 28) * 2        # feet line inside a composed frame canvas
TARGET_H = 56                # on-screen height of a standard character


def list_custom():
    if not os.path.isdir(SKIN_DIR):
        return []
    return [os.path.splitext(f)[0] for f in sorted(os.listdir(SKIN_DIR))
            if f.lower().endswith(".png")]


def all_skin_names():
    custom = [n for n in list_custom() if n not in SKINS and n != "Custom"]
    return ["Custom"] + list(SKINS) + custom


def make_gfx(look):
    """Graphics object for a look: built-in drawing or a sprite sheet."""
    name = (look or {}).get("skin_preset", "Custom")
    if name != "Custom" and name not in SKINS:
        try:
            return SheetSkinGfx(name, look)
        except (OSError, pygame.error, ValueError, KeyError) as e:
            print(f"[skins] could not load '{name}': {e}")
    return PlayerGfx(look)


def _guess_frames(w, h):
    """Number of frames in a vertical strip whose frames are ~1.4w tall."""
    best, best_err = 1, abs(h / w - 1.4)
    for n in range(2, 200):
        if h % n:
            continue
        err = abs(h / n / w - 1.4)
        if err < best_err:
            best, best_err = n, err
    return best if best_err < 0.35 else 1


def _feet(surf):
    """Centre of the lowest few opaque rows (where the feet are)."""
    bb = surf.get_bounding_rect()
    if not bb.w:
        return (surf.get_width() // 2, surf.get_height())
    mask = pygame.mask.from_surface(surf)
    xs = [x for y in range(max(bb.top, bb.bottom - 6), bb.bottom)
          for x in range(bb.left, bb.right) if mask.get_at((x, y))]
    return ((min(xs) + max(xs) + 1) // 2, bb.bottom)


class SheetSkinGfx:
    """Same interface as PlayerGfx, backed by frames from a PNG."""

    def __init__(self, name, look):
        self.name = name
        self.look = dict(look or {})
        path = os.path.join(SKIN_DIR, name + ".png")
        img = pygame.image.load(path)
        if pygame.display.get_surface():
            img = img.convert_alpha()
        meta = {}
        jpath = os.path.join(SKIN_DIR, name + ".json")
        if os.path.exists(jpath):
            with open(jpath, encoding="utf-8") as f:
                meta = json.load(f)
        iw, ih = img.get_size()
        layout = meta.get("layout", "vertical")
        if "frame_width" in meta or "frame_height" in meta:
            fw = int(meta.get("frame_width", iw if layout == "vertical"
                              else ih))
            fh = int(meta.get("frame_height", ih if layout == "horizontal"
                              else iw))
        elif layout == "horizontal":
            fh = ih
            n = max(1, round(iw / (ih / 1.4)))
            while n > 1 and iw % n:
                n -= 1
            fw = iw // n
        else:
            fw = iw
            fh = ih // _guess_frames(iw, ih)
        if layout == "horizontal":
            count = max(1, iw // fw)
            rects = [(i * fw, 0, fw, fh) for i in range(count)]
        else:
            count = max(1, ih // fh)
            rects = [(0, i * fh, fw, fh) for i in range(count)]
        frames = [img.subsurface(r).copy() for r in rects]
        facing = meta.get("facing", "left" if count > 1 else "right")
        if facing == "left":
            frames = [pygame.transform.flip(f, True, False) for f in frames]
        scale = meta.get("scale")
        if not scale:
            content = max(f.get_bounding_rect().h for f in frames) or fh
            scale = 1 if content >= 36 else max(1, round(TARGET_H / content))
        if scale != 1:
            frames = [pygame.transform.scale(f, (int(fw * scale),
                                                 int(fh * scale)))
                      for f in frames]
        self.count = count
        self.idle = int(meta.get("idle", 0)) % count
        self.jump = int(meta.get("jump", 1 if count > 1 else 0)) % count
        walk = meta.get("walk")
        if walk is None:
            walk = list(range(2, min(count, 16))) or [self.idle]
        self.walk = [int(i) % count for i in walk] or [self.idle]
        # every frame shares one anchor - the point between the feet - so
        # the animation doesn't wobble; hats, tails or weapons don't skew it
        if "anchor" in meta:
            ax, ay = meta["anchor"]
            if facing == "left":
                ax = fw - ax
            self.anchor = (int(ax * scale), int(ay * scale))
        else:
            self.anchor = _feet(frames[self.idle])
        self.canvas = [self._place(f) for f in frames]
        self.cache = {}

    def _place(self, f):
        c = pygame.Surface((CW * 2, CH * 2), pygame.SRCALPHA)
        c.blit(f, (CW - self.anchor[0], FEET_Y - self.anchor[1]))
        return c

    def frame(self, legs, front_angle, back_angle, walk=None):
        if legs == IDLE:
            return self.canvas[self.idle]
        if legs == JUMP:
            return self.canvas[self.jump]
        prog = (walk if walk is not None else legs) / LEG_FRAMES
        i = int(prog * len(self.walk)) % len(self.walk)
        return self.canvas[self.walk[i]]

    @staticmethod
    def hand_pos(angle):
        return PlayerGfx.hand_pos(angle)

    def head_icon(self):
        if not hasattr(self, "_head_icon"):
            c = self.canvas[self.idle]
            bb = c.get_bounding_rect()
            side = max(8, min(bb.w, int(bb.h * 0.42)))
            r = pygame.Rect(0, 0, side, side)
            r.midtop = (bb.centerx, bb.top)
            r.clamp_ip(c.get_rect())
            self._head_icon = pygame.transform.scale(c.subsurface(r),
                                                     (36, 36))
        return self._head_icon

    def preview(self, scale=2):
        f = self.canvas[self.idle]
        return pygame.transform.scale(
            f, (f.get_width() * scale // 2, f.get_height() * scale // 2))


def export_template(name, out_dir=SKIN_DIR):
    """Write a built-in skin as an editable sprite sheet (+ json)."""
    if name not in SKINS and name != "Custom":
        raise ValueError(f"unknown skin {name!r}")
    import math
    gfx = PlayerGfx({"skin_preset": name})
    frames = [gfx.frame(IDLE, 10, 4), gfx.frame(JUMP, 150, 40)]
    for k in range(LEG_FRAMES):
        sw = math.sin(k / LEG_FRAMES * math.tau) * 28
        frames.append(gfx.frame(k, 8 + sw, 8 - sw))
    fw, fh = frames[0].get_size()
    sheet = pygame.Surface((fw, fh * len(frames)), pygame.SRCALPHA)
    for i, f in enumerate(frames):
        sheet.blit(f, (0, i * fh))
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.join(out_dir, f"{name} (template)")
    pygame.image.save(sheet, base + ".png")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"frame_width": fw, "frame_height": fh,
                   "layout": "vertical", "idle": 0, "jump": 1,
                   "walk": list(range(2, 2 + LEG_FRAMES)),
                   "facing": "right", "scale": 1,
                   "anchor": [CW, FEET_Y]}, f, indent=2)
    return base + ".png"
