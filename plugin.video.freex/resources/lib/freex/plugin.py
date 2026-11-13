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
The plugin: one call per folder Kodi opens (plugin://plugin.video.freex/?action=…) and for playback.

Every folder is read fresh from the server, so watch state changed in FreeX Web or another app is
shown at once; Kodi's own video database is not used.
"""

import json
import os
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcgui
import xbmcplugin

from . import items, session, utils
from .api import ApiError
from .items import folder, plugin_url
from .utils import tr

QUALITIES = ["auto", "original", "20000", "12000", "8000", "4000", "2000", "1000"]

CONTAINER_MIME = {
    "mkv": "video/x-matroska", "webm": "video/webm", "mp4": "video/mp4", "m4v": "video/mp4", "mov": "video/quicktime",
    "avi": "video/x-msvideo", "ts": "video/mp2t", "m2ts": "video/mp2t", "mts": "video/mp2t", "wmv": "video/x-ms-wmv",
    "mpg": "video/mpeg", "mpeg": "video/mpeg", "flv": "video/x-flv", "ogv": "video/ogg",
}


class Plugin:
    def __init__(self, argv):
        self.base = argv[0]
        self.handle = int(argv[1])
        self.params = dict(parse_qsl(argv[2].lstrip("?"))) if len(argv) > 2 else {}
        self._api = None

    @property
    def api(self):
        if self._api is None:
            self._api = session.client()
        return self._api

    # ------------------------------------------------------------------ dispatch

    def run(self):
        action = self.params.get("action", "root")
        handler = getattr(self, "do_" + action, None)
        if handler is None:
            utils.log("Unknown action %s" % action, xbmc.LOGWARNING)
            return self.end(False)
        try:
            handler()
        except session.NotSignedIn as e:
            if action in ("root", "login"):
                raise
            utils.notify(str(e), error=True)
            self.fail(action)
        except ApiError as e:
            if e.status == 401:
                session.forget_token()
                utils.notify(tr(30063), error=True)
                xbmc.executebuiltin("Container.Update(%s,replace)" % plugin_url())
            else:
                utils.notify(e.message if e.status else tr(30056) + ": " + e.message, error=True)
            utils.log("%s failed: %s (%s)" % (action, e.message, e.status), xbmc.LOGWARNING)
            self.fail(action)

    def fail(self, action):
        if action == "play":
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
        elif self.handle >= 0 and action not in ("watched", "watchlist_toggle", "login", "logout", "settings"):
            xbmcplugin.endOfDirectory(self.handle, succeeded=False)

    def end(self, ok=True, cache=False):
        xbmcplugin.endOfDirectory(self.handle, succeeded=ok, cacheToDisc=cache)

    def add(self, entries):
        xbmcplugin.addDirectoryItems(self.handle, entries, len(entries))

    def content(self, kind):
        xbmcplugin.setContent(self.handle, kind)

    def sorts(self, *methods):
        for m in methods:
            xbmcplugin.addSortMethod(self.handle, m)

    def list_items(self, its, context="", content=None, sortable=True):
        """Adds FreeX items, picks the content type from what they are and offers sort orders."""
        entries = [items.build(self.api, it, context) for it in its if it and it.get("id")]
        self.add(entries)
        types = {it.get("type") for it in its if it}
        if content is None:
            if types == {"movie"}:
                content = "movies"
            elif types == {"show"}:
                content = "tvshows"
            elif types == {"season"}:
                content = "seasons"
            elif types == {"episode"}:
                content = "episodes"
            else:
                content = "videos"
        self.content(content)
        if not sortable:
            self.sorts(xbmcplugin.SORT_METHOD_UNSORTED)
        elif content == "episodes" and context == "season":
            self.sorts(xbmcplugin.SORT_METHOD_EPISODE, xbmcplugin.SORT_METHOD_LABEL)
        else:
            self.sorts(xbmcplugin.SORT_METHOD_UNSORTED, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE,
                       xbmcplugin.SORT_METHOD_VIDEO_YEAR, xbmcplugin.SORT_METHOD_VIDEO_RATING,
                       xbmcplugin.SORT_METHOD_DATEADDED, xbmcplugin.SORT_METHOD_DURATION)

    # ------------------------------------------------------------------ menus

    def do_root(self):
        if not session.is_signed_in():
            self.add([
                folder(tr(30005), plugin_url(action="login"), "DefaultUser.png", plot=session.configured_server()),
                folder(tr(30018), plugin_url(action="settings"), "DefaultAddonProgram.png"),
            ])
            return self.end()
        entries = []
        try:
            libraries = self.api.libraries()
            hubs = self.api.hubs() if utils.setting_bool("hubs_in_root") else None
        except ApiError as e:
            if e.status == 401:
                session.forget_token()
                utils.notify(tr(30063), error=True)
                return self.do_root()
            # Unreachable: the settings must stay reachable, so the menu still opens.
            utils.notify(tr(30056) + ": " + e.message, error=True)
            self.add([
                folder(tr(30037), "%s" % plugin_url(action="retry"), "DefaultAddonsUpdates.png"),
                folder(tr(30018), plugin_url(action="settings"), "DefaultAddonProgram.png"),
            ])
            return self.end()
        if hubs is not None:
            entries += self.hub_folders(hubs)
        else:
            entries.append(folder(tr(30001), plugin_url(action="hubs"), "DefaultRecentlyAddedMovies.png"))
        for lib in libraries:
            icon = "DefaultTVShows.png" if lib.get("type") == "shows" else "DefaultMovies.png"
            entries.append(folder(lib.get("name") or "?", plugin_url(action="library", id=lib["id"]), icon))
        entries += [
            folder(tr(30002), plugin_url(action="watchlist"), "DefaultFavourites.png"),
            folder(tr(30003), plugin_url(action="playlists"), "DefaultPlaylist.png"),
            folder(tr(30004), plugin_url(action="search"), "DefaultAddonsSearch.png"),
        ]
        self.add(entries)
        self.end()

    def hub_folders(self, hubs, library_id=None):
        out = []
        for hub in hubs or []:
            if not hub.get("items"):
                continue
            icon = hub["items"][0]
            art = {"thumb": self.api.art(icon, "poster" if icon.get("type") != "episode" else "thumb"),
                   "fanart": self.api.art({"id": icon.get("showId") or icon["id"], "artVersion": icon.get("artVersion")},
                                          "backdrop")}
            out.append(folder(hub.get("title") or hub.get("key"),
                              plugin_url(action="hub", key=hub.get("key"), lib=library_id), art=art))
        return out

    def do_hubs(self):
        self.add(self.hub_folders(self.api.hubs()))
        self.end()

    def do_hub(self):
        lib = self.params.get("lib")
        hubs = self.api.request("GET", "/api/libraries/%s/hubs" % lib) if lib else self.api.hubs()
        hub = next((h for h in hubs or [] if h.get("key") == self.params.get("key")), None)
        self.list_items((hub or {}).get("items") or [], sortable=False)
        self.end()

    def do_library(self):
        lib_id = self.params["id"]
        entries = [
            folder(tr(30008), plugin_url(action="items", id=lib_id, sort="title")),
            folder(tr(30009), plugin_url(action="items", id=lib_id, sort="title", watched="unwatched")),
            folder(tr(30010), plugin_url(action="items", id=lib_id, sort="added", order="desc", watched="inProgress")),
            folder(tr(30011), plugin_url(action="items", id=lib_id, sort="added", order="desc", addedDays="60")),
        ]
        try:
            entries += self.hub_folders(self.api.request("GET", "/api/libraries/%s/hubs" % lib_id), lib_id)
        except ApiError:
            pass  # older servers without library rows
        entries += [
            folder(tr(30012), plugin_url(action="collections", id=lib_id), "DefaultSets.png"),
            folder(tr(30013), plugin_url(action="genres", id=lib_id), "DefaultGenre.png"),
            folder(tr(30014), plugin_url(action="years", id=lib_id), "DefaultYear.png"),
        ]
        self.add(entries)
        self.end()

    FILTER_KEYS = ("sort", "order", "watched", "genre", "yearFrom", "yearTo", "minRating", "resolution",
                   "contentRating", "person", "addedDays", "q")

    def do_items(self):
        query = urlencode({k: self.params[k] for k in self.FILTER_KEYS if self.params.get(k)})
        res = self.api.library_items(self.params["id"], query)
        self.list_items(res.get("items") or [])
        self.end()

    def do_genres(self):
        res = self.api.library_items(self.params["id"])
        self.add([folder(g, plugin_url(action="items", id=self.params["id"], sort="title", genre=g), "DefaultGenre.png")
                  for g in res.get("genres") or []])
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL)
        self.end()

    def do_years(self):
        res = self.api.library_items(self.params["id"])
        years = res.get("years") or []
        decades = []
        if len(years) == 2 and years[0] and years[1]:
            first, last = int(years[0]) // 10 * 10, int(years[1]) // 10 * 10
            decades = list(range(last, first - 1, -10))
        self.add([folder("%ds" % d, plugin_url(action="items", id=self.params["id"], sort="year", order="desc",
                                               yearFrom=d, yearTo=d + 9), "DefaultYear.png") for d in decades])
        self.end()

    def do_collections(self):
        entries = []
        for c in self.api.library_collections(self.params["id"]):
            url, li, _ = folder(c.get("title") or "?", plugin_url(action="collection", id=c["id"]), "DefaultSets.png",
                                art={"thumb": self.api.collection_art(c["id"], "poster"),
                                     "poster": self.api.collection_art(c["id"], "poster"),
                                     "fanart": self.api.collection_art(c["id"], "backdrop")})
            li.getVideoInfoTag().setMediaType("set")
            entries.append((url, li, True))
        self.add(entries)
        self.content("sets")
        xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
        self.end()

    def do_collection(self):
        c = self.api.collection(self.params["id"])
        self.list_items(c.get("items") or [], sortable=False)
        self.end()

    def do_playlists(self):
        entries = []
        for p in self.api.playlists():
            art = {}
            if p.get("firstItemId"):
                art = {"thumb": self.api.art(p["firstItemId"], "thumb"), "fanart": self.api.art(p["firstItemId"], "backdrop")}
            entries.append(folder("%s (%d)" % (p.get("title") or "?", p.get("childCount") or 0),
                                  plugin_url(action="playlist", id=p["id"]), "DefaultPlaylist.png", art=art))
        self.add(entries)
        self.end()

    def do_playlist(self):
        self.list_items(self.api.playlist(self.params["id"]).get("items") or [], sortable=False)
        self.end()

    def do_watchlist(self):
        self.list_items(self.api.watchlist(), sortable=False)
        self.end()

    def do_search(self):
        text = self.params.get("q")
        if not text:
            text = xbmcgui.Dialog().input(tr(30059), type=xbmcgui.INPUT_ALPHANUM)
            if not text or len(text.strip()) < 2:
                return self.end(False)
            # Into the history, so "back" from a title returns to the results without asking again.
            xbmc.executebuiltin("Container.Update(%s,replace)" % plugin_url(action="search", q=text.strip()))
            return self.end(False)
        res = self.api.search(text)
        found = (res.get("movies") or []) + (res.get("shows") or []) + (res.get("episodes") or [])
        if not found:
            utils.notify(tr(30060))
        self.list_items(found, sortable=False)
        self.end()

    # ------------------------------------------------------------------ shows

    def do_show(self):
        show = self.api.item(self.params["id"])
        seasons = [c for c in show.get("children") or [] if c.get("type") == "season"]
        for s in seasons:
            s.setdefault("showId", show["id"])
            s.setdefault("showTitle", show.get("title"))
            s.setdefault("artVersion", show.get("artVersion"))
        if len(seasons) == 1 and utils.setting_bool("flatten_seasons") and not self.params.get("all"):
            return self.show_season(seasons[0]["id"])
        if not seasons:
            episodes = [c for c in show.get("children") or [] if c.get("type") == "episode"]
            self.list_items(episodes, "season")
            return self.end()
        self.list_items(seasons, "show", content="seasons", sortable=False)
        self.end()

    def do_season(self):
        self.show_season(self.params["id"])

    def show_season(self, season_id):
        season = self.api.item(season_id)
        episodes = [c for c in season.get("children") or [] if c.get("type") == "episode"]
        self.list_items(episodes, "season", content="episodes")
        self.end()

    def do_item(self):
        it = self.api.item(self.params["id"])
        t = it.get("type")
        if t == "show":
            self.params["id"] = it["id"]
            return self.do_show()
        if t == "season":
            return self.show_season(it["id"])
        self.list_items([it] + (it.get("extras") or []), "extras", sortable=False)
        self.end()

    def do_extras(self):
        it = self.api.item(self.params["id"])
        extras = it.get("extras") or []
        if not extras:
            utils.notify(tr(30061))
        self.list_items(extras, "extras", content="videos", sortable=False)
        self.end()

    # ------------------------------------------------------------------ actions

    def do_retry(self):
        xbmc.executebuiltin("Container.Update(%s,replace)" % plugin_url())
        self.end(False)

    def do_login(self):
        ok = session.sign_in()
        if self.handle >= 0:
            # Opened as a folder from the main menu: back to the (now signed-in) main menu.
            self.end(False)
            if ok:
                xbmc.executebuiltin("Container.Update(%s,replace)" % plugin_url())

    def do_logout(self):
        session.sign_out()
        if self.handle >= 0:
            self.end(False)

    def do_settings(self):
        utils.ADDON.openSettings()
        if self.handle >= 0:
            self.end(False)

    def do_watched(self):
        self.api.set_watched(self.params["id"], self.params.get("on") == "1")
        xbmc.executebuiltin("Container.Refresh")

    def do_watchlist_toggle(self):
        self.api.set_watchlist(self.params["id"], self.params.get("on") == "1")
        xbmc.executebuiltin("Container.Refresh")

    # ------------------------------------------------------------------ playback

    def do_play(self):
        api = self.api
        it = api.item(self.params["id"])
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

        subs = self.subtitle_files(api, it, hls)
        if subs:
            li.setSubtitles(subs)

        if self.params.get("start") == "0":
            li.getVideoInfoTag().setResumePoint(0, utils.ms_to_s((it.get("media") or {}).get("durationMs")))
            li.setProperty("StartOffset", "0")

        nxt = it.get("next")
        info = {
            "itemId": it["id"], "type": it.get("type"), "title": it.get("title"), "showTitle": it.get("showTitle"),
            "server": api.server, "url": plan["url"], "session": plan.get("session"), "mode": plan.get("mode"),
            "durationMs": plan.get("durationMs") or (it.get("media") or {}).get("durationMs") or 0,
            "markers": it.get("markers") or {}, "next": compact(nxt) if nxt else None, "current": compact(it),
        }
        xbmcgui.Window(utils.HOME_WINDOW).setProperty(utils.PLAYING_PROPERTY, json.dumps(info))
        utils.log("Playing %s: %s" % (it.get("id"), plan.get("mode")), xbmc.LOGINFO)
        xbmcplugin.setResolvedUrl(self.handle, True, li)

    def subtitle_files(self, api, it, hls):
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


def run(argv=None):
    Plugin(argv or sys.argv).run()
