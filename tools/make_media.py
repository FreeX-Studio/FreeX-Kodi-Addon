# Copyright (c) 2026 MirraNET, Niklas Linz. All rights reserved.
#
# This file is part of the MirraNET project and is licensed under the
# GNU Lesser General Public License v3.0 (LGPLv3).
#
# You may use, distribute and modify this code under the terms
# of the LGPLv3 license. You should have received a copy of the
# license along with this file. If not, see <https://www.gnu.org/licenses/lgpl-3.0.html>
# or contact: niklas.linz@mirranet.de

"""
Draws the textures of the FreeX windows (rounded masks, focus rings, buttons, shades, icons) into
plugin.video.freex/resources/skins/Default/media. Run it after changing a shape; the PNGs are
committed, so building the add-on does not need it. Needs Pillow and cairosvg.

The icons are the line icons of FreeX TV (web/js/core.js), the colours those of FreeX Web.
"""

import os
import sys

import cairosvg
from PIL import Image, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "..", "plugin.video.freex", "resources", "skins", "Default", "media")
LOGO = sys.argv[1] if len(sys.argv) > 1 else None  # path of FreeX-TV-Apps/web/img/logo.svg
S = 4  # supersampling

INK = (18, 24, 33)
RED, ORANGE, AMBER = (217, 59, 66), (233, 138, 70), (244, 183, 92)

ICONS = {
    "home": '<path d="M4 11l8-6.5 8 6.5V20h-5.5v-5.5h-5V20H4z" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>',
    "bookmark": '<path d="M6.5 4h11v16.5l-5.5-4-5.5 4z" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>',
    "bookmark-on": '<path d="M6.5 4h11v16.5l-5.5-4-5.5 4z" fill="#fff" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>',
    "list": '<path d="M8.5 6.5h11M8.5 12h11M8.5 17.5h11" stroke="#fff" stroke-width="2" stroke-linecap="round"/><circle cx="4.8" cy="6.5" r="1.3" fill="#fff"/><circle cx="4.8" cy="12" r="1.3" fill="#fff"/><circle cx="4.8" cy="17.5" r="1.3" fill="#fff"/>',
    "search": '<circle cx="11" cy="11" r="6.5" fill="none" stroke="#fff" stroke-width="2.2"/><path d="M16 16l4.5 4.5" stroke="#fff" stroke-width="2.2" stroke-linecap="round"/>',
    "movie": '<rect x="3.5" y="5" width="17" height="14" rx="2" fill="none" stroke="#fff" stroke-width="2"/><path d="M3.5 9.5h17M8 5v4.5M12 5v4.5M16 5v4.5" stroke="#fff" stroke-width="2"/>',
    "tv": '<rect x="3" y="5.5" width="18" height="12" rx="2" fill="none" stroke="#fff" stroke-width="2"/><path d="M8.5 21h7M9 2.5l3 3 3-3" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "gear": '<circle cx="12" cy="12" r="3.2" fill="none" stroke="#fff" stroke-width="2"/><path d="M12 2.8v2.6M12 18.6v2.6M2.8 12h2.6M18.6 12h2.6M5.5 5.5l1.8 1.8M16.7 16.7l1.8 1.8M5.5 18.5l1.8-1.8M16.7 7.3l1.8-1.8" stroke="#fff" stroke-width="2" stroke-linecap="round"/>',
    "play": '<path d="M8 5.5v13l11-6.5z" fill="#fff"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>',
    "restart": '<path d="M4 12a8 8 0 1 0 2.4-5.7M4 4v4.5h4.5" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "exit": '<path d="M14 4h5v16h-5M10 8l-4 4 4 4M6 12h10" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
    "extras": '<rect x="3.5" y="6" width="12" height="12" rx="2" fill="none" stroke="#fff" stroke-width="2"/><path d="M15.5 10.5l5-3v9l-5-3" fill="none" stroke="#fff" stroke-width="2" stroke-linejoin="round"/>',
    "star": '<path d="M12 3.5l2.6 5.6 6.1.7-4.5 4.2 1.2 6-5.4-3-5.4 3 1.2-6-4.5-4.2 6.1-.7z" fill="#fff"/>',
    "skip": '<path d="M4 6l7 6-7 6zM12 6l7 6-7 6z" fill="#fff"/>',
    "next": '<path d="M5.5 5.5v13l9-6.5zM17 5.5h2.5v13H17z" fill="#fff"/>',
}


def save(im, name):
    im.save(os.path.join(OUT, name))


