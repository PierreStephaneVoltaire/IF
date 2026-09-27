from __future__ import annotations

import argparse
import copy
import hashlib
import os
import re
import sys
import uuid
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


POINTER_SK = "program#current"
SESSION_SK_PREFIX = "session#"
TEMPLATE_SK_PREFIX = "template#"
SEED_MARKER = "operator-health-to-private-test-v2"
IDENTITY_FIELDS = {
    "person_pk", "author_person_pk", "owner_person_pk", "athlete_person_pk",
    "grantee_person_pk", "recipient_person_pk", "requester_person_pk",
    "user_pk", "mapped_pk", "athlete_mapped_pk", "grantee_mapped_pk",
    "owner_pk", "athlete_pk", "author_pk", "created_by", "updated_by",
    "actor", "person", "owner", "athlete", "source_pk", "author_person", "owner_person",
}
IDENTITY_LINK_FIELDS = {
    "identity_provider", "identity_issuer", "identity_sub", "authentik_sub",
    "discord_id", "discord_username",
}
IDENTIFIER_FIELDS = {"session_id", "note_id", "attachment_id", "cache_id", "generation_id", "analysis_id", "generated_cache_id", "source_fingerprint"}
IDENTIFIER_ALIASES = {
    "source_fingerprint": "generation_id", "generated_cache_id": "generation_id",
    "cache_id": "generation_id", "analysis_id": "generation_id",
}
TEMPLATE_REF_FIELDS = {
    "template_sk", "source_template_sk", "parent_template_sk", "template_ref",
    "applied_template_sk", "derived_from_template_sk",
}
FORBIDDEN_SK_PREFIXES = ("Identity#", "Grant#", "Relationship#", "RelationshipPending#", "Event#", "Notification")


def to_dynamo(value: Any) -> Any:
    if isinstance(value, float):
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: to_dynamo(child) for key, child in value.items()}
    if isinstance(value, list):
        return [to_dynamo(child) for child in value]
    return value


