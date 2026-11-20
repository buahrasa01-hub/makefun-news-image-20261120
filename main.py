#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Draw a one-day world news front page for Friday 20 November 2026.

Every pixel is drawn by this program: a 1024x1024 PNG holding a masthead, six
story panels (flat vector scenes plus a built-in 5x7 bitmap font) and a sources
footer, written to $MAKEFUN_OUTPUT_DIR/entry.png.  Standard library only, no
file is read, and every run writes the same bytes.
"""

import os
import struct
import sys
import zlib

W = 1024
H = 1024

PAPER = (242, 236, 222)
PANEL = (248, 244, 234)
PANEL_EDGE = (196, 187, 168)
INK = (22, 19, 14)
CAPTION = (72, 66, 56)
NAVY = (16, 26, 58)
GOLD = (214, 178, 92)
WHITE = (255, 255, 255)

MARGIN = 16
GUTTER = 16
PANEL_W = (W - 2 * MARGIN - GUTTER) // 2
PANEL_H = 272
PAD = 12
SCENE_H = 144
MASTHEAD_H = 140
GRID_TOP = 156
FOOTER_TOP = GRID_TOP + 3 * PANEL_H + 2 * GUTTER

HEAD_TOP = 184          # y offset of a panel's headline inside the panel
TEXT_W = PANEL_W - 2 * PAD

# --------------------------------------------------------------------------
# 5x7 bitmap font: A-Z, 0-9, . , : ; ! ? ' - / ( ) % & + = $ and space
# --------------------------------------------------------------------------

_RAW = {
    ' ': '00000 00000 00000 00000 00000 00000 00000',
    'A': '01110 10001 10001 11111 10001 10001 10001',
    'B': '11110 10001 10001 11110 10001 10001 11110',
    'C': '01110 10001 10000 10000 10000 10001 01110',
    'D': '11110 10001 10001 10001 10001 10001 11110',
    'E': '11111 10000 10000 11110 10000 10000 11111',
    'F': '11111 10000 10000 11110 10000 10000 10000',
    'G': '01110 10001 10000 10111 10001 10001 01111',
    'H': '10001 10001 10001 11111 10001 10001 10001',
    'I': '01110 00100 00100 00100 00100 00100 01110',
    'J': '00111 00010 00010 00010 00010 10010 01100',
    'K': '10001 10010 10100 11000 10100 10010 10001',
    'L': '10000 10000 10000 10000 10000 10000 11111',
    'M': '10001 11011 10101 10101 10001 10001 10001',
    'N': '10001 11001 10101 10011 10001 10001 10001',
    'O': '01110 10001 10001 10001 10001 10001 01110',
    'P': '11110 10001 10001 11110 10000 10000 10000',
    'Q': '01110 10001 10001 10001 10101 10010 01101',
    'R': '11110 10001 10001 11110 10100 10010 10001',
    'S': '01111 10000 10000 01110 00001 00001 11110',
    'T': '11111 00100 00100 00100 00100 00100 00100',
    'U': '10001 10001 10001 10001 10001 10001 01110',
    'V': '10001 10001 10001 10001 10001 01010 00100',
    'W': '10001 10001 10001 10101 10101 10101 01010',
    'X': '10001 10001 01010 00100 01010 10001 10001',
    'Y': '10001 10001 01010 00100 00100 00100 00100',
    'Z': '11111 00001 00010 00100 01000 10000 11111',
    '0': '01110 10001 10011 10101 11001 10001 01110',
    '1': '00100 01100 00100 00100 00100 00100 01110',
    '2': '01110 10001 00001 00010 00100 01000 11111',
    '3': '11111 00010 00100 00010 00001 10001 01110',
    '4': '00010 00110 01010 10010 11111 00010 00010',
    '5': '11111 10000 11110 00001 00001 10001 01110',
    '6': '00110 01000 10000 11110 10001 10001 01110',
    '7': '11111 00001 00010 00100 01000 01000 01000',
    '8': '01110 10001 10001 01110 10001 10001 01110',
    '9': '01110 10001 10001 01111 00001 00010 01100',
    '.': '00000 00000 00000 00000 00000 01100 01100',
    ',': '00000 00000 00000 00000 01100 01100 01000',
    ':': '00000 01100 01100 00000 01100 01100 00000',
    ';': '00000 01100 01100 00000 01100 01100 01000',
    '!': '00100 00100 00100 00100 00100 00000 00100',
    '?': '01110 10001 00001 00010 00100 00000 00100',
    "'": '00100 00100 00000 00000 00000 00000 00000',
    '-': '00000 00000 00000 11111 00000 00000 00000',
    '/': '00001 00010 00010 00100 01000 01000 10000',
    '(': '00010 00100 01000 01000 01000 00100 00010',
    ')': '01000 00100 00010 00010 00010 00100 01000',
    '%': '11001 11001 00010 00100 01000 10011 10011',
    '&': '01100 10010 10010 01100 10101 10010 01101',
    '+': '00000 00100 00100 11111 00100 00100 00000',
    '=': '00000 00000 11111 00000 11111 00000 00000',
    '$': '00100 01111 10100 01110 00101 11110 00100',
}
FONT = {ch: tuple(int(r, 2) for r in pat.split()) for ch, pat in _RAW.items()}

ADVANCE = 6  # 5 pixel glyph + 1 pixel letter spacing


def text_width(text, scale):
    if not text:
        return 0
    return len(text) * ADVANCE * scale - scale


# --------------------------------------------------------------------------
# canvas
# --------------------------------------------------------------------------

class Canvas(object):
    def __init__(self, w, h, bg):
        self.w = w
        self.h = h
        self.rows = [bytearray(bytes(bg) * w) for _ in range(h)]
        self.clip = (0, 0, w, h)

    def set_clip(self, x0, y0, x1, y1):
        self.clip = (x0, y0, x1, y1)

    def rect(self, x, y, w, h, col):
        cx0, cy0, cx1, cy1 = self.clip
        xs = max(int(x), cx0)
        ys = max(int(y), cy0)
        xe = min(int(x) + int(w), cx1)
        ye = min(int(y) + int(h), cy1)
        if xe <= xs or ye <= ys:
            return
        span = bytes(col) * (xe - xs)
        off = xs * 3
        end = off + len(span)
        for yy in range(ys, ye):
            self.rows[yy][off:end] = span

    def frame(self, x, y, w, h, thick, col):
        self.rect(x, y, w, thick, col)
        self.rect(x, y + h - thick, w, thick, col)
        self.rect(x, y, thick, h, col)
        self.rect(x + w - thick, y, thick, h, col)

    def disc(self, cx, cy, r, col):
        for yy in range(int(cy - r) - 1, int(cy + r) + 2):
            dy = yy + 0.5 - cy
            t = r * r - dy * dy
            if t <= 0:
                continue
            half = t ** 0.5
            x0 = int(cx - half + 0.5)
            x1 = int(cx + half + 0.5)
            self.rect(x0, yy, x1 - x0, 1, col)

    def poly(self, pts, col):
        y0 = int(min(p[1] for p in pts))
        y1 = int(max(p[1] for p in pts)) + 1
        n = len(pts)
        for yy in range(y0, y1):
            yc = yy + 0.5
            cuts = []
            for i in range(n):
                ax, ay = pts[i]
                bx, by = pts[(i + 1) % n]
                if ay == by:
                    continue
                if (ay <= yc < by) or (by <= yc < ay):
                    cuts.append(ax + (yc - ay) * (bx - ax) / float(by - ay))
            cuts.sort()
            for i in range(0, len(cuts) - 1, 2):
                xa = int(cuts[i] + 0.5)
                xb = int(cuts[i + 1] + 0.5)
                self.rect(xa, yy, xb - xa, 1, col)

    def to_png(self):
        raw = bytearray()
        for row in self.rows:
            raw.append(0)
            raw += row
        ihdr = struct.pack('>IIBBBBB', self.w, self.h, 8, 2, 0, 0, 0)
        out = bytearray(b'\x89PNG\r\n\x1a\n')
        for tag, data in ((b'IHDR', ihdr), (b'IDAT', zlib.compress(bytes(raw), 9)),
                          (b'IEND', b'')):
            out += struct.pack('>I', len(data)) + tag + data
            out += struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff)
        return bytes(out)


# --------------------------------------------------------------------------
# text
# --------------------------------------------------------------------------

def draw_text(cv, x, y, text, scale, col):
    """Draw uppercase text with its top-left at (x, y); returns the ink width."""
    pen = int(x)
    for ch in text.upper():
        glyph = FONT.get(ch, FONT['?'])
        for r in range(7):
            bits = glyph[r]
            if not bits:
                continue
            c = 0
            while c < 5:
                if bits & (1 << (4 - c)):
                    c2 = c + 1
                    while c2 < 5 and (bits & (1 << (4 - c2))):
                        c2 += 1
                    cv.rect(pen + c * scale, int(y) + r * scale,
                            (c2 - c) * scale, scale, col)
                    c = c2
                else:
                    c += 1
        pen += ADVANCE * scale
    return max(0, pen - int(x) - scale)


def draw_center(cv, cx, y, text, scale, col):
    return draw_text(cv, cx - text_width(text, scale) // 2, y, text, scale, col)


def wrap_words(text, maxw, scale, max_lines):
    """Greedy whole-word wrap.  Returns (lines, complete).

    complete is False when words had to be dropped rather than overflow, which
    tells the caller to retry at a smaller scale.
    """
    per_line = max(1, (maxw + scale) // (ADVANCE * scale))
    lines = []
    cur = ''
    for word in text.split():
        if len(word) > per_line:
            return ([word[:per_line]], False)
        cand = word if not cur else cur + ' ' + word
        if len(cand) <= per_line:
            cur = cand
            continue
        lines.append(cur)
        cur = word
        if len(lines) == max_lines:
            return (lines, False)
    if cur:
        if len(lines) < max_lines:
            lines.append(cur)
        else:
            return (lines, False)
    return (lines, True)


def fit_text(text, maxw, max_lines, scales):
    """Pick the largest scale that sets text in max_lines lines, unharmed."""
    for scale in scales:
        lines, complete = wrap_words(text, maxw, scale, max_lines)
        if complete:
            return scale, lines
    scale = scales[-1]
    return scale, wrap_words(text, maxw, scale, max_lines)[0]


# --------------------------------------------------------------------------
# drawing helpers
# --------------------------------------------------------------------------

def vgrad(cv, x, y, w, h, c1, c2, bands):
    for i in range(bands):
        t = i / float(bands - 1) if bands > 1 else 0.0
        col = tuple(int(round(c1[k] + (c2[k] - c1[k]) * t)) for k in range(3))
        ya = y + (h * i) // bands
        yb = y + (h * (i + 1)) // bands
        cv.rect(x, ya, w, yb - ya, col)


def bezier(cv, p0, p1, p2, col, thick, steps=64):
    px = py = None
    for i in range(steps + 1):
        t = i / float(steps)
        mt = 1.0 - t
        x = int(mt * mt * p0[0] + 2 * mt * t * p1[0] + t * t * p2[0])
        y = int(mt * mt * p0[1] + 2 * mt * t * p1[1] + t * t * p2[1])
        if (x, y) != (px, py):
            cv.rect(x - thick // 2, y - thick // 2, thick, thick, col)
        px, py = x, y


def polyline(cv, pts, col, thick):
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        steps = max(2, int(max(abs(x1 - x0), abs(y1 - y0))))
        for s in range(steps + 1):
            t = s / float(steps)
            cv.rect(int(x0 + (x1 - x0) * t) - thick // 2,
                    int(y0 + (y1 - y0) * t) - thick // 2, thick, thick, col)


STAR5 = (
    (0.0000, -1.0000), (-0.2469, -0.3399), (-0.9511, -0.3090), (-0.3996, 0.1297),
    (-0.5878, 0.8090), (0.0000, 0.4200), (0.5878, 0.8090), (0.3996, 0.1297),
    (0.9511, -0.3090), (0.2469, -0.3399),
)


def star(cv, cx, cy, r, col):
    cv.poly([(cx + r * ux, cy + r * uy) for ux, uy in STAR5], col)


def burst(cv, cx, cy, size, col):
    cv.rect(cx - 1, cy - size, 3, size * 2, col)
    cv.rect(cx - size, cy - 1, size * 2, 3, col)
    cv.rect(cx - size + 5, cy - size + 5, size * 2 - 10, size * 2 - 10,
            (min(255, col[0] + 20), col[1], col[2]))


# --------------------------------------------------------------------------
# scenes: each fills (sx, sy, sw, sh) with the clip already set
# --------------------------------------------------------------------------

def scene_ukraine(cv, sx, sy, sw, sh):
    vgrad(cv, sx, sy, sw, sh, (9, 12, 30), (74, 52, 78), 10)
    cv.disc(sx + 396, sy + 30, 17, (228, 234, 250))
    cv.disc(sx + 389, sy + 25, 15, (30, 30, 62))
    cv.rect(sx, sy + 96, sw, 24, (96, 60, 74))          # city glow haze
    # skyline seen as a silhouette
    base = sy + 122
    dark = (6, 7, 16)
    for bx, bh, bw in ((14, 52, 42), (62, 38, 32), (100, 62, 46), (152, 44, 34),
                       (192, 58, 40), (238, 34, 30), (274, 66, 48), (328, 48, 38),
                       (372, 56, 44), (422, 40, 34)):
        cv.rect(sx + bx, base - bh, bw, bh + 24, dark)
    for wx, wy in ((26, 74), (32, 86), (110, 64), (122, 64), (116, 80), (202, 68),
                   (214, 82), (284, 60), (296, 74), (336, 74), (384, 66), (396, 80)):
        cv.rect(sx + wx, sy + wy, 4, 5, (255, 200, 96))
    # river and the bridge across it
    cv.rect(sx, sy + 126, sw, sh - 126, (12, 20, 46))
    cv.rect(sx, sy + 126, sw, 3, (40, 56, 100))
    for dx in (26, 96, 158, 220, 282, 344, 406, 452):
        cv.rect(sx + dx, sy + 134, 24, 3, (26, 40, 78))
    for tx in (100, 356):
        cv.rect(sx + tx, sy + 74, 12, 62, dark)         # bridge towers
        cv.rect(sx + tx - 3, sy + 70, 18, 6, dark)
    cv.rect(sx, sy + 116, sw, 9, dark)                  # bridge deck
    cv.rect(sx, sy + 116, sw, 2, (58, 58, 70))
    bezier(cv, (sx + 4, sy + 114), (sx + 228, sy + 76), (sx + 476, sy + 114),
           dark, 5, 80)
    bezier(cv, (sx + 106, sy + 74), (sx + 228, sy + 96), (sx + 356, sy + 74),
           dark, 4, 48)
    for hx in (66, 148, 216, 288, 330, 412):
        cv.rect(sx + hx, sy + 92, 2, 24, dark)
    # missile arcs with bursts
    for p0, p1, p2 in (((2, 140), (54, 26), (146, 58)),
                       ((58, 144), (152, 14), (256, 44)),
                       ((306, 142), (356, 44), (424, 62))):
        bezier(cv, (sx + p0[0], sy + p0[1]), (sx + p1[0], sy + p1[1]),
               (sx + p2[0], sy + p2[1]), (246, 146, 44), 4, 56)
        bezier(cv, (sx + p0[0] + 2, sy + p0[1]), (sx + p1[0] + 2, sy + p1[1] - 5),
               (sx + p2[0], sy + p2[1]), (255, 230, 150), 2, 56)
        burst(cv, sx + p2[0], sy + p2[1], 13, (255, 236, 132))


def scene_asia(cv, sx, sy, sw, sh):
    vgrad(cv, sx, sy, sw, sh, (26, 34, 72), (212, 118, 66), 10)
    cv.disc(sx + 352, sy + 118, 36, (255, 192, 122))
    cv.rect(sx, sy + 126, sw, sh - 126, (26, 30, 52))
    cv.rect(sx, sy + 126, sw, 3, (62, 68, 98))
    towers = ((16, 60, 34), (56, 92, 42), (104, 74, 40), (150, 46, 30),
              (186, 68, 38), (230, 88, 44), (280, 62, 36), (322, 74, 40),
              (368, 56, 34), (410, 82, 46))
    for bx, bh, bw in towers:
        cv.rect(sx + bx, sy + 126 - bh, bw, bh, (14, 22, 48))
        cv.rect(sx + bx + bw - 5, sy + 126 - bh, 5, bh, (32, 44, 80))
        for wy in range(sy + 126 - bh + 6, sy + 122, 12):
            cv.rect(sx + bx + 5, wy, 4, 4, (236, 206, 132))
    # three flagpoles with national flags
    for px in (sx + 74, sx + 200, sx + 326):
        cv.rect(px, sy + 52, 3, sh - 60, (202, 208, 222))
        cv.disc(px + 1, sy + 50, 4, (230, 234, 244))
    fl_w, fl_h = 62, 40
    fx, fy = sx + 77, sy + 56                                   # United States
    for i in range(7):
        col = (178, 34, 52) if i % 2 == 0 else (242, 242, 246)
        cv.rect(fx, fy + (fl_h * i) // 7, fl_w,
                (fl_h * (i + 1)) // 7 - (fl_h * i) // 7, col)
    cv.rect(fx, fy, 27, fl_h // 2, (58, 58, 110))
    for gx in range(3, 27, 6):
        for gy in range(3, fl_h // 2 - 2, 6):
            cv.rect(fx + gx, fy + gy, 2, 2, WHITE)
    fx, fy = sx + 203, sy + 56                                  # China
    cv.rect(fx, fy, fl_w, fl_h, (222, 41, 16))
    cv.rect(fx, fy, fl_w, 3, (238, 78, 50))
    star(cv, fx + 17, fy + 15, 13, (255, 222, 0))
    fx, fy = sx + 329, sy + 56                                  # Russia
    third = fl_h // 3
    cv.rect(fx, fy, fl_w, third, (250, 250, 250))
    cv.rect(fx, fy + third, fl_w, third + (fl_h % 3), (0, 57, 166))
    cv.rect(fx, fy + 2 * third + (fl_h % 3), fl_w,
            fl_h - 2 * third - (fl_h % 3), (213, 43, 30))


def scene_justice(cv, sx, sy, sw, sh):
    vgrad(cv, sx, sy, sw, sh, (240, 231, 212), (206, 190, 162), 8)
    ink, gold = (44, 40, 34), (198, 158, 58)
    cx = sx + 240
    cv.rect(cx - 3, sy + 14, 6, 36, ink)
    cv.rect(cx - 60, sy + 16, 120, 5, ink)
    cv.disc(cx, sy + 13, 6, ink)
    cv.poly([(cx - 22, sy + 48), (cx + 22, sy + 48), (cx + 14, sy + 55),
             (cx - 14, sy + 55)], ink)
    for sgn in (-1, 1):
        px = cx + sgn * 58
        cv.rect(px - 1, sy + 21, 2, 16, ink)
        cv.poly([(px - 22, sy + 37), (px + 22, sy + 37), (px + 15, sy + 48),
                 (px - 15, sy + 48)], gold)
        cv.poly([(px - 22, sy + 37), (px + 22, sy + 37), (px + 20, sy + 41),
                 (px - 20, sy + 41)], (150, 116, 34))
    stone_l, stone_m, stone_d = (224, 212, 188), (186, 172, 146), (140, 128, 106)
    cv.poly([(sx + 56, sy + 96), (sx + 240, sy + 62), (sx + 424, sy + 96)], stone_m)
    cv.poly([(sx + 96, sy + 96), (sx + 240, sy + 73), (sx + 384, sy + 96)],
            (206, 194, 170))
    cv.disc(cx, sy + 76, 7, (156, 142, 118))
    cv.rect(sx + 52, sy + 96, 376, 12, stone_l)
    cv.rect(sx + 52, sy + 96, 376, 3, (242, 234, 216))
    for i in range(7):
        px = sx + 74 + i * 52
        cv.rect(px, sy + 110, 26, 34, stone_l)
        cv.rect(px + 20, sy + 110, 6, 34, stone_m)
        cv.rect(px - 3, sy + 107, 32, 4, stone_d)
        cv.rect(px - 3, sy + 143, 32, 4, stone_d)
    cv.rect(sx + 60, sy + 147, 360, 5, stone_m)
    cv.rect(sx + 40, sy + 152, 400, 6, stone_m)
    cv.rect(sx + 20, sy + 158, 440, 6, stone_d)
    cv.rect(sx + 4, sy + 164, 472, 6, (124, 112, 92))


def scene_markets(cv, sx, sy, sw, sh):
    cv.rect(sx, sy, sw, sh, (13, 18, 25))
    for gy in range(sy + 8, sy + 142, 22):
        cv.rect(sx, gy, sw, 1, (30, 38, 50))
    for gx in range(sx + 16, sx + sw, 48):
        cv.rect(gx, sy, 1, sh, (24, 31, 41))
    cv.rect(sx, sy + 112, sw, 32, (7, 10, 15))
    cv.rect(sx, sy + 112, sw, 2, (46, 56, 70))
    base, red, red_hi = sy + 108, (208, 32, 38), (255, 94, 86)
    for i, bh in enumerate((96, 82, 88, 62, 46, 30)):
        bx = sx + 20 + i * 54
        cv.rect(bx, base - bh, 40, bh, red)
        cv.rect(bx, base - bh, 40, 4, red_hi)
        cv.rect(bx, base - bh, 3, bh, red_hi)
    ax = sx + 418
    cv.rect(ax - 6, sy + 2, 12, 78, (255, 58, 58))
    cv.poly([(ax - 28, sy + 76), (ax + 28, sy + 76), (ax, sy + 110)], (255, 58, 58))
    polyline(cv, [(sx + 12, sy + 128), (sx + 96, sy + 136), (sx + 176, sy + 130),
                  (sx + 256, sy + 140), (sx + 336, sy + 135), (sx + 420, sy + 143),
                  (sx + 468, sy + 139)], (255, 100, 100), 3)


def scene_tech(cv, sx, sy, sw, sh):
    cv.rect(sx, sy, sw, sh, (9, 15, 24))
    for gx in range(sx, sx + sw, 32):
        cv.rect(gx, sy, 1, sh, (17, 26, 40))
    for gy in range(sy, sy + sh, 32):
        cv.rect(sx, gy, sw, 1, (17, 26, 40))
    chx, chy, chw, chh = sx + 34, sy + 34, 132, 78
    cv.rect(chx - 4, chy - 4, chw + 8, chh + 8, (26, 40, 60))
    for i in range(5):
        py = chy + 8 + i * 16
        cv.rect(chx - 16, py, 12, 5, (206, 162, 66))
        cv.rect(chx + chw + 4, py, 12, 5, (206, 162, 66))
    for i in range(5):
        px = chx + 12 + i * 26
        cv.rect(px, chy - 16, 5, 12, (206, 162, 66))
        cv.rect(px, chy + chh + 4, 5, 12, (206, 162, 66))
    cv.rect(chx, chy, chw, chh, (28, 96, 68))
    cv.rect(chx + 6, chy + 6, chw - 12, chh - 12, (46, 136, 96))
    cv.rect(chx + 34, chy + 26, chw - 68, chh - 52, (16, 62, 46))
    cv.rect(chx + 12, chy + 12, 10, 10, (154, 218, 180))
    bx0, by = sx + 240, sy + 130
    green, bright = (46, 176, 98), (126, 226, 158)
    for i, bh in enumerate((26, 46, 66, 92)):
        bx = bx0 + i * 46
        cv.rect(bx, by - bh, 33, bh, green)
        cv.rect(bx, by - bh, 33, 4, bright)
        cv.rect(bx, by - bh, 3, bh, bright)
    draw_text(cv, bx0 + 22, sy + 14, 'ANT', 3, (202, 244, 218))
    cv.rect(bx0 - 4, by + 4, 200, 3, (44, 70, 56))


def scene_americas(cv, sx, sy, sw, sh):
    vgrad(cv, sx, sy, sw, sh, (208, 228, 246), (154, 188, 224), 6)
    cv.disc(sx + 96, sy + 42, 52, (230, 240, 250))
    cv.disc(sx + 402, sy + 116, 66, (136, 176, 220))
    cv.rect(sx, sy + 112, sw, 11, (12, 62, 146))
    cv.rect(sx, sy + 123, sw, 10, (248, 249, 251))
    cv.rect(sx, sy + 133, sw, sh - 133, (12, 62, 146))
    cv.disc(sx + 240, sy + 128, 8, (206, 168, 60))
    cv.disc(sx + 240, sy + 128, 4, (248, 249, 251))
    slip_x, slip_y, slip_w, slip_h = sx + 232, sy + 14, 62, 52
    cv.rect(slip_x + 3, slip_y + 3, slip_w, slip_h, (176, 190, 208))
    cv.rect(slip_x, slip_y, slip_w, slip_h, (252, 250, 246))
    cv.rect(slip_x, slip_y, slip_w, 3, (212, 210, 204))
    cv.rect(slip_x + 8, slip_y + 8, 34, 4, (172, 178, 188))
    cv.rect(slip_x + 8, slip_y + 17, 26, 4, (172, 178, 188))
    polyline(cv, [(slip_x + 15, slip_y + 35), (slip_x + 23, slip_y + 43),
                  (slip_x + 42, slip_y + 24)], (22, 126, 60), 4)
    bx, by, bw, bh = sx + 160, sy + 56, 168, 56
    cv.rect(bx + 4, by + 4, bw, bh, (10, 34, 84))
    cv.rect(bx, by, bw, bh, (20, 84, 176))
    cv.rect(bx, by, bw, 6, (58, 126, 214))
    cv.rect(bx, by + 18, bw, 3, (14, 62, 136))
    cv.rect(bx + 56, by - 2, 56, 8, (8, 26, 66))
    cv.rect(bx + 56, by, 56, 5, (4, 14, 40))
    star(cv, bx + 4, by + 10, 7, (250, 250, 250))


STORIES = (
    dict(tag='UKRAINE', chip=(31, 59, 115),
         head='RUSSIA FIRES 100+ MISSILES AT UKRAINE',
         cap="Overnight strike kills eight people and injures at least 28. "
             "Three Kyiv bridges are damaged and power is cut in several regions.",
         scene=scene_ukraine),
    dict(tag='ASIA', chip=(180, 69, 43),
         head='TRUMP, XI AND PUTIN HOLD FIRST TRILATERAL SUMMIT',
         cap="Trump, Xi and Putin meet in Shenzhen at the APEC forum and issue a "
             "Declaration toward Peace, but the Ukraine war talks bring no breakthrough.",
         scene=scene_asia),
    dict(tag='JUSTICE', chip=(74, 58, 125),
         head='WORLD COURT RULES MYANMAR COMMITTED GENOCIDE',
         cap="The International Court of Justice votes 9-6, finding the 2017 "
             "crackdown on the Rohingya in northern Rakhine broke the Genocide Convention.",
         scene=scene_justice),
    dict(tag='MARKETS', chip=(165, 28, 34),
         head='ASIAN MARKETS PLUNGE ON AI BUBBLE FEARS',
         cap="Taiwan's index falls more than 2,200 points in a day to below 37,000, "
             "after shedding over 7,000 points in a week.",
         scene=scene_markets),
    dict(tag='TECH', chip=(15, 122, 90),
         head='ANTHROPIC GOES PUBLIC, FIRST FOR FRONTIER AI',
         cap="The maker of Claude lists on the Nasdaq under the ticker ANT and its "
             "shares rise 17 percent on the first day of trading.",
         scene=scene_tech),
    dict(tag='AMERICAS', chip=(20, 66, 143),
         head='BUKELE BIDS FOR UNPRECEDENTED THIRD TERM',
         cap="El Salvador's president registers for February elections after his party "
             "scrapped term limits; polls put his support at 55 to 70 percent.",
         scene=scene_americas),
)

HEAD_SCALES = (3, 2)
CAP_SCALES = (2, 1)


# --------------------------------------------------------------------------
# page
# --------------------------------------------------------------------------

def draw_masthead(cv):
    cv.rect(0, 0, W, MASTHEAD_H, NAVY)
    cv.rect(0, 0, W, 6, (28, 42, 88))
    cv.rect(0, MASTHEAD_H - 6, W, 6, (9, 15, 36))
    draw_center(cv, W // 2, 18, 'THE WORLD IN ONE IMAGE', 6, WHITE)
    draw_center(cv, W // 2, 74, 'FRIDAY 20 NOVEMBER 2026', 4, GOLD)
    cv.rect(MARGIN + 8, 121, W - 2 * (MARGIN + 8), 4, GOLD)
    cv.rect(MARGIN + 8, 129, W - 2 * (MARGIN + 8), 2, (92, 106, 152))


def draw_chip(cv, x, y, text, col):
    w = text_width(text, 1) + 20
    cv.rect(x, y, w, 18, col)
    draw_text(cv, x + 10, y + 6, text, 1, WHITE)
    return w


def draw_panel(cv, x, y, story):
    cv.rect(x, y, PANEL_W, PANEL_H, PANEL)
    cv.frame(x, y, PANEL_W, PANEL_H, 2, PANEL_EDGE)
    sx, sy = x + 4, y + 4
    cv.set_clip(sx, sy, sx + PANEL_W - 8, sy + SCENE_H)
    story['scene'](cv, sx, sy, PANEL_W - 8, SCENE_H)
    cv.set_clip(0, 0, W, H)
    cv.frame(sx, sy, PANEL_W - 8, SCENE_H, 2, (126, 118, 102))
    draw_chip(cv, x + PAD, y + 156, story['tag'], story['chip'])
    cv.rect(x + PAD, y + 178, TEXT_W, 2, PANEL_EDGE)
    hscale, hlines = fit_text(story['head'], TEXT_W, 2, HEAD_SCALES)
    for i, line in enumerate(hlines):
        draw_text(cv, x + PAD, y + HEAD_TOP + i * 8 * hscale, line, hscale, INK)
    cscale, clines = fit_text(story['cap'], TEXT_W, 2, CAP_SCALES)
    cap_top = HEAD_TOP + (len(hlines) - 1) * 8 * hscale + 7 * hscale + 10
    for i, line in enumerate(clines):
        draw_text(cv, x + PAD, y + cap_top + i * 8 * cscale, line, cscale, CAPTION)


def draw_footer(cv):
    cv.rect(0, FOOTER_TOP, W, H - FOOTER_TOP, PAPER)
    cv.rect(MARGIN, FOOTER_TOP + 4, W - 2 * MARGIN, 2, INK)
    draw_center(cv, W // 2, FOOTER_TOP + 11,
                'SOURCES: REUTERS - AP - AFP - 20 NOVEMBER 2026', 1, INK)


def build():
    cv = Canvas(W, H, PAPER)
    draw_masthead(cv)
    for i, story in enumerate(STORIES):
        x = MARGIN + (i % 2) * (PANEL_W + GUTTER)
        y = GRID_TOP + (i // 2) * (PANEL_H + GUTTER)
        draw_panel(cv, x, y, story)
    draw_footer(cv)
    return cv.to_png()


def main():
    data = build()
    out_dir = os.environ.get('MAKEFUN_OUTPUT_DIR', '/output')
    if not os.path.isdir(out_dir):
        os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, 'entry.png')
    with open(path, 'wb') as fh:
        fh.write(data)
    sys.stdout.write('wrote %s (%d bytes)\n' % (path, len(data)))


if __name__ == '__main__':
    main()
