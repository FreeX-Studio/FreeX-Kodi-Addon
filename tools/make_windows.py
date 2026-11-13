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
Writes the window files of the FreeX interface (resources/skins/Default/1080i/*.xml). The rows
and cards repeat a lot, so they are generated; the XML files are committed, run this after a
change here.

Layout and colours follow FreeX TV (web/css/tv.css): 1920 x 1080, ink background, a sidebar,
rows of rounded cards with a white focus ring, the orange brand gradient for the main button.
Only fonts every skin has are used where possible (font12/13); the larger ones are Estuary's,
other skins fall back to font13.
"""

import os

OUT = os.path.join(os.path.dirname(__file__), "..", "plugin.video.freex", "resources", "skins", "Default", "1080i")

INK = "FF121821"
INK2 = "FF0E131A"
SURFACE = "FF1B2430"
RAISED = "FF243042"
LINE = "FF2E3B4E"
TEXT = "FFE8EDF2"
MUTED = "FF8A97A8"
GLASS = "FFF0974A"
GLASS_INK = "FF2A1306"

ROWS = 8
SIDEBAR_W = 330
CONTENT_X = 390


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def image(left, top, w, h, texture, extra="", diffuse=None, color=None, aspect="scale", visible=None, bg=False):
    parts = ['<control type="image">', "<left>%s</left><top>%s</top><width>%s</width><height>%s</height>" % (left, top, w, h)]
    parts.append('<aspectratio scalediffuse="false">%s</aspectratio>' % aspect)
    parts.append('<texture%s%s>%s</texture>' % (' background="true"' if bg else "",
                                                 ' diffuse="%s"' % diffuse if diffuse else "", texture))
    if color:
        parts.append("<colordiffuse>%s</colordiffuse>" % color)
    if visible:
        parts.append("<visible>%s</visible>" % visible)
    parts.append(extra)
    parts.append("</control>")
    return "".join(parts)


def label(left, top, w, h, text, font="font13", color=TEXT, align="left", aligny="top", visible=None, extra="",
          scroll=False):
    parts = ['<control type="label">', "<left>%s</left><top>%s</top><width>%s</width><height>%s</height>" % (left, top, w, h),
             "<font>%s</font><textcolor>%s</textcolor><align>%s</align><aligny>%s</aligny>" % (font, color, align, aligny),
             "<label>%s</label>" % text]
    if scroll:
        parts.append("<scroll>true</scroll>")
    if visible:
        parts.append("<visible>%s</visible>" % visible)
    parts.append(extra)
    parts.append("</control>")
    return "".join(parts)


def progress(left, top, w, h, info, visible=None):
    return ('<control type="progress"><left>%s</left><top>%s</top><width>%s</width><height>%s</height>'
            '<texturebg colordiffuse="8C000000">bar.png</texturebg><lefttexture/><righttexture/>'
            '<midtexture colordiffuse="%s">bar.png</midtexture><info>%s</info>%s</control>'
            % (left, top, w, h, GLASS, info, "<visible>%s</visible>" % visible if visible else ""))


# ---------------------------------------------------------------------- cards


def card(kind, focused, list_id):
    """One card of a row: artwork with mask, progress, unwatched corner or badge, two lines below."""
    if kind == "poster":
        w, h, art, mask, ring = 210, 315, "$INFO[ListItem.Art(freexposter)]", "mask-poster.png", "ring-poster.png"
    else:
        w, h, art, mask, ring = 370, 208, "$INFO[ListItem.Art(freexland)]", "mask-land.png", "ring-land.png"
    zoom = ('<animation effect="zoom" start="100" end="106" time="160" tween="cubic" easing="out" center="%d,%d" '
            'condition="Control.HasFocus(%d)">Conditional</animation>' % (w // 2, h // 2, list_id)) if focused else ""
    out = ["<control type=\"group\">", zoom]
    out.append(image(0, 0, w, h, "panel.png", color=RAISED, aspect="stretch"))
    out.append(label(16, 0, w - 32, h, "$INFO[ListItem.Label]", "font13", MUTED, "center", "center"))
    out.append(image(0, 0, w, h, art, diffuse=mask, aspect="scale", bg=True))
    out.append(progress(14, h - 20, w - 28, 6, "ListItem.PercentPlayed",
                        "Integer.IsGreater(ListItem.PercentPlayed,0) + !ListItem.IsFolder"))
    out.append(image(w - 40, 0, 40, 40, "corner.png", aspect="stretch", visible="String.IsEqual(ListItem.Property(corner),true)"))
    out.append(image(w - 52, 12, 40, 40, "circle.png", color=GLASS, aspect="stretch",
                     visible="!String.IsEmpty(ListItem.Property(badge))"))
    out.append(label(w - 52, 12, 40, 40, "$INFO[ListItem.Property(badge)]", "font12", GLASS_INK, "center", "center",
                     "!String.IsEmpty(ListItem.Property(badge))"))
    out.append(image(w - 52, 12, 40, 40, "circle.png", color="D10E131A", aspect="stretch",
                     visible="String.IsEqual(ListItem.Property(done),true)"))
    out.append(image(w - 44, 20, 24, 24, "icon-check.png", color=GLASS, aspect="keep",
                     visible="String.IsEqual(ListItem.Property(done),true)"))
    if focused:
        out.append(image(-4, -4, w + 8, h + 8, ring, aspect="stretch", visible="Control.HasFocus(%d)" % list_id))
    out.append("</control>")
    color = TEXT if focused else "D9E8EDF2"
    out.append(label(4, h + 16, w - 8, 34, "$INFO[ListItem.Label]", "font13", color, scroll=focused))
    out.append(label(4, h + 50, w - 8, 30, "$INFO[ListItem.Label2]", "font12", MUTED))
    return "".join(out)


def card_list(list_id, kind, left, top, width, onleft=None, extra=""):
    w, h = (240, 400) if kind == "poster" else (400, 300)
    nav = "<onleft>%s</onleft>" % onleft if onleft else ""
    return ('<control type="list" id="%d"><left>%d</left><top>%d</top><width>%d</width><height>%d</height>'
            '<orientation>horizontal</orientation><scrolltime tween="cubic" easing="out">260</scrolltime>%s%s'
            '<itemlayout width="%d" height="%d">%s</itemlayout><focusedlayout width="%d" height="%d">%s</focusedlayout>'
            '</control>' % (list_id, left, top, width, h + 20, nav, extra, w, h, card(kind, False, list_id), w, h,
                            card(kind, True, list_id)))


def face_list(list_id, left, top, width):
    """Cast: round photos with name and role."""
    def layout(focused):
        out = [image(20, 0, 160, 160, "circle.png", color=RAISED, aspect="stretch"),
               image(20, 0, 160, 160, "$INFO[ListItem.Art(thumb)]", diffuse="mask-circle.png", bg=True)]
        if focused:
            out.append(image(16, -4, 168, 168, "ring-circle.png", aspect="stretch", visible="Control.HasFocus(%d)" % list_id))
        out.append(label(0, 176, 200, 34, "$INFO[ListItem.Label]", "font13", TEXT, "center"))
        out.append(label(0, 210, 200, 30, "$INFO[ListItem.Label2]", "font12", MUTED, "center"))
        return "".join(out)
    return ('<control type="list" id="%d"><left>%d</left><top>%d</top><width>%d</width><height>260</height>'
            '<orientation>horizontal</orientation><scrolltime tween="cubic" easing="out">260</scrolltime>'
            '<itemlayout width="220" height="250">%s</itemlayout><focusedlayout width="220" height="250">%s</focusedlayout>'
            '</control>' % (list_id, left, top, width, layout(False), layout(True)))


# ---------------------------------------------------------------------- main window


def sidebar():
    item = lambda focused: "".join([  # noqa: E731
        image(0, 6, 290, 64, "panel.png", color=RAISED if focused else "00000000", aspect="stretch",
              visible="Control.HasFocus(100)" if focused else None),
        image(0, 6, 290, 64, "panel.png", color=SURFACE, aspect="stretch",
              visible="String.IsEqual(ListItem.Property(active),true)" + (" + !Control.HasFocus(100)" if focused else "")),
        image(0, 20, 6, 36, "accent.png", aspect="stretch",
              visible="String.IsEqual(ListItem.Property(active),true)"),
        image(26, 20, 36, 36, "$INFO[ListItem.Art(icon)]", color=TEXT if focused else MUTED, aspect="keep",
              visible="Control.HasFocus(100)" if focused else None),
        image(26, 20, 36, 36, "$INFO[ListItem.Art(icon)]", color=MUTED, aspect="keep",
              visible="!Control.HasFocus(100)") if focused else "",
        label(82, 6, 200, 64, "$INFO[ListItem.Label]", "font13", TEXT if focused else MUTED, aligny="center",
              visible="Control.HasFocus(100)" if focused else None),
        label(82, 6, 200, 64, "$INFO[ListItem.Label]", "font13", TEXT, aligny="center",
              visible="!Control.HasFocus(100)") if focused else "",
    ])
    return "".join([
        image(0, 0, SIDEBAR_W, 1080, "white.png", color=INK2, aspect="stretch"),
        image(SIDEBAR_W - 1, 0, 1, 1080, "white.png", color=LINE, aspect="stretch"),
        image(40, 42, 60, 60, "logo.png", aspect="keep"),
        label(114, 40, 200, 64, "FreeX", "font32_title", GLASS, aligny="center"),
        '<control type="list" id="100"><left>20</left><top>140</top><width>290</width><height>860</height>'
        '<orientation>vertical</orientation><onright>noop</onright><scrolltime>200</scrolltime>'
        '<itemlayout width="290" height="76">%s</itemlayout><focusedlayout width="290" height="76">%s</focusedlayout>'
        '</control>' % (item(False), item(True)),
        label(40, 1010, 260, 40, "$INFO[Window.Property(freex.user)]", "font12", MUTED),
    ])


def backdrops(ids):
    """The backdrop of the focused title, faded in behind the rows (as FreeX TV does)."""
    out = []
    for cid in ids:
        out.append(image(SIDEBAR_W, 0, 1920 - SIDEBAR_W, 900, "$INFO[Container(%d).ListItem.Art(fanart)]" % cid,
                         color="73FFFFFF", bg=True, visible="Control.HasFocus(%d)" % cid,
                         extra='<animation effect="fade" time="400">VisibleChange</animation>'))
    out.append(image(SIDEBAR_W, 0, 960, 900, "shade-left.png", aspect="stretch"))
    out.append(image(SIDEBAR_W, 360, 1920 - SIDEBAR_W, 540, "shade-bottom.png", aspect="stretch"))
    out.append(image(SIDEBAR_W, 0, 1920 - SIDEBAR_W, 200, "shade-top.png", aspect="stretch"))
    return "".join(out)


def main_window():
    rows = []
    row_ids = []
    width = 1920 - CONTENT_X
    for i in range(1, ROWS + 1):
        land, poster = 1000 + i, 1100 + i
        row_ids += [land, poster]
        title = "$INFO[Window.Property(row%d.title)]" % i
        rows.append('<control type="group"><height>370</height><width>%d</width>'
                    '<visible>String.IsEqual(Window.Property(row%d.style),land)</visible>%s%s</control>'
                    % (width, i, label(0, 0, width - 60, 56, title, "font32_title", TEXT, aligny="center"),
                       card_list(land, "land", 0, 66, width, onleft=100)))
        rows.append('<control type="group"><height>480</height><width>%d</width>'
                    '<visible>String.IsEqual(Window.Property(row%d.style),poster)</visible>%s%s</control>'
                    % (width, i, label(0, 0, width - 60, 56, title, "font32_title", TEXT, aligny="center"),
                       card_list(poster, "poster", 0, 66, width, onleft=100)))
    home = ('<control type="grouplist" id="200"><left>%d</left><top>40</top><width>%d</width><height>1040</height>'
            '<orientation>vertical</orientation><itemgap>18</itemgap><scrolltime tween="cubic" easing="out">300</scrolltime>'
            '<onleft>100</onleft><visible>String.IsEqual(Window.Property(view),home)</visible>%s</control>'
            % (CONTENT_X, width, "".join(rows)))
    def chip_layout(focused):
        # A pill per filter; the selected one keeps an orange outline.
        bg_on = image(0, 0, 250, 60, "pill-white.png", color=TEXT, aspect="stretch", visible="Control.HasFocus(301)")
        bg_off = image(0, 0, 250, 60, "pill-white.png", color=RAISED, aspect="stretch",
                       visible="!Control.HasFocus(301)" if focused else None)
        sel = image(0, 0, 250, 60, "pill-white.png", color="40F0974A", aspect="stretch",
                    visible="String.IsEqual(ListItem.Property(active),true)" + (" + !Control.HasFocus(301)" if focused else ""))
        text_on = label(0, 0, 250, 60, "$INFO[ListItem.Label]", "font13", INK, "center", "center", "Control.HasFocus(301)")
        text_off = label(0, 0, 250, 60, "$INFO[ListItem.Label]", "font13", TEXT, "center", "center",
                         "!Control.HasFocus(301)" if focused else None)
        return (bg_on + bg_off + sel + text_on + text_off) if focused else (bg_off + sel + text_off)

    grid = "".join([
        '<control type="group"><visible>String.IsEqual(Window.Property(view),grid)</visible>',
        label(CONTENT_X, 40, 1400, 80, "$INFO[Window.Property(header)]", "font45_title", TEXT, aligny="center"),
        '<control type="list" id="301"><left>%d</left><top>136</top><width>%d</width><height>60</height>'
        '<orientation>horizontal</orientation><onleft>100</onleft><ondown>300</ondown><onup>noop</onup>'
        '<visible>Integer.IsGreater(Container(301).NumItems,0)</visible>'
        '<itemlayout width="266" height="60">%s</itemlayout><focusedlayout width="266" height="60">%s</focusedlayout>'
        '</control>' % (CONTENT_X, width, chip_layout(False), chip_layout(True)),
        '<control type="panel" id="300"><left>%d</left><top>226</top><width>%d</width><height>854</height>'
        '<orientation>vertical</orientation><scrolltime tween="cubic" easing="out">260</scrolltime>'
        '<onleft>100</onleft><onup>301</onup>'
        '<itemlayout width="250" height="430">%s</itemlayout><focusedlayout width="250" height="430">%s</focusedlayout>'
        '</control>' % (CONTENT_X, width, card("poster", False, 300), card("poster", True, 300)),
        label(CONTENT_X, 500, width - 100, 60, "$INFO[Window.Property(empty)]", "font13", MUTED, "center"),
        "</control>",
    ])
    controls = "".join([
        image(0, 0, 1920, 1080, "white.png", color=INK, aspect="stretch"),
        backdrops(row_ids + [300]),
        home, grid, sidebar(),
    ])
    return window(controls, default=100)


# ---------------------------------------------------------------------- detail window


def circle_button(cid, left, top, icon, icon_on=None):
    """
    A round button with an icon as in FreeX (check, bookmark, restart). The four icon images (plain,
    "on" in orange, both dark when focused) have the ids cid*10+1 … cid*10+4, so the window can
    move them together with the button.
    """
    on_icon = icon_on or icon
    out = ['<control type="button" id="%d"><left>%d</left><top>%d</top><width>96</width><height>96</height>'
           '<texturefocus colordiffuse="%s">circle.png</texturefocus><texturenofocus colordiffuse="33FFFFFF">circle.png</texturenofocus>'
           '<label></label></control>' % (cid, left, top, TEXT)]
    variants = (
        (icon, TEXT, "!Control.HasFocus(%d) + !String.IsEqual(Window.Property(on%d),true)"),
        (on_icon, GLASS, "!Control.HasFocus(%d) + String.IsEqual(Window.Property(on%d),true)"),
        (icon, INK, "Control.HasFocus(%d) + !String.IsEqual(Window.Property(on%d),true)"),
        (on_icon, INK, "Control.HasFocus(%d) + String.IsEqual(Window.Property(on%d),true)"),
    )
    for n, (ic, color, cond) in enumerate(variants, 1):
        out.append('<control type="image" id="%d"><left>%d</left><top>%d</top><width>44</width><height>44</height>'
                   '<aspectratio>keep</aspectratio><texture colordiffuse="%s">icon-%s.png</texture>'
                   '<visible>Control.IsVisible(%d) + %s</visible></control>'
                   % (cid * 10 + n, left + 26, top + 26, color, ic, cid, cond % (cid, cid)))
    return "".join(out)


def detail_window():
    x = 560
    w = 1250
    rows = []
    for base, top, prop in ((50, 0, "a"), (60, 400, "b")):
        style = "Window.Property(row%s.style)" % prop
        rows.append('<control type="group"><top>%d</top><visible>!String.IsEmpty(%s)</visible>' % (top, style))
        rows.append(label(0, 0, 1500, 56, "$INFO[Window.Property(row%s.title)]" % prop, "font32_title", TEXT, aligny="center"))
        rows.append('<control type="group"><visible>String.IsEqual(%s,poster)</visible>%s</control>'
                    % (style, card_list(base, "poster", 0, 70, 1810)))
        rows.append('<control type="group"><visible>String.IsEqual(%s,land)</visible>%s</control>'
                    % (style, card_list(base + 1, "land", 0, 70, 1810)))
        rows.append('<control type="group"><visible>String.IsEqual(%s,face)</visible>%s</control>'
                    % (style, face_list(base + 2, 0, 74, 1810)))
        rows.append("</control>")
    top_part = "".join([
        # Poster (or the episode's still) with its progress.
        image(110, 110, 380, 570, "panel.png", color=RAISED, aspect="stretch",
              visible="!String.IsEqual(Window.Property(art.style),land)"),
        image(110, 110, 380, 570, "$INFO[Window.Property(poster)]", diffuse="mask-poster.png", bg=True,
              visible="!String.IsEqual(Window.Property(art.style),land)"),
        image(110, 110, 380, 214, "panel.png", color=RAISED, aspect="stretch",
              visible="String.IsEqual(Window.Property(art.style),land)"),
        image(110, 110, 380, 214, "$INFO[Window.Property(poster)]", diffuse="mask-land.png", bg=True,
              visible="String.IsEqual(Window.Property(art.style),land)"),
        '<control type="image" id="31"><left>130</left><top>650</top><width>340</width><height>8</height>'
        '<texture colordiffuse="8C000000">bar.png</texture><visible>!String.IsEmpty(Window.Property(progress))</visible></control>',
        '<control type="image" id="32"><left>130</left><top>650</top><width>1</width><height>8</height>'
        '<texture colordiffuse="%s">bar.png</texture><visible>!String.IsEmpty(Window.Property(progress))</visible></control>' % GLASS,
        label(x, 92, w, 100, "$INFO[Window.Property(title)]", "font52_title", TEXT, aligny="center"),
        label(x, 190, w, 50, "$INFO[Window.Property(subtitle)]", "font32_title", TEXT),
        label(x, 246, w, 44, "$INFO[Window.Property(meta)]", "font13", MUTED),
        # Main button: brand pill with a play icon.
        '<control type="button" id="21"><left>%d</left><top>310</top><width>440</width><height>96</height>'
        '<texturefocus>pill-brand.png</texturefocus><texturenofocus colordiffuse="CCFFFFFF">pill-brand.png</texturenofocus>'
        '<label>$INFO[Window.Property(playlabel)]</label><font>font13</font><textcolor>%s</textcolor>'
        '<focusedcolor>%s</focusedcolor><textoffsetx>80</textoffsetx><aligny>center</aligny></control>' % (x, GLASS_INK, GLASS_INK),
        image(x + 34, 336, 44, 44, "icon-play.png", color=GLASS_INK, aspect="keep"),
        circle_button(22, x + 404, 310, "restart"),
        circle_button(23, x + 522, 310, "check"),
        circle_button(24, x + 640, 310, "bookmark", "bookmark-on"),
        label(x, 432, w, 44, "$INFO[Window.Property(tagline)]", "font13", MUTED),
        '<control type="textbox"><left>%d</left><top>%d</top><width>1150</width><height>132</height>'
        '<font>font13</font><textcolor>%s</textcolor><label>$INFO[Window.Property(summary)]</label>'
        '<autoscroll delay="6000" time="3000" repeat="8000">true</autoscroll></control>' % (x, 478, TEXT),
        label(x, 618, w, 40, "$INFO[Window.Property(genres)]", "font13", MUTED),
        '<control type="textbox"><left>%d</left><top>668</top><width>1150</width><height>120</height>'
        '<font>font12</font><textcolor>%s</textcolor><label>$INFO[Window.Property(facts)]</label></control>' % (x, TEXT),
    ])
    controls = "".join([
        image(0, 0, 1920, 1080, "white.png", color=INK, aspect="stretch"),
        image(0, 0, 1920, 1080, "$INFO[Window.Property(backdrop)]", color="80FFFFFF", bg=True,
              extra='<animation effect="fade" time="400">WindowOpen</animation>'),
        image(0, 0, 1300, 1080, "shade-left.png", aspect="stretch"),
        image(0, 400, 1920, 680, "shade-bottom.png", aspect="stretch"),
        '<control type="group" id="300">'
        '<animation effect="slide" end="0,-430" time="320" tween="cubic" easing="out" '
        'condition="ControlGroup(400).HasFocus">Conditional</animation>',
        top_part,
        '<control type="group" id="400"><left>110</left><top>830</top>%s</control>' % "".join(rows),
        "</control>",
    ])
    return window(controls, default=21)


def skip_dialog():
    controls = "".join([
        '<control type="button" id="10"><left>1400</left><top>900</top><width>440</width><height>88</height>'
        '<texturefocus colordiffuse="F2FFFFFF">pill-white.png</texturefocus>'
        '<texturenofocus colordiffuse="CC1B2430">pill-white.png</texturenofocus>'
        '<label>$INFO[Window.Property(label)]</label><font>font13</font><textcolor>%s</textcolor>'
        '<focusedcolor>%s</focusedcolor><align>left</align><aligny>center</aligny><textoffsetx>84</textoffsetx>'
        '<animation effect="slide" start="0,60" time="300" tween="cubic" easing="out">WindowOpen</animation>'
        '<animation effect="fade" start="0" time="300">WindowOpen</animation></control>' % (TEXT, INK),
        image(1430, 922, 44, 44, "$INFO[Window.Property(icon)]", color=INK, aspect="keep", visible="Control.HasFocus(10)",
              extra='<animation effect="slide" start="0,60" time="300" tween="cubic" easing="out">WindowOpen</animation>'),
    ])
    return window(controls, default=10, dialog=True)


def window(controls, default, dialog=False):
    head = '<?xml version="1.0" encoding="UTF-8"?>\n<!-- Generated by tools/make_windows.py: change that, not this file. -->\n'
    return (head + '<window%s><defaultcontrol always="true">%d</defaultcontrol>'
            '<coordinates><left>0</left><top>0</top></coordinates>%s<controls>%s</controls></window>\n'
            % (' type="dialog"' if dialog else "", default,
               "<zorder>2</zorder>" if dialog else "<backgroundcolor>%s</backgroundcolor>" % INK, controls))


def main():
    os.makedirs(OUT, exist_ok=True)
    for name, content in (("freex-main.xml", main_window()), ("freex-detail.xml", detail_window()),
                          ("freex-skip.xml", skip_dialog())):
        with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
            f.write(content)
    print("written to", os.path.normpath(OUT))


if __name__ == "__main__":
    main()
