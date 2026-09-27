# Frontend candidate

Prepared 2026-09-15. Terra accepted the AuthProvider revocation fix. The refreshed image was published and rolled to the existing frontend Deployment; no AWS resource deletion occurred.

The existing frontend workspace passed `npm run typecheck` and `npm run build`. Live browser revocation acceptance passed against `https://dev.nolift.training`; delegated cache was cleared while the draft, pending mutation and other partition remained.

| Field | Value |
| --- | --- |
| Repository | `429310424269.dkr.ecr.ca-central-1.amazonaws.com/if-powerlifting-app-frontend` |
| Candidate tag | `backlog-20260915-frontend-revocation` |
| Candidate digest | `sha256:a0b96a7b99b871b89a2b3bcc2f1a5c96480f69a84268e6d274cd6fee635eea8f` |
| Candidate ECR status | `ACTIVE` |
| Live rollback tag | `native-20260914-frontend` |
| Live rollback digest | `sha256:b06fbfb3d24f6f7230504629c58062c03509ba5d03fac4a602947156545273fe` |
| Rollback ECR status | `ACTIVE` |
| Existing recipe | `utils/powerlifting-app/docker/powerlifting-frontend.pkr.hcl` |
| Base | `node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293` |
| API build variables | `VITE_API_URL=/api`, `VITE_API_BASE_URL=/api`, empty CloudFront base |

Source hashes:

- frontend source aggregate: `7b1e3bb3d3e290af0655206fe22e73d66047e5bebbc47c4ed915a8a275796298`
- frontend public aggregate: `cfd9b4322760876b3159dbb26a082cd293a38f979ad1f836a63ed6bce3e1c334`
- frontend config aggregate: `01cadfabe453e595e784818526c39a52f1af99f93a1c32aeb7e0c3997c90916d`
- package lock: `847c50536fb945d76b49289caf8b85475fb8e95324f0047983cf23c3119cab40`
- checked-in recipe: `7b2bcc61c4c5577e33095864d7dec3b7ac68262121145c1df576d732d6a0f852`
- disposable release recipe: `da173ff1c19eccd1b5679e16c1435afe9f5843af9f49d84730d96ab11ed593c2`

The disposable recipe changed only the source path for the workspace copy, the base reference because `public.ecr.aws` returned HTTP 403 while the exact local official equivalent was cached, and the post-processor tags from `[candidate, latest]` to `[candidate]`. The checked-in recipe was not changed and `latest` was not overwritten.

Build and publication completed with Packer. The refreshed candidate was re-read from ECR by digest and is `ACTIVE`. Deployment generation 9 is observed with one Ready replica on the exact imageID and zero restarts. Post-deploy evidence is `/tmp/frontend-revocation-live-evidence.json`.

The Cloudflare 500 MiB allowance remains pending, so the full-size media acceptance is still deferred. Any subsequent rollout must pin the refreshed digest and preserve the existing rollback digest.
