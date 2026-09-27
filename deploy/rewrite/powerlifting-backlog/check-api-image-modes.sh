#!/usr/bin/env bash
set -euo pipefail

repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
terraform_dir="$repo_root/terraform"
candidate_digest="sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f"

latest_check=$(terraform -chdir="$terraform_dir" console -var-file=../deploy/rewrite/models.tfvars.json -var='if_agent_api_image_digest=' <<'EOF'
local.if_agent_api_image == "${aws_ecr_repository.if_agent_api.repository_url}:latest" && local.if_agent_api_image_checksum == local.if_agent_api_build_checksum && sha1(jsonencode({dir_sha1 = local.docker_hash, source_sha1 = sha1("changed-source"), powerlifting_operations = local.powerlifting_operations_hash, repo_url = aws_ecr_repository.if_agent_api.repository_url})) != local.if_agent_api_build_checksum
EOF
)

pinned_check=$(terraform -chdir="$terraform_dir" console -var-file=../deploy/rewrite/models.tfvars.json -var="if_agent_api_image_digest=$candidate_digest" <<'EOF'
local.if_agent_api_image == "${aws_ecr_repository.if_agent_api.repository_url}@sha256:3076896f4dd3ca09e779ece06cd58b7e593a32196349b6e970d8f67428a4343f" && local.if_agent_api_image_checksum == sha1(local.if_agent_api_image) && local.if_agent_api_image_checksum != local.if_agent_api_build_checksum
EOF
)

test "$latest_check" = "true"
test "$pinned_check" = "true"
