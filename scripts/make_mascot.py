#!/usr/bin/env python3
"""Generate the Packrat mascot PNG (packrat with a bundle on its back)."""

import os
import struct
import sys
import zlib

W = H = 128

BLUE = (63, 81, 181, 255)
BLUE_DARK = (40, 53, 147, 255)
CREAM = (245, 235, 200, 255)
BROWN = (150, 105, 60, 255)
BROWN_DARK = (110, 76, 41, 255)
PINK = (235, 150, 160, 255)
WHITE = (255, 255, 255, 255)
BLACK = (30, 30, 30, 255)


def _circle(cx, cy, r):
    def inside(x, y):
        return (x - cx) ** 2 + (y - cy) ** 2 <= r * r

    return inside


def _ellipse(cx, cy, rx, ry):
    def inside(x, y):
        return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1

    return inside


def _round_rect(x0, y0, x1, y1, r):
    def inside(x, y):
        if not (x0 + r <= x <= x1 - r or x0 <= x < x0 + r or x1 - r < x <= x1):
            return False
        if not (y0 <= y <= y1):
            return False
        if x0 <= x < x0 + r and y0 <= y < y0 + r:
            return (x - (x0 + r)) ** 2 + (y - (y0 + r)) ** 2 <= r * r
        if x1 - r < x <= x1 and y0 <= y < y0 + r:
            return (x - (x1 - r)) ** 2 + (y - (y0 + r)) ** 2 <= r * r
        if x0 <= x < x0 + r and y1 - r < y <= y1:
            return (x - (x0 + r)) ** 2 + (y - (y1 - r)) ** 2 <= r * r
        if x1 - r < x <= x1 and y1 - r < y <= y1:
            return (x - (x1 - r)) ** 2 + (y - (y1 - r)) ** 2 <= r * r
        return True

    return inside


def build_pixel(x, y):
    # Tail (curling behind, bottom-left)
    if _round_rect(8, 78, 42, 90, 5)(x, y) and x < 40:
        return BROWN_DARK
    # Body
    if _ellipse(64, 78, 34, 28)(x, y):
        # bundle (pack) on the back
        if _round_rect(40, 38, 92, 64, 12)(x, y):
            if _round_rect(46, 44, 86, 58, 6)(x, y):
                return BLUE
            return BLUE_DARK
        return BROWN
    # Head (big ears first)
    if _circle(44, 30, 13)(x, y) or _circle(86, 30, 13)(x, y):
        if _circle(44, 30, 7)(x, y) or _circle(86, 30, 7)(x, y):
            return PINK
        return BROWN
    if _ellipse(65, 46, 24, 20)(x, y):
        # snout
        if _ellipse(65, 54, 12, 9)(x, y):
            if _circle(60, 56, 3)(x, y) or _circle(70, 56, 3)(x, y):
                return BLACK
            return CREAM
        # eyes
        if _circle(56, 42, 3)(x, y) or _circle(74, 42, 3)(x, y):
            return BLACK
        # nose
        if _ellipse(65, 50, 3, 2)(x, y):
            return PINK
        return BROWN
    # Feet
    if _ellipse(50, 106, 10, 5)(x, y) or _ellipse(80, 106, 10, 5)(x, y):
        return BROWN_DARK
    return (0, 0, 0, 0)


def make_png(path, scale=1):
    raw = b""
    for y in range(H):
        raw += b"\x00"
        for x in range(W):
            raw += bytes(build_pixel(x, y))

    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(png)
    print(f"wrote {path} ({len(png)} bytes)")


if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    make_png(os.path.join(root, "packrat", "assets", "packrat-mascot.png"))
    make_png(os.path.join(root, "icons", "128x128", "apps", "org.packrat.Backup.png"))
