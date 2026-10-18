"""Tile and wall definitions.

Every tile type is described by a TileDef.  Fast numpy lookup tables are
built from the definitions so the world, lighting and renderer can work on
whole regions at once.
"""
import numpy as np


class TileDef:
    def __init__(self, tid, name, *, kind="block", solid=True, style="speckle",
                 color=(128, 128, 128), accent=None, drop=None, mult=1.0,
                 min_pick=0, light=None, map_color=None, size=(1, 1),
                 falls=False, tool="pick", breakable=True, sound="dig",
                 dust=None, blocks_sun=None, station=None, grass_base=None):
        self.id = tid
        self.name = name
        self.kind = kind            # block | platform | torch | tree | plant | vine
        #                             | furniture | cactus | sapling | air
        self.solid = solid
        self.style = style          # texture style key
        self.color = color          # base colour for texture generation
        self.accent = accent        # secondary colour (grass, ore, glow ...)
        self.drop = drop            # item name dropped when mined
        self.mult = mult            # pick damage multiplier (Terraria-like)
        self.min_pick = min_pick    # minimum pickaxe power required
        self.light = light          # emitted light (r, g, b) in 0..1
        self.map_color = map_color or color
        self.size = size            # multi-tile objects (w, h)
        self.falls = falls          # sand-like: falls when unsupported
        self.tool = tool            # pick | axe | hammer | any
        self.breakable = breakable
        self.sound = sound
        self.dust = dust or color
        self.blocks_sun = solid if blocks_sun is None else blocks_sun
        self.station = station      # crafting station name
        self.grass_base = grass_base  # tile id this grass reverts to


TILES = []
_by_name = {}


def _t(name, **kw):
    tid = len(TILES)
    d = TileDef(tid, name, **kw)
    TILES.append(d)
    _by_name[name] = d
    return tid


# --- id 0 -------------------------------------------------------------------
AIR = _t("Air", kind="air", solid=False, breakable=False, map_color=(0, 0, 0))

# --- natural blocks ---------------------------------------------------------
DIRT = _t("Dirt", color=(151, 107, 75), drop="Dirt Block", mult=2.0)
STONE = _t("Stone", style="cobble", color=(128, 128, 128), drop="Stone Block",
           sound="tink")
GRASS = _t("Grass", style="grass", color=(151, 107, 75), accent=(52, 185, 62),
           drop="Dirt Block", mult=2.0, map_color=(40, 190, 80), grass_base=1)
CORRUPT_GRASS = _t("Corrupt Grass", style="grass", color=(151, 107, 75),
                   accent=(126, 106, 192), drop="Dirt Block", mult=2.0,
                   map_color=(125, 105, 180), grass_base=1)
EBONSTONE = _t("Ebonstone", style="cobble", color=(98, 86, 130),
               drop="Ebonstone Block", mult=0.5, min_pick=65, sound="tink",
               map_color=(108, 92, 140))
SAND = _t("Sand", style="sand", color=(206, 186, 108), drop="Sand Block",
          mult=2.0, falls=True)
EBONSAND = _t("Ebonsand", style="sand", color=(112, 100, 138),
              drop="Ebonsand Block", mult=2.0, falls=True)
SANDSTONE = _t("Sandstone", style="strata", color=(188, 128, 76),
               drop="Sandstone Block", sound="tink")
HARDENED_SAND = _t("Hardened Sand", style="speckle", color=(165, 142, 92),
                   drop="Hardened Sand Block")
MUD = _t("Mud", color=(94, 68, 74), drop="Mud Block", mult=2.0)
JUNGLE_GRASS = _t("Jungle Grass", style="grass", color=(94, 68, 74),
                  accent=(140, 212, 36), drop="Mud Block", mult=2.0,
                  map_color=(140, 205, 40), grass_base=None)
SNOW = _t("Snow", style="snow", color=(222, 236, 246), drop="Snow Block",
          mult=2.0)
ICE = _t("Ice", style="ice", color=(146, 196, 236), drop="Ice Block",
         sound="tink")
PURPLE_ICE = _t("Purple Ice", style="ice", color=(176, 146, 228),
                drop="Purple Ice Block", sound="tink")
CLAY = _t("Clay", color=(150, 84, 70), drop="Clay Block", mult=2.0)
ASH = _t("Ash", color=(78, 74, 82), drop="Ash Block", mult=2.0)
HELLSTONE = _t("Hellstone", style="hellstone", color=(70, 30, 34),
               accent=(255, 128, 40), drop="Hellstone", mult=0.5, min_pick=65,
               light=(0.55, 0.22, 0.06), map_color=(150, 60, 50),
               sound="tink")
