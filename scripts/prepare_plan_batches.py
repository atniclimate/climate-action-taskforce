"""Prepare deterministic metadata-only assignments for a 575-Nation plan sweep."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

EXPECTED_NATIONS = 575
BATCH_SIZE = 25
REQUESTED_MODEL = "gpt-6-luna"
REQUESTED_REASONING_EFFORT = "high"
CATEGORIES = (
    "climate_adaptation_plan",
    "climate_vulnerability_assessment",
    "hazard_mitigation_or_management_plan",
)


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def load_roster(source: Path) -> tuple[list[dict[str, Any]], str]:
    raw = source.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    document = json.loads(raw.decode("utf-8"))
    rows = document.get("tribes", document) if isinstance(document, dict) else document
    if not isinstance(rows, list):
        raise ValueError("Registry must be a JSON array or an object with a tribes array")
    if len(rows) != EXPECTED_NATIONS:
        raise ValueError(f"Expected {EXPECTED_NATIONS} registry rows; found {len(rows)}")

    nations: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Every registry row must be an object")
        tribe_id, name = row.get("tribe_id"), row.get("name")
        if not isinstance(tribe_id, str) or not tribe_id.strip():
            raise ValueError("Every registry row needs a non-empty tribe_id")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Registry row {tribe_id!r} needs a non-empty name")
        if tribe_id in seen:
            raise ValueError(f"Duplicate tribe_id: {tribe_id}")
        seen.add(tribe_id)

        states = row.get("states", [])
        aliases = row.get("alternate_names", [])
        region = row.get("epa_region")
        if not isinstance(states, list) or not all(isinstance(item, str) for item in states):
            raise ValueError(f"Invalid states list for {tribe_id}")
        if not isinstance(aliases, list) or not all(isinstance(item, str) for item in aliases):
            raise ValueError(f"Invalid alternate_names list for {tribe_id}")
        if region is not None and not isinstance(region, (str, int)):
            raise ValueError(f"Invalid epa_region for {tribe_id}")
        nations.append(
            {
                "tribe_id": tribe_id,
                "name": name.strip(),
                "states": states,
                "alternate_names": aliases,
                "epa_region": region,
            }
        )
    nations.sort(key=lambda nation: nation["tribe_id"])
    return nations, digest


def make_assignments(nations: list[dict[str, Any]], source_sha256: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if len(nations) != EXPECTED_NATIONS:
        raise ValueError(f"Expected {EXPECTED_NATIONS} Nations; found {len(nations)}")
    ids = [nation["tribe_id"] for nation in nations]
    if len(set(ids)) != len(ids):
        raise ValueError("Nation IDs must be unique before batching")

    assignments: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []
    for offset in range(0, len(nations), BATCH_SIZE):
        batch_index = offset // BATCH_SIZE + 1
        batch_id = f"D{batch_index:02d}"
        assigned_nations = []
        for nation in nations[offset : offset + BATCH_SIZE]:
            assigned_nations.append(
                {
                    "tribe_id": nation["tribe_id"],
                    "name": nation["name"],
                    "categories": {
                        category: {"status": "not_started", "outcome_receipt": None}
                        for category in CATEGORIES
                    },
                }
            )
            manifest_rows.append(
                {
                    "tribe_id": nation["tribe_id"],
                    "batch_id": batch_id,
                    "status": "not_started",
                    "category_status": {category: "not_started" for category in CATEGORIES},
                }
            )
        assignments.append(
            {
                "schema_version": "catf-plan-discovery-assignment.v1",
                "batch_id": batch_id,
                "ordinal_start": offset + 1,
                "ordinal_end": offset + len(assigned_nations),
                "requested_model": REQUESTED_MODEL,
                "requested_reasoning_effort": REQUESTED_REASONING_EFFORT,
                "source_registry_sha256": source_sha256,
                "status": "not_started",
                "nations": assigned_nations,
            }
        )

    validate_partition(ids, assignments)
    return {
        "schema_version": "catf-plan-discovery-manifest.v1",
        "source_registry": "TCR active configured reference registry",
        "source_registry_sha256": source_sha256,
        "roster_count": len(nations),
        "batch_size": BATCH_SIZE,
        "batch_count": len(assignments),
        "requested_model": REQUESTED_MODEL,
        "requested_reasoning_effort": REQUESTED_REASONING_EFFORT,
        "status": "not_started",
        "categories": list(CATEGORIES),
        "nation_assignments": manifest_rows,
    }, assignments


def validate_partition(expected_ids: list[str], assignments: list[dict[str, Any]]) -> None:
    assigned = [nation["tribe_id"] for batch in assignments for nation in batch["nations"]]
    if assigned != expected_ids:
        raise ValueError("Batch assignments do not exactly preserve sorted registry IDs")
    if len(assigned) != len(set(assigned)):
        raise ValueError("A Nation ID appears in more than one assignment")
    if len(assignments) != 23 or any(len(batch["nations"]) != BATCH_SIZE for batch in assignments):
        raise ValueError("Expected 23 complete batches of 25 Nations")
    for batch in assignments:
        for nation in batch["nations"]:
            if tuple(nation["categories"]) != CATEGORIES:
                raise ValueError("Every Nation assignment must contain all three categories")
            if any(item["status"] != "not_started" or item["outcome_receipt"] is not None
                   for item in nation["categories"].values()):
                raise ValueError("Prepared assignments cannot include search outcomes")


def self_test() -> None:
    nations = [{"tribe_id": f"nation-{index:03d}", "name": f"Nation {index}"}
               for index in range(EXPECTED_NATIONS)]
    manifest, assignments = make_assignments(nations, "0" * 64)
    assert all(item["requested_model"] == "gpt-6-luna"
               and item["requested_reasoning_effort"] == "high"
               for item in [manifest, *assignments])
    assert manifest["roster_count"] == EXPECTED_NATIONS
    assert [len(batch["nations"]) for batch in assignments] == [BATCH_SIZE] * 23
    assert len({row["tribe_id"] for row in manifest["nation_assignments"]}) == EXPECTED_NATIONS
    assert all(row["category_status"] == {category: "not_started" for category in CATEGORIES}
               for row in manifest["nation_assignments"])

    def rejects(ids: list[str], batches: list[dict[str, Any]]) -> bool:
        try:
            validate_partition(ids, batches)
        except ValueError:
            return True
        return False

    assert rejects([nation["tribe_id"] for nation in nations[:-1]], assignments)
    duplicate = json.loads(json.dumps(assignments))
    duplicate[0]["nations"][1]["tribe_id"] = duplicate[0]["nations"][0]["tribe_id"]
    assert rejects([nation["tribe_id"] for nation in nations], duplicate)
    print("self-test: 575 unique IDs partitioned exactly once into 23 complete 25-Nation batches")


def write_new_or_identical(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise FileExistsError(f"Refusing to overwrite different existing output: {path}")
        return
    try:
        with path.open("xb") as handle:
            handle.write(content)
    except FileExistsError:
        if path.read_bytes() != content:
            raise FileExistsError(f"Refusing to overwrite different existing output: {path}")


def generate(source: Path, output: Path) -> None:
    nations, source_sha256 = load_roster(source)
    manifest, assignments = make_assignments(nations, source_sha256)
    roster = {
        "schema_version": "catf-plan-discovery-roster.v1",
        "source_registry_sha256": source_sha256,
        "nation_count": len(nations),
        "nations": nations,
    }
    files = {
        output / "roster.json": canonical_json(roster),
        output / "manifest.json": canonical_json(manifest),
    }
    for assignment in assignments:
        files[output / "batches" / f"{assignment['batch_id']}.assignment.json"] = canonical_json(assignment)

    for path, content in files.items():
        if path.exists() and path.read_bytes() != content:
            raise FileExistsError(f"Refusing to overwrite different existing output: {path}")
    (output / "batches").mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    for path, content in files.items():
        write_new_or_identical(path, content)
    print(json.dumps({"roster_count": len(nations), "batch_count": len(assignments),
                      "source_registry_sha256": source_sha256,
                      "output_files": len(files)}, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-registry", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    if args.source_registry is None and args.output_dir is None and args.self_test:
        return
    if args.source_registry is None or args.output_dir is None:
        parser.error("--source-registry and --output-dir are required unless running only --self-test")
    generate(args.source_registry, args.output_dir)


if __name__ == "__main__":
    main()
