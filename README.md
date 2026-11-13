<p align="center">
  <img src="plugin.video.freex/resources/media/icon.png" alt="FreeX" width="110">
</p>

<h1 align="center">FreeX for Kodi</h1>

<p align="center">
  <strong>The Kodi add-on for <a href="https://github.com/FreeX-Studio/freex-media-server">FreeX Media Server</a>.</strong>
</p>

FreeX for Kodi (`plugin.video.freex`) brings your FreeX library into Kodi: the home rows, your libraries, collections,
playlists, the watchlist and search, with artwork, descriptions, cast and media flags like a Kodi library. Videos play
in Kodi's own player, which decodes practically every file, so the server converts nothing. Watch state and resume
positions stay on the server: what you start in Kodi continues in FreeX Web, FreeX TV or FreeX Mobile, and the other
way round.

<p align="center">
  <img src="docs/screenshots/home.jpg" width="49%" alt="Home rows in the FreeX design">
  <img src="docs/screenshots/library.jpg" width="49%" alt="A library with filters">
  <img src="docs/screenshots/show.jpg" width="49%" alt="The page of a show with Resume S1 E1">
  <img src="docs/screenshots/season.jpg" width="49%" alt="The episodes of a season">
</p>

<sub>Kodi 20.5 in German against a FreeX Media Server with test media (titles and posters made up). More in
<a href="docs/screenshots">docs/screenshots</a>.</sub>

## Features

- **The FreeX design** – the add-on opens in windows of its own that look like FreeX TV and FreeX Web, whatever
  skin Kodi uses: the sidebar, the home rows as rows of rounded cards with progress bars, "unwatched" corners
  and episode counts, the backdrop of the focused title, libraries as a grid with filters, detail pages with the
  *Resume S1 E3* button in the brand gradient, from-the-start, watched and watchlist buttons, seasons,
  episodes, extras and cast. Kodi's own lists (below) remain, for the skin's widgets and as a setting
- **Browse** – the server's home rows (*Continue watching*, *Up next*, *Recently added* …) right in the main menu;
  per library *All*, *Unwatched*, *In progress*, *Recently added*, the library's rows, collections, genres and
  decades; watchlist, playlists and search
- **Like a Kodi library** – posters, backdrops and episode thumbnails, plot, genres and rating; resolution, codecs,
  HDR, audio and subtitle languages as media flags; watched marks, unwatched episode counts and resume points;
  Kodi's sort orders (title, year, rating, added, length). Cast with photos, directors, writers, studio and age
  rating come with a title's full details, so Kodi shows them while it plays (the server's lists do not carry them)
- **Plays everything** – direct play by default (the file as it is, with seeking); optionally the server decides and
  converts what the device cannot decode or limits the quality for slow connections
- **Synced** – the position is reported every ten seconds and on pause, seek and stop; 90 % counts as watched, the
  playback shows up in the admin's activity view and triggers the server's webhooks
- **Subtitles** – subtitle files next to the video (`.srt`, `.vtt`) are loaded together with the subtitles inside the
  file
