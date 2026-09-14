from types import SimpleNamespace

from flow import runner


def test_runner_preserves_duplicate_upload_filenames_and_history(monkeypatch, tmp_path):
    first = tmp_path / "first" / "report.txt"
    second = tmp_path / "second" / "report.txt"
    first.parent.mkdir()
    second.parent.mkdir()
    first.write_text("first")
    second.write_text("second")
    monkeypatch.setenv("IF_ARTIFACT_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(runner, "get_directive_store", lambda owner: SimpleNamespace(load=lambda: None, get_for_subagent=lambda _: [], format_directives=lambda _: "current directives"))
    monkeypatch.setattr(runner, "list_specialists", lambda: [])
    monkeypatch.setattr(runner, "resolve_session_dir", lambda *_: tmp_path)
    monkeypatch.setattr(runner, "build_runtime_context", lambda **_: "context")
    data = {"_owner": "a", "messages": [{"role": "user", "content": "hello"}], "_uploaded_files": [{"local_path": str(first)}, {"local_path": str(second)}]}
    owner, request, path = runner.prepare_conversation(data, "conversation-a", "cache")
    assert owner == "a" and request.conversation_id == "conversation-a"
    uploads = request.payload["uploaded_files"]
    assert len({upload["name"] for upload in uploads}) == 2
    assert request.payload["directives"] == "current directives"
    assert request.kind == "conversation"


def test_each_turn_refreshes_only_its_person_directives(monkeypatch):
    seen = []
    versions = iter(['first', 'updated'])
    current = {}
    def store(owner):
        seen.append(owner)
        return SimpleNamespace(load=lambda: current.update(text=next(versions)), get_for_subagent=lambda _: [], format_directives=lambda _: current['text'])
    monkeypatch.setattr(runner, 'get_directive_store', store)
    monkeypatch.setattr(runner, 'list_specialists', lambda: [])
    assert runner.instruction_payload('alice')['directives'] == 'first'
    assert runner.instruction_payload('alice')['directives'] == 'updated'
    assert seen == ['alice', 'alice']
