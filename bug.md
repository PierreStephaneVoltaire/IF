# Observed issues outside the current correction

## Powerlifting public avatar URLs — 2026-09-15

During the genuine browser check of `https://dev.nolift.training/profiles`,
public avatar requests contained a duplicated `/api/videos/media/` prefix and
returned HTTP 401 at 320, 375 and 1440 pixel widths. The Search page itself
loaded. Gateway: `758baac…`; frontend: `7c77cf5…`. Sanitized response evidence is
in `/tmp/entry-mobile-live-browser.json`. Investigate URL construction and the
existing authorized media contract; preserve permission enforcement.

## Powerlifting ranking percentile request — 2026-09-15

The authenticated Sessions browser sweep observed one HTTP 404 from
`GET /api/stats/ranking_percentile`. Sessions content loaded. The same live
artifact records the response. This was not diagnosed or changed during the
login, landing, banner and small-screen correction.