OBSIDIAN = _t("Obsidian", style="obsidian", color=(48, 38, 64),
              drop="Obsidian", mult=0.5, min_pick=55, sound="tink")
CLOUD = _t("Cloud", style="cloud", color=(236, 242, 252), drop="Cloud",
           mult=2.0)
DUNGEON_BRICK = _t("Blue Brick", style="brick", color=(66, 88, 164),
                   drop="Blue Brick", mult=0.5, min_pick=65, sound="tink")
COPPER_ORE = _t("Copper Ore", style="ore", color=(128, 128, 128),
                accent=(214, 116, 52), drop="Copper Ore", sound="tink",
                map_color=(180, 92, 40))
TIN_ORE = _t("Tin Ore", style="ore", color=(128, 128, 128),
             accent=(186, 178, 136), drop="Tin Ore", sound="tink",
             map_color=(160, 152, 112))
IRON_ORE = _t("Iron Ore", style="ore", color=(128, 128, 128),
              accent=(196, 156, 126), drop="Iron Ore", sound="tink",
              map_color=(162, 126, 102))
LEAD_ORE = _t("Lead Ore", style="ore", color=(128, 128, 128),
              accent=(78, 98, 140), drop="Lead Ore", sound="tink",
              map_color=(70, 88, 126))
SILVER_ORE = _t("Silver Ore", style="ore", color=(128, 128, 128),
                accent=(214, 222, 228), drop="Silver Ore", sound="tink",
                map_color=(192, 200, 204))
TUNGSTEN_ORE = _t("Tungsten Ore", style="ore", color=(128, 128, 128),
                  accent=(118, 166, 124), drop="Tungsten Ore", sound="tink",
                  map_color=(104, 142, 110))
GOLD_ORE = _t("Gold Ore", style="ore", color=(128, 128, 128),
              accent=(236, 204, 52), drop="Gold Ore", sound="tink",
              map_color=(200, 176, 40))
PLATINUM_ORE = _t("Platinum Ore", style="ore", color=(128, 128, 128),
                  accent=(204, 210, 236), drop="Platinum Ore", sound="tink",
                  map_color=(186, 190, 214))
DEMONITE_ORE = _t("Demonite Ore", style="ore", color=(98, 86, 130),
                  accent=(150, 118, 236), drop="Demonite Ore", mult=0.5,
                  min_pick=55, sound="tink", map_color=(118, 96, 196))
MUSHROOM_GRASS = _t("Mushroom Grass", style="grass", color=(94, 68, 74),
                    accent=(86, 120, 255), drop="Mud Block", mult=2.0,
                    light=(0.06, 0.12, 0.38), map_color=(90, 120, 250))
SILT = _t("Silt", color=(108, 108, 120), drop="Silt Block", mult=2.0,
          falls=True)

# --- crafted blocks ---------------------------------------------------------
WOOD = _t("Wood", style="planks", color=(168, 122, 82), drop="Wood")
EBONWOOD = _t("Ebonwood", style="planks", color=(122, 98, 140), drop="Ebonwood")
RICH_MAHOGANY = _t("Rich Mahogany", style="planks", color=(156, 72, 62),
                   drop="Rich Mahogany")
BOREAL_WOOD = _t("Boreal Wood", style="planks", color=(150, 128, 102),
                 drop="Boreal Wood")
PALM_WOOD = _t("Palm Wood", style="planks", color=(196, 156, 98),
               drop="Palm Wood")
GRAY_BRICK = _t("Gray Brick", style="brick", color=(132, 132, 138),
                drop="Gray Brick", sound="tink")
GLASS = _t("Glass", style="glass", color=(196, 228, 255), drop="Glass",
           sound="glass", blocks_sun=False)

# --- non-solid / special ----------------------------------------------------
PLATFORM = _t("Wood Platform", kind="platform", solid=False, style="platform",
              color=(168, 122, 82), drop="Wood Platform", mult=2.0)
TORCH = _t("Torch", kind="torch", solid=False, color=(255, 200, 80),
           drop="Torch", light=(1.0, 0.94, 0.78), tool="any", mult=100.0,
           map_color=(253, 221, 3), dust=(255, 200, 80))

TREE = _t("Tree", kind="tree", solid=False, color=(151, 107, 75), drop="Wood",
          tool="axe", mult=0.6, map_color=(151, 107, 75),
          accent=(52, 150, 48))
TREE_EBON = _t("Ebonwood Tree", kind="tree", solid=False, color=(110, 90, 128),
               drop="Ebonwood", tool="axe", mult=0.6,
               map_color=(110, 90, 128), accent=(126, 96, 180))
