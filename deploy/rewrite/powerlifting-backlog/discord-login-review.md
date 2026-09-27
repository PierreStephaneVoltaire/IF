# Direct Discord login — Terra review

## Current live finding

The deployed `/api/auth/discord/login` is not a direct Discord application
flow. An anonymous browser sends Discord client `1459678985473757400` with
`redirect_uri=https://auth.nolift.training/source/oauth/callback/discord/` via
the Authentik Discord source. The live gateway instead configures the same
client with `DISCORD_REDIRECT_URI=https://dev.nolift.training/api/auth/discord/callback`.
This is the concrete redirect-URI mismatch behind Discord's rejection when the
Discord application registers the existing direct callback.

## Required repair contract

Restore the direct authorize request with that configured client ID and exact
callback URI, preserving state in the existing Valkey-backed Passport session.
The callback must exchange the code using the same exact redirect URI, validate
state, fetch the Discord identity, serialize and deserialize a `discord`
identity, and map it through the verified subject/person contract without
email, display-name, or username account linkage. Keep Authentik login on its
existing OIDC/PKCE/state/callback path.

The historic direct controller did use the configured callback in both
authorization and token exchange, but its old JWT settings path is not an
acceptable restoration by itself: current `getOrCreateSettingsForIdentity`
rejects a `discord` provider, and current Passport deserialization accepts only
the Authentik issuer. The repair therefore needs focused callback/session and
identity-mapping regression coverage, not merely an authorize URL assertion.

## Candidate gate

Do not accept a bespoke OAuth implementation that reimplements authorization,
state, PKCE, token exchange, and profile fetch inside a custom Passport
strategy. Use a maintained Discord/OAuth2 strategy, or an existing maintained
client facility with equivalent protections. The candidate must prove exact
configured client and callback use; session-bound, consumed state; callback
error handling; verifier use; validated Discord subject mapping without
username/email linking; Passport deserialize; and an authenticated `/me` after
callback.

No Discord OAuth application or Authentik-source configuration was changed in
this review. No identity login was completed.

## Source-review result: accepted for rollout

The repaired route uses `passport.authenticate('discord')` with maintained
`passport-oauth2`, the live configuration's direct callback, session state,
and PKCE. The dead URL helper is gone. The source maps only the validated
numeric Discord profile subject to `issuer=https://discord.com`,
`provider=discord`, and `sub`; username becomes identity-resolver display data,
not an account-link key, and email is discarded. Issuer/provider pairing is
validated again when Passport restores a session. Settings lookup failures are
returned through Passport's verification callback. The separate Authentik OIDC
strategy is statically typed and retains its own callback and state flow.

Independent validation passed on the frozen candidate:

- `npm run typecheck`
- `npm run build`
- `node --import tsx --test src/controllers/authLogin.test.ts` — 4/4 pass

The focused test drives the actual configured Passport strategy, observes the
Discord authorize URL and exact client/callback with an S256 challenge, rejects
missing/invalid/replayed session state before exchange, and completes a mocked
code/profile callback while proving state consumption and verified-subject
identity handling.

Post-rollout acceptance remains required: an anonymous deployed login must
reach Discord with client `1459678985473757400` and
`https://dev.nolift.training/api/auth/discord/callback`, a direct callback with
invalid state must be rejected, and a normal Authentik login must still use its
existing OIDC path. This review did not complete Discord consent or authenticate
a Discord identity, so it makes no claim about a completed live Discord login.

## Live acceptance: passed

Gateway generation 31 is Ready on
`sha256:b688e943a910ec37b23285f75586f0a7b8f2c346c08653e1509b6b5520130f62`.
Its running `dist/middleware/auth.js` SHA-256 is
`9e731f41df6e82d50e90eb79c1e2d6c924c62219d07c3e9966693a91e66ac0b9`, the
same as the reviewed local compiled module. The slim runtime image retains the
gateway's compiled backend, type package, operation manifests, and calculation
constants under the existing non-root runtime configuration.
Static-read inspection confirms that those manifests and constants are the
gateway's repository-file dependencies; the country locale is supplied by the
installed runtime package, and video handling reads request-created temporary
files rather than an omitted source asset.

An independent anonymous browser followed `/api/auth/discord/login` to
`discord.com/oauth2/authorize` with the exact direct client and callback,
`response_type=code`, and `code_challenge_method=S256`. The visible Discord
page did not contain an invalid-redirect-URI error before consent. An anonymous
direct callback with a fabricated state returned `302` to
`/login?error=auth_failed`. In a new browser context, a normal Authentik login
completed and `/api/auth/me` returned 200 with an Authentik identity and its
Person and own Athlete references.

Sanitized observations are in `/tmp/discord-direct-login-terra-live.json`.
Discord consent and the resulting identity callback were deliberately not
performed because no Discord identity was available; successful end-to-end
Discord identity login remains unclaimed.
