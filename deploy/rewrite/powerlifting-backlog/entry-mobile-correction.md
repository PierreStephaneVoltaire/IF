# Entry and small-screen correction — 2026-09-15

Discord regression found after this checkpoint: the Authentik-source callback
differs from the original configured Discord callback at
`https://dev.nolift.training/api/auth/discord/callback`. Authorization dispatch
alone did not establish successful Discord login. The source-routing decision
and its acceptance below are historical and require direct-flow restoration.

The operator clarified that Authentik must be added alongside Discord, guests
must enter through a dedicated landing page with both login options, About must
remain separate, and informational pages must not display read-only notices.
The correction also addresses iPhone SE navigation and content at 320×568 and
375×667. Earlier desktop/guest navigation evidence did not establish these
requirements.

Luna workers implemented and deployed the changes; Terra accepted the final
source, runtime and scoped live evidence. The coordinator
inspected the small-screen screenshots and rejected clipped labels and the
oversized Athlete context panel before rollout.

## Implementation

- Landing and Login share two distinct provider actions. Public navigation
  retains Home, Search, About and Sign in.
- Discord uses the existing Authentik Discord source with the trusted,
  Passport-generated OIDC continuation. Authentik uses the normal OIDC entry.
  Verified subject mapping, Valkey sessions, state and PKCE remain shared.
- Read-only notices follow route-domain access. Informational routes have none.
- Mobile navigation uses flexible targets and scrollable menus. The selected
  Athlete and active role remain visible while Change expands context controls.

The first backend candidate's `source=discord` query did not select the live
source and was rejected. The final gateway instead wraps Passport’s actual Location header with the source login endpoint; an intermediate
Express res.redirect hook was rejected after live testing showed Passport
bypasses it. Earlier screenshots with clipped labels and the expanded context
filling the initial viewport are excluded from acceptance.

## Verification and rollout

The focused backend continuation test passes. The retained browser regression
script passes 39 assertions, including both small-screen context sizes. It uses
local Vite with simulated API responses and does not establish live login or
deployment behavior. Fresh built landing previews verify distinct endpoint
requests, 44px targets, label width and height, and public navigation.

Final gateway `8740348739cfbce86ef59e800e6c80146dc36897067a57dbcc9413d100ff5b4e`
is Ready at observed generation 30. Final frontend
`5bb25bdb27864d990ecd2b4587a458226eb9f1cc86aedb7396b076afa45c64fe`
is Ready at observed generation 12. Both ECR manifests are ACTIVE. All 18 portal
Deployments remain Ready; the sixteen domain services, IF API and native worker
were not redeployed for this correction.

Genuine browser checks verify guest Landing, Login, Search and About at 320×568,
375×667 and 1440×900. Both login choices are visible and use distinct endpoints;
informational pages have no read-only notice. Compact authenticated context and
More navigation pass. The final Dashboard check uses 320×568 and 375×568 with
loaded content and document/body widths matching each viewport, without injected
styles. The remaining 29px overflow was fixed through grid-card `min-width: 0`.

Terra independently followed Discord through the Authentik source to Discord's
actual authorization endpoint. A fresh normal Authentik browser login returned
HTTP 200 with the correct isolated Echo Person/Athlete, and invalid callback
state was rejected. No Discord identity completion is claimed. Echo selection
and read-only display were observed; a complete cross-Athlete round trip was not
fully reverified during this correction. Known unrelated avatar 401 and ranking
404 responses are recorded in [bug.md](../../../bug.md).

[Sanitized summary](entry-mobile-summary.json), [final review](entry-mobile-review.md),
[runtime inventory](entry-mobile-runtime-inventory.json), [More proof](entry-mobile-more.json)
and [context proof](entry-mobile-context.json) retain the precise evidence.
[320px landing capture](entry-mobile-landing-320.png) and
[375px capture](entry-mobile-landing-375.png) came from the preceding `7c77cf5…`
frontend; the final change only adjusts Dashboard card sizing.

Gateway rollback `d4cbce47…` and frontend rollbacks `7c77cf5e…` / `a7aad69a…`
remain available. Exact unused local candidate images were removed after ECR
publication and Docker container-reference checks. No Git writes, AWS resource
deletions, second environment or operator-data changes occurred.