TREE_JUNGLE = _t("Mahogany Tree", kind="tree", solid=False,
                 color=(140, 70, 58), drop="Rich Mahogany", tool="axe",
                 mult=0.6, map_color=(140, 70, 58), accent=(34, 128, 44))
TREE_BOREAL = _t("Boreal Tree", kind="tree", solid=False, color=(150, 120, 92),
                 drop="Boreal Wood", tool="axe", mult=0.6,
                 map_color=(150, 120, 92), accent=(40, 104, 70))
TREE_PALM = _t("Palm Tree", kind="tree", solid=False, color=(190, 150, 96),
               drop="Palm Wood", tool="axe", mult=0.6,
               map_color=(190, 150, 96), accent=(60, 170, 60))
TREE_MUSHROOM = _t("Giant Glowing Mushroom", kind="tree", solid=False,
                   color=(150, 160, 200), drop=None, tool="axe", mult=0.6,
                   light=(0.12, 0.24, 0.62), map_color=(110, 130, 220),
                   accent=(70, 110, 255))
CACTUS = _t("Cactus", kind="cactus", solid=False, color=(60, 150, 60),
            drop="Cactus", tool="axe", mult=1.0, map_color=(60, 150, 60))

PLANT = _t("Grass Plant", kind="plant", solid=False, color=(52, 185, 62),
           tool="any", mult=100.0, map_color=None, sound="grass")
PLANT_CORRUPT = _t("Corrupt Plant", kind="plant", solid=False,
                   color=(126, 106, 192), tool="any", mult=100.0,
                   sound="grass")
PLANT_JUNGLE = _t("Jungle Plant", kind="plant", solid=False,
                  color=(140, 212, 36), tool="any", mult=100.0,
                  sound="grass")
PLANT_MUSHROOM = _t("Glowing Mushroom", kind="plant", solid=False,
                    color=(86, 120, 255), tool="any", mult=100.0,
                    light=(0.16, 0.32, 0.8), sound="grass")
VINE = _t("Vine", kind="vine", solid=False, color=(52, 165, 62), tool="any",
          mult=100.0, sound="grass")
VINE_JUNGLE = _t("Jungle Vine", kind="vine", solid=False,
                 color=(110, 190, 30), tool="any", mult=100.0, sound="grass")
SAPLING = _t("Sapling", kind="sapling", solid=False, color=(70, 170, 60),
             drop="Acorn", tool="any", mult=100.0, sound="grass")

WORKBENCH = _t("Work Bench", kind="furniture", solid=False,
               color=(168, 122, 82), drop="Work Bench", size=(2, 1),
               tool="any", mult=100.0, station="Work Bench")
FURNACE = _t("Furnace", kind="furniture", solid=False, color=(120, 120, 126),
             drop="Furnace", size=(3, 2), tool="any", mult=100.0,
             light=(0.75, 0.42, 0.18), station="Furnace")
CHEST = _t("Chest", kind="furniture", solid=False, color=(168, 122, 82),
           drop="Chest", size=(2, 2), tool="any", mult=100.0)
DOOR_CLOSED = _t("Wooden Door", kind="furniture", solid=True,
                 color=(168, 122, 82), drop="Wooden Door", size=(1, 3),
                 tool="any", mult=100.0, blocks_sun=True)
DOOR_OPEN = _t("Wooden Door (Open)", kind="furniture", solid=False,
               color=(168, 122, 82), drop="Wooden Door", size=(1, 3),
               tool="any", mult=100.0)
DEMON_ALTAR = _t("Demon Altar", kind="furniture", solid=False,
                 color=(90, 70, 120), size=(3, 2), breakable=False,
                 light=(0.22, 0.06, 0.3), map_color=(120, 80, 160),
                 station="Demon Altar")

NUM_TILES = len(TILES)


def tile_by_name(name):
    return _by_name[name]


# ---------------------------------------------------------------------------
# Tree trunk frame codes (stored in World.frame for tree / cactus tiles)
# ---------------------------------------------------------------------------
TR_TRUNK, TR_BRANCH_L, TR_BRANCH_R, TR_ROOT_L, TR_ROOT_R, TR_TOP = range(6)
# torch attachment codes
TORCH_GROUND, TORCH_LEFT, TORCH_RIGHT, TORCH_WALL = range(4)

# ---------------------------------------------------------------------------
# Walls
# ---------------------------------------------------------------------------


class WallDef:
    def __init__(self, wid, name, style="speckle", color=(80, 80, 80),
                 drop=None):
        self.id = wid
        self.name = name
        self.style = style
        self.color = color
        self.drop = drop
        self.map_color = tuple(int(c * 0.9) for c in color)


WALLS = []


def _w(name, **kw):
    wid = len(WALLS)
    WALLS.append(WallDef(wid, name, **kw))
    return wid


