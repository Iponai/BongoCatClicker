# -*- coding: utf-8 -*-
"""
Generates assets/cat_icon.ico and cat_icon.png from a 16x16 pixel grid.
Requires Pillow (only for this script). Run: python tools/make_icon.py
"""

import os
from PIL import Image

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
GRID = 16  # 16x16 logical grid - divides evenly into every icon size

T = (0, 0, 0, 0)          # transparent
B = (24, 24, 27, 255)     # black fur
E = (250, 204, 21, 255)   # yellow eyes
P = (244, 114, 182, 255)  # pink nose

grid = [[T for _ in range(GRID)] for _ in range(GRID)]


def hline(row, c0, c1, color):
    for x in range(c0, c1 + 1):
        grid[row][x] = color


# ears (symmetric around the vertical axis between col7/col8)
hline(1, 3, 3, B); hline(1, 12, 12, B)
hline(2, 2, 3, B); hline(2, 12, 13, B)
hline(3, 1, 4, B); hline(3, 11, 14, B)

# top of the head
hline(4, 1, 14, B)
hline(5, 1, 14, B)

# eyes
hline(6, 0, 15, B)
hline(7, 0, 15, B)
for row in (6, 7):
    grid[row][4] = grid[row][5] = E
    grid[row][10] = grid[row][11] = E

# nose
hline(8, 0, 15, B)
grid[8][7] = grid[8][8] = P

# body
hline(9, 0, 15, B)
hline(10, 0, 15, B)

# tapering toward the bottom
hline(11, 1, 14, B)
hline(12, 2, 13, B)
hline(13, 3, 12, B)


def build_image(scale):
    img = Image.new("RGBA", (GRID * scale, GRID * scale), T)
    px = img.load()
    for y in range(GRID):
        for x in range(GRID):
            color = grid[y][x]
            if color[3] == 0:
                continue
            for dy in range(scale):
                for dx in range(scale):
                    px[x * scale + dx, y * scale + dy] = color
    return img


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    big = build_image(scale=16)                      # 256x256, matches the grid exactly
    png_path = os.path.join(OUT_DIR, "cat_icon.png")
    big.save(png_path)
    print("Saved:", png_path, big.size)

    ico_path = os.path.join(OUT_DIR, "cat_icon.ico")
    big.save(ico_path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    print("Saved:", ico_path)


if __name__ == "__main__":
    main()
