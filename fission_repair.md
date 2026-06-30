# Fission Cold-Start Repair Plan

## Summary

- Verified Fission newdeploy + MinScale=0 is the right cold-start model per Fission docs: functions can scale to zero and be recreated on demand. Source: https://fission.io/docs/concepts/executors/
- Root cause 1: the backend calls IF API direct tools, but IF cannot register health tools because health_lambda_mcp fetches GET /openapi.json from Fission and gets 404.
- Verified individual Fission POST routes do work: health_get_program and template_list returned 200 through the Fission router.

## Key Changes

- Deploy the existing tool_registry function instead of skipping it.
  - Remove tool_registry from Fission skip lists in Terraform/archive generation.
  - Add a Fission HTTPTrigger for GET /openapi.json pointing at pl-fn-tool-registry.
  - Keep normal health tools as POST /{tool_name}.
  - Keep pl_authorizer skipped.

## Verification

- Before deploy, record current evidence:
  - GET /openapi.json from if-agent-api pod returns 404.
  - Direct IF invoke /health_get_program {} returns Unknown tool.
  - pl-pkg-analyze-rpe-drift has status.buildstatus=failed.

- After deploy:
  - GET http://router.fission.svc.cluster.local/openapi.json from if-agent-api returns 200 and includes /health_get_program.
  - POST /admin/reload-tools or restart if-agent-api; logs show health_lambda MCP started with the Fission health tools.
  - Direct IF invoke /health_get_program {} from the backend pod returns program JSON, not Unknown tool.
  - pl-pkg-tool-registry and pl-pkg-analyze-rpe-drift both show buildstatus=succeeded.
  - After the idle window, all pl-fn-\* deployments scale back to 0 replicas except functions actively being invoked.

## Assumptions

- Keep stock Fission Python builder/runtime images; do not bake dependencies into a custom image.
- Keep newdeploy and MinScale=0 for powerlifting health functions.
- Leave opencode-job alone even though it has MinScale=1; it is not one of the powerlifting health functions.
- Do not rewrite the Fission setup. The fix is limited to restoring OpenAPI discovery and fixing the one oversized failed package.
