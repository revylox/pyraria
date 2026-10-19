"""Terraria-style user interface: hotbar, hearts/mana, inventory, coins,
ammo, trash, equipment (armour, vanity, dyes, accessories, misc equips),
crafting, chests, buffs, tooltips, chat and the in-game settings menu."""
import pygame

from . import config as C
from . import textures as TX
from . import tiles as T
from .inventory import ARMOR_TYPES, MISC_NAMES
from .items import (ITEMS, RECIPES, RARITY_COLORS, Stack, get_icon,
                    tooltip_lines)

SW, SH = C.SCREEN_W, C.SCREEN_H
SLOT = 44
PITCH = 48
INV_X, INV_Y = 20, 22

SLOT_COLORS = {
    "main": ((63, 82, 151, 190), (98, 120, 200)),
    "hot": ((63, 82, 151, 190), (98, 120, 200)),
    "chest": ((63, 82, 151, 190), (98, 120, 200)),
    "coins": ((140, 120, 60, 190), (200, 180, 90)),
    "ammo": ((63, 82, 151, 190), (98, 120, 200)),
    "trash": ((60, 60, 70, 190), (110, 110, 130)),
    "armor": ((63, 82, 151, 190), (98, 120, 200)),
    "vanity": ((60, 120, 120, 190), (100, 170, 170)),
    "dye": ((140, 70, 110, 190), (200, 110, 160)),
    "misc": ((63, 82, 151, 190), (98, 120, 200)),
    "selected": ((90, 110, 190, 220), (255, 230, 120)),
}


def _slot_surface(size, fill, border):
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(s, (10, 12, 30, 200), (0, 0, size, size),
                     border_radius=6)
    pygame.draw.rect(s, fill, (2, 2, size - 4, size - 4), border_radius=5)
    pygame.draw.rect(s, border, (2, 2, size - 4, size - 4), 2,
                     border_radius=5)
    hl = tuple(min(255, c + 40) for c in border[:3]) + (90,)
    pygame.draw.line(s, hl, (6, 4), (size - 7, 4))
    return s


def _silhouette(kind):
    """Faint placeholder icons for empty equipment slots."""
    s = pygame.Surface((16, 16), pygame.SRCALPHA)
    c = (255, 255, 255, 70)
    if kind == "head":
        pygame.draw.rect(s, c, (3, 3, 10, 9), border_radius=4)
        s.fill((0, 0, 0, 0), (5, 7, 6, 2))
    elif kind == "body":
        pygame.draw.polygon(s, c, [(3, 3), (13, 3), (15, 8), (12, 8),
                                   (12, 14), (4, 14), (4, 8), (1, 8)])
    elif kind == "legs":
        pygame.draw.rect(s, c, (4, 2, 8, 4))
        pygame.draw.rect(s, c, (4, 6, 3, 9))
        pygame.draw.rect(s, c, (9, 6, 3, 9))
    elif kind == "accessory":
        pygame.draw.circle(s, c, (8, 8), 5, 2)
        pygame.draw.circle(s, c, (8, 3), 2)
    elif kind == "dye":
        pygame.draw.rect(s, c, (6, 2, 4, 3))
        pygame.draw.ellipse(s, c, (3, 5, 10, 10))
    elif kind == "pet":
        pygame.draw.ellipse(s, c, (3, 6, 10, 8))
        pygame.draw.circle(s, c, (5, 5), 2)
        pygame.draw.circle(s, c, (11, 5), 2)
    elif kind == "light_pet":
        pygame.draw.circle(s, c, (8, 8), 5)
        for a in range(0, 16, 4):
            s.fill(c, (a, 1, 1, 1))
    elif kind == "minecart":
        pygame.draw.rect(s, c, (2, 4, 12, 7))
        pygame.draw.circle(s, c, (5, 13), 2)
        pygame.draw.circle(s, c, (11, 13), 2)
    elif kind == "mount":
        pygame.draw.polygon(s, c, [(2, 6), (8, 3), (14, 6), (12, 12),
                                   (4, 12)])
    elif kind == "hook":
        pygame.draw.arc(s, c, (3, 3, 10, 10), 3.6, 7.5, 2)
        pygame.draw.line(s, c, (8, 2), (8, 8), 2)
    elif kind == "coin":
        pygame.draw.circle(s, c, (8, 8), 5, 2)
    elif kind == "ammo":
        pygame.draw.rect(s, c, (6, 3, 4, 10))
        pygame.draw.polygon(s, c, [(6, 3), (8, 0), (10, 3)])
    return TX.upscale(s)


class SlotRef:
    __slots__ = ("cname", "index", "rect", "style", "sil", "label")

    def __init__(self, cname, index, rect, style, sil=None, label=""):
        self.cname = cname
        self.index = index
        self.rect = rect
        self.style = style
        self.sil = sil
        self.label = label


