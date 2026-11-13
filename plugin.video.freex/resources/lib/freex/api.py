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
The client for the JSON API of FreeX Media Server (docs/api.md in freex-media-server).

Only the standard library: Kodi ships Python, but not every Kodi has script.module.requests, and the
few calls this add-on makes do not need it. Every request carries the sign-in token in the header
X-FreeX-Token and no Origin header, so the server treats Kodi as a native app.
"""

import json
import re
import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPSHandler

DEFAULT_PORT = 32500


class ApiError(Exception):
    """A failed request; `code` is the server's language-independent error code (error.wrongLogin …)."""

    def __init__(self, status, message, code=""):
        super().__init__(message)
        self.status = status
        self.code = code or ""
        self.message = message


def normalize_server(value):
    """
    Turns what the user typed into the base URL of a server: adds http:// and the default port 32500
    when they are missing, drops a trailing slash or path. Empty if it is not an address.
    """
    s = (value or "").strip()
    if not s:
        return ""
    if not re.match(r"^https?://", s, re.I):
        s = "http://" + s
    try:
        u = urlsplit(s)
        host = u.hostname
        port = u.port
    except ValueError:
        return ""
    if not host:
        return ""
    scheme = u.scheme.lower()
    if ":" in host:
        host = "[" + host + "]"  # IPv6
    if port is None and scheme == "http":
        port = DEFAULT_PORT
    return scheme + "://" + host + (":%d" % port if port else "")


