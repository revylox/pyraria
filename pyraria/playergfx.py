"""Procedural player sprites in the Terraria style, with selectable skins.

The character is drawn at 20x28 art pixels (doubled on screen like
Terraria), with multi-tone shading and a dark silhouette outline.  A look is
either "Custom" (colours picked in the character creator) or one of the
preset skins in SKINS, which add outfits, hats, beards, ears and tails.
"""
import math

import numpy as np
import pygame

from .textures import upscale

HAIR_STYLES = 6
LEG_FRAMES = 8          # walk cycle
IDLE, JUMP = LEG_FRAMES, LEG_FRAMES + 1
O = 8                   # canvas margin in art pixels (room for hats, arms)
CW, CH = 20 + 2 * O, 28 + 2 * O

PALETTES = {
    "hair": [(215, 90, 55), (110, 70, 40), (40, 34, 30), (235, 205, 115),
             (205, 205, 210), (220, 90, 170), (70, 120, 210), (80, 175, 80)],
    "skin": [(250, 200, 160), (235, 175, 135), (200, 140, 100),
             (155, 100, 68), (105, 68, 46), (255, 222, 196)],
    "eyes": [(105, 90, 75), (60, 120, 200), (70, 150, 80), (130, 80, 50),
             (120, 60, 160), (50, 50, 50)],
    "shirt": [(175, 165, 140), (200, 60, 60), (60, 120, 200), (70, 160, 80),
              (220, 180, 60), (140, 80, 180), (230, 230, 230), (60, 60, 70)],
    "undershirt": [(160, 180, 215), (230, 230, 230), (200, 160, 120),
                   (90, 90, 100), (180, 80, 80), (100, 160, 110)],
    "pants": [(255, 230, 175), (80, 90, 140), (90, 70, 50), (60, 60, 70),
              (140, 50, 50), (70, 120, 70)],
    "shoes": [(160, 105, 60), (60, 50, 45), (120, 120, 130), (150, 60, 50),
              (230, 230, 230)],
}
STYLE_NAMES = ["messy", "short", "long", "ponytail", "spiky", "bob"]
DEFAULT_LOOK = {"skin_preset": "Custom", "hair": 0, "skin": 0, "eyes": 0,
                "shirt": 0, "undershirt": 0, "pants": 0, "shoes": 0,
                "hair_style": 0}

