# Local image cleanup

The disposable scan container was verified by exact identity before cleanup:

- container `43be9c9e5fda` used the Analytics candidate tag, ran the one-off `find ... sha256sum` scan with `/:/host:ro`, had `AutoRemove=true`, and had restart policy `no`
- it was stopped gracefully and auto-removed; no live workload used it

The Analytics candidate was verified in ECR before cleanup:

- repository `if-powerlifting-app-backend`, tag `backlog-20260914-analytics-refresh`, digest `sha256:60c83f4c17f59b32ac19e7b1da5894d4ee2fdc9b17e1e2d0942ce1c3987cc69e`

- frontend candidate `backlog-20260914-frontend-authored-notes` digest `sha256:881e0d6d146e20e5dfcd7a666ba14c83af3cb58be8741b71aade6640d129b38c`: `ACTIVE`
- frontend rollback `sha256:b06fbfb3d24f6f7230504629c58062c03509ba5d03fac4a602947156545273fe`: `ACTIVE`

Removed by exact local image ID after ECR verification and container removal:

- frontend candidate `sha256:881e0d6d146e20e5dfcd7a666ba14c83af3cb58be8741b71aade6640d129b38c`
- gateway backend candidate `sha256:27c6ddb82e236602a05ddb3c4af6a854bb31c29dbfeba1a97865802be5c4b1b9`
- services candidate `sha256:c3f5af1b70570d87fcf0044a302b980d3c90b0549cf9e323f36ee0b5ecd04d92`
- API candidate `sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f`

- Analytics candidate local image ID `sha256:60c83f4c17f59b32ac19e7b1da5894d4ee2fdc9b17e1e2d0942ce1c3987cc69e` (tag `backlog-20260914-analytics-refresh`)

No broad prune ran. OCI rollback archives, including `/tmp/if-analytics-image.ZIonqN/analytics-rollback.oci.tar`, and node containerd images were untouched. No AWS resources were deleted.
