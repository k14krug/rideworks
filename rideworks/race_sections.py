"""Deterministic overlapping screenshot crops; no row detection or inference."""

import io

from PIL import Image, ImageOps

from .race_results import RaceError, screenshot


SECTION_HEIGHT = 600
SECTION_OVERLAP = 180
MAX_SECTIONS = 20


def image_dimensions(payload):
    with Image.open(io.BytesIO(payload)) as image:
        return ImageOps.exif_transpose(image).size


def plan_sections(width, height):
    if width <= 0 or height <= 0:
        raise RaceError('The screenshot has invalid dimensions.')
    result = []
    top = 0
    while True:
        bottom = min(height, top + SECTION_HEIGHT)
        result.append((top, bottom))
        if len(result) > MAX_SECTIONS:
            raise RaceError('The screenshot needs too many sections. Try a shorter screenshot.')
        if bottom == height:
            return result
        top = bottom - SECTION_OVERLAP


def crop_image(payload, top, bottom):
    with Image.open(io.BytesIO(payload)) as image:
        source = ImageOps.exif_transpose(image)
        cropped = source.crop((0, top, source.width, bottom))
        output = io.BytesIO()
        cropped.save(output, format='PNG')
        return output.getvalue()


def section_image(store, identity, section_index):
    section = store.connection.execute(
        'SELECT * FROM race_import_sections WHERE import_id=? AND section_index=?',
        (identity, section_index)).fetchone()
    if not section:
        raise RaceError('Screenshot section was not found.')
    _, payload = screenshot(store, identity)
    if image_dimensions(payload) != (section['width'], section['image_height']):
        raise RaceError('Screenshot section dimensions failed verification.')
    return crop_image(payload, section['top'], section['bottom'])
