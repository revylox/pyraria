"""Terraria-style coloured tile lighting.

Light sources (sun, torches, lava, glowing tiles) are propagated with
multiplicative decay per tile.  Each directional sweep is fully vectorised
by working in log space:  L'[i] = max_j (L[j] * prod(d[j+1..i]))  becomes a
cumulative maximum of (log L - cumsum(log d)).
"""
import numpy as np

from . import tiles as T

AIR_DECAY = 0.9
SOLID_DECAY = 0.70
WATER_DECAY = 0.83
LAVA_LIGHT = np.array([1.0, 0.52, 0.18], np.float32)
FLOOR = 1e-3
HELL_AMBIENT = np.array([0.42, 0.2, 0.13], np.float32)


def _sweep(lg, ld, axis, reverse):
    if reverse:
        lg = np.flip(lg, axis)
        ld = np.flip(ld, axis)
    s = np.cumsum(ld, axis=axis)
    res = np.maximum.accumulate(lg - s, axis=axis) + s
    if reverse:
        res = np.flip(res, axis)
    return res


def compute(world, x0, y0, w, h, sun):
    """Light for tiles [x0, x0+w) x [y0, y0+h). Returns float32 (w, h, 3)."""
    out = np.zeros((w, h, 3), np.float32)
    xa, xb = max(0, x0), min(world.w, x0 + w)
    ya, yb = max(0, y0), min(world.h, y0 + h)
    if xa >= xb or yb <= max(ya, 0):
        if y0 < 0:
            out[:, :] = sun
        return out
    tiles = world.tiles[xa:xb, ya:yb]
    liq = world.liquid[xa:xb, ya:yb]
    solid = T.SOLID[tiles]
    decay = np.where(solid, SOLID_DECAY, AIR_DECAY).astype(np.float32)
    wet = (liq > 100) & ~solid
    decay[wet] = WATER_DECAY
    src = T.EMIT[tiles].copy()
    lava = (liq > 0) & (world.ltype[xa:xb, ya:yb] == 1)
    if lava.any():
        amt = (liq[lava].astype(np.float32) / 255.0)[:, None]
        src[lava] = np.maximum(src[lava], LAVA_LIGHT * (0.55 + 0.45 * amt))
    ys = np.arange(ya, yb)[None, :]
    if yb > world.underworld_y:
        hell = (ys >= world.underworld_y) & ~solid
        if hell.any():
            src[hell] = np.maximum(src[hell], HELL_AMBIENT)
    sky = (ys < world.sky_top[xa:xb, None]) & (ys < world.underground_y)
    if sky.any():
        src[sky] = np.maximum(src[sky], sun)
    lg = np.log(np.maximum(src, FLOOR))
    ld = np.log(decay)[..., None]
    for axis, rev in ((0, False), (0, True), (1, False), (1, True),
                      (0, False), (0, True)):
        lg = _sweep(lg, ld, axis, rev)
    light = np.exp(lg)
    light[light < 0.012] = 0
    out[xa - x0:xb - x0, ya - y0:yb - y0] = light
    if y0 < 0:
        out[:, :ya - y0] = sun
    return out
