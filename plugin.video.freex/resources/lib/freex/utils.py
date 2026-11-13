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
Small helpers shared by the plugin and the service: settings, translated strings, logging and the
state kept between starts (server, sign-in token, the id of this device).

The token is not a Kodi setting on purpose: settings.xml is plain text that users copy around when
they ask for help, and the token gives full access to the account.
"""

import json
import os
import platform
import uuid

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "plugin.video.freex"
ADDON = xbmcaddon.Addon(ADDON_ID)
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
VERSION = ADDON.getAddonInfo("version")
STATE_FILE = os.path.join(PROFILE, "state.json")

# Window property through which the plugin tells the service what is being played.
PLAYING_PROPERTY = "freex.playing"
HOME_WINDOW = 10000


_settings = None


def addon():
    """
    The Addon object the settings are read from. Creating one reads settings.xml from disk, which
    takes long on small devices, so it is kept; the service calls reload_settings() when Kodi
    reports changed settings.
    """
    global _settings  # pylint: disable=global-statement
    if _settings is None:
        _settings = xbmcaddon.Addon(ADDON_ID)
    return _settings


def reload_settings():
    global _settings  # pylint: disable=global-statement
    _settings = None


def tr(string_id, *args):
    """A translated string; {0}, {1} … are replaced by the arguments."""
    s = ADDON.getLocalizedString(string_id)
    for i, a in enumerate(args):
        s = s.replace("{%d}" % i, str(a))
    return s


def log(msg, level=xbmc.LOGDEBUG):
    xbmc.log("[%s] %s" % (ADDON_ID, msg), level)


def setting(key):
    return addon().getSetting(key)


def setting_bool(key):
    return addon().getSetting(key) == "true"


def setting_int(key, default=0):
    try:
        return int(addon().getSetting(key))
    except (TypeError, ValueError):
        return default


def set_setting(key, value):
    addon().setSetting(key, value)


def notify(msg, error=False, ms=4000):
    xbmcgui.Dialog().notification("FreeX", msg,
                                  xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO, ms)


def ui_language():
    """The two letters of Kodi's interface language, for the server's messages."""
    try:
        lang = xbmc.getLanguage(xbmc.ISO_639_1) or "en"
    except Exception:  # pylint: disable=broad-except
        lang = "en"
    return lang.split("-")[0].lower() or "en"


def device_name():
    """How this Kodi appears in the server's activity view."""
    custom = setting("device_name").strip()
    if custom:
        return custom
    name = xbmc.getInfoLabel("System.FriendlyName") or platform.node() or ""
    return ("Kodi on " + name) if name and name.lower() != "kodi" else "Kodi"


# ---------------------------------------------------------------------- state


def load_state():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f) or {}
    except (OSError, ValueError):
        state = {}
    if not state.get("clientId"):
        state["clientId"] = "kodi-" + uuid.uuid4().hex[:16]
        save_state(state)
    return state


def save_state(state):
    try:
        os.makedirs(PROFILE, exist_ok=True)
        tmp = STATE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f)
        os.replace(tmp, STATE_FILE)
        try:
            os.chmod(STATE_FILE, 0o600)
        except OSError:
            pass  # not on every platform
    except OSError as e:
        log("Cannot save the state: %s" % e, xbmc.LOGWARNING)


# ---------------------------------------------------------------------- formatting


def ms_to_s(ms):
    try:
        return max(0, int(round((ms or 0) / 1000.0)))
    except (TypeError, ValueError):
        return 0


def episode_code(it):
    season = it.get("seasonIndex")
    if season == 0:
        return "Special E%s" % it.get("index", "?")
    return "S%02dE%02d" % (season or 0, it.get("index") or 0) if season is not None else "E%s" % it.get("index", "?")


def kodi_version():
    try:
        return int(xbmc.getInfoLabel("System.BuildVersion").split(".")[0])
    except (ValueError, IndexError):
        return 20
