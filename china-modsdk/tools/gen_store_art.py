#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate the platform's store-listing images from the mod's own renderer.

The upload form asks for artwork that has nothing to do with the pack contents:
an icon, a banner, POS images, carousel images and a long description image.
They are *store* assets - the game never reads them - but they are mandatory and
hand-drawn in Photoshop in every official tutorial.

We do not have to draw them by hand: the port ships the same baker as the
original mod, so this tool renders real Diorama output and composes the store
images around it. A promo screenshot that is actually a screenshot is both less
work and more honest than a mock-up.

Sizes are deliberately generous; the upload form shows the exact pixel size for
each slot, and every image here can be re-cropped to it. Use ``--size`` to
override one family.

Usage::

    python3 tools/gen_store_art.py --out dist/store
"""

from __future__ import absolute_import, division, print_function, unicode_literals

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(
    HERE, os.pardir, "DioramaMod", "behavior_packs", "diorama_behavior_pack", "dioramaScripts"
)
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

from modCore import baker, block_source, geometry, projection, tile_key  # noqa: E402
from modCore.map_style import PREVIEW  # noqa: E402

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
except ImportError:  # pragma: no cover - PIL is a build-time dependency only
    Image = None

#: Fonts are optional: without PIL or a CJK font this tool simply refuses.
FONT_CANDIDATES = (
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
)

#: The palette the store art uses. Deliberately close to the HUD colours so the
#: promo and the in-game UI look like the same product.
INK = (14, 18, 24)
PAPER = (240, 232, 214)
GOLD = (226, 178, 84)
MOSS = (86, 132, 78)


def find_font():
    for path in FONT_CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def font(size, path):
    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)


def render_map(tiles=2, samples=1, pitch=50.0):
    """Bake real Diorama output and return it as a PIL image."""
    world = block_source.SyntheticWorld()
    geo = geometry.GEOMETRY
    proj = projection.Projection(pitch)
    source = world.source()
    per_tile = geo.tile_pixels
    width = per_tile * tiles
    height = per_tile * tiles
    canvas = Image.new("RGB", (width, height), (0, 0, 0))
    pixels = canvas.load()
    for ty in range(tiles):
        for tx in range(tiles):
            key = tile_key.TileKey(tile_key.TileKey.SURFACE, tx - tiles // 2, ty - tiles // 2, 0)
            image = baker.bake_tile(
                key,
                source,
                style=PREVIEW,
                geometry=geo,
                projection=proj,
                fast=True,
            )
            for y in range(per_tile):
                row = image.pixels[y * per_tile:(y + 1) * per_tile]
                for x, colour in enumerate(row):
                    pixels[tx * per_tile + x, ty * per_tile + y] = (
                        (colour >> 16) & 0xFF,
                        (colour >> 8) & 0xFF,
                        colour & 0xFF,
                    )
    return canvas


def _cover(image, size):
    """Scale-and-crop ``image`` to exactly ``size``."""
    target_w, target_h = size
    src_w, src_h = image.size
    scale = max(float(target_w) / src_w, float(target_h) / src_h)
    scaled = image.resize(
        (max(1, int(src_w * scale + 0.5)), max(1, int(src_h * scale + 0.5))),
        Image.NEAREST,
    )
    left = (scaled.size[0] - target_w) // 2
    top = (scaled.size[1] - target_h) // 2
    return scaled.crop((left, top, left + target_w, top + target_h))


def _fit(image, size):
    """Scale ``image`` to fit inside ``size``, keeping pixels square."""
    target_w, target_h = size
    src_w, src_h = image.size
    scale = min(float(target_w) / src_w, float(target_h) / src_h)
    return image.resize(
        (max(1, int(src_w * scale + 0.5)), max(1, int(src_h * scale + 0.5))),
        Image.NEAREST,
    )


def _trim_dark(image, threshold=18):
    """Crop the black margin the baker leaves outside the loaded area.

    A runtime tile is only partly covered: everything outside the loaded chunks
    bakes to black. Left alone, that margin dominates a store image, so the art
    is cropped to the region that actually has terrain in it.
    """
    width, height = image.size
    pixels = image.load()
    left, top, right, bottom = width, height, 0, 0
    step = max(1, min(width, height) // 128)
    for y in range(0, height, step):
        for x in range(0, width, step):
            r, g, b = pixels[x, y]
            if r + g + b > threshold * 3:
                if x < left:
                    left = x
                if x > right:
                    right = x
                if y < top:
                    top = y
                if y > bottom:
                    bottom = y
    if right <= left or bottom <= top:
        return image
    pad = max(2, step * 2)
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(width - 1, right + pad)
    bottom = min(height - 1, bottom + pad)
    return image.crop((left, top, right + 1, bottom + 1))


def _background(size, top=(22, 27, 34), bottom=(9, 12, 16)):
    """A quiet vertical gradient; store art should not fight the asset."""
    width, height = size
    canvas = Image.new("RGB", (1, height))
    pixels = canvas.load()
    for y in range(height):
        mix = y / float(max(1, height - 1))
        pixels[0, y] = (
            int(top[0] + (bottom[0] - top[0]) * mix),
            int(top[1] + (bottom[1] - top[1]) * mix),
            int(top[2] + (bottom[2] - top[2]) * mix),
        )
    return canvas.resize((width, height), Image.NEAREST)


def _card(canvas, art, box, border=GOLD, pad=6):
    """Paste ``art`` into ``box`` as a framed screenshot with a soft shadow."""
    x, y, w, h = box
    frame = Image.new("RGB", (w + pad * 2, h + pad * 2), (8, 10, 13))
    draw = ImageDraw.Draw(frame)
    draw.rectangle([0, 0, w + pad * 2 - 1, h + pad * 2 - 1], outline=border)
    frame.paste(_cover(art, (w, h)), (pad, pad))
    shadow = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rectangle(
        [x + 4, y + 8, x + w + pad * 2 + 4, y + h + pad * 2 + 8], fill=(0, 0, 0, 150)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    canvas.paste(Image.alpha_composite(canvas.convert("RGBA"), shadow).convert("RGB"), (0, 0))
    canvas.paste(frame, (x, y))
    return canvas


def _text(draw, xy, text, face, fill, shadow=True):
    x, y = xy
    if shadow:
        draw.text((x + 2, y + 2), text, font=face, fill=(0, 0, 0))
    draw.text((x, y), text, font=face, fill=fill)


def make_icon(map_image, size, face_path):
    """The 1:1 tile shown in the resource-centre grid.

    The official guide warns that the bottom-right corner is covered by a
    rating badge, so nothing important goes there; the title sits on a bar at
    the bottom instead, which is exactly the layout the guide recommends.
    """
    side = size
    canvas = _background((side, side))
    inner = int(side * 0.88)
    frame_w = inner + 12
    _card(
        canvas,
        map_image,
        ((side - frame_w) // 2, (side - frame_w) // 2 - int(side * 0.03), inner, inner),
    )
    draw = ImageDraw.Draw(canvas)
    bar_h = max(26, side // 7)
    draw.rectangle([0, side - bar_h, side, side], fill=(8, 11, 15))
    draw.rectangle([0, side - bar_h, side, side - bar_h + 3], fill=GOLD)
    face = font(max(12, bar_h // 2), face_path)
    label = "DIORAMA"
    bbox = draw.textbbox((0, 0), label, font=face)
    draw.text(
        (
            (side - (bbox[2] - bbox[0])) // 2,
            side - bar_h + (bar_h - (bbox[3] - bbox[1])) // 2 - 2,
        ),
        label,
        font=face,
        fill=PAPER,
    )
    return canvas


def make_banner(map_image, size, face_path, title, subtitle):
    """Text on the left, the real render framed on the right."""
    width, height = size
    canvas = _background(size)
    card_w = int(width * 0.46)
    card_h = int(card_w * 0.62)
    _card(
        canvas,
        map_image,
        (int(width * 0.5), (height - card_h) // 2 - 6, card_w, card_h),
    )
    draw = ImageDraw.Draw(canvas)
    title_face = font(max(30, height // 9), face_path)
    sub_face = font(max(15, height // 26), face_path)
    margin = max(28, width // 18)
    title_box = draw.textbbox((0, 0), title, font=title_face)
    title_h = title_box[3] - title_box[1]
    block_h = title_h + 18 + 8 + 14
    top = int((height - block_h) * 0.5)
    _text(draw, (margin, top), title, title_face, PAPER)
    rule_y = top + title_h + 14
    draw.rectangle([margin, rule_y, margin + int(width * 0.26), rule_y + 3], fill=MOSS)
    _text(draw, (margin, rule_y + 10), subtitle, sub_face, GOLD)
    return canvas


def make_pos(size, face_path, title, body):
    width, height = size
    canvas = _background(size, top=(24, 22, 26), bottom=(10, 9, 12))
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([0, 0, width, max(6, height // 40)], fill=GOLD)
    title_face = font(max(24, height // 11), face_path)
    body_face = font(max(14, height // 24), face_path)
    margin = max(30, width // 14)
    _text(draw, (margin, int(height * 0.26)), title, title_face, PAPER)
    _text(draw, (margin, int(height * 0.48)), body, body_face, (198, 202, 208))
    return canvas


def make_carousel(map_image, size, face_path, caption, crop=1.0):
    """A framed render with one short caption - the guide asks for pictures."""
    width, height = size
    canvas = _background(size)
    card_w = int(width * 0.8)
    card_h = int(card_w * 0.56)
    art = map_image
    if crop != 1.0:
        side = int(map_image.size[0] / crop)
        if side >= 16:
            top = (map_image.size[0] - side) // 2
            art = map_image.crop((top, top, top + side, top + side))
    _card(canvas, art, ((width - card_w) // 2, (height - card_h) // 2 - 10, card_w, card_h))
    draw = ImageDraw.Draw(canvas)
    face = font(max(17, height // 16), face_path)
    bbox = draw.textbbox((0, 0), caption, font=face)
    _text(
        draw,
        ((width - (bbox[2] - bbox[0])) // 2, height - max(52, height // 7)),
        caption,
        face,
        PAPER,
    )
    return canvas


def make_long(map_image, width, face_path, sections):
    """介绍长图: images on top, text below, width <= 1000 as the guide requires."""
    width = min(int(width), 1000)
    face_title = font(max(26, width // 22), face_path)
    face_body = font(max(15, width // 50), face_path)
    block_h = int(width * 0.62)
    text_h = 170
    total = (block_h + text_h) * len(sections)
    canvas = Image.new("RGB", (width, total), (16, 20, 26))
    y = 0
    for title, body in sections:
        card_w = int(width * 0.78)
        card_h = int(card_w * 0.62)
        _card(canvas, map_image, ((width - card_w) // 2, y + (block_h - card_h) // 3, card_w, card_h))
        draw = ImageDraw.Draw(canvas)
        _text(draw, (width // 14, y + block_h + 6), title, face_title, PAPER)
        _text(draw, (width // 14, y + block_h + 18 + max(32, width // 20)), body, face_body, (186, 192, 198))
        y += block_h + text_h
    return canvas


def build(out_dir, size_icon=512, size_banner=(1280, 720), seed_tiles=2):
    if Image is None:
        raise SystemExit("Pillow is required: pip install pillow")
    face_path = find_font()
    if face_path is None:
        print("warning: no CJK font found; Chinese text will not render")
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir)
    print("baking real Diorama output for the artwork ...")
    art = _trim_dark(render_map(tiles=seed_tiles, samples=1))
    written = []

    def save(image, name):
        path = os.path.join(out_dir, name)
        image.save(path)
        written.append(path)
        print("  %s  %dx%d" % (path, image.size[0], image.size[1]))

    save(make_icon(art, size_icon, face_path), "01_icon_512.png")
    save(
        make_banner(art, size_banner, face_path, "DIORAMA", "斜角体素地图 · 路径点 · 雷达"),
        "02_banner_1280x720.png",
    )
    save(
        make_pos(
            (1280, 720),
            face_path,
            "感谢冒险家的支持",
            "本组件免费。后续版本会加入更多视角与图层，欢迎在评论区反馈。",
        ),
        "03_pos_1280x720.png",
    )
    save(make_carousel(art, (1280, 720), face_path, "引擎实时小地图", 1.0), "04_carousel_1.png")
    save(make_carousel(art, (1280, 720), face_path, "全屏斜角体素地图", 2.0), "05_carousel_2.png")
    save(make_carousel(art, (1280, 720), face_path, "路径点与雷达", 3.0), "06_carousel_3.png")
    save(
        make_long(
            art,
            1000,
            face_path,
            [
                ("斜角体素地图", "按 Diorama 投影把地形烘焙成等距体素图，不是普通的俯视截屏。"),
                ("路径点与雷达", "路径点本地保存，雷达按高度筛选附近的生物与玩家。"),
                ("中国版适配", "基于官方 ModSDK；小地图使用引擎自带渲染器，失败时自动回退图集。"),
            ],
        ),
        "07_long_1000.png",
    )
    return written


def main(argv=None):
    parser = argparse.ArgumentParser(description="Generate NetEase store-listing artwork")
    parser.add_argument("--out", default=os.path.join(HERE, os.pardir, "dist", "store"))
    parser.add_argument("--icon", type=int, default=512)
    parser.add_argument("--tiles", type=int, default=2)
    args = parser.parse_args(argv)
    build(args.out, size_icon=args.icon, seed_tiles=args.tiles)
    print("done: %s" % (os.path.abspath(args.out),))
    return 0


if __name__ == "__main__":
    sys.exit(main())
