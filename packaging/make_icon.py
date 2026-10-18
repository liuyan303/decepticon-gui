"""Generate packaging/icon.ico (run once, commit the result).

    python packaging/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 256
TOP = (124, 92, 255)
BOTTOM = (85, 54, 224)
GLYPH = (255, 255, 255)


def find_font(size: int) -> ImageFont.FreeTypeFont:
    for name in ("segoeuib.ttf", "seguisb.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def build() -> Image.Image:
    gradient = Image.new("RGB", (1, SIZE))
    for y in range(SIZE):
        t = y / (SIZE - 1)
        color = tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3))
        gradient.putpixel((0, y), color)
    base = gradient.resize((SIZE, SIZE))

    canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(base, (0, 0), rounded_mask(SIZE, 56))

    draw = ImageDraw.Draw(canvas)
    font = find_font(150)
    text = "D"
    box = draw.textbbox((0, 0), text, font=font)
    x = (SIZE - (box[2] - box[0])) / 2 - box[0]
    y = (SIZE - (box[3] - box[1])) / 2 - box[1] - 6
    draw.text((x, y), text, font=font, fill=GLYPH)

    # small prompt chevron under the letter, hints at a terminal
    draw.line([(96, 196), (118, 214), (96, 232)], fill=(255, 255, 255, 210),
              width=10, joint="curve")
    draw.rounded_rectangle((128, 218, 164, 228), radius=5, fill=(255, 255, 255, 210))
    return canvas


def main():
    out = Path(__file__).with_name("icon.ico")
    image = build()
    image.save(out, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    image.resize((256, 256), Image.LANCZOS).save(out.with_suffix(".png"))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
