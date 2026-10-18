"""Outlined text rendering in the Terraria style, with caching."""
import pygame


class Text:
    def __init__(self):
        self.fonts = {}
        self.cache = {}

    def font(self, size):
        f = self.fonts.get(size)
        if f is None:
            f = pygame.font.Font(None, int(size * 1.25))
            self.fonts[size] = f
        return f

    def render(self, text, size=20, color=(255, 255, 255), outline=(0, 0, 0),
               thickness=2):
        key = (text, size, color, outline, thickness)
        img = self.cache.get(key)
        if img is not None:
            return img
        f = self.font(size)
        base = f.render(text, True, color)
        if outline is None:
            img = base
        else:
            o = f.render(text, True, outline)
            w, h = base.get_width() + thickness * 2, \
                base.get_height() + thickness * 2
            img = pygame.Surface((w, h), pygame.SRCALPHA)
            for dx in range(-thickness, thickness + 1):
                for dy in range(-thickness, thickness + 1):
                    if dx * dx + dy * dy <= thickness * thickness + 1 and \
                            (dx or dy):
                        img.blit(o, (dx + thickness, dy + thickness))
            img.blit(base, (thickness, thickness))
        if len(self.cache) > 3000:
            self.cache.clear()
        self.cache[key] = img
        return img

    def draw(self, surf, text, pos, size=20, color=(255, 255, 255),
             anchor="topleft", **kw):
        img = self.render(text, size, color, **kw)
        r = img.get_rect(**{anchor: pos})
        surf.blit(img, r)
        return r

    def size(self, text, size=20):
        return self.render(text, size).get_size()
