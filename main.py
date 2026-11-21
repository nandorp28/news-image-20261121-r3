#!/usr/bin/env python3
"""Saturday 21 November 2026 world news in one image (make.fun news-image-20261121, round 3).

Draws a dense illustrated front page: 50 sourced stories, 7 regions, 16 fields,
3 hero illustrations, 10 illustrated secondary cards, a world map with numbered
pins, a UTC timeline, a numbers strip and a DATE CHECK footer. Pure stdlib.
Deterministic: fixed seeds, no timestamps, byte-identical runs.
"""
import os
import random
import struct
import zlib

W, H = 1024, 1024

# ---------------------------------------------------------------- PNG writer
def _chunk(kind, data):
    out = struct.pack(">I", len(data)) + kind + data
    return out + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def write_png(path, px, w, h):
    """px: bytes-like RGB buffer, w*h*3. Per-row filter pick (None/Sub/Up)."""
    raw = bytearray()
    stride = w * 3
    prev = bytes(stride)
    for y in range(h):
        row = bytes(px[y * stride:(y + 1) * stride])
        cands = []
        cands.append(b"\x00" + row)
        sub = bytearray(row)
        for i in range(3, stride):
            sub[i] = (row[i] - row[i - 3]) & 0xFF
        cands.append(b"\x01" + bytes(sub))
        up = bytes((row[i] - prev[i]) & 0xFF for i in range(stride))
        cands.append(b"\x02" + up)

        def cost(b):
            s = 0
            for v in b[1:]:
                s += v if v < 128 else 256 - v
            return s

        raw += min(cands, key=cost)
        prev = row
    data = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


# ------------------------------------------------------------------ canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bytes(bg) * (w * h))

    def put(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i + 3] = bytes(c)

    def get(self, x, y):
        i = (y * self.w + x) * 3
        return self.px[i], self.px[i + 1], self.px[i + 2]

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def frame(self, x, y, w, h, c, t=1):
        self.rect(x, y, w, t, c)
        self.rect(x, y + h - t, w, t, c)
        self.rect(x, y, t, h, c)
        self.rect(x + w - t, y, t, h, c)

    def hline(self, x, y, w, c):
        self.rect(x, y, w, 1, c)

    def vline(self, x, y, h, c):
        self.rect(x, y, 1, h, c)

    def line(self, x0, y0, x1, y1, c):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        while True:
            self.put(x0, y0, c)
            if x0 == x1 and y0 == y1:
                return
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x0 += sx
            if e2 < dx:
                err += dx
                y0 += sy

    def circle(self, cx, cy, r, c, fill=True):
        if fill:
            for yy in range(cy - r, cy + r + 1):
                for xx in range(cx - r, cx + r + 1):
                    if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                        self.put(xx, yy, c)
        else:
            for a in range(360):
                import math
                self.put(cx + int(r * math.cos(math.radians(a))),
                         cy + int(r * math.sin(math.radians(a))), c)

    def ellipse(self, cx, cy, rx, ry, c):
        for yy in range(cy - ry, cy + ry + 1):
            for xx in range(cx - rx, cx + rx + 1):
                if ((xx - cx) / max(1, rx)) ** 2 + ((yy - cy) / max(1, ry)) ** 2 <= 1:
                    self.put(xx, yy, c)

    def tri(self, pts, c):
        self.poly(pts, c)

    def poly(self, pts, c):
        if not pts:
            return
        ys = [p[1] for p in pts]
        for yy in range(min(ys), max(ys) + 1):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= yy < y1) or (y1 <= yy < y0):
                    xs.append(x0 + (yy - y0) * (x1 - x0) / (y1 - y0))
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.hline(int(xs[i]), yy, max(1, int(xs[i + 1]) - int(xs[i])), c)

    def vgrad(self, x, y, w, h, top, bot):
        for yy in range(h):
            t = yy / max(1, h - 1)
            c = tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3))
            self.rect(x, y + yy, w, 1, c)

    def speckle(self, x, y, w, h, rng, colors, n, size=1):
        for _ in range(n):
            px = rng.randrange(x, x + w)
            py = rng.randrange(y, y + h)
            self.rect(px, py, size, size, rng.choice(colors))

    def hatch(self, x, y, w, h, c, step=4, diag=1):
        for yy in range(y, y + h, step):
            for xx in range(x, x + w, step):
                if diag:
                    self.put(xx + (yy - y) % step, yy, c)
                else:
                    self.put(xx, yy, c)


# -------------------------------------------------------------------- font
# 5x7 bitmap font, one glyph per line, '#' = ink. Written from scratch.
FONT = {
    'A': ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    'B': ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    'C': ("01111", "10000", "10000", "10000", "10000", "10000", "01111"),
    'D': ("11100", "10010", "10001", "10001", "10001", "10010", "11100"),
    'E': ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    'F': ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    'G': ("01111", "10000", "10000", "10111", "10001", "10001", "01110"),
    'H': ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    'I': ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    'J': ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    'K': ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    'L': ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    'M': ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    'N': ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    'O': ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    'P': ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    'Q': ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    'R': ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    'S': ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    'T': ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    'U': ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    'V': ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    'W': ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    'X': ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    'Y': ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    'Z': ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    '0': ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    '1': ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    '2': ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
    '3': ("01110", "10001", "00001", "00110", "00001", "10001", "01110"),
    '4': ("00010", "00110", "01010", "10001", "11111", "00010", "00010"),
    '5': ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    '6': ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
    '7': ("11111", "00001", "00010", "00010", "00100", "00100", "00100"),
    '8': ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    '9': ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
}

# lowercase (x-height rows 2..6, ascenders where needed)
FONT.update({
    'a': ("00000", "00000", "01110", "00001", "01111", "10001", "01111"),
    'b': ("10000", "10000", "11110", "10001", "10001", "10001", "11110"),
    'c': ("00000", "00000", "01111", "10000", "10000", "10000", "01111"),
    'd': ("00001", "00001", "01111", "10001", "10001", "10001", "01111"),
    'e': ("00000", "00000", "01110", "10001", "11111", "10000", "01110"),
    'f': ("00110", "01001", "01000", "11100", "01000", "01000", "01000"),
    'g': ("00000", "01110", "10001", "10001", "01111", "00001", "01110"),
    'h': ("10000", "10000", "11110", "10001", "10001", "10001", "10001"),
    'i': ("00100", "00000", "01100", "00100", "00100", "00100", "01110"),
    'j': ("00010", "00000", "00110", "00010", "00010", "10010", "01100"),
    'k': ("10000", "10000", "10010", "10100", "11000", "10100", "10010"),
    'l': ("01100", "00100", "00100", "00100", "00100", "00100", "01110"),
    'm': ("00000", "00000", "11010", "10101", "10101", "10101", "10101"),
    'n': ("00000", "00000", "11110", "10001", "10001", "10001", "10001"),
    'o': ("00000", "00000", "01110", "10001", "10001", "10001", "01110"),
    'p': ("00000", "00000", "11110", "10001", "10001", "11110", "10000"),
    'q': ("00000", "00000", "01111", "10001", "10001", "01111", "00001"),
    'r': ("00000", "00000", "10110", "11001", "10000", "10000", "10000"),
    's': ("00000", "00000", "01111", "10000", "01110", "00001", "11110"),
    't': ("01000", "01000", "11100", "01000", "01000", "01001", "00110"),
    'u': ("00000", "00000", "10001", "10001", "10001", "10011", "01101"),
    'v': ("00000", "00000", "10001", "10001", "10001", "01010", "00100"),
    'w': ("00000", "00000", "10001", "10101", "10101", "10101", "01010"),
    'x': ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    'y': ("00000", "00000", "10001", "10001", "10011", "01110", "00010"),
    'z': ("00000", "00000", "11111", "00010", "00100", "01000", "11111"),
})

