"""Item definitions, item stacks and crafting recipes.

The world is "empty": only the items that natural tiles drop, Terraria's
starter tools and a handful of basic crafting results exist.  The item
system fully supports armour, accessories, vanity, dyes, coins, ammo and
misc equipment so new content can be added by registering more ItemDefs.
"""
import pygame

from . import tiles as T
from . import textures as TX

RARITY_COLORS = [(255, 255, 255), (150, 150, 255), (150, 255, 150),
                 (255, 200, 150), (255, 150, 150), (255, 150, 255)]


class ItemDef:
    def __init__(self, name, *, kind="material", max_stack=9999,
                 place_tile=None, place_wall=None, pick=0, axe=0, hammer=0,
                 damage=0, knockback=0.0, use_time=15, use_anim=None,
                 use_style="swing", auto_reuse=False, consumable=False,
                 rarity=0, equip=None, defense=0, tooltip=(), icon_key=None,
                 place_style=0):
        self.name = name
        self.kind = kind
        self.max_stack = max_stack
        self.place_tile = place_tile
        self.place_wall = place_wall
        self.place_style = place_style
        self.pick = pick
        self.axe = axe
        self.hammer = hammer
        self.damage = damage
        self.knockback = knockback
        self.use_time = use_time
        self.use_anim = use_anim if use_anim is not None else use_time
        self.use_style = use_style
        self.auto_reuse = auto_reuse
        self.consumable = consumable
        self.rarity = rarity
        # equip: head | body | legs | accessory | dye | pet | light_pet |
        #        minecart | mount | hook | coin | ammo
        self.equip = equip
        self.defense = defense
        self.tooltip = list(tooltip)
        self.icon_key = icon_key
        self.is_material = False


ITEMS = {}


def _reg(item):
    ITEMS[item.name] = item
    return item


def _block(name, tid):
    _reg(ItemDef(name, kind="block", place_tile=tid, use_time=10, use_anim=15,
                 auto_reuse=True, consumable=True, use_style="swing"))


for _name, _tid in [
        ("Dirt Block", T.DIRT), ("Stone Block", T.STONE),
        ("Ebonstone Block", T.EBONSTONE), ("Sand Block", T.SAND),
        ("Ebonsand Block", T.EBONSAND), ("Sandstone Block", T.SANDSTONE),
        ("Hardened Sand Block", T.HARDENED_SAND), ("Mud Block", T.MUD),
        ("Snow Block", T.SNOW), ("Ice Block", T.ICE),
        ("Purple Ice Block", T.PURPLE_ICE), ("Clay Block", T.CLAY),
        ("Ash Block", T.ASH), ("Silt Block", T.SILT),
        ("Hellstone", T.HELLSTONE), ("Obsidian", T.OBSIDIAN),
        ("Cloud", T.CLOUD), ("Blue Brick", T.DUNGEON_BRICK),
        ("Copper Ore", T.COPPER_ORE), ("Tin Ore", T.TIN_ORE),
        ("Iron Ore", T.IRON_ORE), ("Lead Ore", T.LEAD_ORE),
        ("Silver Ore", T.SILVER_ORE), ("Tungsten Ore", T.TUNGSTEN_ORE),
        ("Gold Ore", T.GOLD_ORE), ("Platinum Ore", T.PLATINUM_ORE),
        ("Demonite Ore", T.DEMONITE_ORE),
        ("Wood", T.WOOD), ("Ebonwood", T.EBONWOOD),
        ("Rich Mahogany", T.RICH_MAHOGANY), ("Boreal Wood", T.BOREAL_WOOD),
        ("Palm Wood", T.PALM_WOOD), ("Gray Brick", T.GRAY_BRICK),
        ("Glass", T.GLASS)]:
    _block(_name, _tid)

for _w in T.WALLS[1:]:
    _reg(ItemDef(_w.drop, kind="wall", place_wall=_w.id, use_time=7,
                 use_anim=15, auto_reuse=True, consumable=True))

_reg(ItemDef("Wood Platform", kind="block", place_tile=T.PLATFORM,
             use_time=10, use_anim=15, auto_reuse=True, consumable=True))
_reg(ItemDef("Torch", kind="torch", place_tile=T.TORCH, use_time=10,
             use_anim=15, auto_reuse=True, consumable=True,
             tooltip=["Provides light"]))
_reg(ItemDef("Work Bench", kind="furniture", place_tile=T.WORKBENCH,
             max_stack=99, use_time=14, use_anim=15, auto_reuse=True,
             consumable=True, tooltip=["Used for basic crafting"]))
_reg(ItemDef("Furnace", kind="furniture", place_tile=T.FURNACE, max_stack=99,
             use_time=14, use_anim=15, auto_reuse=True, consumable=True,
             tooltip=["Used for smelting ore"]))
_reg(ItemDef("Chest", kind="furniture", place_tile=T.CHEST, max_stack=99,
             use_time=14, use_anim=15, auto_reuse=True, consumable=True,
             tooltip=["Stores items"]))
