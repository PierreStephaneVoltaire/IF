import importlib.util
from pathlib import Path


SPEC = importlib.util.spec_from_file_location("copy_tool", Path(__file__).with_name("copy_operator_health_to_test.py"))
TOOL = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(TOOL)


def test_remaps_history_session_and_authorship_without_identity_links():
    remapper = TOOL.Remapper("sir_simpalot", "operator", "test-person", "test")
    source = {
        "pk": "operator",
        "sk": "session#program#v001#2026-01-01#001#session-source",
        "entity": "session",
        "id": "session-source",
        "session_id": "session-source",
        "author_person_pk": "sir_simpalot",
        "athlete_mapped_pk": "operator",
        "identity_sub": "operator-subject",
        "notes": {"session_id": "session-source"},
    }
    result = TOOL.copy_item(source, "test", remapper, "if-sessions")
    assert result["pk"] == "test"
    assert result["author_person_pk"] == "test-person"
    assert result["athlete_mapped_pk"] == "test"
    assert result["id"] == result["session_id"] == result["notes"]["session_id"]
    assert result["sk"].endswith(result["session_id"])
    assert "identity_sub" not in result
    assert source["pk"] == "operator"


def test_skips_private_original_and_unknown_person():
    remapper = TOOL.Remapper("sir_simpalot", "operator", "test-person", "test")
    own = TOOL.copy_item({"pk": "operator", "sk": "Note#private", "author_person_pk": "sir_simpalot", "text": "secret"}, "test", remapper, "if-health")
    assert own["author_person_pk"] == "test-person"
    assert TOOL.copy_item({"pk": "operator", "sk": "Note#other", "author_person_pk": "other-person", "text": "secret"}, "test", remapper, "if-health") is None
    assert TOOL.copy_item({"pk": "operator", "sk": "SharedNote#x", "author_person_pk": "other-person"}, "test", remapper, "if-health") is None


def test_media_copy_is_read_only_and_keeps_s3_reference():
    remapper = TOOL.Remapper("sir_simpalot", "operator", "test-person", "test")
    source = {"pk": "operator", "sk": "Media#video", "media_id": "video", "s3_key": "operator/session/video.mp4"}
    result = TOOL.copy_item(source, "test", remapper, "if-health", readonly=True)
    assert result["read_only"] is True
    assert result["readonly"] is True
    assert result["s3_key"] == source["s3_key"]


def test_unrelated_existing_item_is_a_conflict():
    class Table:
        name = "if-health"

        def get_item(self, **kwargs):
            return {"Item": {"pk": "test", "sk": "program#v001", "owner": "someone-else"}}

    plans = [("health", None, Table(), {"pk": "test", "sk": "program#v001", "test_seed_source_table": "if-health", "test_seed_source_pk": "operator", "test_seed_source_sk": "program#v001"})]
    assert TOOL.check_conflicts(plans) == [("health", {"pk": "test", "sk": "program#v001"}, "if-health")]


def test_target_requires_oidc_pointer_and_private_profile():
    class Table:
        def __init__(self, items):
            self.items = items

        def get_item(self, **kwargs):
            return {"Item": self.items.get(kwargs["Key"].get("pk"))}

    person = {"pk": "test-person", "mapped_pk": "test", "identity_issuer": "https://issuer", "identity_sub": "subject", "profile_visibility": "private"}
    table = Table({"test-person": person, TOOL.identity_key("https://issuer", "subject"): {"mapped_pk": "test-person", "identity_issuer": "https://issuer", "identity_sub": "subject"}})
    assert TOOL.validate_target_person(table, "test-person", "test") == person
    public = dict(person, profile_visibility="public")
    table = Table({"test-person": public, TOOL.identity_key("https://issuer", "subject"): {"mapped_pk": "test-person", "identity_issuer": "https://issuer", "identity_sub": "subject"}})
    try:
        TOOL.validate_target_person(table, "test-person", "test")
    except RuntimeError as error:
        assert "private" in str(error)
    else:
        raise AssertionError("public target profile was accepted")


def test_cleanup_apply_deletes_only_marked_items(monkeypatch):
    class Table:
        def __init__(self, name, items):
            self.name = name
            self.items = items
            self.deleted = []

        def query(self, **kwargs):
            return {"Items": list(self.items)}

        def delete_item(self, **kwargs):
            self.deleted.append(kwargs)

    tables = {}
    class Dynamo:
        def Table(self, name):
            tables.setdefault(name, Table(name, [{"pk": "test", "sk": "program#v001", "test_seed_marker": TOOL.SEED_MARKER}]))
            return tables[name]

    monkeypatch.setattr(TOOL.boto3, "resource", lambda *args, **kwargs: Dynamo())
    args = TOOL.parser().parse_args(["--apply", "--cleanup", "--health-table", "health", "--sessions-table", "sessions", "--competitions-table", "competitions", "--goals-table", "goals", "--budget-table", "budget", "--analysis-cache-table", "cache", "--sample-keys", "0"])
    args.dry_run = False
    assert TOOL.cleanup(args) == 0
    assert all(table.deleted for table in tables.values())
    assert "if-user" not in tables


