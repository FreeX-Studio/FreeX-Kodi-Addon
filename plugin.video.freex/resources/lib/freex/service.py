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
The background service: follows what Kodi plays from FreeX and

- reports the position to the server every ten seconds, on pause, seek and stop, like FreeX Web
  (resume points, "watched" at 90 %, the admin's activity view, webhooks),
- ends a conversion on the server when playback stops,
- shows "Skip intro" during an episode's intro (or skips it by itself),
- hands the next episode to Up Next (service.upnext) or shows its own "Next episode" button during
  the credits, and plays the next episode when one ends, if wanted.

The plugin tells the service what it starts through a property of the home window.
"""

import base64
import json
import threading

import xbmc
import xbmcgui

from . import items, session, utils
from .api import ApiError
from .utils import tr

REPORT_EVERY_S = 10
TICK_S = 0.5
# Without a credits marker, "Next episode" appears this long before the end.
NEXT_WITHOUT_MARKER_MS = 30000

ACTION_BACK = (9, 10, 92, 110)  # parent dir, previous menu, back, nav back
ACTION_PAUSE = (12, 79)  # pause, player play


class SkipButton(xbmcgui.WindowXMLDialog):
    """
    A single button at the bottom right over the video, in the look of the FreeX windows
    (resources/skins/Default/1080i/freex-skip.xml). OK presses it, Back hides it.
    """

    def __new__(cls, *args, **kwargs):  # pylint: disable=unused-argument
        return super().__new__(cls, "freex-skip.xml", utils.ADDON_PATH, "Default", "1080i")

    def __init__(self, label, icon, on_press):  # pylint: disable=super-init-not-called
        self.on_press = on_press
        self.dismissed = False
        self.setProperty("label", label)
        self.setProperty("icon", icon)

    def onInit(self):  # noqa: N802
        self.setFocusId(10)

    def onClick(self, control_id):  # noqa: N802
        if control_id == 10:
            self.close()
            self.on_press()

    def onAction(self, action):  # noqa: N802
        aid = action.getId()
        if aid in ACTION_BACK:
            self.dismissed = True
            self.close()
        elif aid in ACTION_PAUSE:
            xbmc.Player().pause()


class Monitor(xbmc.Monitor):
    def onSettingsChanged(self):  # noqa: N802
        utils.reload_settings()


class Player(xbmc.Player):
    def __init__(self, svc):
        super().__init__()
        self.svc = svc

    def onAVStarted(self):  # noqa: N802
        self.svc.started()

    def onPlayBackPaused(self):  # noqa: N802
        self.svc.report("paused", force=True)

    def onPlayBackResumed(self):  # noqa: N802
        self.svc.report("playing", force=True)

    def onPlayBackSeek(self, time, seek_offset):  # noqa: N802 pylint: disable=redefined-outer-name,unused-argument
        self.svc.seeked = True
        self.svc.report("playing", force=True)

    def onPlayBackStopped(self):  # noqa: N802
        self.svc.finished(ended=False)

    def onPlayBackEnded(self):  # noqa: N802
        self.svc.finished(ended=True)

    def onPlayBackError(self):  # noqa: N802
        self.svc.finished(ended=False, error=True)


class Service:
    def __init__(self):
        self.monitor = Monitor()
        self.player = Player(self)
        self.lock = threading.RLock()
        self.current = None
        self.position_ms = 0
        self.last_report = 0.0
        self.button = None
        self.button_kind = None
        self.dismissed = set()
        self.now = 0.0
        # Set while Kodi changes to the next title: the position of the old one is final.
        self.frozen = False
        self.seeked = False

    # ------------------------------------------------------------------ start and end

    def started(self):
        with self.lock:
            if self.current:
                # Kodi moved on to the next title without a stop (playlist, Up Next).
                self._finish(ended=False)
            win = xbmcgui.Window(utils.HOME_WINDOW)
            raw = win.getProperty(utils.PLAYING_PROPERTY)
            win.clearProperty(utils.PLAYING_PROPERTY)
            try:
                info = json.loads(raw) if raw else None
            except ValueError:
                info = None
            try:
                playing = self.player.getPlayingFile()
            except RuntimeError:
                playing = ""
            if not info or not info.get("server") or info["server"] not in playing:
                return  # not ours
            self.current = info
            self.position_ms = 0
            self.frozen = False
            self.seeked = False
            self.dismissed = set()
            utils.log("Following %s (%s)" % (info.get("itemId"), info.get("mode")))
        self.report("playing", force=True)
        self.signal_upnext()

    def finished(self, ended, error=False):
        with self.lock:
            if not self.current:
                return
            cur = self._finish(ended, error)
        if ended and cur and cur.get("next") and self.autoplay_next():
            self.play(cur["next"]["id"])

    def _finish(self, ended, error=False):
        cur = self.current
        self.current = None
        self.close_button()
        if ended and cur.get("durationMs"):
            self.position_ms = int(cur["durationMs"])
        api = self.api()
        if api is None:
            return cur
        body = {"offsetMs": int(self.position_ms), "durationMs": int(cur.get("durationMs") or 0), "state": "stopped",
                "stopped": True, "client": api.client_id, "device": utils.device_name()}
        try:
            api.progress(cur["itemId"], body)
        except ApiError as e:
            utils.log("Final progress report failed: %s" % e.message, xbmc.LOGWARNING)
        # The FreeX windows wait for this before they read their data again.
        xbmcgui.Window(utils.HOME_WINDOW).setProperty(utils.SAVED_PROPERTY, cur["itemId"])
        if cur.get("session"):
            try:
                api.stop_transcode(cur["session"])
            except ApiError:
                pass  # the server ends idle conversions itself
        if error:
            try:
                api.playback_error(cur["itemId"], cur.get("mode"), "Kodi could not play the stream", utils.device_name())
            except ApiError:
                pass
        utils.log("Stopped %s at %d ms" % (cur.get("itemId"), self.position_ms))
        return cur

    # ------------------------------------------------------------------ reports

    def api(self):
        try:
            return session.client()
        except session.NotSignedIn:
            return None

    def report(self, state, force=False):
        with self.lock:
            cur = self.current
            if not cur:
                return
            if not force and self.now - self.last_report < REPORT_EVERY_S:
                return
            self.last_report = self.now
            self.read_position()
            body = {"offsetMs": int(self.position_ms), "durationMs": int(cur.get("durationMs") or 0), "state": state,
                    "device": utils.device_name()}
        api = self.api()
        if api is None:
            return
        body["client"] = api.client_id
        try:
            api.progress(cur["itemId"], body)
        except ApiError as e:
            utils.log("Progress report failed: %s" % e.message)

    def is_ours(self):
        """
        Whether Kodi still plays the file the service follows. When the next title starts, Kodi
        plays it for a moment before it reports the start; its position must not end up on the
        previous one. Every playback has its own token in the URL, which tells them apart.
        """
        cur = self.current
        if not cur:
            return False
        try:
            playing = self.player.getPlayingFile()
        except RuntimeError:
            return False
        marker = cur.get("token") or cur.get("url") or ""
        return bool(marker) and marker in playing

    def read_position(self):
        if self.frozen or not self.is_ours():
            return
        try:
            if self.player.isPlayingVideo():
                pos = max(0, int(self.player.getTime() * 1000))
                if pos < 1000 < self.position_ms and not self.seeked:
                    # Kodi is opening the next file and still names the old one: not a real position.
                    return
                self.seeked = False
                self.position_ms = pos
                if self.current and not self.current.get("durationMs"):
                    self.current["durationMs"] = int(self.player.getTotalTime() * 1000)
        except RuntimeError:
            pass  # between two files

    # ------------------------------------------------------------------ main loop

    def run(self):
        utils.log("Service started", xbmc.LOGINFO)
        while not self.monitor.abortRequested():
            self.now += TICK_S
            if self.current:
                paused = xbmc.getCondVisibility("Player.Paused")
                self.report("paused" if paused else "playing")
                with self.lock:
                    self.read_position()
                self.check_markers()
            elif self.button:
                self.close_button()
            if self.monitor.waitForAbort(TICK_S):
                break
        with self.lock:
            if self.current:
                self._finish(ended=False)
        utils.log("Service stopped", xbmc.LOGINFO)

    # ------------------------------------------------------------------ skip intro, next episode

    def check_markers(self):
        cur = self.current
        if not cur:
            return
        pos = self.position_ms
        mk = cur.get("markers") or {}
        dur = int(cur.get("durationMs") or 0)
        kind = None
        intro, credits = mk.get("intro"), mk.get("credits")
        if intro and intro.get("startMs", 0) <= pos < intro.get("endMs", 0) - 1500:
            kind = "intro"
        elif cur.get("next") and self.own_next_button():
            if credits and credits.get("startMs", 0) <= pos < dur - 1000:
                kind = "next"
            elif not credits and dur and NEXT_WITHOUT_MARKER_MS > dur - pos > 1000:
                kind = "next"
        if kind == "intro":
            mode = utils.setting_int("intro_mode")  # 0 button, 1 automatic, 2 off
            if mode == 2:
                kind = None
            elif mode == 1:
                if "intro" not in self.dismissed:
                    self.dismissed.add("intro")
                    utils.log("Skipping the intro")
                    self.skip_intro()
                kind = None
        if kind in self.dismissed:
            kind = None
        if kind != self.button_kind:
            self.close_button()
            if kind:
                self.open_button(kind)

    def open_button(self, kind):
        label = tr(30070) if kind == "intro" else tr(30071)
        media = utils.ADDON_PATH + "/resources/skins/Default/media/"
        self.button = SkipButton(label, media + ("icon-skip.png" if kind == "intro" else "icon-next.png"),
                                 lambda: self.pressed(kind))
        self.button_kind = kind
        self.button.show()

    def close_button(self):
        if self.button:
            if self.button.dismissed and self.button_kind:
                self.dismissed.add(self.button_kind)
            try:
                self.button.close()
            except RuntimeError:
                pass
            del self.button
        self.button = None
        self.button_kind = None

    def pressed(self, kind):
        self.dismissed.add(kind)
        if kind == "intro":
            self.skip_intro()
        elif kind == "next" and self.current and self.current.get("next"):
            self.read_position()
            self.frozen = True
            self.play(self.current["next"]["id"])

    def skip_intro(self):
        intro = ((self.current or {}).get("markers") or {}).get("intro")
        if intro:
            try:
                self.player.seekTime(intro["endMs"] / 1000.0)
            except RuntimeError:
                pass

    def play(self, item_id):
        xbmc.executebuiltin("PlayMedia(%s)" % items.plugin_url(action="play", id=item_id))

    # ------------------------------------------------------------------ Up Next

    def upnext_active(self):
        return utils.setting_bool("upnext") and xbmc.getCondVisibility("System.AddonIsEnabled(service.upnext)")

    def own_next_button(self):
        return utils.setting_bool("next_button") and not self.upnext_active()

    def autoplay_next(self):
        return utils.setting_bool("autoplay_next") and not self.upnext_active()

    def signal_upnext(self):
        cur = self.current
        if not cur or cur.get("type") != "episode" or not cur.get("next") or not self.upnext_active():
            return
        api = self.api()
        if api is None:
            return
        nxt = cur["next"]
        data = {
            "current_episode": upnext_episode(api, cur.get("current") or {}),
            "next_episode": upnext_episode(api, nxt),
            "play_url": items.plugin_url(action="play", id=nxt["id"]),
        }
        credits = (cur.get("markers") or {}).get("credits")
        if credits and credits.get("startMs"):
            # Up Next shows its pop-up when the credits start (seconds from the start of the episode).
            data["notification_offset"] = int(credits["startMs"] / 1000)
        encoded = base64.b64encode(json.dumps(data).encode("utf-8")).decode("ascii")
        request = {"jsonrpc": "2.0", "id": 1, "method": "JSONRPC.NotifyAll",
                   "params": {"sender": utils.ADDON_ID + ".SIGNAL", "message": "upnext_data", "data": [encoded]}}
        xbmc.executeJSONRPC(json.dumps(request))
        utils.log("Up Next: %s follows" % nxt.get("id"))


def upnext_episode(api, ep):
    show = {"id": ep.get("showId"), "artVersion": ep.get("artVersion")} if ep.get("showId") else None
    art = {"thumb": api.art(ep, "thumb")} if ep.get("id") else {}
    if show:
        art.update({"tvshow.poster": api.art(show, "poster"), "tvshow.fanart": api.art(show, "backdrop"),
                    "tvshow.landscape": api.art(show, "backdrop")})
    return {
        "episodeid": ep.get("id"), "tvshowid": ep.get("showId"), "title": ep.get("title") or "",
        "art": art, "season": ep.get("seasonIndex") or 0, "episode": ep.get("index") or 0,
        "showtitle": ep.get("showTitle") or "", "plot": ep.get("summary") or "",
        "playcount": 1 if ep.get("watched") else 0, "rating": ep.get("rating") or 0,
        "firstaired": (ep.get("airDate") or "")[:10], "runtime": utils.ms_to_s(ep.get("durationMs")),
    }


def run():
    Service().run()
