"""Terraria-style coloured tile lighting.

Works like Terraria's own light map:

* Every light source (sun, torches, lava, glowing tiles, held/dropped
  torches) writes an RGB value into its tile.
* Light then spreads tile by tile.  A ray is multiplied by the decay of each
  tile it *leaves*: 0.91 through air, 0.56 through a solid block, and a
  per-channel factor through water that soaks up red faster than blue (so
  underwater areas turn blue).  Decaying on exit means block faces touching
  light are fully lit and darkness sets in quickly behind them.
* Spreading is done with two full passes of four directional sweeps.  Each
  sweep is fully vectorised in log space:
      L'[i] = max_j L[j] * prod(d[j..i-1])
  becomes a cumulative maximum of (log L - cumsum(log d) + log d).
"""
import numpy as np

from . import tiles as T

AIR_DECAY = 0.91
SOLID_DECAY = 0.56
WATER_DECAY = np.array([0.88, 0.96, 1.015], np.float32) * 0.91
LAVA_LIGHT = np.array([0.69, 0.41, 0.12], np.float32)
HELL_AMBIENT = np.array([0.34, 0.16, 0.10], np.float32)
TORCH_LIGHT = T.EMIT[T.TORCH]
FLOOR = 1e-3
CUTOFF = 0.01

_LOG_AIR = np.log(AIR_DECAY)
_LOG_SOLID = np.log(SOLID_DECAY)
_LOG_WATER = np.log(WATER_DECAY)


def _sweep(lg, ld, axis, reverse):
    if reverse:
        lg = np.flip(lg, axis)
        ld = np.flip(ld, axis)
    s = np.cumsum(ld, axis=axis)
    res = np.maximum.accumulate(lg - s + ld, axis=axis) + s - ld
    if reverse:
        res = np.flip(res, axis)
    return res


def compute(world, x0, y0, w, h, sun, dynamic=()):
    """Light for tiles [x0, x0+w) x [y0, y0+h). Returns float32 (w, h, 3).

    ``dynamic`` is an iterable of (pixel_x, pixel_y, rgb) extra sources such
    as a torch held by the player or torches lying on the ground.
    """
    out = np.zeros((w, h, 3), np.float32)
    xa, xb = max(0, x0), min(world.w, x0 + w)
    ya, yb = max(0, y0), min(world.h, y0 + h)
    if xa >= xb or yb <= max(ya, 0):
        if y0 < 0:
            out[:, :] = sun
        return out
    tiles = world.tiles[xa:xb, ya:yb]
    liq = world.liquid[xa:xb, ya:yb]
    ltype = world.ltype[xa:xb, ya:yb]
    blocks = T.BLOCKS_LIGHT[tiles]
    ld = np.empty(tiles.shape + (3,), np.float32)
    ld[:] = np.where(blocks, _LOG_SOLID, _LOG_AIR)[..., None]
    water = (liq > 100) & (ltype == 0) & ~blocks
    if water.any():
        ld[water] = _LOG_WATER
    # ---- sources
    src = T.EMIT[tiles].copy()
    lava = (liq > 0) & (ltype == 1)
    if lava.any():
        amt = (liq[lava].astype(np.float32) / 255.0)[:, None]
        src[lava] = np.maximum(src[lava], LAVA_LIGHT * (0.6 + 0.4 * amt))
    ys = np.arange(ya, yb)[None, :]
    if yb > world.underworld_y:
        hell = (ys >= world.underworld_y) & ~blocks
        if hell.any():
            src[hell] = np.maximum(src[hell], HELL_AMBIENT)
    sky = (ys < world.sky_top[xa:xb, None]) & (ys < world.underground_y)
    if sky.any():
        src[sky] = np.maximum(src[sky], sun)
    for px, py, rgb in dynamic:
        tx, ty = int(px // 16) - xa, int(py // 16) - ya
        if 0 <= tx < xb - xa and 0 <= ty < yb - ya:
            src[tx, ty] = np.maximum(src[tx, ty], rgb)
    # ---- spread: two full passes of the four directions
    lg = np.log(np.maximum(src, FLOOR))
    for _ in range(2):
        for axis, rev in ((0, False), (0, True), (1, False), (1, True)):
            lg = _sweep(lg, ld, axis, rev)
    light = np.exp(lg)
    light[light < CUTOFF] = 0
    out[xa - x0:xb - x0, ya - y0:yb - y0] = light
    if y0 < 0:
        out[:, :ya - y0] = sun
    return out
