# Changelog

## FreeX for Kodi 1.1.0

- FreeX opens in its own design, the one of FreeX TV and FreeX Web, independent of Kodi's skin: a sidebar
  with home, watchlist, playlists, search and the libraries; the home rows as rows of rounded cards with
  progress bars, "unwatched" corners and episode counts; libraries as a grid with filters (all, unwatched,
  in progress, recently added, collections); detail pages for movies, shows, seasons and episodes with the
  backdrop, a "Resume S1 E3" button in the brand gradient, buttons for from the start, watched and
  watchlist, seasons, episodes, extras and cast
- Playback started there resumes at the saved position; when it ends, the pages show the new state
- "Skip intro" and "Next episode" buttons in the same look
- Kodi's lists remain: setting *Menu → Open FreeX in its own design*

## FreeX for Kodi 1.0.0

First version of the Kodi add-on for FreeX Media Server (Kodi 20 Nexus and newer):

- Sign-in with the server address, user name, password and two-factor authentication; only the token is kept
- Main menu with the server's home rows, the libraries, watchlist, playlists and search; per library *All*,
  *Unwatched*, *In progress*, *Recently added*, the library's rows, collections, genres and decades
- Shows with seasons and episodes, movies with extras; artwork, plot, cast, age rating and media flags; watched marks,
  unwatched episode counts and resume points from the server
- Playback with Kodi's own player: direct play by default, or the server decides and converts with a chosen quality;
  subtitle files next to the video are loaded as well
- Background service: position reports to the server (resume points, watched at 90 %, activity view, webhooks),
  *Skip intro* (button or automatic), *Next episode* during the credits, Up Next integration, the next episode
  starts when one ends
- Context menu: mark as watched or unwatched, watchlist, extras, go to show or season, play from the start
- English and German
