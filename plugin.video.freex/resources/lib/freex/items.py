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
Turns FreeX items (movies, shows, seasons, episodes, extras) into Kodi list items: info labels,
artwork, watch state, resume points and stream details, so skins show them like library entries.
"""

import time
from urllib.parse import urlencode

import xbmc
import xbmcgui

from . import utils
from .utils import tr

PLUGIN = "plugin://" + utils.ADDON_ID + "/"

MEDIATYPE = {"movie": "movie", "show": "tvshow", "season": "season", "episode": "episode", "extra": "video"}

HDR_TYPES = {"HDR10": "hdr10", "HLG": "hlg", "Dolby Vision": "dolbyvision"}


def plugin_url(**params):
    params = {k: v for k, v in params.items() if v is not None and v != ""}
    return PLUGIN + ("?" + urlencode(params) if params else "")


def playable(it):
    return it.get("type") in ("movie", "episode", "extra")


def _genres(it):
    g = it.get("genres") or ""
    if isinstance(g, list):
        return [x for x in g if x]
    return [x.strip() for x in g.split(",") if x.strip()]


def _date(ms):
    if not ms:
        return ""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(ms) / 1000))
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def label_of(it, context=""):
    """
    The label in lists. Episodes outside their season (home rows, search, playlists) carry their
    show and number, as in FreeX Web.
    """
    t = it.get("type")
    title = it.get("title") or ""
    if t == "episode":
        if context == "season":
            return "%s. %s" % (it.get("index", ""), title) if it.get("index") is not None else title
        show = it.get("showTitle") or ""
        return ("%s – %s · %s" % (show, utils.episode_code(it), title)) if show else title
    if t == "extra" and context != "extras" and it.get("ownerTitle"):
        return "%s – %s" % (it["ownerTitle"], title)
    return title


def build(api, it, context="", with_menu=True):
    """(url, ListItem, is_folder) for one item."""
    t = it.get("type")
    li = xbmcgui.ListItem(label_of(it, context), offscreen=True)
    tag = li.getVideoInfoTag()
    tag.setMediaType(MEDIATYPE.get(t, "video"))
    tag.setTitle(it.get("title") or "")
    if it.get("originalTitle") and it.get("originalTitle") != it.get("title"):
        tag.setOriginalTitle(it["originalTitle"])
    if it.get("year"):
        tag.setYear(int(it["year"]))
    if it.get("summary"):
        tag.setPlot(it["summary"])
        tag.setPlotOutline(it["summary"])
    if it.get("tagline"):
        tag.setTagLine(it["tagline"])
    genres = _genres(it)
    if genres:
        tag.setGenres(genres)
    try:
        rating = float(it.get("rating") or 0)
    except (TypeError, ValueError):
        rating = 0
    if rating > 0:
        tag.setRating(rating, 0, "default", True)
    added = _date(it.get("addedAt"))
    if added:
        tag.setDateAdded(added)
    tag.setUniqueIDs({"freex": str(it.get("id"))}, "freex")

    md = it.get("metadata") or {}
    content_rating = md.get("contentRating") or it.get("contentRating")
    if content_rating:
        tag.setMpaa(content_rating)
    if md.get("studio"):
        tag.setStudios([md["studio"]] if isinstance(md["studio"], str) else list(md["studio"]))
    if md.get("directors"):
        tag.setDirectors(_names(md["directors"]))
    if md.get("writers"):
        tag.setWriters(_names(md["writers"]))
    if md.get("airDate"):
        tag.setPremiered(md["airDate"][:10])
        if t == "episode":
            tag.setFirstAired(md["airDate"][:10])
    if md.get("tmdbId"):
        ids = {"freex": str(it.get("id")), "tmdb": str(md["tmdbId"])}
        tag.setUniqueIDs(ids, "freex")
    cast = md.get("cast") or []
    if cast:
        actors = []
        for i, p in enumerate(cast):
            thumb = api.person_image(p["id"]) if p.get("hasImage") and p.get("id") else ""
            actors.append(xbmc.Actor(p.get("name") or "", p.get("role") or "", i, thumb))
        tag.setCast(actors)

    if t == "episode":
        if it.get("showTitle"):
            tag.setTvShowTitle(it["showTitle"])
        if it.get("seasonIndex") is not None:
            tag.setSeason(int(it["seasonIndex"]))
        if it.get("index") is not None:
            tag.setEpisode(int(it["index"]))
    elif t == "season":
        tag.setSeason(int(it.get("index") or 0))
        if it.get("showTitle"):
            tag.setTvShowTitle(it["showTitle"])
    elif t == "show":
        tag.setTvShowTitle(it.get("title") or "")

    _art(api, li, it)
    media = it.get("media") or {}
    duration = utils.ms_to_s(media.get("durationMs"))
    if duration:
        tag.setDuration(duration)

    if playable(it):
        p = it.get("progress") or {}
        tag.setPlaycount(1 if p.get("watched") else 0)
        if not p.get("watched") and p.get("offsetMs") and duration:
            tag.setResumePoint(utils.ms_to_s(p["offsetMs"]), duration)
        else:
            tag.setResumePoint(0, duration)
        _streams(tag, media)
        li.setProperty("IsPlayable", "true")
        url = plugin_url(action="play", id=it["id"])
        folder = False
    else:
        leaves = int(it.get("leafCount") or 0)
        viewed = int(it.get("viewedLeafCount") or 0)
        if leaves:
            li.setProperty("TotalEpisodes", str(leaves))
            li.setProperty("WatchedEpisodes", str(viewed))
            li.setProperty("UnWatchedEpisodes", str(max(0, leaves - viewed)))
            tag.setPlaycount(1 if viewed >= leaves else 0)
        if t == "show":
            li.setProperty("TotalSeasons", str(it.get("childCount") or 0))
            url = plugin_url(action="show", id=it["id"])
        elif t == "season":
            url = plugin_url(action="season", id=it["id"])
        else:
            url = plugin_url(action="item", id=it["id"])
        folder = True

    if with_menu:
        li.addContextMenuItems(context_menu(it, context))
    return url, li, folder


def _names(v):
    if isinstance(v, str):
        return [x.strip() for x in v.split(",") if x.strip()]
    out = []
    for x in v or []:
        out.append(x.get("name") if isinstance(x, dict) else str(x))
    return [x for x in out if x]


def _art(api, li, it):
    t = it.get("type")
    art = {}
    show = {"id": it.get("showId"), "artVersion": it.get("artVersion")} if it.get("showId") else None
    if t == "episode":
        art["thumb"] = api.art(it, "thumb")
        if show:
            art["tvshow.poster"] = api.art(show, "poster")
            season = {"id": it["seasonId"], "artVersion": it.get("artVersion")} if it.get("seasonId") else show
            art["poster"] = api.art(season, "poster")
            art["fanart"] = api.art(show, "backdrop")
        else:
            art["fanart"] = api.art(it, "backdrop")
    elif t == "season":
        art["poster"] = art["thumb"] = api.art(it, "poster")
        art["fanart"] = api.art(show or it, "backdrop")
        if show:
            art["tvshow.poster"] = api.art(show, "poster")
    elif t == "extra":
        art["thumb"] = api.art(it, "thumb")
        art["fanart"] = api.art(it, "backdrop")
    else:
        art["poster"] = art["thumb"] = api.art(it, "poster")
        art["fanart"] = api.art(it, "backdrop")
        art["landscape"] = api.art(it, "backdrop")
    li.setArt(art)


def _streams(tag, media):
    """Codec, resolution, HDR, audio and subtitle tracks, for the skin's media flags."""
    if not media:
        return
    try:
        width = int(media.get("width") or 0)
        height = int(media.get("height") or 0)
        video = {"codec": media.get("videoCodec") or "", "width": width, "height": height,
                 "duration": utils.ms_to_s(media.get("durationMs"))}
        if width and height:
            video["aspect"] = width / float(height)
        hdr = HDR_TYPES.get(media.get("hdr") or "")
        if hdr:
            video["hdrType"] = hdr
        tag.addVideoStream(xbmc.VideoStreamDetail(**video))
        for a in media.get("audio") or []:
            tag.addAudioStream(xbmc.AudioStreamDetail(int(a.get("channels") or 0), a.get("codec") or "",
                                                      a.get("language") or ""))
        for s in media.get("subtitles") or []:
            tag.addSubtitleStream(xbmc.SubtitleStreamDetail(s.get("language") or ""))
    except (TypeError, ValueError) as e:
        utils.log("Stream details: %s" % e)