# ---------------------------------------------------------------------------
# Preset skins (inspired by the classic Terraria town folk)
# ---------------------------------------------------------------------------
_S = dict
SKINS = {
    "Guide": _S(skin=(240, 188, 148), hair=(116, 74, 42), style="messy",
                eyes=(90, 64, 40), shirt=(176, 140, 96),
                undershirt=(222, 210, 178), pants=(72, 94, 150),
                shoes=(96, 62, 40), outfit="shirt"),
    "Nurse": _S(skin=(252, 208, 176), hair=(248, 218, 120), style="pigtails",
                eyes=(70, 130, 210), shirt=(244, 244, 250),
                undershirt=(236, 120, 150), pants=(244, 244, 250),
                shoes=(244, 244, 250), outfit="dress", hat="nurse_cap"),
    "Merchant": _S(skin=(238, 186, 152), hair=(226, 226, 232), style="bald",
                   eyes=(60, 60, 70), beard="long",
                   beard_color=(226, 226, 232), shirt=(228, 220, 196),
                   undershirt=(228, 220, 196), coat=(124, 82, 50),
                   pants=(110, 80, 56), shoes=(70, 50, 36), outfit="coat"),
    "Arms Dealer": _S(skin=(122, 82, 56), hair=(34, 32, 36), style="short",
                      eyes=(40, 30, 30), shirt=(88, 94, 78),
                      undershirt=(60, 60, 64), vest=(58, 66, 52),
                      pants=(52, 52, 58), shoes=(36, 36, 40), outfit="vest",
                      hat="bandana", hat_color=(232, 232, 236)),
    "Dryad": _S(skin=(232, 196, 160), hair=(96, 206, 96), style="long",
                eyes=(60, 150, 70), shirt=(70, 162, 62),
                undershirt=(124, 212, 92), pants=(64, 146, 54),
                shoes=(60, 132, 52), outfit="dress", hat="leaf_crown",
                hat_color=(62, 176, 62)),
    "Stylist": _S(skin=(252, 206, 176), hair=(236, 92, 172), style="long",
                  eyes=(120, 60, 160), shirt=(232, 112, 192),
                  undershirt=(252, 204, 232), pants=(150, 62, 150),
                  shoes=(122, 40, 112), outfit="dress"),
    "Goblin Tinkerer": _S(skin=(112, 142, 164), ears="goblin",
                          hair=(44, 44, 54), style="short", eyes=(224, 64, 60),
                          shirt=(240, 240, 244), undershirt=(240, 240, 244),
                          coat=(48, 48, 64), pants=(42, 42, 52),
                          shoes=(32, 32, 38), outfit="coat",
                          tie=(204, 40, 40)),
    "Mechanic": _S(skin=(252, 202, 166), hair=(232, 92, 42), style="ponytail",
                   eyes=(70, 130, 70), shirt=(242, 222, 132),
                   undershirt=(250, 240, 200), pants=(204, 62, 52),
                   shoes=(112, 62, 42), outfit="overalls"),
    "Golfer": _S(skin=(244, 194, 156), hair=(150, 96, 52), style="short",
                 eyes=(80, 70, 60), shirt=(244, 244, 248),
                 undershirt=(214, 52, 52), pants=(206, 186, 140),
                 shoes=(244, 244, 248), outfit="shirt", hat="cap",
                 hat_color=(214, 48, 48)),
    "Painter": _S(skin=(120, 84, 62), hair=(30, 28, 32), style="short",
                  eyes=(40, 30, 30), shirt=(60, 74, 60),
                  undershirt=(236, 236, 236), pants=(48, 52, 46),
                  shoes=(30, 30, 30), outfit="apron", apron=(236, 236, 236),
                  hat="cap", hat_color=(236, 236, 240)),
    "Truffle": _S(skin=(206, 212, 228), hair=None, style="bald",
                  eyes=(40, 60, 140), shirt=(204, 210, 226),
                  undershirt=(204, 210, 226), robe=(196, 202, 218),
                  pants=(196, 202, 218), shoes=(170, 176, 196),
                  outfit="robe", hat="mushroom", hat_color=(72, 112, 244)),
    "Arcanist": _S(skin=(240, 196, 160), hair=(40, 40, 120), style="long",
                   eyes=(250, 220, 90), shirt=(84, 64, 176),
                   undershirt=(232, 190, 64), armor=(84, 64, 176),
                   trim=(234, 192, 62), pants=(64, 48, 140),
                   shoes=(234, 192, 62), outfit="armor"),
    "Zoologist": _S(skin=(150, 90, 62), hair=(222, 104, 50), style="long",
                    eyes=(60, 140, 90), ears="fox", tail=True,
                    shirt=(62, 132, 144), undershirt=(232, 222, 196),
                    pants=(64, 92, 124), shoes=(80, 56, 40), outfit="shirt"),
    "Clothier": _S(skin=(236, 190, 156), hair=(220, 220, 226), style="short",
                   eyes=(60, 60, 70), beard="long",
                   beard_color=(220, 220, 226), shirt=(186, 36, 40),
                   undershirt=(220, 200, 160), robe=(176, 32, 36),
                   pants=(120, 24, 28), shoes=(70, 30, 30), outfit="robe",
                   hat="wide_hat", hat_color=(196, 40, 44)),
    "Tax Collector": _S(skin=(226, 196, 172), hair=(196, 196, 204),
                        style="long", eyes=(50, 50, 60), shirt=(70, 66, 74),
                        undershirt=(236, 236, 236), coat=(44, 40, 48),
                        pants=(40, 38, 44), shoes=(26, 26, 30), outfit="coat",
                        hat="top_hat", hat_color=(34, 32, 38)),
    "Demolitionist": _S(skin=(240, 182, 140), hair=(214, 104, 44),
                        style="bald", eyes=(60, 50, 40), beard="long",
                        beard_color=(214, 104, 44), shirt=(160, 112, 66),
                        undershirt=(206, 166, 110), pants=(110, 80, 52),
                        shoes=(70, 50, 34), outfit="vest",
                        vest=(120, 84, 50), hat="mining_helmet",
                        hat_color=(234, 196, 54)),
    "Tavernkeep": _S(skin=(236, 184, 146), hair=(120, 80, 50), style="bald",
                     eyes=(60, 50, 40), beard="short",
                     beard_color=(120, 80, 50), shirt=(96, 118, 170),
                     undershirt=(96, 118, 170), apron=(236, 232, 220),
                     pants=(74, 70, 70), shoes=(60, 44, 32),
                     outfit="apron"),
    "Party Girl": _S(skin=(252, 208, 178), hair=(250, 120, 200), style="long",
                     eyes=(80, 140, 220), shirt=(160, 92, 220),
                     undershirt=(250, 210, 240), pants=(120, 70, 190),
                     shoes=(250, 120, 200), outfit="dress", hat="bow",
                     hat_color=(80, 200, 240)),
    "Steampunker": _S(skin=(244, 200, 166), hair=(90, 60, 40), style="long",
                      eyes=(70, 110, 160), shirt=(150, 106, 66),
                      undershirt=(230, 214, 184), coat=(112, 76, 46),
                      pants=(76, 58, 44), shoes=(54, 40, 30), outfit="coat",
                      hat="goggles", hat_color=(190, 150, 70)),
    "Witch Doctor": _S(skin=(122, 92, 66), hair=None, style="bald",
                       eyes=(250, 230, 120), shirt=(122, 92, 66),
                       undershirt=(122, 92, 66), pants=(70, 136, 60),
                       shoes=(122, 92, 66), outfit="dress", hat="mask",
                       hat_color=(84, 150, 70)),
    "Wizard": _S(skin=(238, 190, 156), hair=(236, 236, 240), style="short",
                 eyes=(60, 80, 160), beard="long",
                 beard_color=(236, 236, 240), shirt=(108, 70, 180),
                 undershirt=(220, 210, 240), robe=(108, 70, 180),
                 pants=(84, 52, 150), shoes=(70, 44, 120), outfit="robe",
                 hat="wizard_hat", hat_color=(108, 70, 180)),
    "Cyborg": _S(skin=(170, 190, 200), hair=None, style="bald",
                 eyes=(90, 250, 230), shirt=(60, 150, 150),
                 undershirt=(40, 70, 80), armor=(60, 150, 150),
                 trim=(40, 70, 80), pants=(50, 120, 124), shoes=(40, 70, 80),
                 outfit="armor", hat="visor", hat_color=(60, 150, 150)),
    "Angler": _S(skin=(246, 200, 164), hair=(160, 100, 52), style="messy",
                 eyes=(70, 120, 180), shirt=(160, 160, 150),
                 undershirt=(220, 214, 196), vest=(110, 116, 100),
                 pants=(92, 98, 108), shoes=(80, 62, 44), outfit="vest",
                 hat="bucket_hat", hat_color=(150, 150, 140)),
}
SKIN_NAMES = ["Custom"] + list(SKINS)

