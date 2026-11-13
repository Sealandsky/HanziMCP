#!/usr/bin/env python3
"""Build the site favicon from the project's own stroke data.

Outputs favicon.svg + favicon.ico, and exposes FAVICON_LINKS (an inline
data-URI <link>) so every page stays self-contained and works on file://,
GitHub Pages and the local server alike.

The glyph is drawn from hanzi-strokes.json rather than a <text> element, so it
renders identically on every platform regardless of installed CJK fonts.
"""
import io
import json
import os
import re
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
GLYPH = "天"                 # first char of the library / first card on the site
BG = "#18181b"              # matches --ink
INK = "#f7f5ef"             # warm rice-paper white
GRID = "#2d68ff"            # matches --accent


def _glyph_geom():
    with open(os.path.join(HERE, "hanzi-strokes.json"), encoding="utf-8") as f:
        strokes = json.load(f)[GLYPH]["strokes"]
    pts = []
    for path in strokes:
        n = [float(v) for v in re.findall(r"-?\d+\.?\d*", path)]
        pts += [(n[i], n[i + 1]) for i in range(0, len(n) - 1, 2)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return strokes, min(xs), max(xs), min(ys), max(ys)


def _glyph_group(frac=40.0, bold=0.0):
    """Map hanzi-writer-data coordinates (y-up, 1024 grid) into a 64px box.

    frac: glyph size inside the 64px box. bold: extra outline as a fraction of
    the source bbox span, used only for tiny ICO frames.
    """
    strokes, xmin, xmax, ymin, ymax = _glyph_geom()
    span = max(xmax - xmin, ymax - ymin, 1)
    scale = frac / span
    cx, cy = (xmin + xmax) / 2, (ymin + ymax) / 2
    tf = "translate(32 32) scale(%.6f -%.6f) translate(%.3f %.3f)" % (
        scale, scale, -cx, -cy)
    extra = "" if not bold else (
        ' stroke="%s" stroke-width="%.3f" stroke-linejoin="round"' % (INK, span * bold))
    body = "".join('<path d="%s" fill="%s"%s/>' % (p, INK, extra) for p in strokes)
    return '<g transform="%s">%s</g>' % (tf, body)


def svg_string():
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        + '<rect width="64" height="64" rx="14" fill="%s"/>' % BG
        + '<g fill="none" stroke="%s" stroke-width=".9" stroke-opacity=".34">' % GRID
        + '<rect x="8.5" y="8.5" width="47" height="47" rx="2"/>'
        + '<path d="M32 8.5V55.5M8.5 32H55.5" stroke-dasharray="2.5 3"/>'
        + '</g>'
        + _glyph_group()
        + '</svg>'
    )


def small_svg_string(frac=46.0, bold=0.05):
    """Compact icon for 16/32px ICO frames: no keylines, larger + bolder glyph.

    Scaling a 256px render down destroys thin kaishu strokes, so tiny frames
    are rasterised from their own artwork at the exact target size instead.
    """
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
        + '<rect width="64" height="64" rx="14" fill="%s"/>' % BG
        + _glyph_group(frac, bold)
        + '</svg>'
    )


def _data_uri(svg):
    # Single-quote attributes so the whole thing can live inside href="...".
    compact = re.sub(r">\s+<", "><", svg.strip()).replace('"', "'")
    return "data:image/svg+xml," + quote(compact, safe="/=:-,;.+~*'()!&?")


SVG = svg_string()
FAVICON_LINKS = '<link rel="icon" type="image/svg+xml" href="%s">' % _data_uri(SVG)


def build():
    import struct
    import cairosvg
    svg_path = os.path.join(HERE, "favicon.svg")
    ico_path = os.path.join(HERE, "favicon.ico")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(SVG + "\n")

    # Rasterise each ICO frame at its exact size (PNG-compressed frames), so
    # the 16px icon stays legible instead of being a downscaled 256px blur.
    frames = []
    for size in (16, 32, 48, 64):
        art = small_svg_string() if size <= 32 else SVG
        png = cairosvg.svg2png(bytestring=art.encode("utf-8"),
                               output_width=size, output_height=size)
        frames.append((size, png))

    out = io.BytesIO()
    out.write(struct.pack("<HHH", 0, 1, len(frames)))
    offset = 6 + 16 * len(frames)
    for size, png in frames:
        w = 0 if size >= 256 else size
        out.write(struct.pack("<BBBBHHII", w, w, 0, 0, 1, 32,
                              len(png), offset))
        offset += len(png)
    for _size, png in frames:
        out.write(png)
    with open(ico_path, "wb") as f:
        f.write(out.getvalue())
    return svg_path, ico_path


if __name__ == "__main__":
    svg_p, ico_p = build()
    print("wrote %s (%d bytes)" % (svg_p, os.path.getsize(svg_p)))
    print("wrote %s (%d bytes)" % (ico_p, os.path.getsize(ico_p)))
    print("inline <link> length: %d bytes" % len(FAVICON_LINKS))
