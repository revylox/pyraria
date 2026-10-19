"""The player character's sprite and its animation.

The character is a fixed pixel-art sprite (sprites/player.png, 17x30 art
pixels, drawn doubled like Terraria).  Its frames are derived from the
single picture:

* walking - each leg is sheared from the hip (feet move most) and the body
  bobs a pixel when the stride is widest;
* jumping - legs spread;
* using an item / holding a torch - the drawn front hand is replaced by an
  arm in the sprite's own sleeve and skin colours that rotates with the
  swing, like Terraria swaps its arm frames.
"""
import math
import os

import pygame

from .textures import upscale

LEG_FRAMES = 8          # walk cycle
IDLE, JUMP = LEG_FRAMES, LEG_FRAMES + 1
O = 8                   # canvas margin in art pixels
CW, CH = 20 + 2 * O, 28 + 2 * O     # composed frame canvas (art pixels)

SPRITE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "sprites", "player.png")

# --- layout of sprites/player.png (art pixel coordinates) ------------------
HIP_ROW = 22            # legs below this row are animated
LEG_SPLIT = 10          # x < LEG_SPLIT: back leg, x >= LEG_SPLIT: front leg
FRONT_HAND = [(14, 19), (14, 20), (14, 21), (15, 19), (15, 20), (15, 21)]
FRONT_HAND_EDGE = [(13, 19), (13, 20), (13, 21)]   # becomes the new outline
SHOULDER_PX = (12, 14)  # front shoulder pivot
SLEEVE = (0, 92, 39)
SLEEVE_DARK = (0, 44, 26)
SKIN = (253, 166, 83)
SKIN_DARK = (205, 90, 29)
OUTLINE = (36, 2, 10)

# where the sprite sits on the frame canvas: feet on canvas row 36, centred
SPRITE_POS = (9, 6)
# body coordinates (canvas - O) are what Player uses for the hand position
SHOULDER = (SPRITE_POS[0] + SHOULDER_PX[0] - O,
            SPRITE_POS[1] + SHOULDER_PX[1] - O)
ARM_LEN = 7


def _k(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


class PlayerGfx:
    """Builds and caches composed player frames."""

    def __init__(self, look=None):
        img = pygame.image.load(SPRITE_PATH)
        if pygame.display.get_surface():
            img = img.convert_alpha()
        self.sprite = img
        self.sw, self.sh = img.get_size()
        # the sprite without its front hand, used while the arm is animated
        self.no_hand = img.copy()
        for x, y in FRONT_HAND:
            self.no_hand.set_at((x, y), (0, 0, 0, 0))
        for x, y in FRONT_HAND_EDGE:
            self.no_hand.set_at((x, y), OUTLINE + (255,))
        self.cache = {}

    # ------------------------------------------------------------- parts
    def _leg_offsets(self, legs):
        """(back_dx, front_dx, front_dy, body_dy) for a pose."""
        if legs == IDLE:
            return 0, 0, 0, 0
        if legs == JUMP:
            return -1, 2, -2, 0
        k = math.sin(legs / LEG_FRAMES * math.tau)
        bob = 1 if abs(k) > 0.7 else 0
        return round(-k * 2), round(k * 2), 0, bob

    def _body(self, src, legs):
        """Sprite with the legs posed; returns a surface the sprite's size
        plus a little room for moving feet."""
        back_dx, front_dx, front_dy, bob = self._leg_offsets(legs)
        w, h = self.sw, self.sh
        out = pygame.Surface((w + 6, h + 2), pygame.SRCALPHA)
        span = h - HIP_ROW
        for y in range(HIP_ROW, h):
            t = (y - HIP_ROW + 1) / span          # 0 at the hip, 1 at the feet
            for x0, x1, dx, dy in ((0, LEG_SPLIT, back_dx, 0),
                                   (LEG_SPLIT, w, front_dx, front_dy)):
                sx = round(dx * t)
                sy = round(dy * t)
                out.blit(src, (3 + x0 + sx, y + sy), (x0, y, x1 - x0, 1))
        # upper body on top (sinks a pixel into the hips at the widest stride)
        out.blit(src, (3, bob), (0, 0, w, HIP_ROW))
        return out

    def _arm(self, angle):
        """Front arm (sleeve + hand) for an angle in degrees, art canvas."""
        s = pygame.Surface((CW, CH), pygame.SRCALPHA)
        ox = SHOULDER[0] + O
        oy = SHOULDER[1] + O
        r = math.radians(angle)
        ex = ox + math.sin(r) * ARM_LEN
        ey = oy + math.cos(r) * ARM_LEN
        hx = ox + math.sin(r) * (ARM_LEN - 2.5)
        hy = oy + math.cos(r) * (ARM_LEN - 2.5)
        pygame.draw.line(s, OUTLINE, (ox, oy), (hx, hy), 4)
        pygame.draw.line(s, SLEEVE_DARK, (ox, oy), (hx, hy), 3)
        pygame.draw.line(s, SLEEVE, (ox, oy), (hx, hy), 2)
        pygame.draw.line(s, OUTLINE, (hx, hy), (ex, ey), 4)
        pygame.draw.line(s, SKIN_DARK, (hx, hy), (ex, ey), 3)
        pygame.draw.line(s, SKIN, (hx, hy), (ex, ey), 2)
        return s

    @staticmethod
    def hand_pos(angle):
        r = math.radians(angle)
        return (SHOULDER[0] + math.sin(r) * (ARM_LEN - 1),
                SHOULDER[1] + math.cos(r) * (ARM_LEN - 1))

    # ------------------------------------------------------------ compose
    def frame(self, legs, front_angle, back_angle, walk=None,
              arm=False):
        """Composed frame (2x scale).  ``arm`` replaces the drawn front hand
        with an arm pointing at ``front_angle`` (item use, held torch)."""
        key = (legs, int(front_angle) // 6 if arm else None)
        surf = self.cache.get(key)
        if surf is None:
            s = pygame.Surface((CW, CH), pygame.SRCALPHA)
            body = self._body(self.no_hand if arm else self.sprite, legs)
            s.blit(body, (SPRITE_POS[0] - 3, SPRITE_POS[1]))
            if arm:
                s.blit(self._arm(key[1] * 6), (0, 0))
            surf = upscale(s)
            if len(self.cache) > 300:
                self.cache.clear()
            self.cache[key] = surf
        return surf

    def head_icon(self):
        if not hasattr(self, "_head_icon"):
            self._head_icon = upscale(self.sprite.subsurface(
                (0, 0, self.sw, 15)).copy())
        return self._head_icon

    def preview(self, scale=2):
        f = self.frame(IDLE, 0, 0)
        return pygame.transform.scale(
            f, (f.get_width() * scale // 2, f.get_height() * scale // 2))
