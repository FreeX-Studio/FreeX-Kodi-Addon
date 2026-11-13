# Copyright (c) 2026 MirraNET, Niklas Linz. All rights reserved.
#
# This file is part of the MirraNET project and is licensed under the
# GNU Lesser General Public License v3.0 (LGPLv3).
#
# You may use, distribute and modify this code under the terms
# of the LGPLv3 license. You should have received a copy of the
# license along with this file. If not, see <https://www.gnu.org/licenses/lgpl-3.0.html>
# or contact: niklas.linz@mirranet.de

"""Sign-in and the API client of the signed-in user."""

import xbmc
import xbmcgui

from . import utils
from .api import ApiError, FreeX, normalize_server
from .utils import tr


class NotSignedIn(Exception):
    pass


def configured_server():
    return normalize_server(utils.setting("server"))


def client(state=None, require_token=True):
    """
    The API client for the configured server. The token only counts for the server it was issued
    by: after the address was changed in the settings, the user signs in again.
    """
    state = state or utils.load_state()
    server = configured_server()
    if not server:
        raise NotSignedIn(tr(30057))
    token = state.get("token", "") if state.get("server") == server else ""
    if require_token and not token:
        raise NotSignedIn(tr(30058))
    return FreeX(server, token, language=utils.ui_language(), verify_tls=utils.setting_bool("verify_tls"),
                 client_id=state.get("clientId", ""), user_agent="FreeX-Kodi/%s" % utils.VERSION)


def is_signed_in():
    try:
        client()
        return True
    except NotSignedIn:
        return False


def sign_in():
    """Asks for address (if missing), user name, password and, if needed, the second factor."""
    dialog = xbmcgui.Dialog()
    server = configured_server()
    if not server:
        typed = dialog.input(tr(30050), "http://", type=xbmcgui.INPUT_ALPHANUM)
        server = normalize_server(typed)
        if not server:
            return False
        utils.set_setting("server", server)
    api = FreeX(server, language=utils.ui_language(), verify_tls=utils.setting_bool("verify_tls"),
                user_agent="FreeX-Kodi/%s" % utils.VERSION)
    try:
        st = api.status()
    except ApiError as e:
        dialog.ok("FreeX", tr(30056) + "\n" + server + "\n" + e.message)
        return False
    username = dialog.input(tr(30051), utils.setting("username"), type=xbmcgui.INPUT_ALPHANUM)
    if not username:
        return False
    password = dialog.input(tr(30052), type=xbmcgui.INPUT_ALPHANUM, option=xbmcgui.ALPHANUM_HIDE_INPUT)
    if not password:
        return False
    try:
        res = api.login(username.strip(), password)
        if res and res.get("twoFactorRequired"):
            code = dialog.input(tr(30053), type=xbmcgui.INPUT_ALPHANUM)
            if not code:
                return False
            res = api.verify(res.get("challenge"), code.replace(" ", ""))
    except ApiError as e:
        dialog.ok("FreeX", e.message)
        return False
    if not res or not res.get("token"):
        dialog.ok("FreeX", tr(30058))
        return False
    state = utils.load_state()
    state.update({"server": server, "token": res["token"], "user": res.get("user") or {},
                  "serverName": (st or {}).get("name") or (st or {}).get("serverName") or ""})
    utils.save_state(state)
    utils.set_setting("username", username.strip())
    user = (res.get("user") or {}).get("username") or username
    utils.notify(tr(30054, user))
    xbmc.executebuiltin("Container.Refresh")
    return True


def sign_out():
    state = utils.load_state()
    try:
        client(state).logout()
    except (ApiError, NotSignedIn):
        pass  # the token is forgotten here either way
    state.pop("token", None)
    state.pop("user", None)
    utils.save_state(state)
    utils.notify(tr(30055))
    xbmc.executebuiltin("Container.Refresh")


def forget_token():
    """The server no longer accepts the token (signed out elsewhere, expired)."""
    state = utils.load_state()
    if state.pop("token", None):
        utils.save_state(state)