def context_menu(it, context=""):
    t = it.get("type")
    menu = []
    run = lambda **p: "RunPlugin(%s)" % plugin_url(**p)  # noqa: E731
    update = lambda **p: "Container.Update(%s)" % plugin_url(**p)  # noqa: E731
    if t in ("movie", "episode", "show", "season"):
        if t in ("movie", "episode"):
            watched = (it.get("progress") or {}).get("watched")
        else:
            leaves = int(it.get("leafCount") or 0)
            watched = leaves > 0 and int(it.get("viewedLeafCount") or 0) >= leaves
        menu.append((tr(30031) if watched else tr(30030), run(action="watched", id=it["id"], on="0" if watched else "1")))
    if t in ("movie", "show"):
        on = it.get("onWatchlist")
        menu.append((tr(30033) if on else tr(30032), run(action="watchlist_toggle", id=it["id"], on="0" if on else "1")))
        menu.append((tr(30017), update(action="extras", id=it["id"])))
    if t == "episode" and context != "season":
        if it.get("seasonId"):
            menu.append((tr(30035), update(action="season", id=it["seasonId"])))
        if it.get("showId"):
            menu.append((tr(30034), update(action="show", id=it["showId"], all="1")))
    if t == "season" and it.get("showId") and context != "show":
        menu.append((tr(30034), update(action="show", id=it["showId"], all="1")))
    if t == "extra" and it.get("ownerId") and context != "extras":
        menu.append((it.get("ownerTitle") or tr(30017), update(action="item", id=it["ownerId"])))
    if playable(it):
        p = it.get("progress") or {}
        if p.get("offsetMs") and not p.get("watched"):
            menu.append((tr(30038), "PlayMedia(%s)" % plugin_url(action="play", id=it["id"], start="0")))
    return menu


def folder(label, url, icon="", art=None, plot=""):
    li = xbmcgui.ListItem(label, offscreen=True)
    a = {"icon": icon or "DefaultFolder.png", "thumb": icon or "DefaultFolder.png",
         "fanart": utils.ADDON.getAddonInfo("fanart")}
    if art:
        a.update(art)
    li.setArt(a)
    if plot:
        li.getVideoInfoTag().setPlot(plot)
    return url, li, True
