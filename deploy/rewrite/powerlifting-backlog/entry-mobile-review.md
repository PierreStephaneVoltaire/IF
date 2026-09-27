# Entry and mobile correction — final Terra review

## Accepted deployed correction

The scoped dual-login and mobile correction is accepted. Gateway generation 30
is Ready on `sha256:8740348739cfbce86ef59e800e6c80146dc36897067a57dbcc9413d100ff5b4e`.
An un-intercepted anonymous browser followed
`/api/auth/discord/login` through Authentik's installed Discord source to
`discord.com/api/oauth2/authorize`; normal Authentik login still reaches its
ordinary flow. A fresh Authentik login obtained `/api/auth/me` 200 for
`live-acceptance-echo` and its own Athlete. The invalid-state callback is
denied. No Discord identity completion is claimed.

The first gateway image was rejected because its wrapper replaced Express
`res.redirect`, while Passport emits its authorization redirect with
`setHeader('Location')` and `end()`. The deployed repair hooks that actual
Passport response boundary and restores it on both `end` and `next`. The
focused real-Passport regression passed along with backend typecheck. Reviewed
source hashes are `e0a29d00658c8bfbd9e12e92936ca5c082922a43d8604002b33f66e182af49f8`
for the controller and `494d055fed70ff1b0b2e532d7a07cecbc252aed9d67e2eeaa6cfc89cbe7f1c9d`
for its test; compiled runtime hashes are `58dee5156895e3ed81dd23dee5bec0047d1d2e28c4b088ca51de0d04fd5d7bd5`
and `b8503a8bc3d64b9086eddec153f1bc0b1315b2b40a5b5500b0004c0637df0ff5`.

The guest landing has distinct Discord and Authentik endpoints, accessible
labels, no global read-only banner, and retained Home, Search, About, and Sign
in navigation. Local built-preview evidence at 320x568 and 375x667 confirms
44px compact controls without label or page overflow; it is explicitly local
candidate evidence, not a deployment claim.

Frontend `sha256:5bb25bdb27864d990ecd2b4587a458226eb9f1cc86aedb7396b076afa45c64fe`
contains the narrow mobile Dashboard grid fix. Fresh real HTTPS Dashboard
checks at **320x568** and **375x568** have content loaded and document/body
width equal to the viewport. The former 29px 320px document overflow is gone.

The live compact context check at 320x568 confirms visible selected context,
a 44px Change control, visible Sessions heading, and controls changing from
closed to expanded. It successfully selected delegated Live Acceptance Echo
and observed its read-only notice. A complete cross-Athlete round trip was not
reverified. No data or grant was mutated to manufacture one.

The independent live More evidence is `/tmp/entry-mobile-more-terra.json` and
`/tmp/entry-mobile-more-terra-375x667.png`: at 375x667, `aria-expanded` changes
false to true, all ten intended links render in the portal, scrolling reaches
the bottom, page overflow is zero, and there are no console errors.

## Verification boundary and retained limitations

`/tmp/nolift-mobile-final/backlog-ui-result.json` records **39** passing local
browser assertions, including compact 320px and 375px context controls. Its
Vite server intercepts API operations with fixtures, so it does not establish
deployment, Authentik, or live permission behavior. The offline conflict dialog
remains uncovered.

Known unrelated live responses remain recorded: `GET /api/stats/ranking_percentile`
returns 404 in the authenticated Sessions sweep, and public-profile avatar
loads returned 401. They are not acceptance evidence for this scoped correction.