_reg(ItemDef("Wooden Door", kind="furniture", place_tile=T.DOOR_CLOSED,
             max_stack=99, use_time=14, use_anim=15, auto_reuse=True,
             consumable=True))
_reg(ItemDef("Acorn", kind="seed", place_tile=T.SAPLING, use_time=10,
             use_anim=15, auto_reuse=True, consumable=True,
             tooltip=["Plant it on grass, snow or sand to grow a tree"]))
_reg(ItemDef("Cactus"))
for _bar in ("Copper Bar", "Tin Bar", "Iron Bar", "Lead Bar", "Silver Bar",
             "Tungsten Bar", "Gold Bar", "Platinum Bar"):
    _reg(ItemDef(_bar))
_reg(ItemDef("Demonite Bar", rarity=1))

# Terraria's default starting equipment
_reg(ItemDef("Copper Shortsword", kind="weapon", max_stack=1, damage=5,
             knockback=4, use_time=12, use_anim=12, use_style="stab"))
_reg(ItemDef("Copper Pickaxe", kind="tool", max_stack=1, damage=4,
             knockback=2, pick=35, use_time=15, use_anim=23, auto_reuse=True))
_reg(ItemDef("Copper Axe", kind="tool", max_stack=1, damage=3, knockback=4.5,
             axe=35, use_time=21, use_anim=30, auto_reuse=True))
_reg(ItemDef("Wooden Hammer", kind="tool", max_stack=1, damage=2,
             knockback=5.5, hammer=25, use_time=30, use_anim=37,
             auto_reuse=True))

STARTER_ITEMS = [("Copper Shortsword", 1), ("Copper Pickaxe", 1),
                 ("Copper Axe", 1)]

# ---------------------------------------------------------------------------
# Recipes
# ---------------------------------------------------------------------------
GROUPS = {
    "Any Wood": ["Wood", "Ebonwood", "Rich Mahogany", "Boreal Wood",
                 "Palm Wood"],
    "Any Iron Bar": ["Iron Bar", "Lead Bar"],
}


class Recipe:
    def __init__(self, result, count, ingredients, station=None):
        self.result = result
        self.count = count
        self.ingredients = ingredients     # list of (name or group, count)
        self.station = station


RECIPES = [
    Recipe("Work Bench", 1, [("Any Wood", 10)]),
    Recipe("Wood Platform", 2, [("Any Wood", 1)]),
    Recipe("Torch", 3, [("Any Wood", 1)]),
    Recipe("Wooden Door", 1, [("Any Wood", 6)], "Work Bench"),
    Recipe("Wooden Hammer", 1, [("Any Wood", 8)], "Work Bench"),
    Recipe("Wood Wall", 4, [("Any Wood", 1)], "Work Bench"),
    Recipe("Chest", 1, [("Any Wood", 8), ("Any Iron Bar", 2)], "Work Bench"),
    Recipe("Furnace", 1, [("Stone Block", 20), ("Any Wood", 4),
                          ("Torch", 3)], "Work Bench"),
    Recipe("Stone Wall", 4, [("Stone Block", 1)], "Work Bench"),
    Recipe("Dirt Wall", 4, [("Dirt Block", 1)], "Work Bench"),
    Recipe("Snow Wall", 4, [("Snow Block", 1)], "Work Bench"),
    Recipe("Ebonstone Wall", 4, [("Ebonstone Block", 1)], "Work Bench"),
    Recipe("Sandstone Wall", 4, [("Sandstone Block", 1)], "Work Bench"),
    Recipe("Hardened Sand Wall", 4, [("Hardened Sand Block", 1)],
           "Work Bench"),
    Recipe("Blue Brick Wall", 4, [("Blue Brick", 1)], "Work Bench"),
    Recipe("Gray Brick", 1, [("Stone Block", 2)], "Furnace"),
    Recipe("Gray Brick Wall", 4, [("Gray Brick", 1)], "Work Bench"),
    Recipe("Glass", 1, [("Sand Block", 1)], "Furnace"),
    Recipe("Copper Bar", 1, [("Copper Ore", 3)], "Furnace"),
    Recipe("Tin Bar", 1, [("Tin Ore", 3)], "Furnace"),
    Recipe("Iron Bar", 1, [("Iron Ore", 3)], "Furnace"),
    Recipe("Lead Bar", 1, [("Lead Ore", 3)], "Furnace"),
    Recipe("Silver Bar", 1, [("Silver Ore", 4)], "Furnace"),
    Recipe("Tungsten Bar", 1, [("Tungsten Ore", 4)], "Furnace"),
    Recipe("Gold Bar", 1, [("Gold Ore", 4)], "Furnace"),
    Recipe("Platinum Bar", 1, [("Platinum Ore", 4)], "Furnace"),
    Recipe("Demonite Bar", 1, [("Demonite Ore", 3)], "Furnace"),
]
for _r in RECIPES:
    for _n, _c in _r.ingredients:
        for _m in GROUPS.get(_n, [_n]):
            if _m in ITEMS:
                ITEMS[_m].is_material = True


