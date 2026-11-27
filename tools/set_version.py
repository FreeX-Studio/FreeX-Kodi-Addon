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
Version helper for releases (used by .github/workflows/release.yml, works locally as well).

  python3 tools/set_version.py current           prints the version in addon.xml
  python3 tools/set_version.py set X.Y.Z         writes X.Y.Z into addon.xml and fills its <news>
                                                 from the CHANGELOG section of that version
  python3 tools/set_version.py notes X.Y.Z       prints the CHANGELOG section of X.Y.Z (release notes)

A CHANGELOG section starts with a heading "## FreeX for Kodi X.Y.Z". Without one the release notes
and <news> name only the version.
"""

import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
ADDON_XML = os.path.join(ROOT, "plugin.video.freex", "addon.xml")
CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")
# Kodi shows <news> in the add-on's information dialog; its repositories allow 1500 characters.
NEWS_LIMIT = 1500


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def current():
    m = re.search(r'<addon\b[^>]*\bversion="([^"]+)"', read(ADDON_XML))
    if not m:
        sys.exit("No version in addon.xml")
    return m.group(1)


def notes(version):
    """The CHANGELOG text below "## FreeX for Kodi <version>" up to the next heading of that level."""
    try:
        text = read(CHANGELOG)
    except OSError:
        return ""
    m = re.search(r"^## FreeX for Kodi %s[ \t]*\n(.*?)(?=^## |\Z)" % re.escape(version), text, re.M | re.S)
    return m.group(1).strip() if m else ""


def news(version):
    """The CHANGELOG section as plain text for Kodi: no Markdown emphasis, lines joined per item."""
    body = notes(version)
    if not body:
        return "%s: see https://github.com/FreeX-Studio/FreeX-Kodi-Addon/releases" % version
    body = re.sub(r"[*_`]", "", body)
    body = re.sub(r"\n[ \t]+", " ", body)  # continuation lines of a list item
    text = "%s:\n%s" % (version, body)
    if len(text) > NEWS_LIMIT:
        text = text[:NEWS_LIMIT - 1].rsplit(" ", 1)[0] + "…"
    return text


def escape(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def set_version(version):
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        sys.exit("Version must be X.Y.Z, got %r" % version)
    xml = read(ADDON_XML)
    xml, n = re.subn(r'(<addon\b[^>]*\bversion=")[^"]+(")', r"\g<1>%s\g<2>" % version, xml, count=1)
    if n != 1:
        sys.exit("No version in addon.xml")
    xml, n = re.subn(r"<news>.*?</news>", lambda _: "<news>%s</news>" % escape(news(version)), xml, count=1, flags=re.S)
    if n != 1:
        sys.exit("No <news> in addon.xml")
    with open(ADDON_XML, "w", encoding="utf-8") as f:
        f.write(xml)


def main():
    if len(sys.argv) == 2 and sys.argv[1] == "current":
        print(current())
    elif len(sys.argv) == 3 and sys.argv[1] == "set":
        set_version(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "notes":
        print(notes(sys.argv[2]) or "FreeX for Kodi %s" % sys.argv[2])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
