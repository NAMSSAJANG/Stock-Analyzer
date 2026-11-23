"""Reproducible SVG wordmarks from the supplied layout and OFL font outlines."""

import json
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

root = Path("web")
brands = json.loads((root / "theme/brands.json").read_text())
ink = brands["personal"]["ink"]
font = TTFont(root / "brand/originals/RobotoSerif.ttf")
font = instantiateVariableFont(
    font, {"wght": 900, "wdth": 75, "opsz": 48, "GRAD": 0}, inplace=False
)
glyphs = font.getGlyphSet()
cmap = font.getBestCmap()


def outline(text):
    x = 0
    pieces = []
    for char in text:
        name = cmap[ord(char)]
        pen = SVGPathPen(glyphs)
        glyphs[name].draw(pen)
        pieces.append(f'<path transform="translate({x},0)" d="{pen.getCommands()}"/>')
        x += font["hmtx"][name][0]
    return "".join(pieces), x


gold, width = outline("Goldnam")
sachs, _ = outline("Sachs")
scale = 460 / width
wordmark = f'<g fill="{ink}"><g transform="translate(26,150) scale({scale},-{scale})">{gold}</g><g transform="translate(26,265) scale({scale},-{scale})">{sachs}</g></g>'
for theme, brand in brands.items():
    color = brand["color"]
    square = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" role="img"><title>Goldnam Sachs</title><rect width="512" height="512" fill="{color}"/>{wordmark}</svg>'
    (root / f"public/brand/{theme}-square.svg").write_text(square)
    if theme == "personal":
        logo = square
    else:
        logo = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 415 445" role="img"><title>Goldnam Sachs</title><rect width="415" height="445" fill="{ink}"/><g transform="translate(60,65) scale({324 / 512})"><rect width="512" height="512" fill="{color}"/>{wordmark}</g></svg>'
    (root / f"public/brand/{theme}.svg").write_text(logo)
print("4 SVG wordmarks generated from Roboto Serif OFL outlines")
