import asyncio
from types import SimpleNamespace

from channels import slash_commands


def test_import_forwards_downloaded_attachment(monkeypatch, tmp_path):
    captured = {}

    async def download(attachments, conversation_id, target_uploads_dir):
        captured["attachments"] = attachments
        captured["conversation_id"] = conversation_id
        captured["uploads_dir"] = target_uploads_dir
        return [{**attachments[0], "local_path": str(target_uploads_dir / attachments[0]["filename"])}]

    async def process(*, request_data, http_client, **kwargs):
        captured["request_data"] = request_data
        return "done", []

    monkeypatch.setattr("channels.attachments.download_discord_attachments", download)
    monkeypatch.setattr("api.completions.process_chat_completion_internal", process)
    monkeypatch.setattr("main.app", SimpleNamespace(state=SimpleNamespace(http_client=object())))
    monkeypatch.setattr("config.API_MODEL_NAME", "test-model")
    monkeypatch.setattr("flow.session_dirs.resolve_session_dir", lambda *args, **kwargs: tmp_path)
    monkeypatch.setattr("channels.channel_coordinator.discord_conversation", lambda channel_id: str(channel_id))
    interaction = SimpleNamespace(
        id=42,
        channel_id=123,
        guild_id=456,
        user=SimpleNamespace(id=789),
    )
    attachment = SimpleNamespace(
        filename="program.csv",
        url="https://cdn.invalid/program.csv",
        content_type="text/csv",
    )

    result = asyncio.run(slash_commands._invoke_via_agent("import this", interaction, attachment))

    assert result == "done"
    assert captured["attachments"] == [{
        "filename": "program.csv",
        "url": "https://cdn.invalid/program.csv",
        "content_type": "text/csv",
    }]
    assert captured["request_data"]["_uploaded_files"][0]["local_path"].endswith("uploads/program.csv")


def test_template_fetch_uses_scoped_internal_request(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return [{"name": "Squat", "sk": "template#1"}, {"name": "Bench", "sk": "template#2"}]

    class Client:
        def __init__(self, **kwargs):
            captured["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def post(self, url, *, json, headers):
            captured.update(url=url, json=json, headers=headers)
            return Response()

    monkeypatch.setattr("httpx.AsyncClient", Client)
    monkeypatch.setenv("INTERNAL_API_TOKEN", "internal-test")
    monkeypatch.setenv("PL_SERVICE_URL_TEMPLATE", "http://pl-{domain}.{namespace}:8000")
    monkeypatch.setattr("config.IF_MCP_NAMESPACE", "if-test")
    monkeypatch.setattr("config.IF_USER_PK", "operator-test")

    templates = asyncio.run(slash_commands._fetch_templates())

    assert [template["name"] for template in templates] == ["Squat", "Bench"]
    assert captured["url"] == "http://pl-templates.if-test:8000/operations/template_list"
    assert captured["json"] == {"pk": "operator-test", "include_archived": False}
    assert captured["headers"] == {
        "X-Internal-Token": "internal-test",
        "X-Athlete-Pk": "operator-test",
        "X-Person-Pk": "operator-test",
    }
    assert [choice.value for choice in slash_commands._template_choices(templates, "sQu")] == ["template#1"]