def rounded(w, h, r, fill=(255, 255, 255, 255), outline=None, width=0):
    im = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius=r * S, fill=fill, outline=outline, width=width * S)
    return im.resize((w, h), Image.LANCZOS)


def gradient(w, h, stops, horizontal=True):
    """stops: [(pos, (r, g, b, a)), ...]"""
    im = Image.new("RGBA", (w, h))
    px = im.load()
    n = w if horizontal else h
    for i in range(n):
        t = i / max(1, n - 1)
        for k in range(len(stops) - 1):
            p0, c0 = stops[k]
            p1, c1 = stops[k + 1]
            if p0 <= t <= p1:
                f = (t - p0) / max(1e-6, p1 - p0)
                c = tuple(int(c0[j] + (c1[j] - c0[j]) * f) for j in range(4))
                break
        if horizontal:
            for y in range(h):
                px[i, y] = c
        else:
            for x in range(w):
                px[x, i] = c
    return im


def brand(w, h):
    """The FreeX gradient, 135 degrees from red over orange to amber."""
    im = Image.new("RGBA", (w, h))
    px = im.load()
    for y in range(h):
        for x in range(w):
            t = (x / w * 0.8 + y / h * 0.2)
            if t < 0.55:
                f = t / 0.55
                c = tuple(int(RED[j] + (ORANGE[j] - RED[j]) * f) for j in range(3))
            else:
                f = (t - 0.55) / 0.45
                c = tuple(int(ORANGE[j] + (AMBER[j] - ORANGE[j]) * f) for j in range(3))
            px[x, y] = c + (255,)
    return im


def masked(src, mask):
    out = src.copy()
    out.putalpha(mask.split()[3])
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    save(Image.new("RGBA", (8, 8), (255, 255, 255, 255)), "white.png")
    # Masks for artwork (Kodi multiplies the image with them: rounded corners).
    save(rounded(210, 315, 14), "mask-poster.png")
    save(rounded(370, 208, 14), "mask-land.png")
    save(rounded(400, 400, 200), "mask-circle.png")
    # Focus rings, drawn 8 px larger than the artwork (4 px white ring as in FreeX TV).
    save(rounded(218, 323, 18, fill=(0, 0, 0, 0), outline=(255, 255, 255, 255), width=4), "ring-poster.png")
    save(rounded(378, 216, 18, fill=(0, 0, 0, 0), outline=(255, 255, 255, 255), width=4), "ring-land.png")
    save(rounded(408, 408, 204, fill=(0, 0, 0, 0), outline=(255, 255, 255, 255), width=4), "ring-circle.png")
    # Rounded panels in white, coloured with colordiffuse.
    save(rounded(200, 64, 14), "panel.png")
    save(rounded(240, 72, 36), "pill-white.png")
    save(rounded(96, 96, 48), "circle.png")
    save(rounded(96, 96, 48, fill=(0, 0, 0, 0), outline=(255, 255, 255, 255), width=3), "circle-ring.png")
    save(rounded(8, 8, 3), "bar.png")
    # The brand pill of the primary button.
    save(masked(brand(480, 96), rounded(480, 96, 48)), "pill-brand.png")
    save(masked(brand(96, 96), rounded(96, 96, 48)), "circle-brand.png")
    save(masked(brand(16, 64), rounded(16, 64, 4)), "accent.png")
    # The corner of unwatched titles (top right of a card).
    tri = Image.new("RGBA", (40 * S, 40 * S), (0, 0, 0, 0))
    ImageDraw.Draw(tri).polygon([(0, 0), (40 * S, 0), (40 * S, 40 * S)], fill=(255, 255, 255, 255))
    tri = tri.resize((40, 40), Image.LANCZOS)
    save(masked(brand(40, 40), tri), "corner.png")
    # Shades over the backdrop.
    save(gradient(960, 8, [(0, INK + (255,)), (0.45, INK + (235,)), (1, INK + (0,))]), "shade-left.png")
    save(gradient(8, 540, [(0, INK + (0,)), (0.6, INK + (200,)), (1, INK + (255,))], horizontal=False), "shade-bottom.png")
    save(gradient(8, 300, [(0, INK + (210,)), (1, INK + (0,))], horizontal=False), "shade-top.png")
    # Icons, white; coloured in the window.
    for name, body in ICONS.items():
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="96" height="96">%s</svg>' % body
        cairosvg.svg2png(bytestring=svg.encode(), write_to=os.path.join(OUT, "icon-%s.png" % name))
    if LOGO:
        cairosvg.svg2png(url=LOGO, write_to=os.path.join(OUT, "logo.png"), output_width=128, output_height=128)


if __name__ == "__main__":
    main()
