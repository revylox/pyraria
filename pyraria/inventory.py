"""Player inventory: 50 main slots, coins, ammo, trash and equipment."""
from .items import ITEMS, Stack, matches

ARMOR_TYPES = ("head", "body", "legs")
MISC_TYPES = ("pet", "light_pet", "minecart", "mount", "hook")
MISC_NAMES = ("Pet", "Light Pet", "Minecart", "Mount", "Grappling Hook")


class Inventory:
    def __init__(self):
        self.main = [None] * 50          # 0-9 hotbar
        self.coins = [None] * 4
        self.ammo = [None] * 4
        self.trash = [None]
        self.armor = [None] * 3
        self.vanity_armor = [None] * 3
        self.dye_armor = [None] * 3
        self.acc = [None] * 5
        self.vanity_acc = [None] * 5
        self.dye_acc = [None] * 5
        self.misc = [None] * 5
        self.misc_dye = [None] * 5
        self.mouse = None
        self.selected = 0
        self.acc_visible = [True] * 5

    # ------------------------------------------------------------- access
    def container(self, name):
        return getattr(self, name)

    @property
    def held(self):
        return self.main[self.selected]

    def accepts(self, cname, index, stack):
        if stack is None:
            return True
        it = stack.item
        if cname in ("main", "chest"):
            return True
        if cname == "trash":
            return True
        if cname == "coins":
            return it.equip == "coin"
        if cname == "ammo":
            return it.equip == "ammo"
        if cname in ("armor", "vanity_armor"):
            return it.equip == ARMOR_TYPES[index]
        if cname in ("acc", "vanity_acc"):
            if it.equip != "accessory":
                return False
            for i, s in enumerate(self.acc + self.vanity_acc):
                if s and s.name == stack.name and \
                        not (cname == ("acc" if i < 5 else "vanity_acc")
                             and i % 5 == index):
                    return False
            return True
        if cname in ("dye_armor", "dye_acc", "misc_dye"):
            return it.equip == "dye"
        if cname == "misc":
            return it.equip == MISC_TYPES[index]
        return False

    # -------------------------------------------------------------- adding
    def add(self, name, count):
        """Add items; returns the number that did not fit."""
        it = ITEMS[name]
        targets = []
        if it.equip == "coin":
            targets.append(self.coins)
        if it.equip == "ammo":
            targets.append(self.ammo)
        targets.append(self.main)
        # merge into existing stacks
        for slots in targets:
            for s in slots:
                if s and s.name == name and s.count < it.max_stack:
                    n = min(count, it.max_stack - s.count)
                    s.count += n
                    count -= n
                    if count == 0:
                        return 0
        # empty slots (hotbar first, like Terraria)
        for slots in targets:
            for i in range(len(slots)):
                if slots[i] is None:
                    n = min(count, it.max_stack)
                    slots[i] = Stack(name, n)
                    count -= n
                    if count == 0:
                        return 0
        return count

    def room_for(self, name):
        it = ITEMS[name]
        for s in self.main:
            if s is None or (s.name == name and s.count < it.max_stack):
                return True
        return False

    # ------------------------------------------------------------ crafting
    def count_ingredient(self, ingredient):
        n = 0
        for s in self.main:
            if s and matches(ingredient, s.name):
                n += s.count
        return n

    def consume_ingredient(self, ingredient, count):
        for i, s in enumerate(self.main):
            if count <= 0:
                break
            if s and matches(ingredient, s.name):
                k = min(count, s.count)
                s.count -= k
                count -= k
                if s.count <= 0:
                    self.main[i] = None

    def consume_selected(self, n=1):
        s = self.main[self.selected]
        if s:
            s.count -= n
            if s.count <= 0:
                self.main[self.selected] = None

    # --------------------------------------------------------------- stats
    def defense(self):
        d = 0
        for s in self.armor + self.acc:
            if s:
                d += s.item.defense
        return d

    # ------------------------------------------------------------ persist
    _LISTS = ("main", "coins", "ammo", "trash", "armor", "vanity_armor",
              "dye_armor", "acc", "vanity_acc", "dye_acc", "misc", "misc_dye")

    def to_json(self):
        data = {k: [s.to_json() if s else None for s in getattr(self, k)]
                for k in self._LISTS}
        data["selected"] = self.selected
        data["acc_visible"] = self.acc_visible
        return data

    @classmethod
    def from_json(cls, data):
        inv = cls()
        for k in cls._LISTS:
            vals = data.get(k)
            if vals:
                lst = getattr(inv, k)
                for i, v in enumerate(vals[:len(lst)]):
                    lst[i] = Stack.from_json(v)
        inv.selected = int(data.get("selected", 0))
        inv.acc_visible = data.get("acc_visible", [True] * 5)
        return inv
