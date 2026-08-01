"""Crop brand assets from logo_designs.png into app/static/brand/."""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "logo_designs.png"
OUT = ROOT / "app" / "static" / "brand"
OUT.mkdir(parents=True, exist_ok=True)

im = Image.open(SRC).convert("RGBA")
rgb = im.convert("RGB")
w, h = rgb.size
px = rgb.load()


def near_white(r, g, b, t=248):
    return r >= t and g >= t and b >= t


def content_bbox(x0, y0, x1, y1, pad=6, white_t=248):
    minx, miny, maxx, maxy = x1, y1, x0, y0
    found = False
    for y in range(y0, min(y1, h)):
        for x in range(x0, min(x1, w)):
            if not near_white(*px[x, y], white_t):
                found = True
                if x < minx:
                    minx = x
                if y < miny:
                    miny = y
                if x > maxx:
                    maxx = x
                if y > maxy:
                    maxy = y
    if not found:
        raise SystemExit(f"no content in {(x0, y0, x1, y1)}")
    return (
        max(0, minx - pad),
        max(0, miny - pad),
        min(w, maxx + 1 + pad),
        min(h, maxy + 1 + pad),
    )


def trim_white(img, white_t=246, pad=16):
    rgb_img = img.convert("RGB")
    lp = rgb_img.load()
    lw, lh = rgb_img.size
    minx, miny, maxx, maxy = lw, lh, 0, 0
    for y in range(lh):
        for x in range(lw):
            r, g, b = lp[x, y]
            if not near_white(r, g, b, white_t):
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
    box = (
        max(0, minx - pad),
        max(0, miny - pad),
        min(lw, maxx + 1 + pad),
        min(lh, maxy + 1 + pad),
    )
    return img.crop(box)


def colored_only_bbox(x0, y0, x1, y1, pad=10):
    minx, miny, maxx, maxy = x1, y1, x0, y0
    found = False
    for y in range(y0, min(y1, h)):
        for x in range(x0, min(x1, w)):
            r, g, b = px[x, y]
            if near_white(r, g, b, 250):
                continue
            if r < 80 and g < 80 and b < 100:
                continue
            if max(r, g, b) - min(r, g, b) < 30:
                continue
            found = True
            if x < minx:
                minx = x
            if y < miny:
                miny = y
            if x > maxx:
                maxx = x
            if y > maxy:
                maxy = y
    if not found:
        raise SystemExit("no colored mark found")
    return (
        max(0, minx - pad),
        max(0, miny - pad),
        min(w, maxx + 1 + pad),
        min(h, maxy + 1 + pad),
    )


def make_transparent_white(img, thresh=250):
    rgba = img.convert("RGBA")
    data = []
    for r, g, b, a in rgba.getdata():
        if r >= thresh and g >= thresh and b >= thresh:
            data.append((255, 255, 255, 0))
        else:
            data.append((r, g, b, a))
    rgba.putdata(data)
    return rgba


def is_navy(r, g, b):
    return r < 60 and g < 60 and b < 90 and not near_white(r, g, b)


def is_purple_teal(r, g, b):
    if near_white(r, g, b, 250):
        return False
    if r < 80 and g < 80 and b < 100:
        return False
    return max(r, g, b) - min(r, g, b) >= 30


def lockup_bbox():
    """Primary lockup: colored S + full Splitwise wordmark + MINI (wordmark is wider than the mark)."""
    minx, miny, maxx, maxy = w, h, 0, 0
    for y in range(40, 400):
        for x in range(40, 550):
            if is_purple_teal(*px[x, y]):
                minx = min(minx, x)
                miny = min(miny, y)
                maxx = max(maxx, x)
                maxy = max(maxy, y)
    tx0, ty0, tx1, ty1 = w, h, 0, 0
    for y in range(maxy, min(maxy + 200, h)):
        for x in range(40, 600):
            if is_navy(*px[x, y]):
                tx0 = min(tx0, x)
                ty0 = min(ty0, y)
                tx1 = max(tx1, x)
                ty1 = max(ty1, y)
    mx0, my0, mx1, my1 = w, h, 0, 0
    for y in range(ty1, min(ty1 + 120, h)):
        for x in range(40, 600):
            r, g, b = px[x, y]
            if near_white(r, g, b):
                continue
            if (b > r and b > g and max(r, g, b) - min(r, g, b) > 20) or is_navy(r, g, b):
                mx0 = min(mx0, x)
                my0 = min(my0, y)
                mx1 = max(mx1, x)
                my1 = max(my1, y)
    pad = 28
    return (
        max(0, min(minx, tx0, mx0) - pad),
        max(0, miny - pad),
        min(w, max(maxx, tx1, mx1) + pad),
        min(h, max(maxy, ty1, my1) + pad),
    )


# logo-lockup (wordmark is wider than the S - use mark+text extents)
lockup = im.crop(lockup_bbox())
lockup.save(OUT / "logo-lockup.png")
print("logo-lockup", lockup.size)

# logo-mark
mark_box = colored_only_bbox(60, 40, 520, 360, pad=10)
mark = make_transparent_white(im.crop(mark_box))
mw, mh = mark.size
side = max(mw, mh)
canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
canvas.paste(mark, ((side - mw) // 2, (side - mh) // 2), mark)
mark_out = canvas.resize((256, 256), Image.Resampling.LANCZOS)
mark_out.save(OUT / "logo-mark.png")
print("logo-mark", mark_box, mark_out.size)

# app-icon: top-left gradient rounded square only (not the white-bg neighbor)

x0s, y0s, x1s, y1s = 700, 60, 980, 310
region = np.array(rgb.crop((x0s, y0s, x1s, y1s)))
r, g, b = region[:, :, 0], region[:, :, 1], region[:, :, 2]
colorful = (np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b) > 15) & ~(
    (r > 245) & (g > 245) & (b > 245)
)
bluish = colorful & (b.astype(int) > 80) & (b.astype(int) + 20 >= g.astype(int))
ys, xs = np.where(bluish)
pad_in = 6
bx0, by0 = int(xs.min()) - pad_in, int(ys.min()) - pad_in
bx1, by1 = int(xs.max()) + 1 + pad_in, int(ys.max()) + 1 + pad_in
cx, cy = (bx0 + bx1) / 2, (by0 + by1) / 2
side = max(bx1 - bx0, by1 - by0)
abs_x0 = x0s + int(round(cx - side / 2))
abs_y0 = y0s + int(round(cy - side / 2))
abs_x1, abs_y1 = abs_x0 + side, abs_y0 + side
icon = rgb.crop((abs_x0, abs_y0, abs_x1, abs_y1))
# Trim bleed from neighboring white icon on the right
arr_i = np.array(icon)
while arr_i.shape[1] > 100:
    edge = arr_i[:, -5:, :]
    white_frac = ((edge[:, :, 0] > 245) & (edge[:, :, 1] > 245) & (edge[:, :, 2] > 245)).mean()
    if white_frac <= 0.55:
        break
    arr_i = arr_i[:, :-2, :]
icon = Image.fromarray(arr_i)
iw, ih = icon.size
side = max(iw, ih)
sq = Image.new("RGB", (side, side), (255, 255, 255))
sq.paste(icon, ((side - iw) // 2, (side - ih) // 2))
sq.resize((256, 256), Image.Resampling.LANCZOS).save(OUT / "app-icon.png")
print("app-icon", (abs_x0, abs_y0, abs_x1, abs_y1), (256, 256))
print("done ->", OUT)