def query_partition(table: Any, pk: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    request: dict[str, Any] = {"KeyConditionExpression": Key("pk").eq(pk)}
    while True:
        response = table.query(**request)
        items.extend(response.get("Items", []))
        if not response.get("LastEvaluatedKey"):
            return items
        request["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def get_item(table: Any, key: dict[str, Any]) -> dict[str, Any] | None:
    return table.get_item(Key=key, ConsistentRead=True).get("Item")


def identity_key(issuer: str, subject: str) -> str:
    return "Identity#" + hashlib.sha256(f"{issuer}\0{subject}".encode()).hexdigest()


def stable_identifier(value: Any, kind: str, source_person: str, target_person: str) -> str:
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"if-test:{kind}:{source_person}:{target_person}:{value}")
    return f"test-{kind}-{digest.hex[:24]}"


class Remapper:
    def __init__(self, source_person: str, source_athlete: str, target_person: str, target_athlete: str):
        self.persons = {source_person: target_person, source_athlete: target_athlete}
        self.identifier_maps: dict[tuple[str, str], str] = {}
        self.source_person = source_person
        self.source_athlete = source_athlete
        self.target_person = target_person
        self.target_athlete = target_athlete
        self.template_maps: dict[str, str] = {}

    def person(self, value: Any) -> Any:
        return self.persons.get(str(value), value)

    def identifier(self, value: Any, kind: str) -> str:
        kind = IDENTIFIER_ALIASES.get(kind, kind)
        key = (kind, str(value))
        if key not in self.identifier_maps:
            self.identifier_maps[key] = stable_identifier(value, kind, self.source_person, self.target_person)
        return self.identifier_maps[key]

    def value(self, value: Any, field: str = "", identifier_kind: str | None = None) -> Any:
        if isinstance(value, dict):
            return {key: self.value(child, str(key), identifier_kind) for key, child in value.items() if key not in IDENTITY_LINK_FIELDS}
        if isinstance(value, list):
            return [self.value(child, field, identifier_kind) for child in value]
        if field in IDENTITY_FIELDS and value not in (None, ""):
            return self.person(value)
        if field in TEMPLATE_REF_FIELDS and str(value) in self.template_maps:
            return self.template_maps[str(value)]
        if field in IDENTIFIER_FIELDS and value not in (None, ""):
            return self.identifier(value, field)
        if identifier_kind and field == "id" and value not in (None, ""):
            return self.identifier(value, f"{identifier_kind}_id")
        return value

    def key(self, value: str, identifier_kind: str | None = None) -> str:
        if value in self.persons:
            return str(self.person(value))
        result = value
        if self.persons:
            sources = sorted(self.persons, key=len, reverse=True)
            pattern = rf"(?<![A-Za-z0-9])(?:{'|'.join(re.escape(source) for source in sources)})(?![A-Za-z0-9])"
            result = re.sub(pattern, lambda match: str(self.persons[match.group(0)]), result)
        if identifier_kind == "session" and result.startswith(SESSION_SK_PREFIX):
            parts = result.split("#")
            if len(parts) > 4:
                parts[-1] = self.identifier(parts[-1], "session_id")
                result = "#".join(parts)
        if identifier_kind == "note" and result.startswith(("Note#", "SharedNote#")):
            parts = result.split("#")
            if len(parts) > 1:
                parts[1] = self.identifier(parts[1], "note_id" if result.startswith("Note#") else "attachment_id")
                result = "#".join(parts)
        if identifier_kind == "cache" and result.startswith("native_generation#"):
            parts = result.split("#")
            if len(parts) > 1:
                parts[1] = self.identifier(parts[1], "generation_id")
                result = "#".join(parts)
        return result


def identifier_kind(item: dict[str, Any]) -> str | None:
    sk = str(item.get("sk") or "")
    entity = str(item.get("entity_type") or item.get("entity") or "").lower()
    if sk.startswith(SESSION_SK_PREFIX) or entity == "session" or isinstance(item.get("sessions"), list):
        return "session"
    if sk.startswith(("Note#", "SharedNote#", "NoteMutation#")) or "note" in entity:
        return "note"
    if sk.startswith("analysis#") or sk.startswith("weekly_analysis#") or sk.startswith("native_generation#") or "cache" in entity or "analysis" in entity or "generation" in entity:
        return "cache"
    return None


def has_unmapped_identity_reference(value: Any, field: str, remapper: Remapper) -> bool:
    if isinstance(value, dict):
        return any(has_unmapped_identity_reference(child, str(key), remapper) for key, child in value.items())
    if isinstance(value, list):
        return any(has_unmapped_identity_reference(child, field, remapper) for child in value)
    known = set(remapper.persons) | {remapper.target_person, remapper.target_athlete}
    return field in IDENTITY_FIELDS and value not in (None, "") and str(value) not in known


def forbidden_item(item: dict[str, Any], remapper: Remapper) -> bool:
    sk = str(item.get("sk") or "")
    if sk.startswith(FORBIDDEN_SK_PREFIXES):
        return True
    if str(item.get("entity") or item.get("entity_type") or "").lower() in {"grant", "notification", "relationship", "relationship_request"}:
        return True
    return has_unmapped_identity_reference(item, "", remapper)


def copy_item(item: dict[str, Any], partition: str, remapper: Remapper, table_name: str, readonly: bool = False) -> dict[str, Any] | None:
    if forbidden_item(item, remapper):
        return None
    copied = remapper.value(copy.deepcopy(item), identifier_kind=identifier_kind(item))
    copied["pk"] = partition
    copied["sk"] = remapper.key(str(item.get("sk") or ""), identifier_kind(item))
    for key in IDENTITY_LINK_FIELDS:
        copied.pop(key, None)
    copied.update({
        "test_seed_marker": SEED_MARKER,
        "test_seed_source_table": table_name,
        "test_seed_source_pk": str(item.get("pk") or ""),
        "test_seed_source_sk": str(item.get("sk") or ""),
    })
    if readonly:
        copied["read_only"] = True
    if str(item.get("sk") or "").startswith("Media#") or str(item.get("entity") or item.get("entity_type") or "").lower() in {"media", "video", "media_registry"}:
        copied["readonly"] = True
    return copied


def source_owned_template(item: dict[str, Any], remapper: Remapper) -> bool:
    if str(item.get("sk") or "") in {"template#index", "template#current_list"}:
        return False
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    author = str(meta.get("author_pk") or item.get("author_pk") or "")
    author_person = str(meta.get("author_person_pk") or item.get("author_person_pk") or "")
    return author in {remapper.source_person, remapper.source_athlete} or author_person == remapper.source_person


def owned_template_key(source_sk: str, target_person: str) -> str:
    digest = uuid.uuid5(uuid.NAMESPACE_URL, f"if-test-template:{target_person}:{source_sk}")
    return f"template#test-owned-{digest.hex[:24]}"


def copy_owned_template(item: dict[str, Any], remapper: Remapper, table_name: str) -> dict[str, Any] | None:
    if not source_owned_template(item, remapper):
        return None
    copied = copy_item(item, item.get("pk", "template_library"), remapper, table_name)
    if copied is None:
        return None
    source_sk = str(item.get("sk") or "")
    copied["sk"] = owned_template_key(source_sk, remapper.target_person)
    meta = copied.setdefault("meta", {})
    meta["legacy_author_pk"] = str((item.get("meta") or {}).get("author_pk") or item.get("author_pk") or "")
    meta["author_pk"] = remapper.target_person
    meta["author_person_pk"] = remapper.target_person
    meta["published"] = False
    meta.pop("published_at", None)
    if "author_pk" in copied:
        copied["author_pk"] = remapper.target_person
    return copied


def private_note_owned(item: dict[str, Any], remapper: Remapper) -> bool:
    sk = str(item.get("sk") or "")
    if sk.startswith("Note#"):
        return str(item.get("author_person_pk") or "") == remapper.source_person
    if sk.startswith("NoteMutation#"):
        return str(item.get("actor") or "") == remapper.source_person
    return False


def template_summary(item: dict[str, Any]) -> dict[str, Any]:
    meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
    return {
        "sk": item.get("sk"),
        "name": meta.get("name"),
        "source_filename": meta.get("source_filename"),
        "source_file_hash": meta.get("source_file_hash"),
        "estimated_weeks": meta.get("estimated_weeks"),
        "days_per_week": meta.get("days_per_week"),
        "archived": bool(meta.get("archived", False)),
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "author": meta.get("author"),
        "author_pk": meta.get("author_pk"),
        "published": bool(meta.get("published", True)),
        "published_at": meta.get("published_at"),
        "import_job_id": meta.get("import_job_id"),
    }


def update_template_index(table: Any, library_pk: str, copied_templates: list[dict[str, Any]]) -> tuple[int, int]:
    if not copied_templates:
        return 0, 0
    summaries = [template_summary(item) for item in copied_templates]
    for _ in range(5):
        current = get_item(table, {"pk": library_pk, "sk": "template#index"})
        if current is None:
            current = get_item(table, {"pk": library_pk, "sk": "template#current_list"}) or {}
        existing = list(current.get("templates") or [])
        by_sk = {str(summary.get("sk")): summary for summary in existing if summary.get("sk")}
        before = dict(by_sk)
        by_sk.update({str(summary["sk"]): summary for summary in summaries})
        templates = sorted(by_sk.values(), key=lambda summary: str(summary.get("created_at") or ""))
        revision = int(current.get("index_revision", 0))
        if before == by_sk and current.get("sk") == "template#index":
            return 0, len(summaries)
        index = to_dynamo({
            **current,
            "pk": library_pk,
            "sk": "template#index",
            "templates": templates,
            "updated_at": max(
                [str(current.get("updated_at") or "")]
                + [str(summary.get("updated_at") or "") for summary in summaries]
            ),
            "index_revision": revision + 1,
        })
        condition = "attribute_not_exists(pk) OR attribute_not_exists(#revision) OR #revision = :revision"
        try:
            table.put_item(
                Item=index,
                ConditionExpression=condition,
                ExpressionAttributeNames={"#revision": "index_revision"},
                ExpressionAttributeValues={":revision": revision},
            )
            return len(summaries), 0
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
    raise RuntimeError("template index changed repeatedly; refusing an unsafe update")


def remove_template_index_entries(table: Any, library_pk: str, removed_sks: set[str]) -> bool:
    if not removed_sks:
        return False
    for _ in range(5):
        current = get_item(table, {"pk": library_pk, "sk": "template#index"})
        if current is None:
            return False
        templates = [summary for summary in current.get("templates") or [] if str(summary.get("sk")) not in removed_sks]
        if len(templates) == len(current.get("templates") or []):
            return False
        revision = int(current.get("index_revision", 0))
        index = to_dynamo({**current, "templates": templates, "updated_at": datetime.now(timezone.utc).isoformat(), "index_revision": revision + 1})
        try:
            table.put_item(
                Item=index,
                ConditionExpression="attribute_exists(pk) AND (attribute_not_exists(#revision) OR #revision = :revision)",
                ExpressionAttributeNames={"#revision": "index_revision"},
                ExpressionAttributeValues={":revision": revision},
            )
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
                raise
    raise RuntimeError("template index changed repeatedly; refusing an unsafe cleanup")


def seed_marker_matches(item: dict[str, Any], source_table: str, source_pk: str, source_sk: str) -> bool:
    return item.get("test_seed_marker") == SEED_MARKER and item.get("test_seed_source_table") == source_table and item.get("test_seed_source_pk") == source_pk and item.get("test_seed_source_sk") == source_sk


def same_key(item: dict[str, Any]) -> dict[str, Any]:
    return {"pk": item["pk"], "sk": item["sk"]} if "sk" in item else {"pk": item["pk"]}


def validate_target_person(table: Any, person_pk: str, athlete_pk: str) -> dict[str, Any]:
    person = get_item(table, {"pk": person_pk})
    if not person:
        raise RuntimeError(f"target Person {person_pk!r} does not exist")
    if str(person.get("mapped_pk") or "") != athlete_pk:
        raise RuntimeError(f"target Person {person_pk!r} is not mapped to Athlete {athlete_pk!r}")
    issuer = str(person.get("identity_issuer") or "").strip()
    subject = str(person.get("identity_sub") or "").strip()
    pointer = get_item(table, {"pk": identity_key(issuer, subject)}) if issuer and subject else None
    if not pointer or str(pointer.get("mapped_pk") or "") != person_pk or pointer.get("identity_issuer") != issuer or str(pointer.get("identity_sub") or "") != subject:
        raise RuntimeError(f"target Person {person_pk!r} has no verified login mapping")
    if person.get("profile_visibility") != "private":
        raise RuntimeError(f"target Person {person_pk!r} must have a private profile")
    return person


def table_plans(args: argparse.Namespace) -> list[tuple[str, Any, str, Any, str, bool]]:
    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    names = [
        ("health", args.health_table, args.source_pk, args.health_table, args.target_pk, False),
        ("sessions", args.sessions_table, args.source_pk, args.sessions_table, args.target_pk, False),
        ("private_notes", args.health_table, args.source_person_pk, args.health_table, args.target_person_pk, False),
        ("global_templates", args.templates_table, args.source_template_library_pk, args.templates_table, args.source_template_library_pk, False),
        ("competition_entries", args.competitions_table, args.source_pk, args.competitions_table, args.target_pk, False),
        ("goals", args.goals_table, args.source_pk, args.goals_table, args.target_pk, False),
        ("budget", args.budget_table, args.source_pk, args.budget_table, args.target_pk, False),
        ("analysis_cache", args.analysis_cache_table, f"analysis#{args.source_pk}", args.analysis_cache_table, f"analysis#{args.target_pk}", True),
    ]
    return [(label, dynamodb.Table(source_table), source_pk, dynamodb.Table(target_table), target_pk, readonly) for label, source_table, source_pk, target_table, target_pk, readonly in names if source_table]


def planned_items(args: argparse.Namespace, remapper: Remapper) -> tuple[list[tuple[str, Any, Any, dict[str, Any]]], Counter[str]]:
    plans: list[tuple[str, Any, Any, dict[str, Any]]] = []
    counts: Counter[str] = Counter()
    all_plans = table_plans(args)
    template_sources = next((query_partition(source_table, source_pk) for label, source_table, source_pk, _, _, _ in all_plans if label == "global_templates"), [])
    remapper.template_maps = {
        str(item.get("sk")): owned_template_key(str(item.get("sk") or ""), remapper.target_person)
        for item in template_sources
        if source_owned_template(item, remapper) and str(item.get("sk") or "") not in {"template#index", "template#current_list"}
    }
    for label, source_table, source_pk, target_table, target_pk, readonly in all_plans:
        for item in query_partition(source_table, source_pk):
            if label == "private_notes" and not private_note_owned(item, remapper):
                counts["skipped_private_notes"] += 1
                continue
            if label != "private_notes" and str(item.get("sk") or "").startswith(("Note#", "NoteMutation#")):
                counts["skipped_private_notes"] += 1
                continue
            if label == "global_templates":
                copied = copy_owned_template(item, remapper, source_table.name)
            else:
                copied = copy_item(item, target_pk, remapper, source_table.name, readonly)
            if copied is None:
                counts[f"skipped_{label}"] += 1
                continue
            plans.append((label, source_table, target_table, copied))
            counts[label] += 1
    return plans, counts


def check_conflicts(plans: list[tuple[str, Any, Any, dict[str, Any]]]) -> list[tuple[str, dict[str, Any], str]]:
    conflicts: list[tuple[str, dict[str, Any], str]] = []
    for label, _, target_table, item in plans:
        existing = get_item(target_table, same_key(item))
        if existing and not seed_marker_matches(existing, str(item["test_seed_source_table"]), str(item["test_seed_source_pk"]), str(item["test_seed_source_sk"])):
            conflicts.append((label, same_key(item), str(target_table.name)))
    return conflicts


def write_plans(plans: list[tuple[str, Any, Any, dict[str, Any]]]) -> tuple[int, int]:
    written = skipped = 0
    for _, _, target_table, item in plans:
        existing = get_item(target_table, same_key(item))
        if existing:
            skipped += 1
            continue
        target_table.put_item(Item=to_dynamo(item), ConditionExpression="attribute_not_exists(pk)")
        written += 1
    return written, skipped


def report(plans: list[tuple[str, Any, Any, dict[str, Any]]], counts: Counter[str], dry_run: bool) -> None:
    print("[operator-health-copy] private test data plan")
    print(f"  mode: {'dry-run' if dry_run else 'apply'}")
    labels = sorted({plan[0] for plan in plans} | {key.removeprefix('skipped_') for key in counts if key.startswith('skipped_')})
    for label in labels:
        print(f"  {label}: {counts.get(label, 0)} copied, {counts.get('skipped_' + label, 0)} skipped")
    index_planned = counts.get("global_templates", 0) > 0
    if index_planned:
        print("  global_template_index: 1 planned, 0 skipped")
    print(f"  total planned keys: {len(plans) + int(index_planned)}")
    for _, _, target_table, item in plans[:5]:
        print(f"    {target_table.name} pk={item['pk']} sk={item.get('sk', '<none>')}")
    if index_planned:
        template_plan = next(item for item in plans if item[0] == "global_templates")
        print(f"    {template_plan[2].name} pk={template_plan[3]['pk']} sk=template#index")
    if dry_run:
        print("Dry run only; no DynamoDB writes or deletes performed.")


def copy_data(args: argparse.Namespace) -> int:
    user_table = boto3.resource("dynamodb", region_name=args.region).Table(args.user_table)
    validate_target_person(user_table, args.target_person_pk, args.target_pk)
    remapper = Remapper(args.source_person_pk, args.source_pk, args.target_person_pk, args.target_pk)
    plans, counts = planned_items(args, remapper)
    conflicts = check_conflicts(plans)
    report(plans, counts, args.dry_run)
    if conflicts:
        print("Refusing to overwrite unrelated target items:", file=sys.stderr)
        for label, key, table_name in conflicts[:25]:
            print(f"  {label} {table_name} {key}", file=sys.stderr)
        return 2
    if args.dry_run:
        return 0
    written, skipped = write_plans(plans)
    template_table = next((target_table for label, _, target_table, _ in plans if label == "global_templates"), None)
    copied_templates = [item for label, _, _, item in plans if label == "global_templates"]
    indexed, already_indexed = update_template_index(template_table, args.source_template_library_pk, copied_templates) if template_table else (0, 0)
    print(f"Applied conditional copies: wrote {written}, already seeded {skipped}; template index wrote {indexed}, already current {already_indexed}.")
    return 0


def cleanup(args: argparse.Namespace) -> int:
    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    tables = table_plans(args)
    candidates: list[tuple[Any, dict[str, Any]]] = []
    seen: set[tuple[str, str, str]] = set()
    for _, _, _, target_table, target_pk, _ in tables:
        for item in query_partition(target_table, target_pk):
            marker_key = (str(target_table.name), str(item.get("pk") or ""), str(item.get("sk") or ""))
            if item.get("test_seed_marker") == SEED_MARKER and marker_key not in seen:
                seen.add(marker_key)
                candidates.append((target_table, item))
    template_table = next((target_table for label, _, _, target_table, _, _ in tables if label == "global_templates"), None)
    removed_template_sks = {str(item.get("sk")) for table, item in candidates if template_table is table and str(item.get("sk") or "").startswith(TEMPLATE_SK_PREFIX)}
    print("[operator-health-copy] marked private test data cleanup")
    print(f"  mode: {'dry-run' if args.dry_run else 'apply'}")
    print(f"  marked keys: {len(candidates)}")
    for table, item in candidates[: args.sample_keys]:
        print(f"    {table.name} pk={item['pk']} sk={item.get('sk', '<none>')}")
    if args.dry_run:
        print("Dry run only; no DynamoDB deletes performed.")
        return 0
    for table, item in candidates:
        table.delete_item(Key=same_key(item), ConditionExpression="test_seed_marker = :marker", ExpressionAttributeValues={":marker": SEED_MARKER})
    if template_table:
        remove_template_index_entries(template_table, args.source_template_library_pk, removed_template_sks)
    print(f"Deleted marked test items: {len(candidates)}. User identity records were not touched.")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Copy all operator training data into an existing private test Person mapping.")
    result.add_argument("--health-table", default=os.getenv("IF_HEALTH_TABLE_NAME", "if-health"))
    result.add_argument("--sessions-table", default=os.getenv("IF_SESSIONS_TABLE_NAME", "if-sessions"))
    result.add_argument("--templates-table", default=os.getenv("IF_TEMPLATES_TABLE_NAME", "if-health-templates"))
    result.add_argument("--competitions-table", default=os.getenv("POWERLIFTING_USER_COMPETITIONS_TABLE", "if-powerlifting-user-competitions"))
    result.add_argument("--goals-table", default=os.getenv("POWERLIFTING_GOALS_TABLE", "if-powerlifting-goals"))
    result.add_argument("--budget-table", default=os.getenv("POWERLIFTING_BUDGET_TABLE", "if-powerlifting-budget"))
    result.add_argument("--analysis-cache-table", default=os.getenv("ANALYSIS_CACHE_TABLE_NAME", "if-powerlifting-analysis-cache"))
    result.add_argument("--user-table", default=os.getenv("IF_USER_TABLE", "if-user"))
    result.add_argument("--region", default=os.getenv("AWS_REGION", "ca-central-1"))
    result.add_argument("--source-pk", default=os.getenv("HEALTH_PROGRAM_PK", "operator"))
    result.add_argument("--source-person-pk", default=os.getenv("IF_OPERATOR_PERSON_PK", "sir_simpalot"))
    result.add_argument("--target-pk", default=os.getenv("POWERLIFTING_TEST_MAPPED_PK", "test"))
    result.add_argument("--target-person-pk", default=os.getenv("POWERLIFTING_TEST_PERSON_PK", "test"))
    result.add_argument("--source-template-library-pk", default=os.getenv("IF_TEMPLATES_LIBRARY_PK", "template_library"))
    result.add_argument("--cleanup", action="store_true")
    result.add_argument("--apply", action="store_true", help="Perform conditional writes or marked-data deletes")
    result.add_argument("--dry-run", action="store_true", help="Explicitly select the default no-write mode")
    result.add_argument("--sample-keys", type=int, default=5)
    return result


def main() -> int:
    args = parser().parse_args()
    if args.apply and args.dry_run:
        print("ERROR: --apply and --dry-run are mutually exclusive", file=sys.stderr)
        return 2
    args.dry_run = not args.apply
    if args.source_pk == args.target_pk or args.source_person_pk == args.target_person_pk:
        print("ERROR: source and target identities must be different", file=sys.stderr)
        return 2
    try:
        return cleanup(args) if args.cleanup else copy_data(args)
    except ClientError as exc:
        error = exc.response.get("Error", {})
        print(f"AWS ERROR: {error.get('Message', str(exc))}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
