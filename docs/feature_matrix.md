# Feature Matrix

The movie library is rendered server-side via FastAPI templates. The `/ui/movies`
view anchors the experience with search, filters, sorting, preferences,
watchlist actions, review flags, and a JS helper that bridges to the
`/movies/picks` API for surprise picks.

The `/ui/movies/{id}` detail page reuses the shared shell, layering in hero art, conditional data sections, and cross-links to similar titles. The table below captures the current status of these flows, the surfaces they touch, and the gaps that should be addressed next.

| Feature | Routes / Entry Points | UI Status | States | Gaps / Notes |
| --- | --- | --- | --- | --- |
| Library landing & filters | `/ui/movies` | Shipped (server-rendered) | Header shows current result count; search and filter submissions reset to page 1; filters open in a dialog with genre, decade, and runtime controls; active filters render removable chips; filter state persists in a cookie | Sort changes require submitting the form; mood filtering is preserved through hidden state but is not exposed as a visible filter control |
| Library presets | `/ui/movies?preset=...` | Backend-supported, mostly hidden | Built-in preset keys such as `hidden-gems`, `under-100`, and `before-2000` are accepted in query/cookie state and appear as active filter chips when present | The current template does not render Fliclist/preset chips or a "Save current filters" UI; `/fliclists` remains API-only for direct preset management |
| Pick for me actions | `#pick-button`; `/movies/picks`; `/movies/picks/{movie_id}/memory` | Functional | Button enters a busy/disabled state; 404 prompts widening filters; non-OK and network failures show toasts; success records pick memory and navigates to the chosen movie detail page | Only the first selected genre and first mood are forwarded to the pick API |
| Results grid, list & pagination | `/ui/movies` | Shipped (server-rendered) | Grid cards and list rows link to detail pages with lazy posters; grid/list toggle preserves query state; pagination links render when pages >1; empty searches show a clear-all action | No quick "back to top" anchor; grid lacks contextual messaging for active sort beyond the select control |
| Preferences & watchlist | `/movies/{movie_id}/like`; `/movies/{movie_id}/watchlist`; `/ui/watchlist` | Shipped | Library cards and detail pages expose like/watchlist controls; watchlist has a dedicated server-rendered page | Preference mutations depend on same-origin session requests; no bulk watchlist management UI |
| Movie detail layout | `/ui/movies/{id}`; `/movies/{id}/detail` service | Shipped | Hero swaps in backdrop or poster with chips; synopsis, at-a-glance metadata, cast/crew, Vault history, trailers, preferences, flags, and similar-by-vibe rail render only when data exists; 404 returns the same template with not-found copy | 404 view lacks navigation back to search or home |
| Vault Health | `/ui/movies/health`; `/ui/movies/health/missing`; `/ui/source-sync/{snapshot_id}/preview` | Shipped for admin sessions | Overview cards, metadata maintenance, review workbench, missing-details view, source sync upload/history, manual add, and new-additions CSV export live under the Health surface | Older compatibility routes redirect into Health; several queues still expose implementation bucket names |