def test_apply_uses_conditional_put_and_is_idempotent():
    class Table:
        name = "health"

        def __init__(self):
            self.items = {}
            self.conditions = []

        def get_item(self, **kwargs):
            return {"Item": self.items.get((kwargs["Key"]["pk"], kwargs["Key"]["sk"]))}

        def put_item(self, **kwargs):
            self.conditions.append(kwargs["ConditionExpression"])
            item = kwargs["Item"]
            self.items[(item["pk"], item["sk"])] = item

    table = Table()
    item = {"pk": "test", "sk": "program#v001", "test_seed_source_table": "health", "test_seed_source_pk": "operator", "test_seed_source_sk": "program#v001"}
    plan = [("health", None, table, item)]
    assert TOOL.write_plans(plan) == (1, 0)
    assert TOOL.write_plans(plan) == (0, 1)
    assert table.conditions == ["attribute_not_exists(pk)"]


def test_planning_reads_source_person_notes_and_global_templates(monkeypatch):
    class Table:
        def __init__(self, name, records):
            self.name = name
            self.records = records
            self.queries = []

        def query(self, **kwargs):
            self.queries.append(kwargs)
            expression = kwargs["KeyConditionExpression"]
            pk = getattr(expression, "_values", [None, None])[1]
            return {"Items": [item for item in self.records if item["pk"] == pk]}

    records = {
        "health": [
            {"pk": "operator", "sk": "program#v001", "author_person_pk": "sir_simpalot", "template_lineage": {"applied_template_sk": "template#one"}},
            {"pk": "operator", "sk": "Note#wrong-partition", "note_id": "wrong-partition", "author_person_pk": "sir_simpalot", "text": "private"},
            {"pk": "sir_simpalot", "sk": "Note#mine", "note_id": "mine", "author_person_pk": "sir_simpalot", "text": "private"},
            {"pk": "sir_simpalot", "sk": "Note#other", "note_id": "other", "author_person_pk": "another-person", "text": "private"},
            {"pk": "sir_simpalot", "sk": "NoteMutation#mine", "actor": "sir_simpalot"},
        ],
        "templates": [
            {"pk": "template_library", "sk": "template#index", "templates": []},
            {"pk": "template_library", "sk": "template#one", "meta": {"author_pk": "operator", "name": "One"}, "template_lineage": {"parent_template_sk": "template#one"}},
            {"pk": "template_library", "sk": "template#other", "meta": {"author_pk": "someone-else", "name": "Other"}},
        ],
    }
    tables = {}

    class Dynamo:
        def Table(self, name):
            records_for_table = records.get(name, [])
            tables.setdefault(name, Table(name, records_for_table))
            return tables[name]

    monkeypatch.setattr(TOOL.boto3, "resource", lambda *args, **kwargs: Dynamo())
    args = TOOL.parser().parse_args([
        "--health-table", "health", "--sessions-table", "sessions", "--templates-table", "templates",
        "--competitions-table", "competitions", "--goals-table", "goals", "--budget-table", "budget",
        "--analysis-cache-table", "cache", "--source-pk", "operator", "--source-person-pk", "sir_simpalot",
        "--target-pk", "test-athlete", "--target-person-pk", "test-person",
    ])
    remapper = TOOL.Remapper("sir_simpalot", "operator", "test-person", "test-athlete")
    plans, counts = TOOL.planned_items(args, remapper)
    template_plans = [item for label, _, _, item in plans if label == "global_templates"]
    note_plans = [item for label, _, _, item in plans if label == "private_notes"]
    program_plans = [item for label, _, _, item in plans if label == "health"]
    assert len(template_plans) == 1
    assert template_plans[0]["pk"] == "template_library"
    assert template_plans[0]["sk"].startswith("template#test-owned-")
    assert len(note_plans) == 2
    assert {item["sk"] for item in note_plans} == {"NoteMutation#mine", "Note#test-note_id-" + TOOL.stable_identifier("mine", "note_id", "sir_simpalot", "test-person").removeprefix("test-note_id-")}
    assert program_plans[0]["template_lineage"]["applied_template_sk"] == template_plans[0]["sk"]
    assert counts["skipped_private_notes"] == 2
    assert all(kwargs["KeyConditionExpression"] is not None for kwargs in tables["health"].queries)


def test_template_index_cas_preserves_global_records_and_adds_private_summary():
    class Table:
        name = "templates"

        def __init__(self):
            self.item = {"pk": "template_library", "sk": "template#index", "index_revision": 4, "templates": [{"sk": "template#operator", "author_pk": "operator"}]}
            self.calls = []

        def get_item(self, **kwargs):
            return {"Item": self.item} if kwargs["Key"]["sk"] == "template#index" else {}

        def put_item(self, **kwargs):
            self.calls.append(kwargs)
            self.item = kwargs["Item"]

    table = Table()
    copied = {"pk": "template_library", "sk": "template#test-owned-one", "meta": {"name": "One", "author_pk": "test-person", "published": False}}
    assert TOOL.update_template_index(table, "template_library", [copied]) == (1, 0)
    assert {entry["sk"] for entry in table.item["templates"]} == {"template#operator", "template#test-owned-one"}
    assert table.item["index_revision"] == 5
    assert table.calls[0]["ConditionExpression"]


def test_cleanup_index_removes_only_marked_template_summaries():
    class Table:
        name = "templates"

        def __init__(self):
            self.item = {"pk": "template_library", "sk": "template#index", "index_revision": 2, "templates": [{"sk": "template#keep"}, {"sk": "template#remove"}]}
            self.calls = []

        def get_item(self, **kwargs):
            return {"Item": self.item}

        def put_item(self, **kwargs):
            self.calls.append(kwargs)
            self.item = kwargs["Item"]

    table = Table()
    assert TOOL.remove_template_index_entries(table, "template_library", {"template#remove"}) is True
    assert [entry["sk"] for entry in table.item["templates"]] == ["template#keep"]