def matches(ingredient, name):
    return name in GROUPS.get(ingredient, [ingredient])


# ---------------------------------------------------------------------------
# Item stacks
# ---------------------------------------------------------------------------
class Stack:
    __slots__ = ("name", "count")

    def __init__(self, name, count=1):
        self.name = name
        self.count = count

    @property
    def item(self):
        return ITEMS[self.name]

    def copy(self):
        return Stack(self.name, self.count)

    def to_json(self):
        return [self.name, self.count]

    @staticmethod
    def from_json(v):
        if not v or v[0] not in ITEMS:
            return None
        return Stack(v[0], int(v[1]))


# ---------------------------------------------------------------------------
# Tooltips & icons
# ---------------------------------------------------------------------------
def speed_text(anim):
    for limit, txt in ((8, "Insanely fast"), (20, "Very fast"), (25, "Fast"),
                       (30, "Average"), (35, "Slow"), (45, "Very slow"),
                       (55, "Extremely slow")):
        if anim <= limit:
            return txt + " speed"
    return "Snail speed"


def tooltip_lines(item):
    lines = []
    if item.damage:
        lines.append(f"{item.damage} melee damage")
        lines.append(speed_text(item.use_anim))
        kb = item.knockback
        kbt = ("No knockback" if kb == 0 else "Extremely weak knockback"
               if kb <= 1.5 else "Very weak knockback" if kb <= 3 else
               "Weak knockback" if kb <= 4 else "Average knockback"
               if kb <= 6 else "Strong knockback")
        lines.append(kbt)
    if item.pick:
        lines.append(f"{item.pick}% pickaxe power")
    if item.axe:
        lines.append(f"{item.axe}% axe power")
    if item.hammer:
        lines.append(f"{item.hammer}% hammer power")
    if item.equip in ("head", "body", "legs"):
        lines.append(f"{item.defense} defense")
    if item.equip == "accessory":
        lines.append("Equipable")
    if item.place_tile is not None or item.place_wall is not None:
        lines.append("Can be placed")
    if item.is_material:
        lines.append("Material")
    lines.extend(item.tooltip)
    return lines


_icon_cache = {}

_ORE_COLOURS = {
    "Copper": (214, 116, 52), "Tin": (186, 178, 136),
    "Iron": (196, 156, 126), "Lead": (78, 98, 140),
    "Silver": (214, 222, 228), "Tungsten": (118, 166, 124),
    "Gold": (236, 204, 52), "Platinum": (204, 210, 236),
    "Demonite": (130, 100, 210),
}


def get_icon(name, assets):
    if name in _icon_cache:
        return _icon_cache[name]
    it = ITEMS[name]
    surf = None
    if name == "Copper Pickaxe":
        surf = TX.tool_art("pickaxe", (214, 116, 52))
    elif name == "Copper Axe":
        surf = TX.tool_art("axe", (214, 116, 52))
    elif name == "Copper Shortsword":
        surf = TX.tool_art("sword", (214, 116, 52))
    elif name == "Wooden Hammer":
        surf = TX.tool_art("hammer", (176, 128, 84))
    elif name.endswith(" Bar"):
        metal = _ORE_COLOURS.get(name.split()[0], (180, 180, 180))
        surf = TX.template(TX.BAR, TX.metal_palette(metal))
    elif name == "Torch":
        surf = assets.torch_icon
    elif name == "Wood Platform":
        surf = assets.platform_icon
    elif name == "Acorn":
        surf = TX.template(TX.ACORN, {"o": (70, 40, 20), "d": (120, 80, 40),
                                      "D": (150, 104, 60),
                                      "B": (190, 130, 70),
                                      "H": (230, 180, 120),
                                      "w": (90, 60, 30)})
    elif name == "Cactus":
        surf = TX.template(TX.CACTUS_ITEM, {"o": (30, 80, 30),
                                            "G": (60, 150, 60),
                                            "L": (110, 200, 90)})
    elif it.place_tile is not None and it.place_tile in assets.block_icon:
        surf = assets.block_icon[it.place_tile]
    elif it.place_tile is not None and it.place_tile in \
            assets.furniture_icon:
        surf = assets.furniture_icon[it.place_tile]
    elif it.place_wall is not None:
        surf = assets.wall_icon[it.place_wall]
    if surf is None:
        surf = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.rect(surf, (200, 200, 200), (4, 4, 16, 16), 2)
    _icon_cache[name] = surf
    return surf


def held_sprite(name, assets):
    """Sprite drawn in the player's hand while using the item."""
    it = ITEMS[name]
    if it.kind in ("tool", "weapon"):
        return get_icon(name, assets)
    icon = get_icon(name, assets)
    w, h = icon.get_size()
    k = 20 / max(w, h)
    return pygame.transform.scale(icon, (max(1, int(w * k)),
                                         max(1, int(h * k))))
