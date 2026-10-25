"""Draw the app icon: a folder with one landscape screenshot inside."""
from pathlib import Path

from PIL import Image, ImageDraw

INK = (36, 31, 27, 255)
PAPER = (246, 243, 238, 255)
HERE = Path(__file__).resolve().parent


def rounded(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw(size):
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if size in (16, 32):
        return draw_small(image, size)
    unit = size / 256
    tab = (36 * unit, 58 * unit, 124 * unit, 108 * unit)
    body = (32 * unit, 92 * unit, 224 * unit, 214 * unit)
    shot = (58 * unit, 118 * unit, 198 * unit, 186 * unit)
    radius_tab = max(2, int(14 * unit))
    radius_body = max(3, int(18 * unit))
    radius_shot = max(2, int(10 * unit))
    rounded(draw, tab, radius_tab, INK)
    rounded(draw, body, radius_body, INK)
    rounded(draw, shot, radius_shot, PAPER)
    return image


def draw_small(image, size):
    pixels = image.load()
    scale = size / 16
    # 16px layout, centered. 1 = folder, 2 = screenshot.
    rows = [
        "................",
        "................",
        ".######.........",
        ".##############.",
        ".##############.",
        ".##++++++++++##.",
        ".##++++++++++##.",
        ".##++++++++++##.",
        ".##++++++++++##.",
        ".##++++++++++##.",
        ".##############.",
        ".##############.",
        "................",
        "................",
        "................",
        "................",
    ]
    for y, row in enumerate(rows):
        for x, cell in enumerate(row):
            if cell == ".":
                continue
            color = INK if cell == "#" else PAPER
            x0 = int(x * scale)
            y0 = int(y * scale)
            x1 = int((x + 1) * scale)
            y1 = int((y + 1) * scale)
            for py in range(y0, max(y0 + 1, y1)):
                for px in range(x0, max(x0 + 1, x1)):
                    if px < size and py < size:
                        pixels[px, py] = color
    return image


def main():
    sizes = [16, 24, 32, 48, 64, 256]
    images = [draw(size) for size in sizes]
    images[-1].save(HERE / "app-icon.png")
    images[0].save(
        HERE / "app.ico",
        format="ICO",
        append_images=images[1:],
        sizes=[(size, size) for size in sizes],
    )


if __name__ == "__main__":
    main()