class UI:
    def __init__(self, game):
        self.game = game
        self.text = game.text
        self.assets = game.assets
        self._icon_fit = {}
        self.inventory_open = False
        self.equip_page = 0          # 0 = armour/accessories, 1 = misc
        self.settings_open = False
        self._settings_hover = None
        self.chest = None            # (x, y) of open chest
        self.recipe_scroll = 0
        self.selected_recipe = 0
        self.available = []
        self.messages = []           # [text, colour, ttl]
        self.hover_text = None
        self.slots = []
        self.buttons = []
        self.right_hold = 0
        self.right_ref = None
        self.slot_imgs = {k: _slot_surface(SLOT, *v)
                          for k, v in SLOT_COLORS.items()}
        self.slot_imgs_small = {k: _slot_surface(34, *v)
                                for k, v in SLOT_COLORS.items()}
        self.hot_selected = _slot_surface(52, *SLOT_COLORS["selected"])
        self.hot_slot = _slot_surface(42, *SLOT_COLORS["hot"])
        self.sil = {k: _silhouette(k) for k in
                    ("head", "body", "legs", "accessory", "dye", "pet",
                     "light_pet", "minecart", "mount", "hook", "coin",
                     "ammo")}
        self.heart = TX.template(TX.HEART, {"o": (60, 8, 16),
                                            "R": (226, 40, 52),
                                            "H": (255, 170, 170),
                                            "d": (150, 20, 34)})
        self.star = TX.template(TX.STAR, {"o": (12, 22, 84),
                                          "B": (44, 96, 236),
                                          "H": (150, 200, 255)})
        self.shield = TX.template(TX.SHIELD, {"o": (40, 40, 50),
                                              "H": (220, 220, 230),
                                              "S": (150, 150, 165),
                                              "d": (100, 100, 115)}, 3)
        self.trash_icon = TX.template(TX.TRASH, {"o": (30, 30, 40, 160),
                                                 "H": (170, 170, 190, 160),
                                                 "S": (120, 120, 140, 160),
                                                 "d": (80, 80, 100, 160)})
        self.bubble = TX.template(TX.BUBBLE, {"o": (40, 80, 160),
                                              "W": (255, 255, 255),
                                              "B": (120, 190, 255),
                                              "d": (70, 130, 220)})
        self.fire_icon = self._fire_icon()
        self.eye_on, self.eye_off = self._eye_icons()

    # --------------------------------------------------------------- misc
    @staticmethod
    def _fire_icon():
        s = pygame.Surface((16, 16), pygame.SRCALPHA)
        pygame.draw.rect(s, (40, 20, 10), (0, 0, 16, 16))
        pygame.draw.polygon(s, (255, 120, 30), [(3, 14), (5, 6), (8, 9),
                                                (9, 2), (13, 8), (13, 14)])
        pygame.draw.polygon(s, (255, 220, 80), [(6, 14), (7, 9), (9, 11),
                                                (10, 7), (11, 14)])
        return TX.upscale(s)

    @staticmethod
    def _eye_icons():
        on = pygame.Surface((8, 6), pygame.SRCALPHA)
        pygame.draw.ellipse(on, (230, 230, 240), (0, 0, 8, 6))
        on.fill((40, 60, 140), (3, 2, 2, 2))
        off = on.copy()
        pygame.draw.line(off, (200, 40, 40), (0, 5), (7, 0))
        return TX.upscale(on), TX.upscale(off)

    def message(self, text, color=(255, 255, 255)):
        self.messages.append([text, color, 60 * 10])
        self.messages = self.messages[-10:]

    def toggle_inventory(self):
        if self.inventory_open:
            self.close_inventory()
        else:
            self.inventory_open = True
            self.game.sound("menu_open")

    def close_inventory(self, silent=False):
        if self.inventory_open and not silent:
            self.game.sound("menu_close")
        self.inventory_open = False
        self.chest = None
        self.settings_open = False
        inv = self.game.player.inv
        if inv.mouse:
            left = inv.add(inv.mouse.name, inv.mouse.count)
            if left:
                p = self.game.player
                self.game.drop_item(inv.mouse.name, left, p.cx, p.cy,
                                    vx=p.dir * 3, delay=60)
            inv.mouse = None

    def open_chest(self, pos):
        self.chest = pos
        self.inventory_open = True
        self.game.sound("open")

    # ------------------------------------------------------------- layout
    def _layout(self):
        """Build the list of interactive slot rectangles for this frame."""
        slots = []
        if not self.inventory_open:
            x = INV_X
            for i in range(10):
                sel = i == self.game.player.inv.selected
                size = 52 if sel else 42
                r = pygame.Rect(x, INV_Y + (0 if sel else 5), size, size)
                slots.append(SlotRef("main", i, r, "hotbar"))
                x += size + 4
            self.slots = slots
            return
        for row in range(5):
            for col in range(10):
                r = pygame.Rect(INV_X + col * PITCH, INV_Y + row * PITCH, SLOT,
                                SLOT)
                slots.append(SlotRef("main", row * 10 + col, r, "main"))
        cx = INV_X + 10 * PITCH + 6
        for i in range(4):
            r = pygame.Rect(cx, INV_Y + 20 + i * 38, 34, 34)
            slots.append(SlotRef("coins", i, r, "coins", "coin", "Coin"))
            r = pygame.Rect(cx + 38, INV_Y + 20 + i * 38, 34, 34)
            slots.append(SlotRef("ammo", i, r, "ammo", "ammo", "Ammo"))
        r = pygame.Rect(cx + 38, INV_Y + 4 * PITCH, SLOT, SLOT)
        slots.append(SlotRef("trash", 0, r, "trash", None, "Trash"))
        if self.chest:
            for row in range(4):
                for col in range(10):
                    r = pygame.Rect(INV_X + col * PITCH,
                                    INV_Y + 5 * PITCH + 34 + row * PITCH,
                                    SLOT, SLOT)
                    slots.append(SlotRef("chest", row * 10 + col, r, "chest"))
        # equipment column (below the minimap)
        ex = SW - 20 - 3 * PITCH
        ey = 288
        if self.equip_page == 0:
            names = ["Helmet", "Shirt", "Pants"]
            for i in range(3):
                y = ey + i * PITCH
                slots.append(SlotRef("dye_armor", i, pygame.Rect(
                    ex, y, SLOT, SLOT), "dye", "dye", "Dye"))
                slots.append(SlotRef("vanity_armor", i, pygame.Rect(
                    ex + PITCH, y, SLOT, SLOT), "vanity", ARMOR_TYPES[i],
                    "Social " + names[i]))
                slots.append(SlotRef("armor", i, pygame.Rect(
                    ex + 2 * PITCH, y, SLOT, SLOT), "armor", ARMOR_TYPES[i],
                    names[i]))
            for i in range(5):
                y = ey + (3 + i) * PITCH
                slots.append(SlotRef("dye_acc", i, pygame.Rect(
                    ex, y, SLOT, SLOT), "dye", "dye", "Dye"))
                slots.append(SlotRef("vanity_acc", i, pygame.Rect(
                    ex + PITCH, y, SLOT, SLOT), "vanity", "accessory",
                    "Social Accessory"))
                slots.append(SlotRef("acc", i, pygame.Rect(
                    ex + 2 * PITCH, y, SLOT, SLOT), "armor", "accessory",
                    "Accessory"))
        else:
            sil = ("pet", "light_pet", "minecart", "mount", "hook")
            for i in range(5):
                y = ey + i * PITCH
                slots.append(SlotRef("misc_dye", i, pygame.Rect(
                    ex + PITCH, y, SLOT, SLOT), "dye", "dye", "Dye"))
                slots.append(SlotRef("misc", i, pygame.Rect(
                    ex + 2 * PITCH, y, SLOT, SLOT), "misc", sil[i],
                    MISC_NAMES[i]))
        self.slots = slots

    def _container(self, cname):
        if cname == "chest":
            return self.game.world.chests.get(self.chest)
        return self.game.player.inv.container(cname)

    def _get(self, ref):
        lst = self._container(ref.cname)
        if lst is None:
            return None
        v = lst[ref.index]
        if ref.cname == "chest" and v is not None and not isinstance(v,
                                                                      Stack):
            v = Stack(v[0], v[1])
            lst[ref.index] = v
        return v

    def _set(self, ref, stack):
        lst = self._container(ref.cname)
        if lst is not None:
            lst[ref.index] = stack

    # ------------------------------------------------------- crafting data
    def _stations(self):
        p = self.game.player
        w = self.game.world
        found = set()
        x0, x1 = int(p.cx // 16) - 5, int(p.cx // 16) + 5
        y0, y1 = int(p.cy // 16) - 4, int(p.cy // 16) + 4
        reg = w.tiles[max(0, x0):x1 + 1, max(0, y0):y1 + 1]
        for tid in set(reg.ravel().tolist()):
            st = T.TILES[tid].station
            if st:
                found.add(st)
        return found

    def _update_recipes(self):
        inv = self.game.player.inv
        stations = self._stations()
        avail = []
        for r in RECIPES:
            if r.station and r.station not in stations:
                continue
            if all(inv.count_ingredient(n) >= c for n, c in r.ingredients):
                avail.append(r)
        prev = self.available[self.selected_recipe] if self.available and \
            self.selected_recipe < len(self.available) else None
        self.available = avail
        if prev in avail:
            self.selected_recipe = avail.index(prev)
        else:
            self.selected_recipe = min(self.selected_recipe,
                                       max(0, len(avail) - 1))

    def _craft_rect(self, i):
        top = INV_Y + 5 * PITCH + 40
        if self.chest:
            top += 4 * PITCH + 34
        return pygame.Rect(INV_X, top + (i - self.recipe_scroll) * PITCH,
                           SLOT, SLOT)

    def _visible_recipes(self):
        top = self._craft_rect(self.recipe_scroll).top
        n = max(1, (SH - 20 - top) // PITCH)
        return n

    def craft(self, shift=False):
        if not self.available:
            return
        r = self.available[self.selected_recipe]
        inv = self.game.player.inv
        it = ITEMS[r.result]
        if not shift:
            if inv.mouse and (inv.mouse.name != r.result or
                              inv.mouse.count + r.count > it.max_stack):
                return
        for n, c in r.ingredients:
            inv.consume_ingredient(n, c)
        if shift:
            left = inv.add(r.result, r.count)
            if left:
                p = self.game.player
                self.game.drop_item(r.result, left, p.cx, p.cy)
        elif inv.mouse:
            inv.mouse.count += r.count
        else:
            inv.mouse = Stack(r.result, r.count)
        self.game.sound("grab")
        self._update_recipes()

    # ------------------------------------------------------------ queries
    def mouse_over_ui(self, pos):
        if self.settings_open:
            return True
        for ref in self.slots:
            if ref.rect.collidepoint(pos):
                return True
        for rect, _ in self.buttons:
            if rect.collidepoint(pos):
                return True
        if self.inventory_open:
            if pygame.Rect(INV_X - 6, INV_Y - 6, 10 * PITCH + 100,
                           5 * PITCH + 10).collidepoint(pos):
                return True
            if self.available and any(self._craft_rect(i).collidepoint(pos)
                                      for i in range(len(self.available))):
                return True
        return False

    # -------------------------------------------------------------- input
    def handle_click(self, button, pos, mods):
        """Returns True if the UI consumed the click."""
        if self.settings_open:
            return self._settings_click(pos)
        for rect, action in self.buttons:
            if rect.collidepoint(pos):
                if button == 1:
                    action()
                    if action != self._open_settings:   # has its own sound
                        self.game.sound("menu")
                return True
        for ref in self.slots:
            if ref.rect.collidepoint(pos):
                if ref.style == "hotbar":
                    if button == 1:
                        self.game.player.inv.selected = ref.index
                    return True
                if button == 1:
                    self._left_click(ref, mods)
                elif button == 3:
                    self._right_click(ref)
                    self.right_ref = ref
                    self.right_hold = 0
                return True
        if self.inventory_open and self.available:
            for i in range(len(self.available)):
                r = self._craft_rect(i)
                if r.collidepoint(pos) and r.top >= self._craft_rect(
                        self.recipe_scroll).top:
                    if button == 1:
                        if i == self.selected_recipe:
                            self.craft(bool(mods & pygame.KMOD_SHIFT))
                        else:
                            self.selected_recipe = i
                    return True
        return self.mouse_over_ui(pos)

    def handle_wheel(self, dy, pos):
        if self.inventory_open and self.available:
            top = self._craft_rect(self.recipe_scroll).top
            if pygame.Rect(INV_X - 4, top - 4, 400, SH - top).collidepoint(
                    pos):
                n = self._visible_recipes()
                self.recipe_scroll = max(0, min(max(0, len(self.available) -
                                                    n),
                                                self.recipe_scroll - dy))
                return True
        return False

    def _left_click(self, ref, mods):
        inv = self.game.player.inv
        item = self._get(ref)
        mouse = inv.mouse
        shift = mods & pygame.KMOD_SHIFT
        ctrl = mods & pygame.KMOD_CTRL
        if ctrl and item and ref.cname != "trash" and mouse is None:
            inv.trash[0] = item
            self._set(ref, None)
            self.game.sound("grab")
            return
        if shift and item and mouse is None:
            self._quick_move(ref, item)
            return
        if mouse is None:
            if item is not None:
                inv.mouse = item
                self._set(ref, None)
                self.game.sound("grab")
            return
        if not inv.accepts(ref.cname, ref.index, mouse):
            return
        if item is None:
            self._set(ref, mouse)
            inv.mouse = None
        elif item.name == mouse.name and item.count < item.item.max_stack:
            n = min(mouse.count, item.item.max_stack - item.count)
            item.count += n
            mouse.count -= n
            if mouse.count <= 0:
                inv.mouse = None
        else:
            self._set(ref, mouse)
            inv.mouse = item
        self.game.sound("grab")

    def _right_click(self, ref):
        inv = self.game.player.inv
        item = self._get(ref)
        if item is None:
            return
        it = item.item
        if ref.cname == "main" and it.equip in ("head", "body", "legs",
                                                "accessory", "pet",
                                                "light_pet", "minecart",
                                                "mount", "hook", "dye"):
            self._equip(ref, item)
            return
        mouse = inv.mouse
        if mouse is None:
            inv.mouse = Stack(item.name, 1)
        elif mouse.name == item.name and mouse.count < it.max_stack:
            mouse.count += 1
        else:
            return
        item.count -= 1
        if item.count <= 0:
            self._set(ref, None)
        self.game.sound("grab")

    def _equip(self, ref, item):
        inv = self.game.player.inv
        eq = item.item.equip
        if eq in ARMOR_TYPES:
            idx = ARMOR_TYPES.index(eq)
            old = inv.armor[idx]
            inv.armor[idx] = item
            self._set(ref, old)
        elif eq == "accessory":
            for i in range(5):
                if inv.acc[i] is None and inv.accepts("acc", i, item):
                    inv.acc[i] = item
                    self._set(ref, None)
                    break
        elif eq == "dye":
            for i in range(3):
                if inv.dye_armor[i] is None:
                    inv.dye_armor[i] = item
                    self._set(ref, None)
                    break
        else:
            from .inventory import MISC_TYPES
            idx = MISC_TYPES.index(eq)
            old = inv.misc[idx]
            inv.misc[idx] = item
            self._set(ref, old)
        self.game.sound("grab")

    def _quick_move(self, ref, item):
        inv = self.game.player.inv
        if self.chest and ref.cname in ("main", "chest"):
            dest = "chest" if ref.cname == "main" else "main"
            lst = self._container(dest)
            left = self._insert(lst, item, dest)
            if left == 0:
                self._set(ref, None)
            else:
                item.count = left
            self.game.sound("grab")
            return
        if ref.cname == "main" and item.item.equip:
            self._right_click(ref)
            return
        if ref.cname != "main":
            left = inv.add(item.name, item.count)
            if left == 0:
                self._set(ref, None)
            else:
                item.count = left
            self.game.sound("grab")
            return
        # hotbar <-> inventory
        rng = range(10, 50) if ref.index < 10 else range(0, 10)
        for i in rng:
            if inv.main[i] is None:
                inv.main[i] = item
                self._set(ref, None)
                self.game.sound("grab")
                return

    def _insert(self, lst, item, cname):
        count = item.count
        mx = item.item.max_stack
        for i, s in enumerate(lst):
            if s is not None and not isinstance(s, Stack):
                s = Stack(s[0], s[1])
                lst[i] = s
            if s and s.name == item.name and s.count < mx:
                n = min(count, mx - s.count)
                s.count += n
                count -= n
                if count == 0:
                    return 0
        for i, s in enumerate(lst):
            if s is None:
                lst[i] = Stack(item.name, count)
                return 0
        return count

    # chest buttons
    def _chest_list(self):
        lst = self.game.world.chests.get(self.chest)
        if lst is None:
            return None
        for i, s in enumerate(lst):
            if s is not None and not isinstance(s, Stack):
                lst[i] = Stack(s[0], s[1])
        return lst

    def loot_all(self):
        lst = self._chest_list()
        inv = self.game.player.inv
        if lst is None:
            return
        for i, s in enumerate(lst):
            if s:
                left = inv.add(s.name, s.count)
                lst[i] = Stack(s.name, left) if left else None

    def deposit_all(self):
        lst = self._chest_list()
        inv = self.game.player.inv
        if lst is None:
            return
        for i in range(10, 50):
            s = inv.main[i]
            if s:
                left = self._insert(lst, s, "chest")
                inv.main[i] = Stack(s.name, left) if left else None

    def quick_stack(self):
        lst = self._chest_list()
        inv = self.game.player.inv
        if lst is None:
            return
        names = {s.name for s in lst if s}
        for i in range(10, 50):
            s = inv.main[i]
            if s and s.name in names:
                left = self._insert(lst, s, "chest")
                inv.main[i] = Stack(s.name, left) if left else None

    def sort_chest(self):
        lst = self._chest_list()
        if lst is None:
            return
        items = sorted([s for s in lst if s], key=lambda s: s.name)
        merged = []
        for s in items:
            if merged and merged[-1].name == s.name and \
                    merged[-1].count < s.item.max_stack:
                n = min(s.count, s.item.max_stack - merged[-1].count)
                merged[-1].count += n
                s.count -= n
            if s.count:
                merged.append(s)
        for i in range(len(lst)):
            lst[i] = merged[i] if i < len(merged) else None

    def sort_inventory(self):
        inv = self.game.player.inv
        items = [s for s in inv.main[10:] if s]
        order = {"tool": 0, "weapon": 0, "block": 2, "wall": 3,
                 "furniture": 1, "torch": 1}
        items.sort(key=lambda s: (order.get(s.item.kind, 4), s.name))
        merged = []
        for s in items:
            if merged and merged[-1].name == s.name and \
                    merged[-1].count < s.item.max_stack:
                n = min(s.count, s.item.max_stack - merged[-1].count)
                merged[-1].count += n
                s.count -= n
            if s.count:
                merged.append(s)
        for i in range(10, 50):
            inv.main[i] = merged[i - 10] if i - 10 < len(merged) else None

    # ------------------------------------------------------------- update
    def update(self, mouse_pos, mouse_buttons):
        for m in self.messages:
            m[2] -= 1
        self.messages = [m for m in self.messages if m[2] > 0]
        self._layout()
        # settings panel: tick when the cursor reaches a different option
        hov = None
        if self.settings_open:
            hov = self._settings_option_at(mouse_pos)
            if hov is not None and hov != self._settings_hover:
                self.game.sound("menu_tick")
        self._settings_hover = hov
        if self.inventory_open:
            self._update_recipes()
        # right-click and hold to keep taking single items
        if mouse_buttons[2] and self.right_ref is not None and \
                self.right_ref.rect.collidepoint(mouse_pos):
            self.right_hold += 1
            h = self.right_hold
            if h > 18 and (h < 60 and h % 6 == 0 or h >= 60 and h % 2 == 0):
                self._right_click(self.right_ref)
        else:
            self.right_ref = None
        if self.chest:
            p = self.game.player
            cx, cy = self.chest
            if abs(p.cx - (cx + 1) * 16) > 16 * 7 or \
                    abs(p.cy - (cy + 1) * 16) > 16 * 6 or \
                    self.game.world.get(cx, cy) != T.CHEST:
                self.chest = None
                self.game.sound("close")

    # ------------------------------------------------------------- drawing
    def draw(self, screen, mouse_pos):
        self.buttons = []
        self.hover_text = None
        self._layout()
        self._draw_hotbar_or_inventory(screen, mouse_pos)
        self._draw_life_mana(screen, mouse_pos)
        self._draw_buffs(screen, mouse_pos)
        self._draw_chat(screen)
        if self.inventory_open:
            self._draw_equipment_extras(screen, mouse_pos)
            self._draw_crafting(screen, mouse_pos)
            if self.chest:
                self._draw_chest_buttons(screen, mouse_pos)
            spos = (SW - 20 - 3 * PITCH - 60, SH - 10)
            r = self.text.draw(screen, "Settings", spos, 26,
                               (255, 255, 255), anchor="bottomright")
            if r.collidepoint(mouse_pos):
                self.text.draw(screen, "Settings", spos, 26,
                               (255, 235, 100), anchor="bottomright")
            self.buttons.append((r, self._open_settings))
        if self.settings_open:
            self._draw_settings(screen, mouse_pos)

    def draw_overlay(self, screen, mouse_pos):
        """Tooltip, mouse item and cursor - drawn last."""
        inv = self.game.player.inv
        if self.hover_text and not inv.mouse:
            self._draw_tooltip(screen, mouse_pos, self.hover_text)
        if inv.mouse:
            self._draw_item(screen, inv.mouse, pygame.Rect(
                mouse_pos[0] + 6, mouse_pos[1] + 6, 40, 40))

    def _slot_icon(self, name, lim):
        """Item icon fitted into ``lim`` px; shrunk icons are filtered so
        large sprites keep their shape (cached per size)."""
        key = (name, lim)
        icon = self._icon_fit.get(key)
        if icon is None:
            icon = get_icon(name, self.assets)
            w, h = icon.get_size()
            if max(w, h) > lim:
                k = lim / max(w, h)
                icon = pygame.transform.smoothscale(
                    icon, (max(1, round(w * k)), max(1, round(h * k))))
            self._icon_fit[key] = icon
        return icon

    def _draw_item(self, screen, stack, rect, scale=1.0):
        icon = self._slot_icon(stack.name, int(rect.w * 0.82 * scale))
        screen.blit(icon, icon.get_rect(center=rect.center))
        if stack.count > 1:
            self.text.draw(screen, str(stack.count),
                           (rect.left + 6, rect.bottom - 4), 15,
                           anchor="bottomleft")

    def _draw_slot(self, screen, ref, mouse_pos, style=None):
        style = style or ref.style
        r = ref.rect
        if r.w == 52:
            img = self.hot_selected
        elif r.w == 42:
            img = self.hot_slot
        elif r.w == 34:
            img = self.slot_imgs_small.get(style, self.slot_imgs_small["main"])
        else:
            img = self.slot_imgs.get(style, self.slot_imgs["main"])
        screen.blit(img, r)
        item = self._get(ref)
        if item:
            self._draw_item(screen, item, r)
        elif ref.cname == "trash":
            screen.blit(self.trash_icon, self.trash_icon.get_rect(
                center=r.center))
        elif ref.sil:
            sil = self.sil[ref.sil]
            screen.blit(sil, sil.get_rect(center=r.center))
        if r.collidepoint(mouse_pos):
            hl = pygame.Surface(r.size, pygame.SRCALPHA)
            pygame.draw.rect(hl, (255, 255, 255, 40), hl.get_rect(),
                             border_radius=6)
            screen.blit(hl, r)
            if item:
                self.hover_text = self._item_tooltip(item)
            elif ref.label:
                self.hover_text = [(ref.label, (255, 255, 255))]

    def _item_tooltip(self, stack):
        it = stack.item
        title = it.name + (f" ({stack.count})" if stack.count > 1 else "")
        lines = [(title, RARITY_COLORS[it.rarity])]
        for l in tooltip_lines(it):
            lines.append((l, (255, 255, 255)))
        return lines

    def _draw_tooltip(self, screen, pos, lines):
        imgs = [self.text.render(t, 18, c) for t, c in lines]
        w = max(i.get_width() for i in imgs) + 12
        h = sum(i.get_height() - 4 for i in imgs) + 12
        x, y = pos[0] + 18, pos[1] + 18
        if x + w > SW:
            x = pos[0] - w - 6
        if y + h > SH:
            y = SH - h
        bg = pygame.Surface((w, h), pygame.SRCALPHA)
        pygame.draw.rect(bg, (20, 24, 60, 170), bg.get_rect(), border_radius=6)
        screen.blit(bg, (x, y))
        yy = y + 6
        for img in imgs:
            screen.blit(img, (x + 6, yy))
            yy += img.get_height() - 4

    def _draw_hotbar_or_inventory(self, screen, mouse_pos):
        inv = self.game.player.inv
        if not self.inventory_open:
            held = inv.held
            label = held.name if held else ""
            if label:
                self.text.draw(screen, label, (INV_X + 250, 4), 20,
                               anchor="midtop")
            for ref in self.slots:
                self._draw_slot(screen, ref, mouse_pos)
                n = (ref.index + 1) % 10
                self.text.draw(screen, str(n), (ref.rect.left + 6,
                                                ref.rect.top + 2), 13,
                               color=(255, 255, 255) if ref.rect.w == 52
                               else (200, 200, 200))
            return
        self.text.draw(screen, "Inventory", (INV_X + 2, 0), 18)
        for ref in self.slots:
            if ref.cname in ("main", "coins", "ammo", "trash", "chest"):
                self._draw_slot(screen, ref, mouse_pos)
                if ref.cname == "main" and ref.index < 10:
                    n = (ref.index + 1) % 10
                    sel = ref.index == inv.selected
                    self.text.draw(screen, str(n), (ref.rect.left + 5,
                                                    ref.rect.top + 2), 13,
                                   color=(255, 230, 120) if sel else
                                   (220, 220, 220))
                    if sel:
                        pygame.draw.rect(screen, (255, 230, 120), ref.rect, 2,
                                         border_radius=6)
        cx = INV_X + 10 * PITCH + 6
        self.text.draw(screen, "Coins", (cx + 17, INV_Y + 4), 14,
                       anchor="midtop")
        self.text.draw(screen, "Ammo", (cx + 55, INV_Y + 4), 14,
                       anchor="midtop")
        # sort button
        sr = pygame.Rect(cx - 2, INV_Y + 4 * PITCH + 4, 36, 36)
        hov = sr.collidepoint(mouse_pos)
        pygame.draw.rect(screen, (63, 82, 151, 220) if not hov else
                         (90, 110, 190), sr, border_radius=6)
        pygame.draw.rect(screen, (140, 160, 230), sr, 2, border_radius=6)
        for k, wdt in enumerate((20, 14, 8)):
            screen.fill((230, 230, 240), (sr.x + 8, sr.y + 9 + k * 7, wdt, 3))
        self.buttons.append((sr, self.sort_inventory))
        if hov:
            self.hover_text = [("Sort Inventory", (255, 255, 255))]
        if self.chest:
            self.text.draw(screen, "Chest", (INV_X + 2, INV_Y + 5 * PITCH +
                                             8), 20)

    def _draw_chest_buttons(self, screen, mouse_pos):
        x = INV_X + 10 * PITCH + 12
        y = INV_Y + 5 * PITCH + 40
        for label, fn in (("Loot All", self.loot_all),
                          ("Deposit All", self.deposit_all),
                          ("Quick Stack", self.quick_stack),
                          ("Sort Items", self.sort_chest)):
            r = self.text.draw(screen, label, (x, y), 20)
            if r.collidepoint(mouse_pos):
                self.text.draw(screen, label, (x, y), 20, (255, 235, 100))
            self.buttons.append((r, fn))
            y += 30

    def _draw_life_mana(self, screen, mouse_pos):
        p = self.game.player
        # life
        hearts = max(1, p.life_max // 20)
        per_row = 10
        x0 = SW - 30 - 26 - min(hearts, per_row) * 24
        txt = f"Life: {int(p.life)}/{p.life_max}"
        self.text.draw(screen, txt, (x0 + min(hearts, per_row) * 12, 4), 18,
                       anchor="midtop")
        life_per = p.life_max / hearts
        for i in range(hearts):
            fill = (p.life - i * life_per) / life_per
            fill = max(0.0, min(1.0, fill))
            hx = x0 + (i % per_row) * 24
            hy = 26 + (i // per_row) * 24
            if fill <= 0:
                img = self.heart.copy()
                img.set_alpha(60)
                screen.blit(img, (hx, hy))
                continue
            k = 0.65 + 0.35 * fill
            img = self.heart
            if k < 1:
                img = pygame.transform.scale(img, (int(22 * k), int(20 * k)))
                img.set_alpha(int(110 + 145 * fill))
            screen.blit(img, img.get_rect(center=(hx + 11, hy + 10)))
        # mana
        sx = SW - 30
        self.text.draw(screen, "Mana", (sx + 2, 4), 18, anchor="midtop")
        stars = max(1, p.mana_max // 20)
        for i in range(stars):
            fill = max(0.0, min(1.0, (p.mana - i * 20) / 20))
            img = self.star
            if fill < 1:
                k = 0.6 + 0.4 * fill
                img = pygame.transform.scale(img, (int(22 * k), int(22 * k)))
                img.set_alpha(int(90 + 165 * fill))
            screen.blit(img, img.get_rect(center=(sx + 2, 37 + i * 26)))
        r = pygame.Rect(x0, 0, SW - x0, 52)
        if r.collidepoint(mouse_pos):
            if mouse_pos[0] < sx - 16:
                self.hover_text = [(f"{int(p.life)}/{p.life_max} Life",
                                    (255, 255, 255))]
            else:
                self.hover_text = [(f"{int(p.mana)}/{p.mana_max} Mana",
                                    (255, 255, 255))]

    def _draw_buffs(self, screen, mouse_pos):
        p = self.game.player
        x = INV_X
        y = INV_Y + 64 if not self.inventory_open else INV_Y + 5 * PITCH + 4
        if self.inventory_open:
            x = INV_X + 10 * PITCH + 100
            y = INV_Y + 20
        for name, ticks in p.buffs.items():
            icon = self.fire_icon
            r = screen.blit(icon, (x, y))
            secs = ticks // 60
            self.text.draw(screen, f"{secs}s", (x + 16, y + 34), 14,
                           anchor="midtop")
            if r.collidepoint(mouse_pos):
                self.hover_text = [(name, (255, 255, 255)),
                                   ("Slowly losing life", (255, 255, 255))]
            x += 40

    def _draw_chat(self, screen):
        y = SH - 40 - (34 if self.game.chat is not None else 0)
        if self.inventory_open:
            return
        for text, color, ttl in reversed(self.messages):
            img = self.text.render(text, 20, color)
            if ttl < 60:
                img = img.copy()
                img.set_alpha(int(255 * ttl / 60))
            screen.blit(img, (INV_X, y))
            y -= 24

    def _draw_equipment_extras(self, screen, mouse_pos):
        ex = SW - 20 - 3 * PITCH
        ey = 288
        for ref in self.slots:
            if ref.cname not in ("main", "coins", "ammo", "trash", "chest"):
                self._draw_slot(screen, ref, mouse_pos)
        inv = self.game.player.inv
        if self.equip_page == 0:
            # accessory visibility toggles
            for i in range(5):
                y = ey + (3 + i) * PITCH
                r = pygame.Rect(ex + 2 * PITCH + SLOT - 14, y - 2, 16, 12)
                img = self.eye_on if inv.acc_visible[i] else self.eye_off
                screen.blit(img, r)

                def toggle(i=i):
                    inv.acc_visible[i] = not inv.acc_visible[i]
                self.buttons.append((r, toggle))
            # defense
            sr = self.shield.get_rect(center=(ex - 34, ey + 4 * PITCH))
            screen.blit(self.shield, sr)
            self.text.draw(screen, str(inv.defense()), sr.center, 20,
                           anchor="center")
            if sr.collidepoint(mouse_pos):
                self.hover_text = [(f"{inv.defense()} Defense",
                                    (255, 255, 255))]
        # page tabs
        for page, label, sil in ((0, "Equipment", "body"),
                                 (1, "Misc Equipment", "pet")):
            r = pygame.Rect(ex - 52, ey + page * 40, 34, 34)
            img = self.slot_imgs_small["selected" if self.equip_page == page
                                       else "main"]
            screen.blit(img, r)
            s = self.sil[sil].copy()
            s.set_alpha(255)
            screen.blit(s, s.get_rect(center=r.center))
            if r.collidepoint(mouse_pos):
                self.hover_text = [(label, (255, 255, 255))]

            def setp(page=page):
                self.equip_page = page
            self.buttons.append((r, setp))

    def _draw_crafting(self, screen, mouse_pos):
        if not self.available:
            top = self._craft_rect(0).top
            self.text.draw(screen, "Crafting", (INV_X + 2, top - 22), 18)
            self.text.draw(screen, "Nothing can be crafted right now",
                           (INV_X + 2, top + 6), 16, (190, 190, 200))
            return
        top = self._craft_rect(self.recipe_scroll).top
        self.text.draw(screen, "Crafting", (INV_X + 2, top - 22), 18)
        n = self._visible_recipes()
        for i in range(self.recipe_scroll, min(len(self.available),
                                               self.recipe_scroll + n)):
            r = self._craft_rect(i)
            rec = self.available[i]
            sel = i == self.selected_recipe
            img = self.slot_imgs["selected" if sel else "main"]
            screen.blit(img, r)
            self._draw_item(screen, Stack(rec.result, rec.count), r)
            if r.collidepoint(mouse_pos):
                self.hover_text = self._item_tooltip(Stack(rec.result,
                                                           rec.count))
        # ingredients of the selected recipe
        if self.recipe_scroll <= self.selected_recipe < \
                self.recipe_scroll + n:
            rec = self.available[self.selected_recipe]
            r = self._craft_rect(self.selected_recipe)
            x = r.right + 14
            self.text.draw(screen, "Required Items:", (x, r.top - 4), 16)
            for k, (name, cnt) in enumerate(rec.ingredients):
                sr = pygame.Rect(x + k * 40, r.top + 14, 34, 34)
                screen.blit(self.slot_imgs_small["main"], sr)
                shown = name if name in ITEMS else \
                    {"Any Wood": "Wood", "Any Iron Bar": "Iron Bar"}[name]
                self._draw_item(screen, Stack(shown, cnt), sr)
                if sr.collidepoint(mouse_pos):
                    self.hover_text = [(name, (255, 255, 255)),
                                       (f"x{cnt}", (200, 200, 200))]
            if rec.station:
                self.text.draw(screen, f"Requires: {rec.station}",
                               (x + len(rec.ingredients) * 40 + 8,
                                r.top + 22), 15, (210, 210, 230))

    # ------------------------------------------------------------ settings
    def _open_settings(self):
        self.settings_open = True
        self._settings_hover = self._settings_option_at(
            pygame.mouse.get_pos())
        self.game.sound("menu_open")
        self.game.sound("menu_tick")

    def _settings_option_at(self, pos):
        for r, _label, key in self._settings_rects():
            if r.collidepoint(pos):
                return key
        return None

    def close_settings(self):
        if self.settings_open:
            self.settings_open = False
            self.game.sound("menu_close")

    def _settings_items(self):
        s = C.SETTINGS
        return [
            (f"Lighting: {'Color' if s['lighting'] == 'color' else 'Retro'}",
             "lighting"),
            (f"Minimap: {s['minimap'].title()}", "minimap"),
            (f"Fullscreen: {'On' if s['fullscreen'] else 'Off'}",
             "fullscreen"),
            (f"Show FPS: {'On' if s['show_fps'] else 'Off'}", "show_fps"),
            (f"Volume: {int(s['volume'] * 100)}%", "volume"),
            ("Save World", "save"),
            ("Save & Exit", "exit"),
            ("Back", "back"),
        ]

    def _settings_rects(self):
        items = self._settings_items()
        rects = []
        y = SH // 2 - len(items) * 22
        for label, key in items:
            img = self.text.render(label, 28)
            rects.append((img.get_rect(midtop=(SW // 2, y)), label, key))
            y += 44
        return rects

    def _draw_settings(self, screen, mouse_pos):
        shade = pygame.Surface((SW, SH), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 140))
        screen.blit(shade, (0, 0))
        rects = self._settings_rects()
        panel = rects[0][0].unionall([r for r, _, _ in rects]).inflate(140, 50)
        bg = pygame.Surface(panel.size, pygame.SRCALPHA)
        pygame.draw.rect(bg, (40, 52, 120, 220), bg.get_rect(),
                         border_radius=12)
        pygame.draw.rect(bg, (110, 130, 210), bg.get_rect(), 3,
                         border_radius=12)
        screen.blit(bg, panel)
        for r, label, key in rects:
            hov = r.collidepoint(mouse_pos)
            self.text.draw(screen, label, r.topleft, 28,
                           (255, 235, 100) if hov else (255, 255, 255))

    def _settings_click(self, pos):
        for r, label, key in self._settings_rects():
            if r.collidepoint(pos):
                if key != "back":
                    self.game.sound("menu")
                s = C.SETTINGS
                if key == "lighting":
                    s["lighting"] = "retro" if s["lighting"] == "color" \
                        else "color"
                elif key == "minimap":
                    order = ["frame", "overlay", "off"]
                    s["minimap"] = order[(order.index(s["minimap"]) + 1) % 3]
                elif key == "fullscreen":
                    self.game.toggle_fullscreen()
                elif key == "show_fps":
                    s["show_fps"] = not s["show_fps"]
                elif key == "volume":
                    s["volume"] = round((s["volume"] + 0.2) % 1.2, 1)
                    if s["volume"] > 1.0:
                        s["volume"] = 0.0
                    self.game.audio.set_volume(s["volume"])
                elif key == "save":
                    self.game.save()
                    self.message("World saved.", (255, 240, 150))
                elif key == "exit":
                    self.game.save_and_exit()
                elif key == "back":
                    self.close_settings()
                C.save_settings(s)
                return True
        return True

    # --------------------------------------------------------- world hints
    def draw_breath(self, screen, player, camx, camy):
        if player.breath >= C.BREATH_MAX or player.dead:
            return
        n = 10
        full = player.breath / C.BREATH_MAX * n
        x0 = player.cx - camx - n * 9
        y = player.y - camy - 30
        for i in range(n):
            f = full - i
            if f <= 0:
                continue
            img = self.bubble
            if f < 1:
                img = pygame.transform.scale(img, (max(2, int(16 * f)),
                                                   max(2, int(16 * f))))
            screen.blit(img, img.get_rect(center=(x0 + i * 18 + 8, y)))
