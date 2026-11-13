#!/bin/sh
# Copyright (c) 2026 MirraNET, Niklas Linz. All rights reserved.
#
# This file is part of the MirraNET project and is licensed under the
# GNU Lesser General Public License v3.0 (LGPLv3).
#
# You may use, distribute and modify this code under the terms
# of the LGPLv3 license. You should have received a copy of the
# license along with this file. If not, see <https://www.gnu.org/licenses/lgpl-3.0.html>
# or contact: niklas.linz@mirranet.de

# Packs the add-on into dist/plugin.video.freex-<version>.zip, the file Kodi installs with
# "Install from zip file". Needs python3 (for the version and the checks) and zip.
set -eu
cd "$(dirname "$0")"

ADDON=plugin.video.freex
VERSION=$(python3 -c "import xml.etree.ElementTree as E; print(E.parse('$ADDON/addon.xml').getroot().get('version'))")

# Every Python file must compile with the oldest Python a supported Kodi ships (3.8 on Kodi 20).
python3 -m py_compile $(find "$ADDON" -name '*.py')
find "$ADDON" -name '__pycache__' -type d -prune -exec rm -rf {} +

# addon.xml and settings.xml must be well-formed, or Kodi refuses the add-on.
python3 -c "import xml.etree.ElementTree as E; E.parse('$ADDON/addon.xml'); E.parse('$ADDON/resources/settings.xml')"

mkdir -p dist
rm -f "dist/$ADDON-$VERSION.zip"
zip -qr "dist/$ADDON-$VERSION.zip" "$ADDON" -x '*/__pycache__/*' '*.pyc' '*/.DS_Store'
echo "dist/$ADDON-$VERSION.zip"
