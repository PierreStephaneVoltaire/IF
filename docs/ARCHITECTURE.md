# Current runtime

The [native conversation contract](contracts/native-conversations.md) supersedes the historical execution topology below. The main API retains channel integrations, scoped memory, tools and delivery. A persistent HTTP Codex host owns two independent native Conversations and their child Specialists. Its rollout is awaiting protected API approval.

# IF Architecture

IF accepts requests from Discord, OpenWebUI, and the OpenAI-compatible API. FastAPI creates durable execution state, a local worker runs the request through the native Codex SDK, and the originating channel receives streamed text and any materialized artifacts.

## Request path

```text
Channel or HTTP request
  -> completion route and conversation context
  -> durable execution registry and local SQLite queue
  -> Codex worker with scoped tools, directives, and artifact grants
  -> terminal result, artifacts, and reconciliation state
  -> channel outbox delivery
```

The service keeps a stable workspace for each conversation under `IF_WORKSPACE_BASE`. History and generated files remain in that workspace. Inputs are copied to the artifact store and passed to workers by artifact ID; worker output is uploaded back to the API before the response is delivered.

## Codex execution

The worker starts the native Codex SDK with the operator's ChatGPT subscription. `gpt-5.6-sol` is the default coordination model and `gpt-5.6-luna` is used for lower-cost helper work. The worker checks the subscription model catalogue before beginning a turn.

Jobs carry an owner, conversation ID, priority, idempotency key, and scoped capabilities. A worker receives an HMAC-bound scope token for its role. Tool requests are authorized by the API using that scope, and child workers receive a narrower token. The policy hook must be loaded for scoped work; an unavailable hook fails the job instead of widening access.

## Durable delivery and cancellation

The execution registry records task lifecycle, runs, cancellation requests, reconciliation state, and channel outbox entries. A cancelled active task enters reconciliation when delivery may already have occurred. A pivot replaces the pending request with the new topic; an inactive conversation starts the new request directly.

Streaming preserves terminal output. File references are parsed after the complete response, copied to the artifact store, and materialized by the relevant channel adapter.

## Storage and deployment

DynamoDB stores conversation registry records, directives, and domain data. SQLite with WAL is the local durable execution queue on the main-node PVC. The API and worker use a shared internal token. Packer packages powerlifting operation metadata at `/app/powerlifting-operations`; `PL_OPERATIONS_DIR` selects that location at runtime.

The service runs on a single-node k3s cluster. Terraform remains the operator-managed deployment definition. See [the rewrite contract](contracts/rewrite.md) for required behavior.
