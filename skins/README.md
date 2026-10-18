# Custom skins

Every `*.png` in this folder shows up as a skin in the **Wardrobe** (press
`K` in game) and in the character creator. Use it to wear any sprite exactly
as drawn, pixel for pixel.

## Supported images

- **Single image**: one character, facing right.
- **Animation strip**: equally sized frames stacked vertically. This is the
  layout of Terraria's town-NPC sheets, so a 40-pixel-wide strip of 25
  frames works as-is. Frame 0 is standing, frame 1 is in the air, frames
  2–15 are the walk cycle, and the frames face left.

The frame size is guessed: frames are assumed to be about 1.4× taller than
they are wide. Small art (under 36 px tall) is scaled up to Terraria size.

## Optional settings file

Put a `<same name>.json` next to the PNG to override the guesses:

```json
{
  "frame_width": 40,
  "frame_height": 56,
  "layout": "vertical",
  "idle": 0,
  "jump": 1,
  "walk": [2, 3, 4, 5, 6, 7, 8, 9],
  "facing": "left",
  "scale": 1
}
```

`layout` can also be `"horizontal"`. `facing` is the direction the frames
face in the image.

## Start from a built-in skin

```bash
python main.py --export-skin Wizard
```

This writes `skins/Wizard (template).png` and its `.json`: a standing frame,
a jump frame and 8 walk frames. Edit it in any pixel-art editor and rename it.
