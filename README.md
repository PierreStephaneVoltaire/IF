# IF

IF is a personal FastAPI agent service for Discord, OpenWebUI, and an OpenAI-compatible HTTP API. It keeps durable conversation state, runs persistent Conversations through a subscription-backed Codex host, and delivers text and generated files through the originating channel.

## Runtime

```text
Client -> FastAPI/channel listener -> persistent Codex Conversation host
       -> scoped tools and directives -> response/artifacts -> channel delivery
```

Each request has a conversation workspace under `IF_WORKSPACE_BASE`. The API retains the DynamoDB delivery outbox and saves generated files under `IF_ARTIFACT_DIR`. The host journals native thread/turn IDs in persistent SQLite and admits two concurrent Conversations without a waiting queue. The worker uses the local ChatGPT subscription through the native Codex SDK. Scoped workers receive only their assigned directives, tool grants, artifacts, and child credentials.

The runtime persists task, run, cancellation, and outbox records so an interrupted delivery can be reconciled rather than replayed. Powerlifting operations are packaged separately at `/app/powerlifting-operations` and discovered with `PL_OPERATIONS_DIR`.

## Run locally

```bash
cd app
pip install -r requirements.txt
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

Copy `app/.env.example` to `app/.env`. Set `INTERNAL_API_TOKEN`, storage credentials and table names for the services you use. Authenticate the local Codex SDK with the operator's ChatGPT subscription; no provider API key is required by the execution runtime.

## Configuration

The core runtime settings are:

- `IF_API_URL`, `IF_CODEX_HOST_URL` and `INTERNAL_API_TOKEN` for the authenticated bridge; `IF_HOST_STATE_DIR` and `CODEX_HOME` for persistent native state. `IF_JOB_DB` retains historical job lookups.
- `IF_WORKSPACE_BASE` and `IF_ARTIFACT_DIR` for durable workspaces and artifacts.
- `IF_OPERATOR_DISCORD_ID=400750817382236160` maps `sir_simpalot` to the existing Operator.
- `AWS_REGION`, `IF_EXECUTION_REGISTRY_TABLE_NAME`, and the domain table names for durable state.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Native conversation contract and verification](docs/contracts/native-conversations.md)
- [Protected rollout review](deploy/rewrite/native-rollout.md)
- [Architecture decisions](docs/adr/)

## License

MIT