class FreeX:
    """One server and (optionally) one signed-in user."""

    def __init__(self, server, token="", language="en", verify_tls=True, client_id="", user_agent="FreeX-Kodi"):
        self.server = server.rstrip("/")
        self.token = token or ""
        self.language = language
        self.client_id = client_id
        self.user_agent = user_agent
        if verify_tls:
            context = ssl.create_default_context()
        else:
            context = ssl._create_unverified_context()  # pylint: disable=protected-access
        self._opener = build_opener(HTTPSHandler(context=context))
        self.verify_tls = verify_tls

    # ------------------------------------------------------------------ plumbing

    def url(self, path):
        return path if re.match(r"^https?:", path, re.I) else self.server + path

    def headers(self, json_body=False):
        h = {"Accept": "application/json", "Accept-Language": self.language, "User-Agent": self.user_agent}
        if self.token:
            h["X-FreeX-Token"] = self.token
        if json_body:
            h["Content-Type"] = "application/json"
        return h

    def raw(self, method, path, body=None, timeout=30):
        """The response body as bytes; raises ApiError."""
        data = None if body is None else json.dumps(body).encode("utf-8")
        req = Request(self.url(path), data=data, method=method, headers=self.headers(body is not None))
        try:
            with self._opener.open(req, timeout=timeout) as res:
                return res.status, res.read()
        except HTTPError as e:
            payload = {}
            try:
                payload = json.loads(e.read().decode("utf-8") or "{}")
            except (ValueError, OSError):
                pass
            message = payload.get("error") if isinstance(payload, dict) else None
            code = payload.get("code") if isinstance(payload, dict) else ""
            raise ApiError(e.code, message or "HTTP %d" % e.code, code) from None
        except ssl.SSLError as e:
            raise ApiError(0, "TLS: %s" % (getattr(e, "reason", None) or e), "tls") from None
        except URLError as e:
            reason = getattr(e, "reason", e)
            if isinstance(reason, ssl.SSLError):
                raise ApiError(0, "TLS: %s" % (getattr(reason, "reason", None) or reason), "tls") from None
            raise ApiError(0, str(reason), "unreachable") from None
        except (OSError, ValueError) as e:
            raise ApiError(0, str(e), "unreachable") from None

    def request(self, method, path, body=None, timeout=30):
        status, data = self.raw(method, path, body, timeout)
        if status == 204 or not data:
            return None
        try:
            return json.loads(data.decode("utf-8"))
        except ValueError:
            raise ApiError(status, "Invalid answer from the server", "invalidAnswer") from None

    def get(self, path, **params):
        params = {k: v for k, v in params.items() if v not in (None, "")}
        if params:
            path += ("&" if "?" in path else "?") + urlencode(params)
        return self.request("GET", path)

    def post(self, path, body=None, timeout=30):
        return self.request("POST", path, body if body is not None else {}, timeout)

    def put(self, path, body=None):
        return self.request("PUT", path, body if body is not None else {})

    def delete(self, path):
        return self.request("DELETE", path)

    # ------------------------------------------------------------------ account

    def status(self):
        return self.request("GET", "/api/status", timeout=10)

    def login(self, username, password):
        """{token, user} or {twoFactorRequired, challenge}."""
        return self.post("/api/login", {"username": username, "password": password})

    def verify(self, challenge, code):
        return self.post("/api/login/verify", {"challenge": challenge, "code": code})

    def logout(self):
        return self.post("/api/logout")

    def me(self):
        return self.request("GET", "/api/me")

    # ------------------------------------------------------------------ library

    def hubs(self):
        return self.request("GET", "/api/hubs") or []

    def libraries(self):
        return self.request("GET", "/api/libraries") or []

    def library_items(self, library_id, query=""):
        path = "/api/libraries/%s/items" % q(library_id)
        if query:
            path += "?" + query
        return self.request("GET", path) or {}

    def library_collections(self, library_id):
        return self.request("GET", "/api/libraries/%s/collections" % q(library_id)) or []

    def collection(self, cid):
        return self.request("GET", "/api/collections/%s" % q(cid)) or {}

    def playlists(self):
        return self.request("GET", "/api/playlists") or []

    def playlist(self, pid):
        return self.request("GET", "/api/playlists/%s" % q(pid)) or {}

    def watchlist(self):
        return self.request("GET", "/api/watchlist") or []

    def search(self, text):
        return self.get("/api/search", q=text) or {}

    def item(self, item_id):
        return self.request("GET", "/api/items/%s" % q(item_id)) or {}

    def set_watched(self, item_id, watched):
        return self.request("POST" if watched else "DELETE", "/api/items/%s/watched" % q(item_id),
                            {} if watched else None)

    def set_watchlist(self, item_id, on):
        return self.request("PUT" if on else "DELETE", "/api/watchlist/%s" % q(item_id), {} if on else None)

    # ------------------------------------------------------------------ playback

    def playback(self, item_id, body):
        # The server may need a few seconds to start a conversion.
        return self.post("/api/items/%s/playback" % q(item_id), body, timeout=60)

    def progress(self, item_id, body):
        return self.put("/api/items/%s/progress" % q(item_id), body)

    def stop_transcode(self, session):
        return self.delete("/api/transcode/%s" % q(session))

    def playback_error(self, item_id, mode, detail, device):
        return self.post("/api/items/%s/playback-error" % q(item_id),
                         {"mode": mode or "", "detail": (detail or "")[:400], "device": device or ""})

    def subtitle(self, item_id, sid):
        """A subtitle as WebVTT text."""
        _, data = self.raw("GET", "/api/items/%s/subtitles/%s.vtt" % (q(item_id), q(sid)))
        return data

    # ------------------------------------------------------------------ URLs for Kodi

    def kodi_headers(self):
        """The `|Header=value&…` suffix with which Kodi sends headers for images and streams."""
        h = {"User-Agent": self.user_agent}
        if self.token:
            h["X-FreeX-Token"] = self.token
        if not self.verify_tls:
            h["verifypeer"] = "false"
        return "|" + urlencode(h)

    def art(self, item, kind):
        """URL of an item's artwork (poster, backdrop, thumb), with the token for Kodi's image loader."""
        if isinstance(item, dict):
            item_id = item.get("id")
            version = item.get("artVersion")
        else:
            item_id, version = item, None
        path = "/api/items/%s/image/%s" % (q(item_id), kind)
        if version:
            path += "?v=" + q(version)
        return self.server + path + self.kodi_headers()

    def person_image(self, person_id):
        return self.server + "/api/people/%s/image" % q(person_id) + self.kodi_headers()

    def collection_art(self, cid, kind):
        return self.server + "/api/collections/%s/image/%s" % (q(cid), kind) + self.kodi_headers()


def q(value):
    return quote(str(value), safe="")