SHOULDER = (10, 14)     # art coords (facing right)
ARM_LEN = 7


def _k(c, k):
    return tuple(max(0, min(255, int(v * k))) for v in c[:3])


def look_colors(look):
    return {k: PALETTES[k][look.get(k, 0) % len(PALETTES[k])]
            for k in PALETTES}


def resolve(look):
    """Turn a saved look (custom or preset) into a full drawing spec."""
    look = dict(DEFAULT_LOOK, **(look or {}))
    preset = SKINS.get(look.get("skin_preset"))
    if preset:
        spec = dict(preset)
    else:
        c = look_colors(look)
        spec = dict(skin=c["skin"], hair=c["hair"], eyes=c["eyes"],
                    shirt=c["shirt"], undershirt=c["undershirt"],
                    pants=c["pants"], shoes=c["shoes"], outfit="shirt",
                    style=STYLE_NAMES[look.get("hair_style", 0) %
                                      HAIR_STYLES])
    return spec


class _Art:
    """Small helper to draw on an art-resolution canvas in body coords."""

    def __init__(self):
        self.s = pygame.Surface((CW, CH), pygame.SRCALPHA)

    def rect(self, x, y, w, h, col):
        if w > 0 and h > 0:
            self.s.fill(col, (x + O, y + O, w, h))

    def px(self, x, y, col):
        self.s.fill(col, (x + O, y + O, 1, 1))

    def shaded(self, x, y, w, h, col, light=1.14, dark=0.78, bottom=0.86):
        self.rect(x, y, w, h, col)
        if h > 2:
            self.rect(x, y + h - 1, w, 1, _k(col, bottom))
        if w > 1:
            self.rect(x, y, 1, h, _k(col, light))
            self.rect(x + w - 1, y, 1, h, _k(col, dark))

    def poly(self, pts, col):
        pygame.draw.polygon(self.s, col, [(x + O, y + O) for x, y in pts])

    def line(self, a, b, col, w=1):
        pygame.draw.line(self.s, col, (a[0] + O, a[1] + O),
                         (b[0] + O, b[1] + O), w)


