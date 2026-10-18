"""Global constants and user settings."""
import json
import os

# --------------------------------------------------------------------------
# Display
# --------------------------------------------------------------------------
SCREEN_W, SCREEN_H = 1280, 720
FPS = 60
TILE = 16                 # pixels per tile
CHUNK = 32                # tiles per render chunk (each side)
TITLE = "Pyraria"

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_DIR = os.path.join(ROOT_DIR, "saves")
WORLD_DIR = os.path.join(SAVE_DIR, "worlds")
PLAYER_DIR = os.path.join(SAVE_DIR, "players")
SETTINGS_FILE = os.path.join(SAVE_DIR, "settings.json")

# --------------------------------------------------------------------------
# World
# --------------------------------------------------------------------------
WORLD_SIZES = {
    "Small": (4200, 1200),
    "Medium": (6400, 1800),
    "Large": (8400, 2400),
}
WORLD_EDGE = 41           # invisible boundary, in tiles, like Terraria

# Day/night (ticks at 60/s, same lengths as Terraria)
DAY_LENGTH = 54000        # 4:30 AM -> 7:30 PM
NIGHT_LENGTH = 32400      # 7:30 PM -> 4:30 AM

# --------------------------------------------------------------------------
# Player physics (Terraria values, pixels per tick)
# --------------------------------------------------------------------------
GRAVITY = 0.4
MAX_FALL = 10.0
RUN_ACCEL = 0.08
RUN_SLOWDOWN = 0.2
MAX_RUN = 3.0
JUMP_SPEED = 5.01
JUMP_HEIGHT = 15          # ticks the jump can be held
PLAYER_W, PLAYER_H = 20, 42
TILE_RANGE_X = 5
TILE_RANGE_Y = 4
FALL_DAMAGE_TILES = 25
IMMUNE_TICKS = 40
RESPAWN_TICKS = 60 * 10
BREATH_MAX = 200

# Give the player Terraria's default starting tools (Copper Shortsword,
# Pickaxe and Axe). Set to False for a truly empty start.
STARTER_KIT = True

# --------------------------------------------------------------------------
# Persistent user settings
# --------------------------------------------------------------------------
DEFAULT_SETTINGS = {
    "fullscreen": False,
    "lighting": "color",       # "color" (smooth) or "retro" (blocky)
    "minimap": "frame",        # "frame", "overlay", "off"
    "show_fps": False,
    "volume": 0.6,
    "autosave_minutes": 5,
}


def load_settings():
    data = dict(DEFAULT_SETTINGS)
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            data.update(json.load(f))
    except (OSError, ValueError):
        pass
    return data


def save_settings(settings):
    try:
        os.makedirs(SAVE_DIR, exist_ok=True)
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        from . import webstore
        webstore.persist(SETTINGS_FILE)
    except OSError:
        pass


SETTINGS = load_settings()