- **Skip intro** – a *Skip intro* button during the intros the server detected, or skipping them automatically
- **Next episode** – hands the next episode to [Up Next](https://kodi.wiki/view/Add-on:Up_Next) when it is
  installed (its pop-up appears when the credits start), otherwise its own *Next episode* button during the credits
  and the next episode starts when one ends
- **Context menu** – mark as watched or unwatched (also whole seasons and shows), add to or remove from the
  watchlist, extras and trailers, go to the show or season, play from the start
- **Secure sign-in** – two-factor authentication; the password is never stored, only the sign-in token, outside
  Kodi's settings file
- English and German, following Kodi's language

## Requirements

- **Kodi 20 (Nexus) or newer** on any platform (Windows, Linux, macOS, Android, Android TV / Fire TV, LibreELEC,
  CoreELEC, Raspberry Pi)
- **FreeX Media Server** with stream URLs with an access token
  ([freex-media-server#2](https://github.com/FreeX-Studio/freex-media-server/pull/2), in the release after 0.21.0) –
  the same requirement as FreeX TV
- Optional: **Up Next** (`service.upnext`) for the Netflix-style pop-up for the next episode; **InputStream
  Adaptive** for converted streams, if Kodi's built-in HLS playback stutters on your device

## Installation

1. Download `plugin.video.freex-<version>.zip` from the latest build (Jenkins) or build it yourself (see below).
2. In Kodi: *Settings → System → Add-ons* → switch on **Unknown sources**.
3. *Settings → Add-ons → Install from zip file* → choose the zip.
4. Open *Add-ons → Video add-ons → FreeX* → **Sign in**: enter the server address (e.g. `192.168.1.10`, the port
   32500 is added; or `https://media.example.org`), then user name, password and, if switched on, the code from your
   authenticator app.

The add-on is updated by installing a newer zip the same way.

## Settings

| Setting | Default | |
|---|---|---|
| Server address, user name | | The server; *Sign in…* and *Sign out* |
| Check the server's TLS certificate | on | Switch off only for a server with a self-signed certificate in your own network |
| Device name in FreeX | `Kodi on <device>` | How this Kodi appears in the server's activity view |
| Playback mode | Direct play | *Direct play*: Kodi plays every file as it is. *Let the server decide*: the server converts what the device cannot decode (choose whether it decodes HEVC and AV1, e.g. off on a Raspberry Pi 3) and follows the chosen quality |
| Quality | Automatic | Only for *Let the server decide*: *Automatic* uses your default for the home network or on the go from FreeX Web (*Account → Playback*) |
| Skip intro | Show a button | *Show a button*, *Skip automatically* or *Off* |
| Use Up Next | on | Hand the next episode to Up Next when it is installed |
| Show "Next episode" during the credits | on | Without Up Next |
| Play the next episode when one ends | on | Without Up Next |
| Open FreeX in its own design | on | Off: the add-on shows Kodi's lists in the skin's look (as in [this picture](docs/screenshots/classic-list.jpg)) |
| Show the home rows directly in the main menu | on | Kodi's lists: otherwise behind *Home* |
| Skip the season list for shows with only one season | on | |

## How it works

The add-on has three parts:

- **The FreeX windows** (`ui.py`, started by the plugin when the add-on is opened) are Kodi script windows
  (`WindowXML`) with their own layout in `resources/skins/Default/1080i`, so they look the same in every
  skin. They read the same JSON API and start the player directly, at the saved position.
- **The plugin** (`default.py`) is run by Kodi for every folder. It reads the folder fresh from the server's JSON API
  (`/api/hubs`, `/api/libraries/{id}/items`, `/api/items/{id}` …), so changes made in other apps show at once.
  Artwork is loaded by Kodi's image loader with the token in a header (`url|X-FreeX-Token=…`). For playback it asks
  `POST /api/items/{id}/playback` with `"player": "external"` (direct play, like mpv in FreeX Desktop) or with the
  decoders of Kodi, and `"tokenUrls": true`, so Kodi gets a stream URL that carries its own access token for that
  title only.
- **The service** (`service.py`) runs in the background, follows what Kodi plays from FreeX and reports the position
  with `PUT /api/items/{id}/progress`, shows *Skip intro* and *Next episode*, signals Up Next and ends a conversion on
  the server (`DELETE /api/transcode/{session}`) when playback stops.

The sign-in token, the server it belongs to and a random id of this device are kept in
`userdata/addon_data/plugin.video.freex/state.json` (readable only by the Kodi user where the system allows).

## Development

```bash
./build.sh            # checks the Python files and the XML, writes dist/plugin.video.freex-<version>.zip
```

Python 3.8+ without third-party modules (Kodi 20 ships 3.8 on some platforms). The code is in
`plugin.video.freex/resources/lib/freex/`:

| File | |
|---|---|
| `api.py` | The API client (`urllib`, token header, errors with the server's `code`) |
| `session.py` | Sign-in with two-factor authentication, the client of the signed-in user |
| `ui.py` | The FreeX windows: sidebar, home rows, grid, detail pages |
| `plugin.py` | Kodi's lists (menus, folders) and resolving playback |
| `playback.py` | Asking the server how to play a title, subtitles, starting the player |
| `items.py` | FreeX items as Kodi list items: info, artwork, watch state, stream details, context menu |
| `service.py` | Progress reports, skip intro, next episode, Up Next |
| `utils.py` | Settings, strings, state file |

The window layouts (`resources/skins/Default/1080i/*.xml`) and their textures (`resources/skins/Default/media`)
are generated: change `tools/make_windows.py` or `tools/make_media.py` and run them (`python3 tools/make_windows.py`;
`python3 tools/make_media.py <path to FreeX-TV-Apps/web/img/logo.svg>`, needs Pillow and cairosvg). The layouts use
the colours of FreeX Web and the fonts every skin has (`font12`, `font13`) plus a few of Estuary's larger ones;
other skins fall back to `font13` there.

Strings are in `resources/language/resource.language.*/strings.po`; IDs 30000–30999 for the add-on, 32000–32999
for the settings.

## License

[LGPL-3.0](LICENSE) – © 2026 MirraNET, Niklas Linz