FONT.update({
    ' ': ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    '.': ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ',': ("00000", "00000", "00000", "00000", "00100", "00100", "01000"),
    ':': ("00000", "00000", "00100", "00000", "00100", "00000", "00000"),
    ';': ("00000", "00000", "00100", "00000", "00100", "00100", "01000"),
    '!': ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    '?': ("01110", "10001", "00001", "00010", "00100", "00000", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "01010", "00000", "00000", "00000", "00000"),
    '(': ("00010", "00100", "00100", "00100", "00100", "00100", "00010"),
    ')': ("01000", "00100", "00100", "00100", "00100", "00100", "01000"),
    '-': ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    '/': ("00001", "00001", "00010", "00010", "00100", "00100", "01000"),
    '+': ("00000", "00000", "00100", "00100", "11111", "00100", "00100"),
    '%': ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    '&': ("01100", "10010", "10010", "01010", "00100", "10100", "01101"),
    '$': ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    '#': ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    '@': ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    '*': ("00000", "01010", "00100", "11111", "00100", "01010", "00000"),
    '=': ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    '_': ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    '<': ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    '>': ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    '[': ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    ']': ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    '|': ("00100", "00100", "00100", "00100", "00100", "00100", "00100"),
    '~': ("00000", "00000", "01101", "10110", "00000", "00000", "00000"),
    '^': ("00100", "01010", "00000", "00000", "00000", "00000", "00000"),
    '`': ("01000", "00100", "00000", "00000", "00000", "00000", "00000"),
    '\u2019': ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '\u00b7': ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
    '\u2014': ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    '\u00d7': ("00000", "00000", "10001", "01010", "00100", "01010", "10001"),
    '\u2192': ("00000", "00000", "00100", "00010", "11111", "00010", "00100"),
    '\u25cf': ("00000", "01110", "11111", "11111", "11111", "01110", "00000"),
})


def text_w(s, scale):
    return len(s) * 6 * scale


def draw_text(cv, x, y, s, scale, color, bold=False):
    cx = x
    for ch in s:
        g = FONT.get(ch, FONT[' '])
        for r in range(7):
            row = g[r]
            for c in range(5):
                if row[c] == '1':
                    cv.rect(cx + c * scale, y + r * scale, scale, scale, color)
                    if bold:
                        cv.rect(cx + c * scale + 1, y + r * scale, scale, scale, color)
        cx += 6 * scale
    return cx


def draw_text_center(cv, cx, y, s, scale, color, bold=False):
    draw_text(cv, cx - text_w(s, scale) // 2, y, s, scale, color, bold)


def wrap(s, width):
    """Word-wrap a string into lines of at most `width` characters."""
    words, lines, cur = s.split(), [], ""
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > width:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd) if cur else wd
    if cur:
        lines.append(cur)
    return lines


# ------------------------------------------------------- illustration kit
def sky_grad(cv, x, y, w, h, top, bot):
    cv.vgrad(x, y, w, h, top, bot)


def stars(cv, x, y, w, h, rng, n, color=(255, 255, 255)):
    for _ in range(n):
        px, py = rng.randrange(x, x + w), rng.randrange(y, y + h)
        cv.put(px, py, color)
        if rng.random() < 0.3:
            cv.put(px + 1, py, color)


