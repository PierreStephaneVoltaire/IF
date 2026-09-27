import importlib.util
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "utils" / "powerlifting-app"))
spec = importlib.util.spec_from_file_location("live_contracts", Path(__file__).with_name("test_powerlifting_services_live.py"))
live_contracts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_contracts)


def test_mcp_exposure_excludes_only_internal_operations():
    openapi = {"paths": {f"/operations/{name}": {} for name in ("profile_get", "settings_create", "video_upload_presign")}}
    assert live_contracts.operation_names(openapi) - {"settings_create", "video_upload_presign"} == {"profile_get"}


def test_program_identity_uses_stable_sort_key():
    assert live_contracts.program_sort_key({"version": "034-861d"}) is None
    assert live_contracts.program_sort_key({"version": 34, "sk": "program#v034-861d"}) == "program#v034-861d"


def test_mcp_tool_names_ignores_unshaped_entries():
    assert live_contracts.mcp_tool_names({"result": {"tools": [{"name": "a"}, {}, {"name": None}]}}) == {"a"}


def test_program_list_is_checked_alongside_full_history():
    source = Path(__file__).with_name("test_powerlifting_services_live.py").read_text()
    assert 'operation("program", "program_list", {"pk": ATHLETE})' in source
    assert 'headers("program_list")' in source
    assert 'operation("program", "program_list_full", {"pk": ATHLETE})' in source