NO_WALL = _w("None")
DIRT_WALL = _w("Dirt Wall", color=(88, 62, 46), drop="Dirt Wall")
STONE_WALL = _w("Stone Wall", style="cobble", color=(62, 62, 68),
                drop="Stone Wall")
EBONSTONE_WALL = _w("Ebonstone Wall", style="cobble", color=(62, 52, 84),
                    drop="Ebonstone Wall")
MUD_WALL = _w("Jungle Wall", color=(52, 66, 38), drop="Jungle Wall")
SNOW_WALL = _w("Snow Wall", style="snow", color=(112, 126, 146),
               drop="Snow Wall")
ICE_WALL = _w("Ice Wall", style="ice", color=(78, 108, 146), drop="Ice Wall")
SANDSTONE_WALL = _w("Sandstone Wall", style="strata", color=(112, 72, 46),
                    drop="Sandstone Wall")
HARDENED_SAND_WALL = _w("Hardened Sand Wall", color=(102, 88, 58),
                        drop="Hardened Sand Wall")
DUNGEON_WALL = _w("Blue Brick Wall", style="brick", color=(36, 46, 92),
                  drop="Blue Brick Wall")
WOOD_WALL = _w("Wood Wall", style="planks", color=(92, 64, 44),
               drop="Wood Wall")
GRAY_BRICK_WALL = _w("Gray Brick Wall", style="brick", color=(68, 68, 74),
                     drop="Gray Brick Wall")
MUSHROOM_WALL = _w("Mushroom Wall", color=(40, 46, 98), drop="Mushroom Wall")
CORRUPT_WALL = _w("Corrupt Grass Wall", color=(58, 48, 78),
                  drop="Corrupt Grass Wall")
NUM_WALLS = len(WALLS)

# ---------------------------------------------------------------------------
# Numpy lookup tables
# ---------------------------------------------------------------------------
SOLID = np.array([t.solid for t in TILES], dtype=bool)
# tiles whose textures connect to each other (full blocks)
MERGE = np.array([t.solid and t.kind == "block" for t in TILES], dtype=bool)
BLOCKS_SUN = np.array([t.blocks_sun for t in TILES], dtype=bool)
EMIT = np.zeros((NUM_TILES, 3), dtype=np.float32)
for _d in TILES:
    if _d.light:
        EMIT[_d.id] = _d.light
EMITS = EMIT.max(axis=1) > 0
FALLS = np.array([t.falls for t in TILES], dtype=bool)
IS_TREE = np.array([t.kind in ("tree", "cactus") for t in TILES], dtype=bool)
IS_FURNITURE = np.array([t.kind == "furniture" for t in TILES], dtype=bool)
REPLACEABLE = np.array([t.kind in ("air", "plant") for t in TILES], dtype=bool)

TILE_MAP_COLOR = np.zeros((NUM_TILES, 3), dtype=np.uint8)
TILE_ON_MAP = np.zeros(NUM_TILES, dtype=bool)
for _d in TILES:
    if _d.kind not in ("air", "plant", "vine", "sapling") and _d.map_color:
        TILE_MAP_COLOR[_d.id] = _d.map_color
        TILE_ON_MAP[_d.id] = True
WALL_MAP_COLOR = np.zeros((NUM_WALLS, 3), dtype=np.uint8)
for _w_ in WALLS:
    WALL_MAP_COLOR[_w_.id] = _w_.map_color

# Natural tiles that cave carving / biome conversion may touch
NATURAL = np.zeros(NUM_TILES, dtype=bool)
for _tid in (DIRT, STONE, GRASS, CORRUPT_GRASS, EBONSTONE, SAND, EBONSAND,
             SANDSTONE, HARDENED_SAND, MUD, JUNGLE_GRASS, SNOW, ICE,
             PURPLE_ICE, CLAY, ASH, SILT, COPPER_ORE, TIN_ORE, IRON_ORE,
             LEAD_ORE, SILVER_ORE, TUNGSTEN_ORE, GOLD_ORE, PLATINUM_ORE,
             MUSHROOM_GRASS, HELLSTONE, OBSIDIAN):
    NATURAL[_tid] = True

GRASS_TILES = (GRASS, CORRUPT_GRASS, JUNGLE_GRASS, MUSHROOM_GRASS)

# blending groups: blocks of different groups get a thin seam between them
GROUP = np.arange(NUM_TILES, dtype=np.int32)
for _g in (GRASS, CORRUPT_GRASS, CLAY):
    GROUP[_g] = DIRT
for _g in (JUNGLE_GRASS, MUSHROOM_GRASS):
    GROUP[_g] = MUD