def skyline(cv, x, y, w, h, rng, cols, win_c, ground_y):
    """Row of buildings with lit windows, bases on ground_y."""
    bx = x
    while bx < x + w - 8:
        bw = rng.randrange(10, 26)
        bh = rng.randrange(h // 3, h)
        col = rng.choice(cols)
        cv.rect(bx, ground_y - bh, bw, bh, col)
        cv.rect(bx, ground_y - bh, bw, 2, tuple(min(255, c + 30) for c in col))
        for wy in range(ground_y - bh + 4, ground_y - 3, 6):
            for wx in range(bx + 2, bx + bw - 3, 5):
                if rng.random() < 0.72:
                    cv.rect(wx, wy, 2, 3, win_c)
        if rng.random() < 0.3:
            cv.rect(bx + bw // 2 - 1, ground_y - bh - 5, 2, 5, col)
            cv.put(bx + bw // 2, ground_y - bh - 6, (255, 60, 60))
        bx += bw + rng.randrange(1, 4)


def waves(cv, x, y, w, h, rng, c1, c2):
    for row in range(0, h, 3):
        yy = y + row
        for xx in range(x, x + w, 2):
            import math
            off = int(2 * math.sin((xx - x) / 9.0 + row / 2.0))
            if (xx + row) % 4 == 0:
                cv.put(xx, yy + off, c1 if row % 6 == 0 else c2)


def crowd(cv, x, y, w, h, rng, cols):
    for _ in range(w * h // 6):
        px, py = rng.randrange(x, x + w), rng.randrange(y, y + h)
        cv.circle(px, py, rng.choice([1, 1, 2]), rng.choice(cols))


def trees(cv, x, y, w, h, rng, trunk, leaf):
    bx = x
    while bx < x + w:
        th = rng.randrange(h // 2, h)
        tw = rng.randrange(6, 12)
        cv.rect(bx + tw // 2 - 1, y + h - th // 3, 2, th // 3, trunk)
        cv.tri([(bx, y + h - th // 3), (bx + tw, y + h - th // 3),
                (bx + tw // 2, y + h - th)], leaf)
        cv.tri([(bx + 1, y + h - th // 2), (bx + tw - 1, y + h - th // 2),
                (bx + tw // 2, y + h - th + 4)],
               tuple(min(255, c + 18) for c in leaf))
        bx += tw + rng.randrange(1, 4)


def flag_rect(cv, x, y, w, h, stripes):
    """Horizontal stripes, list of colors top to bottom."""
    n = len(stripes)
    for i, c in enumerate(stripes):
        cv.rect(x, y + i * h // n, w, h // n + 1, c)


def chart_grid(cv, x, y, w, h, c):
    for gx in range(x, x + w + 1, max(6, w // 16)):
        cv.vline(gx, y, h, c)
    for gy in range(y, y + h + 1, max(6, h // 10)):
        cv.hline(x, gy, w, c)


def polyline(cv, pts, c, thick=1):
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], c)
        if thick > 1:
            cv.line(pts[i][0], pts[i][1] + 1, pts[i + 1][0], pts[i + 1][1] + 1, c)


def burst(cv, cx, cy, r, c1, c2, rng):
    for _ in range(26):
        a = rng.uniform(0, 6.283)
        rr = rng.uniform(r * 0.3, r)
        import math
        ex, ey = cx + int(rr * math.cos(a)), cy + int(rr * math.sin(a))
        cv.line(cx, cy, ex, ey, c1 if rng.random() < 0.6 else c2)
    cv.circle(cx, cy, max(2, r // 3), c2)


# ------------------------------------------------------------------ heroes
def art_markets(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (10, 18, 38), (16, 28, 58))
    chart_grid(cv, x + 6, y + 8, w - 12, h - 30, (40, 60, 100))
    # plunging line + area fill
    pts = []
    n = 26
    for i in range(n + 1):
        px = x + 8 + i * (w - 16) // n
        drop = (i / n) ** 1.6 * (h - 44) + rng.uniform(-3, 3)
        py = y + 12 + int(drop)
        pts.append((px, py))
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], (255, 70, 60))
        cv.line(pts[i][0], pts[i][1] + 1, pts[i + 1][0], pts[i + 1][1] + 1, (255, 70, 60))
    for i, (px, py) in enumerate(pts):
        if i % 2 == 0:
            cv.circle(px, py, 2, (255, 200, 190))
    # candlesticks
    for i in range(9):
        cx0 = x + 14 + i * (w - 28) // 9
        top = y + 16 + i * (h - 52) // 9
        cv.rect(cx0, top, 7, rng.randrange(8, 20), (220, 60, 50))
        cv.vline(cx0 + 3, top - 5, rng.randrange(18, 30), (255, 120, 110))
    # big red tag
    cv.rect(x + 8, y + h - 26, 118, 20, (198, 40, 40))
    draw_text(cv, x + 14, y + h - 22, "S&P -3.7%", 2, (255, 255, 255), True)
    draw_text(cv, x + 132, y + h - 21, "NASDAQ -5.3%  NIKKEI -5.1%", 1, (255, 210, 200))
    cv.speckle(x, y, w, h, rng, [(60, 90, 140), (30, 50, 90)], 600)


def art_kryvyi(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (8, 10, 28), (40, 26, 40))
    stars(cv, x, y, w, h // 2, rng, 140, (220, 220, 255))
    # moon + glow
    cv.circle(x + w - 34, y + 22, 13, (240, 235, 200))
    cv.circle(x + w - 38, y + 18, 11, (60, 45, 60))
    # searchlight beams
    for bx0, ang in ((x + 40, -28), (x + w // 2, -12), (x + w - 60, 18)):
        import math
        ex = bx0 + int(120 * math.sin(math.radians(ang)))
        cv.line(bx0, y + h - 20, ex, y + 4, (200, 200, 140))
        cv.line(bx0 + 2, y + h - 20, ex + 2, y + 4, (160, 160, 110))
    gy = y + h - 18
    skyline(cv, x, y + 20, w, h - 38, rng, [(20, 18, 34), (28, 24, 44), (16, 14, 28)],
            (255, 200, 90), gy)
    cv.rect(x, gy, w, h - (gy - y), (12, 10, 20))
    # fires
    for fx in (x + 55, x + w // 2 + 20, x + w - 70):
        burst(cv, fx, gy - rng.randrange(6, 22), 14, (255, 150, 40), (255, 230, 120), rng)
        cv.ellipse(fx, gy - 4, 22, 6, (255, 120, 30))
    # smoke columns
    for sx in (x + 90, x + w - 110):
        for i in range(10):
            cv.circle(sx + rng.randrange(-6, 6), gy - 14 - i * 5, 5 + i // 2,
                      (70, 60, 70) if i % 2 else (90, 78, 84))
    # drones
    for _ in range(8):
        dx, dy = rng.randrange(x + 10, x + w - 10), rng.randrange(y + 8, y + h // 2)
        cv.rect(dx - 3, dy, 7, 1, (200, 200, 200))
        cv.put(dx, dy, (255, 60, 60))
        cv.put(dx, dy + 2, (255, 60, 60))
    cv.rect(x + 8, y + 8, 150, 16, (160, 30, 30))
    draw_text(cv, x + 12, y + 11, "2 KILLED, 60 WOUNDED", 1, (255, 255, 255), True)
    cv.speckle(x, y, w, h, rng, [(50, 40, 70), (25, 22, 45)], 400)


def art_poland(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (214, 228, 240), (170, 196, 218))
    # stylised map: Poland blob + neighbours
    cv.poly([(x + 60, y + 18), (x + 190, y + 10), (x + 250, y + 34), (x + 262, y + 70),
             (x + 210, y + 96), (x + 130, y + 104), (x + 70, y + 84), (x + 48, y + 48)],
            (236, 232, 210))
    cv.poly([(x + 48, y + 48), (x + 70, y + 84), (x + 60, y + 110), (x + 20, y + 108),
             (x + 8, y + 70)], (200, 214, 190))
    cv.poly([(x + 250, y + 34), (x + 300, y + 22), (x + 312, y + 60), (x + 262, y + 70)],
            (214, 200, 190))
    # rivers
    cv.line(x + 90, y + 30, x + 120, y + 100, (120, 170, 210))
    cv.line(x + 170, y + 22, x + 185, y + 92, (120, 170, 210))
    # cities
    for cx0, cy0, nm in ((130, 62, "WARSAW"), (90, 44, "POZNAN"), (200, 70, "LUBLIN"),
                         (160, 30, "GDANSK")):
        cv.circle(x + cx0, y + cy0, 3, (40, 40, 40))
        draw_text(cv, x + cx0 + 6, y + cy0 - 3, nm, 1, (40, 40, 40))
    # missile impact markers with trails
    for ix, iy in ((225, 58), (238, 74), (205, 84)):
        cv.line(x + ix + 26, y + iy - 26, x + ix, y + iy, (200, 40, 30))
        burst(cv, x + ix, y + iy, 9, (220, 60, 40), (255, 200, 60), rng)
        cv.circle(x + ix, y + iy, 3, (160, 20, 20))
    # NATO compass star
    sx, sy = x + 44, y + h - 34
    cv.circle(sx, sy, 14, (20, 60, 120))
    for dx0, dy0 in ((0, -11), (0, 11), (-11, 0), (11, 0)):
        cv.line(sx, sy, sx + dx0, sy + dy0, (255, 255, 255))
        cv.line(sx, sy, sx + dx0 // 2, sy + dy0 // 2, (255, 255, 255))
    draw_text(cv, sx + 20, sy - 4, "NATO: 'SERIOUS", 1, (20, 50, 100), True)
    draw_text(cv, sx + 20, sy + 5, "VIOLATION'", 1, (20, 50, 100), True)
    # Polish flag
    flag_rect(cv, x + w - 58, y + 10, 46, 24, [(255, 255, 255), (220, 20, 60)])
    cv.frame(x + w - 58, y + 10, 46, 24, (60, 60, 60))
    cv.speckle(x, y, w, h, rng, [(190, 205, 220), (225, 220, 200)], 500)


# ------------------------------------------------------- secondary scenes
def art_mexico(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (255, 196, 110), (255, 226, 170))
    cv.circle(x + w - 28, y + 14, 12, (255, 240, 180))
    cv.poly([(x, y + h - 26), (x + 40, y + 22), (x + 80, y + h - 26)], (170, 120, 70))
    cv.poly([(x + 60, y + h - 26), (x + 120, y + 14), (x + 180, y + h - 26)], (150, 100, 60))
    cv.rect(x, y + h - 22, w, 22, (196, 150, 90))
    cv.hline(x, y + h - 22, w, (140, 100, 55))
    for cx0 in (x + 20, x + 90, x + 160):
        cv.rect(cx0, y + h - 40, 4, 18, (40, 130, 60))
        cv.rect(cx0 - 5, y + h - 34, 4, 6, (40, 130, 60))
        cv.rect(cx0 + 5, y + h - 36, 4, 6, (40, 130, 60))
    # helicopter
    hx, hy = x + w // 2, y + 12
    cv.rect(hx - 22, hy, 44, 2, (60, 60, 60))
    cv.ellipse(hx, hy + 6, 12, 5, (70, 70, 70))
    cv.rect(hx + 10, hy + 5, 14, 2, (70, 70, 70))
    cv.rect(x + 6, y + h - 18, 64, 12, (120, 30, 30))
    draw_text(cv, x + 9, y + h - 16, "CAPTURED", 1, (255, 255, 255), True)
    cv.speckle(x, y, w, h, rng, [(230, 180, 120), (255, 210, 150)], 350)


def art_cop31(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (200, 230, 245), (150, 200, 225))
    # globe
    gx, gy, gr = x + 34, y + h // 2, 24
    cv.circle(gx, gy, gr, (60, 140, 210))
    cv.ellipse(gx - 8, gy - 8, 9, 6, (80, 180, 90))
    cv.ellipse(gx + 9, gy + 8, 8, 6, (80, 180, 90))
    cv.ellipse(gx + 4, gy - 12, 6, 5, (80, 180, 90))
    cv.circle(gx, gy, gr, (30, 80, 140), fill=False)
    cv.vline(gx, gy - gr, 2 * gr, (30, 80, 140))
    cv.hline(gx - gr, gy, 2 * gr, (30, 80, 140))
    # flame
    fx, fy = x + w - 30, y + 12
    cv.tri([(fx, fy + 16), (fx + 14, fy + 16), (fx + 7, fy)], (255, 120, 20))
    cv.tri([(fx + 3, fy + 16), (fx + 11, fy + 16), (fx + 7, fy + 6)], (255, 220, 60))
    # draft text struck through
    cv.rect(x + 66, y + 8, w - 76, 26, (255, 255, 255))
    cv.frame(x + 66, y + 8, w - 76, 26, (120, 120, 120))
    draw_text(cv, x + 70, y + 11, "DRAFT", 1, (160, 30, 30), True)
    draw_text(cv, x + 70, y + 21, "FOSSIL FUELS", 1, (40, 40, 40), True)
    cv.line(x + 69, y + 25, x + w - 12, y + 25, (200, 30, 30))
    cv.line(x + 69, y + 26, x + w - 12, y + 26, (200, 30, 30))
    cv.rect(x + 66, y + 38, 78, 14, (200, 60, 20))
    draw_text(cv, x + 70, y + 41, "OVERTIME", 1, (255, 255, 255), True)
    cv.speckle(x, y, w, h, rng, [(170, 210, 235), (220, 240, 250)], 350)


def art_denmark(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (240, 240, 235), (210, 210, 200))
    # Danish flag
    cv.rect(x + 8, y + 8, 64, 34, (200, 20, 50))
    cv.rect(x + 8 + 20, y + 8, 8, 34, (255, 255, 255))
    cv.rect(x + 8, y + 8 + 13, 64, 8, (255, 255, 255))
    cv.frame(x + 8, y + 8, 64, 34, (100, 100, 100))
    # gavel
    cv.rect(x + 96, y + 12, 34, 10, (120, 80, 40))
    cv.rect(x + 108, y + 22, 6, 22, (120, 80, 40))
    cv.rect(x + 92, y + 44, 42, 5, (100, 65, 30))
    cv.rect(x + 140, y + 12, 8, 10, (90, 60, 30))
    # figure with suitcase leaving
    fx, fy = x + w - 34, y + h - 30
    cv.circle(fx, fy - 12, 5, (230, 190, 150))
    cv.rect(fx - 5, fy - 6, 10, 14, (40, 60, 120))
    cv.line(fx - 4, fy + 8, fx - 7, fy + 18, (40, 40, 40))
    cv.line(fx + 4, fy + 8, fx + 8, fy + 18, (40, 40, 40))
    cv.rect(fx + 10, fy + 2, 12, 9, (120, 70, 30))
    cv.rect(fx + 13, fy, 6, 3, (120, 70, 30))
    cv.rect(x + 8, y + h - 16, 92, 12, (160, 20, 40))
    draw_text(cv, x + 12, y + h - 14, "7 DAYS TO LEAVE", 1, (255, 255, 255), True)
    cv.speckle(x, y, w, h, rng, [(225, 225, 215), (200, 200, 190)], 350)


def art_hormuz(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (255, 200, 130), (255, 230, 190))
    cv.circle(x + 26, y + 16, 12, (255, 240, 170))
    # sea
    cv.rect(x, y + h - 26, w, 26, (30, 110, 170))
    waves(cv, x, y + h - 26, w, 26, rng, (120, 200, 240), (70, 160, 210))
    # tanker
    tx, ty = x + 18, y + h - 34
    cv.poly([(tx, ty), (tx + 110, ty), (tx + 102, ty + 12), (tx + 8, ty + 12)],
            (90, 40, 30))
    cv.rect(tx + 12, ty - 12, 22, 12, (200, 200, 200))
    cv.rect(tx + 40, ty - 8, 14, 8, (160, 160, 160))
    cv.rect(tx + 62, ty - 14, 10, 14, (140, 40, 30))
    cv.vline(tx + 66, ty - 22, 8, (60, 60, 60))
    # fire + smoke on deck
    burst(cv, tx + 88, ty - 4, 12, (255, 140, 30), (255, 220, 100), rng)
    for i in range(6):
        cv.circle(tx + 88 + rng.randrange(-4, 8), ty - 12 - i * 5, 4 + i,
                  (80, 80, 80) if i % 2 else (110, 110, 110))
    cv.rect(x + w - 92, y + 6, 86, 14, (160, 30, 30))
    draw_text(cv, x + w - 88, y + 9, "TANKER ON FIRE", 1, (255, 255, 255), True)
    cv.speckle(x, y, w, h, rng, [(255, 215, 160), (240, 190, 140)], 350)


def art_ukeu(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (235, 238, 245), (205, 215, 230))
    # Union Jack (simplified)
    ux, uy, uw, uh = x + 8, y + 8, 56, 32
    cv.rect(ux, uy, uw, uh, (30, 60, 140))
    cv.line(ux, uy, ux + uw, uy + uh, (255, 255, 255))
    cv.line(ux + uw, uy, ux, uy + uh, (255, 255, 255))
    cv.line(ux, uy, ux + uw, uy + uh, (200, 30, 50))
    cv.rect(ux + uw // 2 - 4, uy, 8, uh, (255, 255, 255))
    cv.rect(ux, uy + uh // 2 - 4, uw, 8, (255, 255, 255))
    cv.rect(ux + uw // 2 - 2, uy, 4, uh, (200, 30, 50))
    cv.rect(ux, uy + uh // 2 - 2, uw, 4, (200, 30, 50))
    cv.frame(ux, uy, uw, uh, (80, 80, 80))
    # EU flag
    ex, ey, ew, eh = x + w - 64, y + 8, 56, 32
    cv.rect(ex, ey, ew, eh, (20, 50, 140))
    import math
    for k in range(12):
        a = k * 30 * math.pi / 180
        cv.put(int(ex + ew / 2 + 18 * math.cos(a)), int(ey + eh / 2 + 11 * math.sin(a)),
               (255, 220, 60))
    cv.frame(ex, ey, ew, eh, (80, 80, 80))
    # handshake arcs
    cv.line(x + 70, y + 24, x + w - 70, y + 24, (40, 120, 60))
    cv.line(x + 70, y + 26, x + w - 70, y + 26, (40, 120, 60))
    cv.circle(x + w // 2 - 12, y + 25, 5, (230, 190, 150))
    cv.circle(x + w // 2 + 12, y + 25, 5, (200, 160, 120))
    draw_text(cv, x + 8, y + h - 26, "100,000", 2, (20, 100, 50), True)
    draw_text(cv, x + 8, y + h - 12, "YOUTH PLACES A YEAR", 1, (40, 40, 40))
    cv.speckle(x, y, w, h, rng, [(220, 225, 235), (200, 210, 225)], 350)


def art_chips(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (16, 32, 48), (24, 48, 70))
    # circuit traces
    for _ in range(14):
        tx0 = rng.randrange(x + 4, x + w - 30)
        ty0 = rng.randrange(y + 4, y + h - 4)
        ln = rng.randrange(10, 30)
        if rng.random() < 0.5:
            cv.hline(tx0, ty0, ln, (60, 140, 120))
            cv.put(tx0 + ln, ty0, (90, 200, 170))
        else:
            cv.vline(tx0, ty0, ln, (60, 140, 120))
            cv.put(tx0, ty0 + ln, (90, 200, 170))
    # chip
    cx, cy, cw, ch = x + w // 2 - 34, y + 8, 68, 34
    cv.rect(cx, cy, cw, ch, (30, 30, 34))
    cv.frame(cx, cy, cw, ch, (180, 180, 190), 2)
    for px in range(cx + 6, cx + cw - 4, 10):
        cv.vline(px, cy - 5, 5, (180, 180, 190))
        cv.vline(px, cy + ch, 5, (180, 180, 190))
    for py in range(cy + 6, cy + ch - 4, 10):
        cv.hline(cx - 5, py, 5, (180, 180, 190))
        cv.hline(cx + cw, py, 5, (180, 180, 190))
    draw_text(cv, cx + 20, cy + 8, "H200", 2, (120, 230, 190), True)
    draw_text(cv, cx + 8, cy + 24, "AI CHIP", 1, (160, 160, 170))
    # blocked sign
    bx, by = x + w - 26, y + h - 26
    cv.circle(bx, by, 11, (200, 30, 30))
    cv.circle(bx, by, 8, (16, 32, 48))
    cv.line(bx - 7, by + 7, bx + 7, by - 7, (200, 30, 30))
    cv.line(bx - 7, by + 6, bx + 7, by - 8, (200, 30, 30))
    draw_text(cv, x + 8, y + h - 14, "REMOTE ACCESS SHUT", 1, (255, 200, 180), True)
    cv.speckle(x, y, w, h, rng, [(40, 70, 95), (20, 40, 60)], 400)


def art_geneva(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (230, 238, 245), (190, 210, 225))
    # flags row
    fcols = [(200, 30, 50), (20, 80, 160), (30, 140, 60), (230, 180, 40),
             (120, 40, 140), (20, 120, 140), (220, 100, 30), (40, 40, 40)]
    for i, fc in enumerate(fcols):
        fx = x + 8 + i * 21
        cv.vline(fx, y + 8, 26, (120, 120, 120))
        cv.rect(fx + 1, y + 8, 16, 11, fc)
        cv.rect(fx + 1, y + 19, 16, 3, (255, 255, 255))
    # robot (right side, clear of the text)
    rx, ry = x + w - 52, y + 20
    cv.rect(rx, ry, 28, 20, (150, 160, 170))
    cv.frame(rx, ry, 28, 20, (80, 90, 100))
    cv.rect(rx + 5, ry + 6, 6, 6, (40, 200, 220))
    cv.rect(rx + 17, ry + 6, 6, 6, (40, 200, 220))
    cv.vline(rx + 14, ry - 6, 6, (80, 90, 100))
    cv.circle(rx + 14, ry - 7, 3, (220, 60, 60))
    cv.rect(rx + 4, ry + 20, 20, 3, (80, 90, 100))
    draw_text(cv, x + 8, y + h - 24, "128 NATIONS", 2, (20, 70, 120), True)
    draw_text(cv, x + 8, y + h - 10, "KILLER-ROBOT RULES", 1, (40, 40, 40))
    cv.speckle(x, y, w, h, rng, [(210, 222, 235), (180, 200, 218)], 300)


def art_dengue(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (220, 245, 220), (170, 220, 175))
    # Brazil stripes
    cv.rect(x, y, w, 6, (30, 160, 60))
    cv.rect(x, y + h - 6, w, 6, (250, 210, 40))
    # mosquito
    mx, my = x + 30, y + 26
    cv.ellipse(mx, my, 12, 5, (90, 70, 50))
    cv.circle(mx + 12, my - 1, 4, (90, 70, 50))
    cv.line(mx + 15, my - 1, mx + 24, my - 4, (60, 50, 40))
    for a, b in ((-8, -10), (0, -12), (8, -10)):
        cv.line(mx + a, my - 2, mx + a + 4, my + b, (70, 60, 50))
    cv.ellipse(mx - 2, my - 8, 10, 4, (200, 220, 235))
    cv.ellipse(mx + 6, my - 9, 9, 4, (200, 220, 235))
    for lx in range(mx - 14, mx + 16, 4):
        cv.vline(lx, my + 4, 6, (70, 60, 50))
    # falling bars
    bars = [34, 30, 24, 18, 12]
    for i, bh in enumerate(bars):
        bx = x + w - 78 + i * 15
        cv.rect(bx, y + h - 12 - bh, 11, bh, (30, 140, 80) if i < 4 else (200, 40, 40))
    cv.line(x + w - 80, y + h - 12 - 34, x + w - 6, y + h - 12 - 12, (180, 30, 30))
    draw_text(cv, x + w - 76, y + 6, "-69%", 2, (180, 30, 30), True)
    cv.speckle(x, y, w, h, rng, [(190, 230, 195), (210, 240, 210)], 350)


def art_rahul(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (140, 200, 120), (90, 170, 80))
    # pitch
    cv.rect(x + 30, y + 8, w - 60, h - 16, (220, 200, 150))
    cv.rect(x + 30, y + 8, w - 60, 3, (255, 255, 255))
    cv.rect(x + 30, y + h - 11, w - 60, 3, (255, 255, 255))
    # stumps
    for sx in (x + 44, x + 49, x + 54):
        cv.vline(sx, y + 12, 14, (240, 220, 120))
    for sx in (x + w - 54, x + w - 49, x + w - 44):
        cv.vline(sx, y + 12, 14, (240, 220, 120))
    # bat + ball
    cv.line(x + 78, y + 40, x + 100, y + 16, (150, 110, 60))
    cv.line(x + 79, y + 40, x + 101, y + 16, (150, 110, 60))
    cv.rect(x + 96, y + 12, 10, 8, (170, 130, 70))
    cv.circle(x + w - 70, y + 34, 5, (200, 40, 40))
    cv.circle(x + w - 71, y + 33, 2, (255, 180, 180))
    # crowd dots
    crowd(cv, x + 6, y + h - 14, w - 12, 8, rng,
          [(255, 255, 255), (255, 220, 60), (60, 140, 220), (220, 60, 60)])
    crowd(cv, x + 6, y + h - 14, w - 12, 8, rng,
          [(255, 255, 255), (255, 220, 60), (60, 140, 220), (220, 60, 60)])
    cv.rect(x + 6, y + h - 30, 74, 14, (20, 90, 160))
    draw_text(cv, x + 9, y + h - 27, "100 IN SENA x4", 1, (255, 255, 255), True)
    cv.speckle(x, y, w, h, rng, [(160, 215, 140), (120, 190, 100)], 350)


def art_haiti(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, (200, 225, 245), (160, 195, 220))
    # mountains
    cv.poly([(x, y + h - 18), (x + 50, y + 12), (x + 100, y + h - 18)], (90, 130, 80))
    cv.poly([(x + 80, y + h - 18), (x + 140, y + 6), (x + 195, y + h - 18)], (70, 110, 70))
    cv.poly([(x + 42, y + 22), (x + 50, y + 12), (x + 58, y + 22)], (245, 245, 245))
    cv.poly([(x + 132, y + 16), (x + 140, y + 6), (x + 148, y + 16)], (245, 245, 245))
    cv.rect(x, y + h - 18, w, 18, (120, 100, 70))
    # Haitian flag
    flag_rect(cv, x + 8, y + 8, 40, 24, [(30, 60, 160), (200, 30, 50)])
    cv.rect(x + 20, y + 16, 16, 8, (255, 255, 255))
    cv.frame(x + 8, y + 8, 40, 24, (80, 80, 80))
    # helmeted figures
    for fx in (x + 70, x + 100, x + 130):
        cv.circle(fx, y + h - 30, 5, (230, 190, 150))
        cv.ellipse(fx, y + h - 33, 7, 4, (60, 90, 50))
        cv.rect(fx - 5, y + h - 24, 10, 12, (70, 100, 60))
        cv.line(fx - 4, y + h - 12, fx - 6, y + h - 2, (50, 50, 50))
        cv.line(fx + 4, y + h - 12, fx + 7, y + h - 2, (50, 50, 50))
    cv.rect(x + w - 60, y + 6, 54, 14, (160, 30, 30))
    draw_text(cv, x + w - 56, y + 9, "3 DEAD", 1, (255, 255, 255), True)
    cv.speckle(x, y, w, h, rng, [(185, 210, 235), (170, 200, 225)], 350)


# -------------------------------------------------------------------- map
LAND = (232, 220, 190)
LAND2 = (222, 208, 172)
SEA1, SEA2 = (168, 208, 232), (140, 188, 220)

CONTINENTS = [
    # North America
    [(8, 38), (30, 26), (70, 22), (95, 30), (105, 44), (98, 58), (88, 52),
     (80, 66), (60, 78), (38, 80), (20, 66), (10, 52)],
    # Greenland
    [(108, 16), (128, 14), (132, 26), (114, 30)],
    # Central America
    [(60, 80), (78, 84), (84, 92), (66, 92)],
    # South America
    [(78, 96), (100, 92), (112, 106), (108, 128), (96, 152), (86, 142), (78, 118)],
    # Europe
    [(140, 26), (162, 20), (180, 28), (178, 44), (160, 52), (146, 46), (138, 36)],
    # UK
    [(136, 26), (142, 24), (143, 32), (137, 33)],
    # Africa
    [(140, 58), (172, 54), (188, 66), (192, 88), (178, 112), (162, 128),
     (150, 112), (142, 88), (136, 70)],
    # Asia
    [(180, 28), (230, 18), (280, 22), (290, 44), (272, 62), (240, 66),
     (215, 58), (196, 48), (186, 38)],
    # India
    [(216, 62), (228, 60), (230, 78), (222, 88), (216, 76)],
    # SE Asia
    [(232, 66), (248, 64), (252, 78), (238, 82)],
    # Australia
    [(246, 116), (282, 114), (288, 132), (272, 146), (250, 140)],
]

ISLANDS = [(250, 92), (264, 96), (276, 92), (272, 44), (276, 50),
           (290, 150), (292, 156), (160, 60), (200, 60)]

PINS = [(52, 52, "1"), (175, 42, "2"), (163, 31, "3"), (28, 74, "4"),
        (178, 56, "5"), (150, 24, "6"), (208, 70, "7"), (145, 38, "8"),
        (58, 60, "9"), (152, 46, "10"), (94, 118, "11"), (288, 152, "12"),
        (66, 86, "13")]


def draw_map(cv, x, y, w, h, rng):
    cv.vgrad(x, y, w, h, SEA1, SEA2)
    # graticule
    for gx in range(x + 24, x + w, 37):
        cv.vline(gx, y, h, (150, 195, 220))
    for gy in range(y + 22, y + h, 34):
        cv.hline(x, gy, w, (150, 195, 220))
    # Antarctica strip
    cv.rect(x, y + h - 8, w, 8, (235, 242, 248))
    # continents
    for i, poly in enumerate(CONTINENTS):
        pts = [(x + px, y + py) for px, py in poly]
        cv.poly(pts, LAND if i % 2 == 0 else LAND2)
        for j in range(len(pts)):
            cv.line(pts[j][0], pts[j][1], pts[(j + 1) % len(pts)][0],
                    pts[(j + 1) % len(pts)][1], (170, 155, 115))
    for ix, iy in ISLANDS:
        cv.ellipse(x + ix, y + iy, 3, 2, LAND)
    # ocean texture
    cv.speckle(x, y, w, h, rng, [(155, 198, 225), (178, 215, 238)], 700)
    cv.speckle(x, y, w, h, rng, [(222, 208, 172), (240, 230, 205)], 400, size=2)
    waves(cv, x + 8, y + h - 30, 60, 14, rng, (190, 222, 242), (170, 210, 235))
    # pins
    for px, py, num in PINS:
        cv.circle(x + px, y + py, 7, (255, 255, 255))
        cv.circle(x + px, y + py, 6, (198, 40, 40))
        draw_text(cv, x + px - (3 if len(num) == 1 else 6) + 1, y + py - 3,
                  num, 1, (255, 255, 255), True)


# -------------------------------------------------------------------- data
PAPER = (247, 242, 231)
INK = (25, 25, 25)
RED = (198, 40, 40)
DARKRED = (140, 25, 25)
GRAY = (100, 100, 100)

REGION_COLORS = {
    "AMERICAS": (31, 111, 139), "EUROPE": (46, 125, 50),
    "AFRICA": (230, 81, 0), "MIDDLE EAST": (106, 27, 154),
    "ASIA": (198, 40, 40), "GLOBAL": (69, 90, 100), "OCEANIA": (0, 131, 143),
}
REGIONS = [("AMERICAS", 17), ("EUROPE", 9), ("AFRICA", 8), ("MIDDLE EAST", 6),
           ("GLOBAL", 4), ("ASIA", 4), ("OCEANIA", 2)]

UTC_EVENTS = [
    ("07:15", "Haiti: 3rd soldier dies after blast"),
    ("09:26", "Basra: power-station fire kills 4"),
    ("11:27", "Hormuz: two tanker strikes logged"),
    ("13:14", "EU: 1.78tn euro budget plan"),
    ("15:11", "EU, Indonesia sign trade deals"),
    ("18:17", "Finland probes airspace breach"),
    ("23:25", "Peru: 152 homes uninhabitable"),
]

KPIS = [
    ("-3.7%", "S&P 500, Friday", (198, 40, 40)),
    ("6,910", "S&P 500 close", (30, 30, 30)),
    ("148", "drones in one night", (198, 40, 40)),
    ("100,000", "youth places a year", (30, 120, 60)),
    ("69%", "dengue cases cut", (30, 120, 60)),
    ("128", "nations in Geneva", (30, 80, 140)),
]

HEROES = [
    {"art": art_markets, "num": "1", "tag": "US · MARKETS", "color": (69, 90, 100),
     "chip": "CONFIRMED · AP",
     "head": ["AI sell-off sinks", "Wall Street"],
     "deck": "S&P 500 falls 3.7% to 6,910, its seventh straight loss; Nasdaq drops 5.3% as Nvidia slides 14% on an SEC probe report."},
    {"art": art_kryvyi, "num": "2", "tag": "UKRAINE · KYIV", "color": (46, 125, 50),
     "chip": "CONFIRMED · AP",
     "head": ["Missile hits Zelensky's", "home town"],
     "deck": "Two killed and 60 wounded, six of them children, as a Russian missile strikes central Kryvyi Rih; 148 drones fly overnight."},
    {"art": art_poland, "num": "3", "tag": "POLAND · NATO", "color": (46, 125, 50),
     "chip": "CONFIRMED · NATO",
     "head": ["Poland seeks NATO shields", "after missiles land"],
     "deck": "Warsaw asks for more air defences after two Russian cruise missiles and a drone come down on its soil; NATO calls it a 'serious violation'."},
]

SECONDARIES = [
    {"art": art_mexico, "num": "4", "tag": "MEXICO", "color": (31, 111, 139),
     "chip": "CONFIRMED · GOVT",
     "head": "Army seizes FBI most-wanted cartel boss",
     "deck": "'El Chapo Isidro' taken in Sinaloa; violence follows."},
    {"art": art_cop31, "num": "5", "tag": "CLIMATE · COP31", "color": (69, 90, 100),
     "chip": "REPORTED · AP",
     "head": "Climate talks run past deadline",
     "deck": "Antalya in overtime; the draft drops fossil fuels."},
    {"art": art_denmark, "num": "6", "tag": "DENMARK", "color": (46, 125, 50),
     "chip": "CONFIRMED · REUTERS",
     "head": "Denmark expels Russian defence attache",
     "deck": "Seven days to leave over a foiled plot on Kyivstoner."},
    {"art": art_hormuz, "num": "7", "tag": "HORMUZ", "color": (106, 27, 154),
     "chip": "REPORTED · UKMTO",
     "head": "Tanker ablaze after Hormuz strike",
     "deck": "Tanker hit off Oman; Iran claims a US drone downed."},
    {"art": art_ukeu, "num": "8", "tag": "EUROPE", "color": (46, 125, 50),
     "chip": "CONFIRMED · EU",
     "head": "UK and EU sign 'reset' deal",
     "deck": "Food trade eased; 100,000 youth places a year."},
    {"art": art_chips, "num": "9", "tag": "TECH", "color": (69, 90, 100),
     "chip": "CONFIRMED · REUTERS",
     "head": "US shuts chip remote-access loophole",
     "deck": "New rules bite at once; Nvidia halts H200 exports to China."},
    {"art": art_geneva, "num": "10", "tag": "GENEVA", "color": (69, 90, 100),
     "chip": "CONFIRMED · UN",
     "head": "128 nations back killer-robot rules",
     "deck": "Geneva agrees to keep working toward an accord by 2028."},
    {"art": art_dengue, "num": "11", "tag": "SCIENCE", "color": (31, 111, 139),
     "chip": "REPORTED · STUDY",
     "head": "Dengue cut 69% by modified mosquitoes",
     "deck": "Brazil trial: bacteria-carrying mosquitoes slash cases."},
    {"art": art_rahul, "num": "12", "tag": "SPORT", "color": (198, 40, 40),
     "chip": "CONFIRMED · REPORTS",
     "head": "Rahul's century makes SENA history",
     "deck": "First Indian opener with Test hundreds in all four SENA lands."},
    {"art": art_haiti, "num": "13", "tag": "HAITI", "color": (31, 111, 139),
     "chip": "REPORTED · PRESS",
     "head": "Salvadoran troops hit in Haiti",
     "deck": "Three soldiers dead as the gang mission goes on."},
]

BRIEFS = [
    "14 FBI: police database breached",
    "15 Trump: contractors must tell all",
    "16 Judge blocks Trump arch again",
    "17 Cyber chief fired after outages",
    "18 Trump: Iran 'dirty bomb' a rumor",
    "19 Vance splits on Iran atom claim",
    "20 Court ends TPS for 600,000",
    "21 LA ports: strike looms Sunday",
    "22 Palisades arsonist convicted",
    "23 Florida floods: 28in of rain",
    "24 CISA: patch VMware flaw now",
    "25 Canada: unaware of US memo",
    "26 Bukele to seek a third term",
    "27 Peru: 152 homes uninhabitable",
    "28 APEC: Trump, Xi meet in Shenzhen",
    "29 Georgia: gas blast kills six",
    "30 Finland probes airspace breach",
    "31 Drones hit ship off Finland",
    "32 EU budget: 1.78tn euro plan",
    "33 EU, Indonesia sign trade pact",
    "34 France: police jailed over beating",
    "35 Turkey seizes Sozcu TV",
    "36 Basra fire kills four",
    "37 Bahrain blames Iran for blaze",
    "38 Gaza strikes kill six",
    "39 Riyadh: 3 missiles downed",
    "40 Ethiopia: 700,000 displaced",
    "41 Kenya: headcount over recruits",
    "42 Uganda traders end strike",
    "43 S. Africa holds rate at 7.25%",
    "44 Nigeria suspends 3,852 cadets",
    "45 Ghana: 38 stranded in Burkina",
    "46 WHO: Congo Ebola child deaths",
    "47 Morocco, Mali win at U17 Cup",
    "48 Wales end 73-year All Blacks run",
    "49 AFLW: North reach 4th final",
    "50 Air Niugini lands safely",
]

DATE_CHECK = ("Left out on purpose, first reported before Saturday: the Shenzhen summit and joint "
              "declaration (Thu 19 Nov); the ICJ genocide ruling on Myanmar (Thu); Anthropic's IPO debut, "
              "up 17% (Thu); GTA VI launches (Thu); a Houthi missile hits Riyadh's PIF tower (Thu); "
              "Danish MPs back the US Greenland pact 109-0 (Thu); Seoul orders a retrial for ex-PM Han "
              "(Thu); the 6.7 Peru quake (Fri 20); Russian strikes kill 3 in Kyiv (Fri); tainted liquor "
              "kills 11 in Manipur (Fri). Not yet: the COP31 final deal (talks in overtime); a LA port "
              "strike (possible Sun 5pm); the Geneva killer-robot accord (eyed 2028).")


# ------------------------------------------------------------------ layout
def build():
    rng = random.Random(20261121)
    cv = Canvas(W, H, PAPER)
    # paper texture: light speckle everywhere (adds print texture + bytes)
    cv.speckle(0, 0, W, H, rng, [(240, 235, 222), (252, 248, 238), (243, 238, 226)],
               50000)
    cv.speckle(0, 0, W, H, rng, [(236, 230, 214), (250, 245, 232)], 12000, size=2)
    y = 10
    # kicker
    draw_text(cv, 14, y, "THE WORLD ON ONE PAGE", 2, RED, True)
    rk = "50 STORIES  ·  7 REGIONS  ·  16 FIELDS  ·  ALL FROM THIS SATURDAY"
    draw_text(cv, 1010 - text_w(rk, 1), y + 4, rk, 1, DARKRED, True)
    y += 20
    # masthead
    draw_text_center(cv, W // 2, y, "Saturday 21 November 2026", 5, INK, True)
    y += 40
    deck = ("Markets plunge as AI fears spread  ·  Missile hits Zelensky's home town  ·  "
            "Poland calls for NATO shields")
    draw_text_center(cv, W // 2, y, deck, 1, DARKRED)
    y += 14
    cv.hline(14, y, 996, INK)
    cv.hline(14, y + 3, 996, INK)
    y += 8
    # region bar
    seg_w = [143, 143, 143, 143, 142, 141, 141]
    rx = 14
    for (name, cnt), sw in zip(REGIONS, seg_w):
        col = REGION_COLORS[name]
        cv.rect(rx, y, sw, 22, col)
        label = "%s %d" % (name, cnt)
        draw_text(cv, rx + (sw - text_w(label, 1)) // 2, y + 7, label, 1,
                  (255, 255, 255), True)
        rx += sw
    y += 26
    # UTC strip
    cv.rect(14, y, 110, 38, RED)
    draw_text(cv, 20, y + 7, "THE DAY", 1, (255, 255, 255), True)
    draw_text(cv, 20, y + 17, "IN UTC", 1, (255, 255, 255), True)
    cv.vline(128, y, 38, (200, 200, 190))
    col_w = 886 // 7
    for i, (tm, ev) in enumerate(UTC_EVENTS):
        cx = 132 + i * col_w
        draw_text(cv, cx, y + 2, tm, 1, RED, True)
        for j, ln in enumerate(wrap(ev, 20)):
            draw_text(cv, cx, y + 12 + j * 9, ln, 1, INK)
        if i < 6:
            cv.vline(cx + col_w - 4, y + 2, 34, (215, 210, 195))
    y += 42
    # KPI strip
    cv.rect(14, y, 110, 38, INK)
    draw_text(cv, 20, y + 7, "THE DAY", 1, (255, 255, 255), True)
    draw_text(cv, 20, y + 17, "IN NUMBERS", 1, (255, 255, 255), True)
    cell_w = 886 // 6
    for i, (num, lab, col) in enumerate(KPIS):
        cx = 132 + i * cell_w
        draw_text(cv, cx, y + 2, num, 3, col, True)
        for j, ln in enumerate(wrap(lab, 22)):
            draw_text(cv, cx, y + 24 + j * 8, ln, 1, GRAY)
        if i < 5:
            cv.vline(cx + cell_w - 4, y + 2, 34, (215, 210, 195))
    y += 42
    # heroes
    hero_y = y
    for i, h in enumerate(HEROES):
        px = 14 + i * 336
        cv.rect(px, hero_y, 324, 220, (253, 250, 244))
        cv.frame(px, hero_y, 324, 220, (190, 185, 170))
        h["art"](cv, px + 4, hero_y + 4, 316, 126, rng)
        cv.frame(px + 4, hero_y + 4, 316, 126, (120, 120, 110))
        ty = hero_y + 136
        cv.rect(px + 4, ty - 1, 16, 11, h["color"])
        draw_text(cv, px + 8, ty + 1, h["num"], 1, (255, 255, 255), True)
        draw_text(cv, px + 24, ty, h["tag"], 1, h["color"], True)
        chip = h["chip"]
        draw_text(cv, px + 320 - text_w(chip, 1), ty, chip, 1, (30, 120, 60), True)
        hy = hero_y + 152
        for j, ln in enumerate(h["head"]):
            draw_text(cv, px + 6, hy + j * 16, ln, 2, INK, True)
        dy = hero_y + 186
        for j, ln in enumerate(wrap(h["deck"], 52)[:3]):
            draw_text(cv, px + 6, dy + j * 10, ln, 1, (50, 50, 50))
    y += 224
    # secondaries, two rows of five
    for row in range(2):
        for i in range(5):
            s = SECONDARIES[row * 5 + i]
            cx = 14 + i * 200
            cv.rect(cx, y, 196, 120, (253, 250, 244))
            cv.frame(cx, y, 196, 120, (190, 185, 170))
            s["art"](cv, cx + 3, y + 3, 190, 58, rng)
            cv.frame(cx + 3, y + 3, 190, 58, (120, 120, 110))
            ty = y + 64
            cv.rect(cx + 3, ty - 1, 14 if len(s["num"]) == 1 else 20, 11, s["color"])
            draw_text(cv, cx + 6, ty + 1, s["num"], 1, (255, 255, 255), True)
            draw_text(cv, cx + 3 + (17 if len(s["num"]) == 1 else 23), ty,
                      s["tag"], 1, s["color"], True)
            chip = s["chip"]
            draw_text(cv, cx + 193 - text_w(chip, 1), ty, chip, 1, (30, 120, 60))
            hy = y + 78
            for j, ln in enumerate(wrap(s["head"], 32)[:2]):
                draw_text(cv, cx + 4, hy + j * 9, ln, 1, INK, True)
            dy = y + 97
            for j, ln in enumerate(wrap(s["deck"], 32)[:2]):
                draw_text(cv, cx + 4, dy + j * 9, ln, 1, (70, 70, 70))
        y += 124
    # map + briefs
    draw_text(cv, 14, y, "WHERE IT HAPPENED", 2, RED, True)
    draw_text(cv, 318, y, "ALSO ON SATURDAY 21 NOVEMBER", 2, RED, True)
    draw_text(cv, 318, y + 14, "37 briefs, grouped by region", 1, GRAY)
    my = y + 18
    draw_map(cv, 14, my, 296, 184, rng)
    cv.frame(14, my, 296, 184, (120, 120, 110))
    ly = my + 190
    lx = 14
    for name, cnt in REGIONS:
        lab = "%s %d" % (name.title(), cnt)
        need = 11 + text_w(lab, 1) + 14
        if lx + need > 312 and lx > 14:
            lx = 14
            ly += 11
        cv.rect(lx, ly, 8, 8, REGION_COLORS[name])
        draw_text(cv, lx + 11, ly, lab, 1, INK)
        lx += need
    draw_text(cv, 14, ly + 13, "Numbered pins are the picture stories.", 1, GRAY)
    cols = [BRIEFS[0:13], BRIEFS[13:25], BRIEFS[25:37]]
    for ci, col in enumerate(cols):
        bx = 318 + ci * 232
        by = my
        for b in col:
            num, rest = b.split(" ", 1)
            draw_text(cv, bx, by, num, 1, RED, True)
            draw_text(cv, bx + text_w(num + " ", 1), by, rest, 1, INK)
            by += 12
    # how to read
    hy = my + 13 * 12 + 8
    cv.rect(318, hy, 692, 34, (238, 232, 214))
    cv.frame(318, hy, 692, 34, (190, 185, 170))
    draw_text(cv, 326, hy + 5, "HOW TO READ", 1, DARKRED, True)
    draw_text(cv, 326, hy + 16,
              "At thumbnail size: the date, three leads and ten big pictures. "
              "At full size: 37 briefs", 1, INK)
    draw_text(cv, 326, hy + 25,
              "by region. Numbered pins are the picture stories.", 1, INK)
    y += 254
    # date check
    cv.frame(14, y, 996, 64, RED, 2)
    draw_text(cv, 22, y + 6, "DATE CHECK", 1, RED, True)
    dy = y + 6
    for j, ln in enumerate(wrap(DATE_CHECK, 150)):
        draw_text(cv, 110, dy + j * 10, ln, 1, INK)
    y += 68
    # footer
    chips = [("CONFIRMED", (30, 120, 60), "on the record"),
             ("REPORTED", (30, 80, 140), "news report"),
             ("CLAIM", (180, 90, 20), "one side's account")]
    fx = 14
    for name, col, desc in chips:
        cv.rect(fx, y + 1, 10, 10, col)
        draw_text(cv, fx + 13, y + 2, name, 1, col, True)
        fx += 13 + text_w(name, 1) + 4
        draw_text(cv, fx, y + 2, desc, 1, GRAY)
        fx += text_w(desc, 1) + 18
    src = "Sources: AP, Reuters, AFP, NYT, UKMTO, UN."
    draw_text(cv, 1010 - text_w(src, 1), y + 2, src, 1, GRAY)
    draw_text(cv, 14, y + 12, "All stories first reported Saturday 21 November 2026.",
              1, GRAY)
    return cv


def main():
    cv = build()
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, "entry.png")
    n = write_png(path, cv.px, W, H)
    print("wrote %s (%d bytes)" % (path, n))


if __name__ == "__main__":
    main()
