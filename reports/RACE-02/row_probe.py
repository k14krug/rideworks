"""Synthetic separator-contrast probe; not a production row-ownership planner."""

from statistics import median

from PIL import Image, ImageDraw


def image(rows, *, gray=False, short=False, extra_header=False, wrapped=False, clipped=False, identical=False):
    width = 768
    step = 50
    top = 60
    height = top + rows * step if clipped else max(939, top + rows * step + 10)
    background = (220, 220, 220) if gray else (255, 255, 255)
    picture = Image.new('RGB', (width, height), background)
    draw = ImageDraw.Draw(picture)
    color = (90, 90, 90)
    for i in range(rows + 1):
        y = top + i * step
        end = 170 if short and i == rows // 2 else 710
        draw.line((70, y, end, y), fill=color)
    for i in range(rows):
        y = top + i * step
        draw.text((80, y + 6), f'{1 if identical else i + 1} 11/8/2024 11:33 AM', fill='black')
        draw.text((280, y + 5), 'Synthetic Event Title', fill='blue')
        if wrapped:
            draw.text((280, y + 20), 'wrapped continuation', fill='blue')
    if extra_header:
        draw.line((70, top - step, 710, top - step), fill=color)
        draw.text((80, top - step + 6), 'RESULTS TABLE HEADING', fill='black')
    return picture


def probe(picture):
    pixels = picture.convert('L')
    width, height = pixels.size
    found = []
    for y in range(1, height - 1):
        run = longest = 0
        for x in range(width):
            point = pixels.getpixel((x, y))
            contrast = (pixels.getpixel((x, y - 1)) - point > 40 and
                        pixels.getpixel((x, y + 1)) - point > 40)
            run = run + 1 if contrast else 0
            longest = max(longest, run)
        if longest >= 100:
            found.append(y)
    if len(found) < 2:
        return None
    distances = [b - a for a, b in zip(found, found[1:])]
    typical = median(distances)
    if any(not .7 * typical <= gap <= 1.3 * typical for gap in distances):
        return None
    return len(distances)


if __name__ == '__main__':
    for label, picture, actual in (
        ('one row', image(1), 1),
        ('two rows', image(2, identical=True), 2),
        ('17 rows, 768x939, wrapped titles', image(17, wrapped=True), 17),
        ('33 rows, taller image', image(33), 33),
        ('short separator', image(17, short=True), 17),
        ('gray background', image(17, gray=True), 17),
        ('identical adjacent rows', image(17, identical=True), 17),
        ('clipped bottom', image(17, clipped=True), 17),
        ('equally spaced header separator', image(17, extra_header=True), 17),
    ):
        print(f'{label}: physical rows={actual}, inferred={probe(picture)}')
