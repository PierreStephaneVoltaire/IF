# Program cache coherence predeploy review

## Verdict

Accepted for the narrow native Program-cache coherence fix.

`GET /api/programs` and `GET /api/programs/:version` have no `cacheGet` middleware. Each now reaches its unchanged controller, which invokes the authenticated, typed Program operations (`program_list_full` and `program_get`) through the normal authorization and scoped-service path. The native `health_update_current_maxes` operation writes `current_maxes` with `ProgramStore.mutate_source`, so the next exact online Program GET will read the source rather than a seven-day Valkey entry.

The route's remaining `invalidateAfter` middleware is unchanged on gateway-originated writes. `cacheGet` has no remaining call site in `programs.ts`; global search found it only on explicitly separate resources. `server.ts` applies authentication/scope middleware before mounting `/api/programs`; its response path adds no cache. No API cache headers, proxy cache, CDN route, or second response middleware were found. The repository's CloudFront configuration is for media buckets only.

The IndexedDB cache remains intentionally unchanged: `cachedGet` calls the gateway while online and only returns its saved response when offline or after a transport failure. Report and maxes caches also remain out of scope and do not supply the Program response used here.

## Checks

- `git diff --check -- backend/src/routes/programs.ts` passed.
- `npm run typecheck --workspace backend` passed.
- `npm run build --workspace backend` passed.

## Live acceptance requirement

Do not treat a cache-buster as evidence. After deployment, use one identical `/api/programs/v020` URL: read/prime it, make the signed native maxes mutation, repeat that exact URL and require the changed squat plus revision increment while preserving the ready form slot, then restore through the same native operation and repeat the exact URL again. Preserve the gateway's AWS mounts/environment, secure OIDC, Valkey, and the ready video during the deployment and regression proof.
