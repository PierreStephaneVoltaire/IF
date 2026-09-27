# Direct Discord login correction — 2026-09-15

The previous login correction routed Discord through Authentik's Discord source.
That changed the authorization request's callback from
`https://dev.nolift.training/api/auth/discord/callback` to
`https://auth.nolift.training/source/oauth/callback/discord/` for the same Discord
client, `1459678985473757400`. The operator reported Discord's invalid redirect URI.
Live inspection and the original direct controller confirm the mismatch with the
existing gateway configuration. No provider application settings were changed.

The earlier check followed redirects to Discord but did not complete login.
That check was insufficient and its Discord acceptance is superseded here.
Landing, mobile navigation and unrelated feature evidence remain historical
checkpoints in [the previous correction](entry-mobile-correction.md).

The repair preserves the direct Discord application client and callback alongside
the independent Authentik OIDC login. Both providers use Passport and Valkey
sessions. Discord identity comes from its authenticated user API, and existing
Person/Athlete mappings resolve by verified provider subjects. Names and emails
cannot establish account linkage.

Luna implemented the repair using maintained `passport-oauth2`, with separate
typed Authentik OIDC handling. Four tests exercise the actual Discord Passport
strategy, including client/callback selection, PKCE, missing/invalid/replayed
state, a mocked token/profile exchange and identity validation. Lookup errors
reach Passport's error handler. Full workspace typecheck and build pass.
Terra independently reran the backend checks and all four tests and accepted
the source. Gateway publication and deployed verification passed.

These callback tests mock Discord's token/profile responses. They do not establish
real Discord consent or identity login completion; that remains unavailable.

The gateway baseline is `sha256:8740348739cfbce86ef59e800e6c80146dc36897067a57dbcc9413d100ff5b4e`;
the frontend remains `sha256:5bb25bdb27864d990ecd2b4587a458226eb9f1cc86aedb7396b076afa45c64fe`.

The deployed gateway is
`sha256:b688e943a910ec37b23285f75586f0a7b8f2c346c08653e1509b6b5520130f62`,
generation 31 observed and one Ready replica. All 18 portal Deployments remain
Ready. ECR reports the immutable tag `discord-direct-20260915-180322` ACTIVE.
Only the gateway changed. Runtime packaging retains required static assets and
the existing non-root user; the deployed compiled auth hash matches the reviewed
local module.

An independent browser reaches Discord's authorization page with the exact
original client/callback, code flow and S256 PKCE, with no invalid-redirect message
before consent. An invalid direct callback returns 302 to `login?error=auth_failed`.
A fresh isolated Authentik login completes and `/api/auth/me` returns 200 with
its Person and own Athlete references. No completed Discord identity login is
claimed, and no provider application settings were changed.

Evidence: [release](discord-login-release.json), [Terra review](discord-login-review.md),
[independent live checks](discord-login-live.json), and
[runtime inventory](discord-login-runtime-inventory.json). Executable release
manifests use the new immutable gateway pin and retain the previous gateway as
rollback. No Git writes, AWS deletion, operator-data mutation or second environment
was used.
