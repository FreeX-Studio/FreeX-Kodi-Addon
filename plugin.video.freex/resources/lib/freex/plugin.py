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

import os
import sys
from urllib.parse import parse_qsl, urlencode

import xbmc
import xbmcgui
import xbmcplugin

from . import items, playback, session, utils
from .api import ApiError
from .items import folder, plugin_url
from .utils import tr

class Plugin:
    def __init__(self, argv):
        self.base = argv[0]
        self.handle = int(argv[1])
        self.params = dict(parse_qsl(argv[2].lstrip("?"))) if len(argv) > 2 else {}
        self._api = None
        self._sorted = False

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
        if ok and not self._sorted and self.handle >= 0:
            # Menus keep the order they are built in (Kodi would otherwise sort them by date).
            xbmcplugin.addSortMethod(self.handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.endOfDirectory(self.handle, succeeded=ok, cacheToDisc=cache)

    def add(self, entries):
        xbmcplugin.addDirectoryItems(self.handle, entries, len(entries))

    def content(self, kind):
        xbmcplugin.setContent(self.handle, kind)

    def sorts(self, *methods):
        self._sorted = True
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
        if self.open_windows():
            return self.end(False)
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

    def open_windows(self):
        """
        Opening the add-on shows the FreeX windows (setting "Open FreeX in its own design"). Not when
        the skin reads the folder in the background, e.g. for a widget on the home screen.
        """
        if not utils.setting_bool("freex_ui") or self.handle < 0:
            return False
        if xbmc.getCondVisibility("Window.IsActive(home)"):
            return False
        xbmc.executebuiltin("RunScript(%s)" % os.path.join(utils.ADDON_PATH, "ui.py"))
        return True

    def do_ui(self):
        xbmc.executebuiltin("RunScript(%s)" % os.path.join(utils.ADDON_PATH, "ui.py"))
        if self.handle >= 0:
            self.end(False)

    def hub_folders(self, hubs, library_id=None):
        out = []
        for hub in hubs or []:
            # The watchlist has its own entry in the main menu.
            if not hub.get("items") or hub.get("key") == "watchlist":
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
        self.sorts(xbmcplugin.SORT_METHOD_LABEL)
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
        self.sorts(xbmcplugin.SORT_METHOD_LABEL_IGNORE_THE)
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
        it = self.api.item(self.params["id"])
        li, info = playback.prepare(self.api, it)
        playback.publish(info)
        xbmcplugin.setResolvedUrl(self.handle, True, li)


def run(argv=None):
    Plugin(argv or sys.argv).run()
