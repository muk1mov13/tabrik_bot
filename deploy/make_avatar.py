"""
make_avatar.py — bot rasmini (deploy/avatar.png) chizadi.

Ishga tushirish: python deploy/make_avatar.py  (Pillow kerak: pip install pillow)
Keyin rasmni @BotFather → /setuserpic orqali yuboring.
"""

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

SIZE = 640
SCALE = 3  # katta chizib, kichraytiramiz — chetlar silliq chiqadi
S = SIZE * SCALE
OUT = Path(__file__).with_name("avatar.png")

TOP = (255, 138, 101)      # shaftoli
BOTTOM = (186, 75, 214)    # binafsha
CREAM = (255, 246, 232)
PINK = (255, 105, 150)
PINK_DARK = (222, 68, 118)
CHOCO = (120, 66, 52)
CHOCO_DARK = (92, 48, 38)
PLATE = (255, 255, 255)
CONFETTI = [(255, 214, 92), (110, 220, 200), (255, 255, 255), (120, 170, 255), (255, 160, 190)]


def px(v: float) -> int:
    return int(v * SCALE)


def gradient() -> Image.Image:
    img = Image.new("RGB", (S, S))
    draw = ImageDraw.Draw(img)
    for y in range(S):
        t = y / (S - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(TOP, BOTTOM))
        draw.line([(0, y), (S, y)], fill=color)
    return img


def glow(img: Image.Image):
    """Tort orqasidagi yumshoq yorug'lik."""
    layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(layer).ellipse([px(150), px(170), px(490), px(510)], fill=(255, 240, 210, 120))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(px(60))))


def confetti(draw: ImageDraw.ImageDraw):
    rnd = random.Random(7)  # har safar bir xil rasm
    placed = 0
    while placed < 38:
        x, y = rnd.uniform(40, 600), rnd.uniform(40, 600)
        # tort va olov atrofini bo'sh qoldiramiz
        if 140 < x < 500 and 120 < y < 560:
            continue
        if math.hypot(x - 320, y - 320) > 300:
            continue
        color = rnd.choice(CONFETTI)
        if rnd.random() < 0.5:
            r = rnd.uniform(5, 9)
            draw.ellipse([px(x - r), px(y - r), px(x + r), px(y + r)], fill=color)
        else:
            w, h, a = rnd.uniform(16, 24), rnd.uniform(6, 8), rnd.uniform(0, math.pi)
            pts = [
                (x + dx * math.cos(a) - dy * math.sin(a), y + dx * math.sin(a) + dy * math.cos(a))
                for dx, dy in [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
            ]
            draw.polygon([(px(a_), px(b_)) for a_, b_ in pts], fill=color)
        placed += 1


def tier(draw: ImageDraw.ImageDraw, left, top, right, bottom, body, body_dark, icing):
    r = px(22)
    draw.rounded_rectangle([px(left), px(top), px(right), px(bottom)], radius=r, fill=body)
    # pastki soya chizig'i
    draw.rounded_rectangle([px(left), px(bottom - 18), px(right), px(bottom)], radius=r, fill=body_dark)
    # krem va oqib tushgan tomchilar
    draw.rounded_rectangle([px(left - 4), px(top - 4), px(right + 4), px(top + 26)], radius=px(16), fill=icing)
    width = right - left
    drips = 6
    for i in range(drips):
        cx = left + width * (i + 0.5) / drips
        depth = 22 + (i * 13) % 20
        rw = width / drips * 0.32
        draw.rounded_rectangle(
            [px(cx - rw), px(top + 10), px(cx + rw), px(top + 26 + depth)], radius=px(rw), fill=icing
        )


def candle(draw: ImageDraw.ImageDraw, layer: ImageDraw.ImageDraw, x, base):
    top = base - 70
    draw.rounded_rectangle([px(x - 9), px(top), px(x + 9), px(base)], radius=px(5), fill=CREAM)
    for k in range(3):  # spiral chiziqlar
        y = top + 12 + k * 20
        draw.polygon(
            [(px(x - 9), px(y)), (px(x + 9), px(y - 8)), (px(x + 9), px(y)), (px(x - 9), px(y + 8))],
            fill=PINK,
        )
    draw.line([(px(x), px(top)), (px(x), px(top - 10))], fill=CHOCO_DARK, width=px(3))
    # olov — tomchi shakli
    fy = top - 32
    layer.ellipse([px(x - 26), px(fy - 26), px(x + 26), px(fy + 30)], fill=(255, 220, 120, 110))
    draw.ellipse([px(x - 11), px(fy - 4), px(x + 11), px(fy + 20)], fill=(255, 170, 40))
    draw.polygon([(px(x - 11), px(fy + 8)), (px(x), px(fy - 24)), (px(x + 11), px(fy + 8))], fill=(255, 170, 40))
    draw.ellipse([px(x - 5), px(fy + 4), px(x + 5), px(fy + 17)], fill=(255, 245, 190))


def main():
    img = gradient().convert("RGBA")
    glow(img)
    draw = ImageDraw.Draw(img)
    confetti(draw)

    # likopcha
    draw.ellipse([px(130), px(500), px(510), px(560)], fill=(150, 60, 170))
    draw.ellipse([px(140), px(492), px(500), px(546)], fill=PLATE)

    tier(draw, 170, 390, 470, 520, CHOCO, CHOCO_DARK, CREAM)
    tier(draw, 210, 290, 430, 396, PINK, PINK_DARK, CREAM)

    # gilos va shamlar
    for x in (252, 320, 388):
        draw.ellipse([px(x - 11), px(368), px(x + 11), px(390)], fill=(214, 30, 70))
    flames = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    flame_draw = ImageDraw.Draw(flames)
    for x in (265, 320, 375):
        candle(draw, flame_draw, x, 300)
    img.alpha_composite(flames.filter(ImageFilter.GaussianBlur(px(10))))
    for x in (265, 320, 375):  # olovni yorug'lik ustidan qayta chizamiz
        candle(draw, flame_draw, x, 300)

    img.convert("RGB").resize((SIZE, SIZE), Image.LANCZOS).save(OUT, optimize=True)
    print(f"Saqlandi: {OUT}")


if __name__ == "__main__":
    main()
