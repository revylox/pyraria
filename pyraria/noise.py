"""Fast vectorised value-noise helpers (numpy only)."""
import numpy as np


def _smooth(t):
    return t * t * (3.0 - 2.0 * t)


def value_noise_1d(n, scale, rng):
    g = rng.random(int(n / scale) + 3).astype(np.float32) * 2 - 1
    xs = np.arange(n, dtype=np.float32) / scale
    i = xs.astype(np.int32)
    f = _smooth(xs - i)
    return g[i] * (1 - f) + g[i + 1] * f


def fractal_1d(n, scale, octaves, rng, persistence=0.5):
    total = np.zeros(n, dtype=np.float32)
    amp, norm, s = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        total += value_noise_1d(n, max(s, 1.0), rng) * amp
        norm += amp
        amp *= persistence
        s /= 2.0
    return total / norm


def value_noise_2d(w, h, sx, sy, rng):
    """Smooth value noise in [-1, 1] of shape (w, h)."""
    gw, gh = int(w / sx) + 3, int(h / sy) + 3
    g = rng.random((gw, gh), dtype=np.float32) * 2 - 1
    xs = np.arange(w, dtype=np.float32) / sx
    ys = np.arange(h, dtype=np.float32) / sy
    xi = xs.astype(np.int32)
    yi = ys.astype(np.int32)
    fx = _smooth(xs - xi)[:, None]
    fy = _smooth(ys - yi)[None, :]
    gx = g[xi, :] * (1 - fx) + g[xi + 1, :] * fx          # (w, gh)
    return gx[:, yi] * (1 - fy) + gx[:, yi + 1] * fy       # (w, h)


def fractal_2d(w, h, scale, octaves, rng, persistence=0.5, stretch=1.0):
    """Fractal value noise. ``stretch`` > 1 makes features wider than tall."""
    total = np.zeros((w, h), dtype=np.float32)
    amp, norm, s = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        total += value_noise_2d(w, h, max(s * stretch, 1.0), max(s, 1.0),
                                rng) * amp
        norm += amp
        amp *= persistence
        s /= 2.0
    return total / norm
