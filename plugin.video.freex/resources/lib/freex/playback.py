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
Starting a playback: the plugin resolves Kodi's play request with it, the FreeX windows start the
player directly (with the position to resume at).
"""

import json
import os

import xbmc
import xbmcgui

from . import items, utils
from .api import ApiError

QUALITIES = ["auto", "original", "20000", "12000", "8000", "4000", "2000", "1000"]

CONTAINER_MIME = {
    "mkv": "video/x-matroska", "webm": "video/webm", "mp4": "video/mp4", "m4v": "video/mp4", "mov": "video/quicktime",
    "avi": "video/x-msvideo", "ts": "video/mp2t", "m2ts": "video/mp2t", "mts": "video/mp2t", "wmv": "video/x-ms-wmv",
    "mpg": "video/mpeg", "mpeg": "video/mpeg", "flv": "video/x-flv", "ogv": "video/ogg",
}


def prepare(api, it):
    """
    Asks the server how to play a title and returns (ListItem, info): the list item with the
    stream URL, subtitles and info labels, and what the service needs to follow the playback.
    """
    state = utils.load_state()
    server_mode = utils.setting_int("play_mode") == 1
    body = {"client": state.get("clientId"), "device": utils.device_name(), "tokenUrls": True, "startMs": 0}
    if server_mode:
        body["caps"] = kodi_caps()
        body["quality"] = QUALITIES[min(utils.setting_int("quality"), len(QUALITIES) - 1)]
    else:
        # Kodi decodes practically everything itself: always the file as it is, like mpv in FreeX Desktop.
        body["player"] = "external"
    plan = api.playback(it["id"], body)
    url = api.server + plan["url"]
    if not api.verify_tls:
        url += "|verifypeer=false"

    _, li, _ = items.build(api, it, with_menu=False)
    li.setPath(url)
    li.setContentLookup(False)
    hls = bool(plan.get("session"))
    if hls:
        li.setMimeType("application/vnd.apple.mpegurl")
        if utils.setting_bool("inputstream") and xbmc.getCondVisibility("System.HasAddon(inputstream.adaptive)"):
            li.setProperty("inputstream", "inputstream.adaptive")
            if utils.kodi_version() < 21:
                li.setProperty("inputstream.adaptive.manifest_type", "hls")
    else:
        container = ((it.get("media") or {}).get("container") or "").lower()
        li.setMimeType(CONTAINER_MIME.get(container, "video/x-matroska"))

    subs = subtitle_files(api, it, hls)
    if subs:
        li.setSubtitles(subs)

    # Where to start is decided by Kodi's own resume dialog on the list item; a resume point on
    # the resolved item would make Kodi resume even after "from the beginning" was chosen.
    li.getVideoInfoTag().setResumePoint(0, utils.ms_to_s((it.get("media") or {}).get("durationMs")))

    nxt = it.get("next")
    info = {
        "itemId": it["id"], "type": it.get("type"), "title": it.get("title"), "showTitle": it.get("showTitle"),
        "server": api.server, "url": plan["url"], "token": cast_token(plan["url"]),
        "session": plan.get("session"), "mode": plan.get("mode"),
        "durationMs": plan.get("durationMs") or (it.get("media") or {}).get("durationMs") or 0,
        "markers": it.get("markers") or {}, "next": compact(nxt) if nxt else None, "current": compact(it),
    }
    utils.log("Playing %s: %s" % (it.get("id"), plan.get("mode")), xbmc.LOGINFO)
    return li, info


def publish(info):
    """Tells the background service what is about to play."""
    win = xbmcgui.Window(utils.HOME_WINDOW)
    win.clearProperty(utils.SAVED_PROPERTY)
    win.setProperty(utils.PLAYING_PROPERTY, json.dumps(info))


def start(api, it, resume=True):
    """
    Plays a title from the FreeX windows. `it` is the full item (GET /api/items/{id}); with
    resume, playback starts at the saved position unless the title counts as watched.
    """
    li, info = prepare(api, it)
    p = it.get("progress") or {}
    if resume and p.get("offsetMs") and not p.get("watched"):
        li.setProperty("StartOffset", "%.3f" % (p["offsetMs"] / 1000.0))
    publish(info)
    xbmc.Player().play(li.getPath(), li)


def subtitle_files(api, it, hls):
    """
    Subtitle files next to the video (and, for converted streams, the text subtitles inside it,
    which HLS does not carry) as local WebVTT files; Kodi reads subtitles inside the file itself.
    """
    out = []
    folder_path = os.path.join(utils.PROFILE, "subtitles")
    try:
        os.makedirs(folder_path, exist_ok=True)
        for name in os.listdir(folder_path):
            os.remove(os.path.join(folder_path, name))
    except OSError:
        pass
    for s in (it.get("media") or {}).get("subtitles") or []:
        if not s.get("textBased"):
            continue
        if not s.get("external") and not hls:
            continue
        lang = s.get("language") or "und"
        name = "%s.%s%s.vtt" % (s["id"], lang, ".forced" if s.get("forced") else "")
        path = os.path.join(folder_path, name)
        try:
            data = api.subtitle(it["id"], s["id"])
            with open(path, "wb") as f:
                f.write(data)
            out.append(path)
        except (ApiError, OSError) as e:
            utils.log("Subtitle %s: %s" % (s.get("id"), e), xbmc.LOGWARNING)
    return out


def cast_token(url):
    """The "/api/cast/<token>/" part of a stream URL: it is new for every playback."""
    parts = url.split("/")
    try:
        i = parts.index("cast")
        return "/".join(parts[:i + 2]) + "/"
    except ValueError:
        return url


def compact(it):
    """What the service needs to know about an episode (Up Next, the next-episode button)."""
    if not it:
        return None
    media = it.get("media") or {}
    p = it.get("progress") or {}
    return {k: v for k, v in {
        "id": it.get("id"), "type": it.get("type"), "title": it.get("title"), "showTitle": it.get("showTitle"),
        "showId": it.get("showId"), "seasonIndex": it.get("seasonIndex"), "index": it.get("index"),
        "summary": it.get("summary"), "rating": it.get("rating"), "artVersion": it.get("artVersion"),
        "durationMs": media.get("durationMs"), "watched": p.get("watched"),
        "airDate": (it.get("metadata") or {}).get("airDate"),
    }.items() if v is not None}


def kodi_caps():
    """What Kodi decodes, for the server's decision in "let the server decide" mode."""
    video = ["h264", "mpeg2video", "mpeg4", "vc1", "vp8", "vp9"]
    if utils.setting_bool("decode_hevc"):
        video.append("hevc")
    if utils.setting_bool("decode_av1"):
        video.append("av1")
    audio = ["aac", "mp3", "mp2", "ac3", "eac3", "dts", "truehd", "flac", "opus", "vorbis", "alac", "pcm_s16le", "pcm_s24le"]
    return {
        "containers": ["mkv", "mp4", "m4v", "mov", "webm", "avi", "ts", "m2ts", "mts", "mpg", "mpeg", "wmv", "flv"],
        "video": video, "audio": audio, "mseVideo": video, "mseAudio": audio,
        "hevcMain10": utils.setting_bool("decode_hevc"), "mseHevcMain10": utils.setting_bool("decode_hevc"),
    }
