#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

terraform -chdir=terraform apply -input=false -auto-approve \
  -var-file=../deploy/rewrite/models.tfvars.json \
  -target=null_resource.packer_build_main_api

terraform -chdir=terraform apply -input=false -auto-approve \
  -var-file=../deploy/rewrite/models.tfvars.json \
  -target=null_resource.config_sync_content \
  -target=kubernetes_job.sync_config_pvcs \
  -target=kubernetes_config_map.if_agent_api_config \
  -target=kubernetes_config_map.if_agent_api_model_config \
  -target=kubernetes_secret.if_agent_api_secrets \
  -target=kubernetes_secret.ecr_registry \
  -target=kubernetes_deployment.if_agent_api \
  -target=null_resource.rollout_restart_main_api