def _outline(surf, k=0.42):
    """Darken opaque pixels that touch transparency (Terraria-style rim)."""
    a = pygame.surfarray.pixels_alpha(surf)
    opaque = a > 0
    edge = np.zeros_like(opaque)
    edge[1:, :] |= ~opaque[:-1, :]
    edge[:-1, :] |= ~opaque[1:, :]
    edge[:, 1:] |= ~opaque[:, :-1]
    edge[:, :-1] |= ~opaque[:, 1:]
    edge &= opaque
    del a
    rgb = pygame.surfarray.pixels3d(surf)
    rgb[edge] = (rgb[edge] * k).astype(np.uint8)
    del rgb


class PlayerGfx:
    """Builds and caches composed player frames for one look."""

    W, H = 20, 28

    def __init__(self, look):
        self.look = dict(DEFAULT_LOOK, **(look or {}))
        self.spec = resolve(self.look)
        self.cache = {}
        sp = self.spec
        self.robe = sp.get("outfit") == "robe"
        self.skirt = sp.get("outfit") == "dress"
        self.back_layer = self._back_layer()
        self.body = self._body()
        self.head = self._head()
        self.legs = [self._legs(i) for i in range(LEG_FRAMES)] + \
            [self._legs(None), self._legs("jump")]

    # ------------------------------------------------------------ colours
    def sleeve_color(self):
        sp = self.spec
        o = sp.get("outfit")
        if o == "coat":
            return sp["coat"]
        if o == "robe":
            return sp["robe"]
        if o == "armor":
            return sp["armor"]
        return sp["shirt"]

    # -------------------------------------------------------------- parts
    def _back_layer(self):
        """Things behind the body: fox tail, coat tails, long hair."""
        sp = self.spec
        a = _Art()
        if sp.get("tail"):
            col = sp["hair"]
            a.poly([(7, 18), (2, 20), (0, 24), (2, 25), (6, 23), (8, 20)], col)
            a.poly([(0, 24), (2, 25), (3, 23), (1, 22)], (244, 240, 230))
            a.line((6, 19), (2, 21), _k(col, 1.2))
        if sp.get("outfit") == "coat":
            col = _k(sp["coat"], 0.8)
            a.poly([(7, 19), (5, 25), (9, 25), (10, 20)], col)
        style = sp.get("style")
        if sp.get("hair") and style in ("long", "pigtails"):
            col = _k(sp["hair"], 0.82)
            a.rect(5, 6, 4, 11 if style == "long" else 9, col)
        return a.s

    def _legs(self, frame):
        sp = self.spec
        a = _Art()
        pants, shoes = sp["pants"], sp["shoes"]
        if frame is None:
            offs = (0, 0)
        elif frame == "jump":
            offs = (3, -3)
        else:
            k = math.sin(frame / LEG_FRAMES * math.tau)
            offs = (round(k * 3), round(-k * 3))
        top = 21
        if self.skirt:
            top = 24
            pants = sp["skin"] if sp.get("outfit") == "dress" and \
                sp.get("hat") not in ("mask",) else pants
        if self.robe:
            top = 26
        for i, off in enumerate((offs[1], offs[0])):
            col = _k(pants, 0.78) if i == 0 else pants
            hip_x = 8 if i == 0 else 10
            foot_x = hip_x + (off if not self.robe else off // 2)
            for y in range(top, 26):
                t = (y - 21) / 5
                x = round(hip_x + (foot_x - hip_x) * t)
                a.rect(x, y, 3, 1, col)
                a.px(x, y, _k(col, 1.12))
                a.px(x + 2, y, _k(col, 0.78))
            sc = _k(shoes, 0.8) if i == 0 else shoes
            a.rect(foot_x, 25, 3, 2, sc)
            a.rect(foot_x + 1, 26, 3, 1, sc)
            a.px(foot_x, 25, _k(sc, 1.2))
            a.rect(foot_x, 27, 4, 1, _k(sc, 0.55))
        return a.s

    def _body(self):
        sp = self.spec
        a = _Art()
        o = sp.get("outfit", "shirt")
        shirt, under = sp["shirt"], sp["undershirt"]
        pants = sp["pants"]
        body_col = sp.get("armor", shirt) if o == "armor" else shirt
        a.shaded(7, 13, 7, 8, body_col)
        # collar / undershirt V at the front (facing right)
        if o != "armor":
            a.rect(10, 13, 3, 1, under)
            a.rect(11, 14, 2, 2, under)
            a.px(11, 16, under)
        if o in ("shirt", "vest", "coat", "apron", "overalls"):
            a.rect(7, 20, 7, 1, _k(pants, 0.55))          # belt
            a.px(12, 20, (214, 180, 70))
        if o == "vest":
            v = sp["vest"]
            a.shaded(7, 13, 3, 7, v)
            a.rect(12, 14, 2, 6, v)
            a.px(13, 14, _k(v, 0.78))
        elif o == "coat":
            c = sp["coat"]
            a.shaded(7, 13, 4, 8, c)
            a.rect(13, 13, 1, 8, _k(c, 0.75))
            a.rect(11, 13, 1, 1, _k(c, 1.2))
            if sp.get("tie"):
                a.rect(11, 14, 1, 5, sp["tie"])
                a.px(12, 15, _k(sp["tie"], 0.75))
        elif o == "apron":
            ap = sp["apron"]
            a.shaded(9, 15, 5, 9, ap, light=1.04, dark=0.86)
            a.line((9, 15), (8, 13), _k(ap, 0.9))
            a.rect(9, 18, 5, 1, _k(ap, 0.88))
        elif o == "overalls":
            a.shaded(9, 15, 4, 6, pants)
            a.rect(9, 13, 1, 2, pants)
            a.rect(12, 13, 1, 2, pants)
            a.px(10, 15, (230, 210, 120))
            a.px(11, 15, (230, 210, 120))
        elif o == "dress":
            sk = sp["pants"]
            pts = [(7, 19), (14, 19), (16, 25), (5, 25)]
            a.poly(pts, sk)
            a.line((7, 19), (5, 25), _k(sk, 1.15))
            a.line((14, 19), (16, 25), _k(sk, 0.75))
            a.rect(5, 24, 12, 1, _k(sk, 0.75))
            a.rect(8, 21, 1, 3, _k(sk, 0.85))
            a.rect(12, 21, 1, 3, _k(sk, 0.85))
            a.rect(7, 19, 7, 1, _k(under, 1.0))
        elif o == "robe":
            r = sp["robe"]
            a.poly([(7, 13), (14, 13), (16, 26), (5, 26)], r)
            a.line((7, 13), (5, 26), _k(r, 1.18))
            a.line((14, 13), (16, 26), _k(r, 0.72))
            a.rect(5, 25, 12, 1, _k(r, 0.7))
            a.rect(11, 13, 1, 12, _k(r, 0.82))
            a.rect(10, 13, 2, 2, under)
            a.rect(7, 19, 9, 1, _k(r, 0.65))
            a.px(11, 19, (214, 180, 70))
        elif o == "armor":
            ar, trim = sp["armor"], sp["trim"]
            a.rect(7, 16, 7, 1, trim)
            a.rect(7, 13, 7, 1, _k(ar, 1.25))
            a.rect(10, 17, 1, 3, _k(ar, 0.75))
            a.rect(7, 20, 7, 1, trim)
            a.px(12, 18, _k(trim, 1.2))
        return a.s

    def _head(self):
        sp = self.spec
        a = _Art()
        skin = sp["skin"]
        hair = sp.get("hair")
        style = sp.get("style", "short")
        hat = sp.get("hat")
        # neck
        a.rect(9, 12, 3, 1, _k(skin, 0.8))
        # face: lit from the top-left, jaw shadow
        a.rect(7, 4, 8, 8, skin)
        a.rect(7, 4, 1, 8, _k(skin, 1.06))
        a.rect(14, 5, 1, 6, _k(skin, 0.9))
        a.rect(8, 11, 7, 1, _k(skin, 0.84))
        a.px(14, 4, _k(skin, 0.9))
        a.px(7, 11, _k(skin, 0.84))
        # ear
        a.rect(8, 7, 2, 3, _k(skin, 0.88))
        a.px(9, 8, _k(skin, 0.7))
        # eye (white + iris), brow, nose, mouth
        if hat not in ("visor", "mask"):
            a.rect(11, 7, 2, 2, (250, 250, 250))
            a.rect(12, 7, 1, 2, sp.get("eyes", (70, 60, 50)))
            a.px(12, 8, _k(sp.get("eyes", (70, 60, 50)), 0.6))
            brow = _k(hair, 0.7) if hair else _k(skin, 0.6)
            a.rect(11, 6, 2, 1, brow)
            a.px(14, 8, _k(skin, 0.8))
            a.rect(12, 10, 2, 1, _k(skin, 0.62))
        # beard
        beard = sp.get("beard")
        if beard:
            bc = sp.get("beard_color", hair or (200, 200, 200))
            if beard == "long":
                a.poly([(9, 9), (15, 9), (15, 13), (13, 17), (11, 16),
                        (9, 12)], bc)
                a.line((9, 10), (11, 15), _k(bc, 0.8))
                a.rect(12, 9, 3, 1, _k(bc, 1.1))
                a.rect(12, 10, 2, 1, _k(bc, 0.7))     # mouth line
            else:
                a.rect(10, 9, 5, 4, bc)
                a.rect(10, 12, 5, 1, _k(bc, 0.78))
                a.rect(12, 10, 2, 1, _k(bc, 0.6))
        # hair
        if hair and hat not in ("mushroom", "visor"):
            self._hair(a, hair, style)
        # ears that stick out of the hair
        ears = sp.get("ears")
        if ears == "goblin":
            a.poly([(9, 6), (2, 4), (4, 7), (9, 9)], skin)
            a.line((8, 7), (4, 6), _k(skin, 0.7))
        elif ears == "fox":
            for x0 in (7, 11):
                a.poly([(x0, 3), (x0 + 1, -1), (x0 + 3, 3)], hair)
                a.px(x0 + 1, 1, (250, 190, 190))
        if hat:
            self._hat(a, hat, sp.get("hat_color", (200, 200, 200)), sp)
        return a.s

    def _hair(self, a, hair, style):
        hd, hl = _k(hair, 0.68), _k(hair, 1.25)
        if style == "bald":
            a.rect(7, 5, 2, 3, hair)
            a.px(7, 7, hd)
            return
        a.rect(6, 2, 10, 3, hair)
        a.rect(7, 1, 8, 1, hair)
        a.rect(6, 4, 3, 5, hair)          # back of the head
        a.rect(13, 4, 2, 2, hair)         # fringe at the front
        a.px(14, 6, hair)
        a.rect(8, 2, 5, 1, hl)
        a.px(7, 3, hl)
        a.rect(6, 7, 2, 2, hd)
        a.px(12, 4, hd)
        if style == "messy":
            for x in (7, 10, 13):
                a.px(x, 0, hair)
            a.px(15, 3, hair)
            a.px(5, 5, hd)
        elif style == "long":
            a.rect(5, 4, 3, 12, hair)
            a.rect(5, 4, 1, 12, hd)
            a.rect(6, 15, 2, 1, hd)
            a.px(7, 6, hl)
        elif style == "ponytail":
            a.rect(3, 4, 3, 2, hd)
            a.rect(2, 5, 3, 8, hair)
            a.rect(2, 5, 1, 8, hd)
            a.px(3, 6, hl)
        elif style == "pigtails":
            for (x, y) in ((3, 6), (14, 6)):
                if x > 10:
                    continue
                a.rect(x, y, 3, 7, hair)
                a.rect(x, y + 6, 3, 1, hd)
                a.px(x + 1, y + 1, hl)
            a.rect(5, 5, 2, 2, (236, 120, 150))
        elif style == "spiky":
            for x in (6, 9, 12):
                a.poly([(x, 2), (x + 1, -2), (x + 3, 2)], hair)
            a.px(10, -1, hl)
        elif style == "bob":
            a.rect(5, 4, 3, 8, hair)
            a.rect(5, 11, 3, 1, hd)
            a.rect(8, 4, 6, 1, hair)
        elif style == "short":
            a.rect(6, 4, 2, 3, hair)

    def _hat(self, a, hat, col, sp):
        dark, light = _k(col, 0.7), _k(col, 1.2)
        if hat == "nurse_cap":
            a.rect(8, 0, 6, 3, (248, 248, 252))
            a.rect(8, 2, 6, 1, (210, 210, 220))
            a.rect(10, 0, 2, 2, (220, 40, 50))
        elif hat == "cap":
            a.rect(6, 1, 9, 3, col)
            a.rect(7, 0, 7, 1, col)
            a.rect(13, 3, 4, 1, dark)
            a.rect(7, 1, 4, 1, light)
            a.px(10, 0, light)
        elif hat == "bucket_hat":
            a.rect(5, 3, 11, 2, dark)
            a.rect(7, 0, 7, 3, col)
            a.rect(7, 0, 7, 1, light)
        elif hat == "top_hat":
            a.rect(5, 3, 11, 1, col)
            a.rect(7, -5, 7, 8, col)
            a.rect(7, -5, 1, 8, light)
            a.rect(7, 1, 7, 1, (140, 40, 50))
            a.rect(5, 3, 11, 1, _k(col, 0.6))
        elif hat == "wide_hat":
            a.rect(3, 3, 15, 1, dark)
            a.rect(4, 2, 13, 1, col)
            a.rect(7, -2, 7, 4, col)
            a.rect(7, -2, 2, 4, light)
            a.rect(7, 1, 7, 1, (240, 220, 120))
        elif hat == "wizard_hat":
            a.rect(4, 3, 13, 1, dark)
            a.poly([(6, 3), (14, 3), (9, -4), (5, -7), (7, -2)], col)
            a.line((6, 3), (7, -2), light)
            a.px(10, 0, (250, 230, 90))
            a.px(8, -3, (250, 230, 90))
            a.px(12, 2, (250, 230, 90))
        elif hat == "mining_helmet":
            a.rect(6, 0, 10, 4, col)
            a.rect(7, -1, 8, 1, col)
            a.rect(5, 3, 12, 1, dark)
            a.rect(7, 0, 3, 1, light)
            a.rect(14, 0, 2, 3, (250, 250, 210))
            a.px(15, 1, (255, 255, 255))
        elif hat == "goggles":
            a.rect(6, 3, 10, 1, (90, 60, 40))
            for x in (10, 13):
                a.rect(x, 2, 3, 3, col)
                a.px(x + 1, 3, (110, 220, 220))
        elif hat == "bandana":
            a.rect(6, 3, 10, 2, col)
            a.rect(6, 3, 10, 1, _k(col, 1.05))
            a.rect(4, 4, 3, 1, col)
            a.px(3, 5, dark)
        elif hat == "bow":
            a.poly([(3, 1), (6, 3), (3, 5)], col)
            a.poly([(9, 1), (6, 3), (9, 5)], col)
            a.rect(5, 2, 2, 2, dark)
        elif hat == "leaf_crown":
            for x in (6, 9, 12):
                a.poly([(x, 2), (x + 1, -1), (x + 3, 1), (x + 2, 2)], col)
                a.px(x + 1, 0, light)
        elif hat == "mushroom":
            a.poly([(2, 5), (4, 0), (8, -3), (13, -3), (17, 0), (19, 5)], col)
            a.rect(2, 5, 18, 1, dark)
            a.rect(4, 6, 14, 1, _k(col, 0.5))
            for (x, y) in ((5, 1), (9, -2), (14, 0), (11, 3)):
                a.rect(x, y, 2, 2, (180, 210, 255))
        elif hat == "mask":
            a.rect(8, 3, 8, 10, col)
            a.rect(8, 3, 1, 10, light)
            a.rect(11, 6, 2, 2, (20, 20, 20))
            a.px(12, 6, sp.get("eyes", (250, 230, 120)))
            a.rect(10, 10, 5, 1, (240, 240, 220))
            a.rect(10, 11, 5, 1, dark)
            for x, c in ((8, (220, 50, 50)), (10, (250, 210, 60)),
                         (12, (60, 170, 220)), (14, (220, 50, 50))):
                a.line((x, 3), (x - 1, -3), c, 1)
        elif hat == "visor":
            a.rect(6, 2, 10, 11, col)
            a.rect(6, 2, 10, 1, light)
            a.rect(6, 2, 1, 11, light)
            a.rect(10, 7, 6, 2, (40, 60, 70))
            a.rect(11, 7, 4, 1, sp.get("eyes", (90, 250, 230)))
            a.rect(6, 12, 10, 1, dark)

    def _arm(self, angle, back=False):
        """Arm surface for an angle in degrees (0 = down, 90 = forward)."""
        sp = self.spec
        a = _Art()
        ox, oy = SHOULDER
        r = math.radians(angle)
        ex = ox + math.sin(r) * ARM_LEN
        ey = oy + math.cos(r) * ARM_LEN
        hx = ox + math.sin(r) * (ARM_LEN - 2.5)
        hy = oy + math.cos(r) * (ARM_LEN - 2.5)
        sleeve = self.sleeve_color()
        skin = sp["skin"]
        if sp.get("outfit") == "dress" and sp.get("hat") != "mask":
            hx = ox + math.sin(r) * 2.5
            hy = oy + math.cos(r) * 2.5
        if back:
            sleeve, skin = _k(sleeve, 0.72), _k(skin, 0.78)
        a.line((ox, oy), (hx, hy), _k(sleeve, 0.55), 3)
        a.line((ox, oy), (hx, hy), sleeve, 2)
        a.line((hx, hy), (ex, ey), _k(skin, 0.6), 3)
        a.line((hx, hy), (ex, ey), skin, 2)
        return a.s

    @staticmethod
    def hand_pos(angle):
        r = math.radians(angle)
        return (SHOULDER[0] + math.sin(r) * (ARM_LEN - 1),
                SHOULDER[1] + math.cos(r) * (ARM_LEN - 1))

    # ------------------------------------------------------------ compose
    def frame(self, legs, front_angle, back_angle, walk=None):
        key = (legs, int(front_angle) // 6, int(back_angle) // 6)
        surf = self.cache.get(key)
        if surf is None:
            s = pygame.Surface((CW, CH), pygame.SRCALPHA)
            s.blit(self._arm(key[2] * 6, back=True), (0, 0))
            s.blit(self.back_layer, (0, 0))
            s.blit(self.legs[legs], (0, 0))
            s.blit(self.body, (0, 0))
            s.blit(self.head, (0, 0))
            s.blit(self._arm(key[1] * 6), (0, 0))
            _outline(s)
            surf = upscale(s)
            if len(self.cache) > 600:
                self.cache.clear()
            self.cache[key] = surf
        return surf

    def head_icon(self):
        if not hasattr(self, "_head_icon"):
            s = pygame.Surface((CW, CH), pygame.SRCALPHA)
            s.blit(self.back_layer, (0, 0))
            s.blit(self.head, (0, 0))
            _outline(s)
            sub = s.subsurface((O + 1, O - 2, 18, 18)).copy()
            self._head_icon = upscale(sub)
        return self._head_icon

    def preview(self, scale=2):
        f = self.frame(IDLE, 10, 4)
        return pygame.transform.scale(
            f, (f.get_width() * scale // 2, f.get_height() * scale // 2))
