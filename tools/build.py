"""Build index.html for GitHub Pages from the artifact source page.

The artifact viewer supplies its own <head> (charset, viewport, reset). GitHub
Pages serves the file raw, so this wraps the page in a full document with the
iPhone viewport, home-screen web-app tags and an app icon.

Usage: python3 tools/build.py <source.html>   (writes index.html and icons/)
"""
import os
import re
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def build_page(src_path):
    src = open(src_path, encoding="utf-8").read()
    split = src.index('<div id="scene"')
    head_part, body_part = src[:split], src[split:]
    if re.search(r"<!doctype|<html|<body", src, re.I):
        raise SystemExit("source already has a document skeleton")
    page = (
        "<!doctype html>\n<html lang=\"en\">\n<head>\n"
        "<meta charset=\"utf-8\">\n"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, maximum-scale=1, viewport-fit=cover\">\n"
        "<meta name=\"theme-color\" content=\"#0d1013\">\n"
        "<meta name=\"apple-mobile-web-app-capable\" content=\"yes\">\n"
        "<meta name=\"mobile-web-app-capable\" content=\"yes\">\n"
        "<meta name=\"apple-mobile-web-app-status-bar-style\" content=\"black-translucent\">\n"
        "<meta name=\"apple-mobile-web-app-title\" content=\"House Weather\">\n"
        "<link rel=\"apple-touch-icon\" href=\"icons/apple-touch-icon.png\">\n"
        "<link rel=\"icon\" type=\"image/png\" href=\"icons/icon-192.png\">\n"
        "<style>html,body{margin:0;height:100%}img{max-width:100%}[hidden]{display:none!important}"
        "body{font-size:14px;font-family:system-ui,-apple-system,sans-serif}</style>\n"
        + head_part.strip()
        + "\n</head>\n<body>\n"
        + body_part.strip()
        + "\n</body>\n</html>\n"
    )
    with open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)


def draw_icon(size):
    """Butter-yellow house with a gray roof and lit window on a dusk sky."""
    s = size / 180.0
    im = Image.new("RGB", (size, size), (28, 38, 66))
    d = ImageDraw.Draw(im)
    for y in range(size):  # dusk gradient
        t = y / size
        d.line([(0, y), (size, y)], fill=(int(28 + 70 * t), int(38 + 50 * t), int(66 + 30 * t)))
    d.rectangle([0, int(140 * s), size, size], fill=(62, 96, 44))
    d.rectangle([int(38 * s), int(86 * s), int(142 * s), int(142 * s)], fill=(239, 222, 150))
    d.polygon([(int(28 * s), int(90 * s)), (int(90 * s), int(44 * s)), (int(152 * s), int(90 * s))], fill=(104, 116, 128))
    d.rectangle([int(80 * s), int(108 * s), int(100 * s), int(142 * s)], fill=(244, 244, 238))
    d.rectangle([int(52 * s), int(100 * s), int(70 * s), int(120 * s)], fill=(255, 205, 128))
    d.rectangle([int(110 * s), int(100 * s), int(128 * s), int(120 * s)], fill=(255, 205, 128))
    for wx in (46, 70, 104, 128):
        d.rectangle([int(wx * s), int(100 * s), int((wx + 5) * s), int(120 * s)], fill=(30, 106, 61))
    return im


def build_icons():
    out = os.path.join(ROOT, "icons")
    os.makedirs(out, exist_ok=True)
    draw_icon(180).save(os.path.join(out, "apple-touch-icon.png"))
    draw_icon(192).save(os.path.join(out, "icon-192.png"))


if __name__ == "__main__":
    build_page(sys.argv[1])
    build_icons()
    print("built index.html and icons/")
