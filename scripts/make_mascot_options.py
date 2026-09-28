#!/usr/bin/env python3
"""Generate cuter packrat mascot variants for review."""

import os
import struct
import zlib

W = H = 128


def _circle(cx, cy, r):
    return lambda x, y: (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _ellipse(cx, cy, rx, ry):
    return lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1


def _rounded_rect(x0, y0, x1, y1, r):
    def inside(x, y):
        if not (x0 <= x <= x1 and y0 <= y <= y1):
            return False
        cx = min(max(x, x0 + r), x1 - r)
        cy = min(max(y, y0 + r), y1 - r)
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r or (x0 + r <= x <= x1 - r) or (y0 + r <= y <= y1 - r)

    return inside


def _render(shapes, path):
    """shapes: list of (predicate, color); later shapes draw underneath earlier ones."""
    raw = b""
    for y in range(H):
        raw += b"\x00"
        for x in range(W):
            color = (0, 0, 0, 0)
            for predicate, col in shapes:
                if predicate(x, y):
                    color = col
            raw += bytes(color)

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    print("wrote", path)


def _ring(cx, cy, r_out, r_in):
    c1 = _circle(cx, cy, r_out)
    c2 = _circle(cx, cy, r_in)
    return lambda x, y: c1(x, y) and not c2(x, y)


def variant_kawaii():
    """Round kawaii face: soft warm body, big sparkly eyes, tiny bundle on head."""
    fur = (226, 178, 124, 255)
    fur_dark = (198, 150, 98, 255)
    cream = (250, 240, 220, 255)
    pink = (255, 170, 180, 255)
    eye = (50, 40, 45, 255)
    sparkle = (255, 255, 255, 255)
    blush = (255, 150, 150, 160)
    bundle_a = (86, 122, 214, 255)
    bundle_b = (66, 96, 180, 255)

    shapes = [
        # ears (outer, inner)
        (_circle(38, 34, 18), fur),
        (_circle(38, 34, 10), fur_dark),
        (_circle(92, 34, 18), fur),
        (_circle(92, 34, 10), fur_dark),
        # head: big soft circle
        (_circle(64, 72, 52), fur),
        # tiny bundle resting on top between ears
        (_rounded_rect(50, 6, 78, 22, 7), bundle_b),
        (_rounded_rect(53, 9, 75, 19, 5), bundle_a),
        (_ellipse(64, 6, 10, 5), bundle_a),
        # muzzle
        (_ellipse(64, 88, 22, 16), cream),
        # nose
        (_ellipse(64, 78, 6, 4), pink),
        # mouth: two small arcs -> simplified as tiny dark curve dots
        (_ellipse(64, 92, 2, 2), eye),
        # whisker dots
        (_circle(46, 84, 2), eye),
        (_circle(82, 84, 2), eye),
        # big shiny eyes
        (_circle(46, 66, 9), eye),
        (_circle(82, 66, 9), eye),
        (_circle(49, 63, 3), sparkle),
        (_circle(85, 63, 3), sparkle),
        # blush
        (_ellipse(34, 80, 8, 5), blush),
        (_ellipse(94, 80, 8, 5), blush),
    ]
    return shapes


def variant_chibi():
    """Chibi side-view: small round body, huge head, oversized bundle."""
    fur = (240, 200, 150, 255)
    fur_dark = (210, 165, 115, 255)
    cream = (255, 248, 235, 255)
    eye = (45, 40, 40, 255)
    sparkle = (255, 255, 255, 255)
    bundle_a = (255, 193, 94, 255)
    bundle_b = (233, 168, 61, 255)
    knot = (226, 90, 90, 255)

    shapes = [
        # tail curling right
        (_rounded_rect(96, 96, 122, 106, 5), fur_dark),
        (_circle(122, 101, 7), fur_dark),
        # body
        (_ellipse(58, 96, 26, 22), fur),
        # feet
        (_ellipse(44, 116, 9, 4), fur_dark),
        (_ellipse(72, 116, 9, 4), fur_dark),
        # big bundle strapped on back
        (_rounded_rect(78, 44, 116, 84, 14), bundle_b),
        (_rounded_rect(83, 49, 111, 79, 10), bundle_a),
        (_ellipse(97, 44, 12, 5), bundle_a),
        # knot at top of bundle
        (_circle(97, 40, 6), knot),
        (_circle(89, 36, 5), knot),
        (_circle(105, 36, 5), knot),
        # head overlapping bundle
        (_circle(50, 62, 34), fur),
        # ear
        (_circle(30, 34, 13), fur),
        (_circle(30, 34, 7), fur_dark),
        (_circle(66, 30, 13), fur),
        (_circle(66, 30, 7), fur_dark),
        # face
        (_ellipse(50, 76, 16, 12), cream),
        (_ellipse(50, 70, 5, 3), (255, 150, 160, 255)),
        (_circle(38, 58, 7), eye),
        (_circle(64, 58, 7), eye),
        (_circle(40, 56, 2), sparkle),
        (_circle(66, 56, 2), sparkle),
        (_circle(34, 70, 4), (255, 160, 150, 170)),
        (_circle(68, 70, 4), (255, 160, 150, 170)),
    ]
    return shapes


def variant_minimal():
    """Minimal flat geometric mark: circle + ears + bundle, two-tone."""
    bg = (52, 73, 140, 255)
    cream = (255, 244, 226, 255)
    accent = (255, 205, 105, 255)

    shapes = [
        # background disc
        (_circle(64, 64, 60), bg),
        # ears as triangles -> simplified rounded nubs
        (_circle(40, 30, 11), cream),
        (_circle(88, 30, 11), cream),
        # head disc
        (_circle(64, 70, 42), cream),
        # bundle: simple arc on top
        (_rounded_rect(44, 20, 84, 44, 10), accent),
        # eyes: two bg-colored dots
        (_circle(50, 64, 5), bg),
        (_circle(78, 64, 5), bg),
        # nose: small bg triangle-ish dot
        (_circle(64, 80, 4), bg),
    ]
    return shapes


def variant_pixel():
    """Chunky pixel-art rat with bundle, retro style."""
    body = (176, 124, 82, 255)
    dark = (120, 80, 48, 255)
    cream = (240, 224, 190, 255)
    black = (40, 34, 30, 255)
    red = (214, 69, 65, 255)
    teal = (62, 143, 140, 255)

    px = 4

    def cell(cx, cy):
        return _rounded_rect(cx * px, cy * px, (cx + 1) * px - 1, (cy + 1) * px - 1, 1)

    shapes = []
    grid = {}
    # head
    for gx, gy in [(12, 8), (13, 8), (14, 8), (15, 8), (16, 8),
                   (11, 9), (12, 9), (13, 9), (14, 9), (15, 9), (16, 9), (17, 9),
                   (11, 10), (12, 10), (13, 10), (14, 10), (15, 10), (16, 10), (17, 10),
                   (11, 11), (12, 11), (13, 11), (14, 11), (15, 11), (16, 11),
                   (12, 12), (13, 12), (14, 12), (15, 12)]:
        grid[(gx, gy)] = body
    # ears
    for gx, gy in [(11, 6), (12, 6), (16, 6), (17, 6), (11, 7), (17, 7)]:
        grid.setdefault((gx, gy), dark)
    # eyes
    grid[(13, 10)] = black
    grid[(15, 10)] = black
    # nose
    grid[(14, 12)] = black
    # body
    for gx in range(12, 20):
        for gy in range(13, 22):
            grid.setdefault((gx, gy), body)
    # feet
    for gx in (12, 13, 18, 19):
        grid.setdefault((gx, 22), dark)
    # bundle (red with teal strap) on the back-top
    for gx in range(20, 27):
        for gy in range(8, 15):
            grid[(gx, gy)] = red
    for gx in range(20, 27):
        grid[(gx, 11)] = teal
    # bundle knot
    grid[(23, 7)] = red
    grid[(23, 6)] = red
    # tail
    for gx in (20, 21, 22, 23, 24):
        grid[(gx, 21)] = dark
        grid[(gx, 22)] = dark

    for (gx, gy), col in grid.items():
        shapes.append((cell(gx, gy), col))
    return shapes


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    out = os.path.join(root, "docs", "mascot-options")
    os.makedirs(out, exist_ok=True)
    _render(variant_kawaii(), os.path.join(out, "option-1-kawaii.png"))
    _render(variant_chibi(), os.path.join(out, "option-2-chibi.png"))
    _render(variant_minimal(), os.path.join(out, "option-3-minimal.png"))
    _render(variant_pixel(), os.path.join(out, "option-4-pixel.png"))
