"""Project the pinned October 22 inventory without joining the CATF roster."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METRICS_SHA256 = "efa13418340f740a62f6f95f11487e65244492fffc26c0a482e6f6d3266feb1b"
MANIFEST_SHA256 = "cad2597208ab9671e329035dcef4213f5ca35b72a2d38a9f75e9c400260510a9"
LABELS = {
    "climate_action": "Climate action",
    "climate_adaptation": "Climate adaptation",
    "hazard_mitigation": "Hazard mitigation",
    "vulnerability_assessment": "Vulnerability assessment",
    "ghg_reduction": "GHG reduction",
    "pollution_reduction": "Pollution reduction",
}
INPUT_LABELS = ["source_manifest", "definition_review", "acquisition_summary",
                "acquisition_manifest", "acquisition_coverage", "evaluation_card",
                "roster_crosswalk"]
STORIES = {
    "national-naknek-bbna-ccap-2025": {
        "pages": [2, 5, 39],
        "date_basis": "Body states completed September 2025 (physical PDF page 5); this controls over the filename date. Publication day, adoption and current edition are unknown.",
        "limits": ["Named participant in a broader regional plan; standalone Tribal authorship or adoption is not established."],
    },
    "national-ambler-nwab-pcap-2024": {
        "pages": [1075, 1082, 1089, 1092, 1102, 1130],
        "date_basis": "Component cover is dated March 1, 2024 (physical PDF page 1075). Final, adopted and current status are unknown.",
        "limits": ["Represented community scope does not establish attendance, direct participation, authorization or adoption.",
                   "NWAB component occupies physical PDF pages 1075–1130 within the TCC bundle. Count the component once; do not add the parent container or embedded inventory as separate plans."],
    },
    "national-yocha-yolo-hmp-2012": {
        "pages": [7, 12, 13, 109, 119, 121],
        "date_basis": "Plan is labeled December 2012 Final. Formal adoption and current edition are unknown; the URL's 2018 directory is not the publication date.",
        "limits": ["County GHG inventory explicitly excludes the Tribe (physical PDF page 109); Tribal climate-specific coverage remains withheld and unresolved.",
                   "One broader hazard mitigation plan edition; no separate Tribal annex admitted."],
    },
}


def verified_json(path, expected):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"Pinned input hash mismatch: {Path(path).name}")
    return json.loads(raw)


def check_identity(crosswalk, records):
    """Fail closed if the frozen unresolved identity evidence changes."""
    if (crosswalk["national_government_membership_status"] != "unresolved"
            or crosswalk["operational_profiles"] != 577
            or crosswalk["official_headline_entities"] != 575
            or crosswalk["applied_exclusions"] or crosswalk["applied_merges"]):
        raise ValueError("Identity evidence requires a new reviewed adapter")
    rows = {row["operational_id"]: row for row in crosswalk["rows"]}
    for record in records:
        row = rows.get(record["tribe_slug"])
        if not row or row.get("government_id") is not None:
            raise ValueError("No accepted CATF identity crosswalk for source profile")


def project_relationship(record):
    story = STORIES[record["candidate_id"]]
    support = record["roles"].get("federal_support", {})
    recipient = support.get("recipient", support.get("award_recipient"))
    federal = bool(support)
    adjudication = record["definition_adjudication"]
    if adjudication["root_decision"] != "accept_independent_definition_review":
        raise ValueError("Relationship lacks accepted definition review")
    if not record["adoption_status"].startswith("unknown") or not record["current_edition_status"].startswith("unknown"):
        raise ValueError("Edition status requires a new reviewed adapter")
    return {
        "id": record["candidate_id"],
        "source_profile_name": record["legal_name"],
        "catf_tribe_id": None,
        "identity_status": "unreconciled",
        "plan_title": record["title_verbatim"],
        "relationship_type": record["relationship"]["kind"],
        "relationship_summary": record["relationship"]["basis"],
        "eligibility": {key: adjudication[key] for key in ("broad", "climate_specific", "action_adaptation")},
        "federal_support": {
            "status": "documented_program_support" if federal else "unknown",
            "program": support.get("program"),
            "agency": support.get("agency"),
            "recipient": recipient,
            "subawardee": support.get("subawardee"),
            "award_id": None,
            "amount": None,
            "explanation": (f"EPA Climate Pollution Reduction Grants support; {recipient} is the recipient. "
                            + (f"{support['subawardee']} is the subawardee. " if support.get("subawardee") else "")
                            + "This does not establish a direct Tribal award, award amount or unspent balance."
                            if federal else "Federal support is unknown, not zero. Public hosting alone is not funding evidence."),
        },
        "internal_tribal_resources_status": "unknown",
        "dates": {
            "publication_year": record["publication_year"],
            "publication_date": None,
            "cover_date": record.get("date_on_cover"),
            "completion_date": record.get("date_evidence", {}).get("completion_month"),
            "adoption_status": "unknown",
            "current_edition_status": "unknown",
            "date_basis": story["date_basis"],
        },
        "scope_limits": story["limits"],
        "document_identity": {key: record["identity"].get(key) for key in (
            "document_id", "edition_id", "component_id", "parent_document_id", "component_pdf_pages", "count_rule")},
        "citations": [{
            "url": record["artifact"]["public_url"],
            "title": record["title_verbatim"],
            "physical_pdf_pages": story["pages"],
            "object_sha256": record["acquired_artifact"]["sha256"],
        }],
    }


def build(metrics_path, source_root):
    metrics = verified_json(metrics_path, METRICS_SHA256)
    source_root = Path(source_root).resolve()
    inputs = []
    for item in metrics["input_manifest"]:
        path = (source_root / item["path"]).resolve()
        if not path.is_relative_to(source_root):
            raise ValueError("Input outside source root")
        inputs.append(verified_json(path, item["sha256"]))
    if len(inputs) != len(INPUT_LABELS) or metrics["input_manifest"][0]["sha256"] != MANIFEST_SHA256:
        raise ValueError("Unexpected input manifest")
    records = inputs[0]["records"]
    if len(records) != 3 or {r["candidate_id"] for r in records} != set(STORIES):
        raise ValueError("Reviewed relationship set changed")
    if set(metrics["plan_types_observed"]) != set(LABELS):
        raise ValueError("Provisional label set changed")
    check_identity(inputs[-1], records)
    relationships = [project_relationship(record) for record in records]
    output = {
        "schema_version": "catf-plan-update-v1",
        "source_tool": "plan-assessor",
        "generated_at": metrics["generated_utc"],
        "data_as_of": metrics["inventory_data_as_of"],
        "status": metrics["status"],
        "inventory": metrics["inventory"],
        "identity": {"operational_roster_size": 577, "catf_roster_size": 575,
                     "crosswalk_status": "unresolved", "national_prevalence": None,
                     "explanation": "Source profiles remain unjoined to the CATF roster. The 577 operational identities have not been reconciled to 575 governments; profiles without documents remain unknown."},
        "plan_types": [{"id": key, "label": label,
                        "byte_distinct_files": metrics["plan_types_observed"][key]["byte_distinct_files"],
                        "operational_profiles_with_label": metrics["plan_types_observed"][key]["operational_profiles_with_that_receipt_label"]}
                       for key, label in LABELS.items()],
        "reviewed_subset": metrics["reviewed_subset"],
        "relationships": relationships,
        "unavailable_metrics": metrics["whole_inventory_unavailable_metrics"],
        "format_unvalidated": [
            {"label": "Solomon PCAP", "reason": "Encrypted PDF", "count": 1},
            {"label": "Climate Vulnerability Assessment", "reason": "Unsupported or corrupt under the validator; recorded MIME type application/json", "count": 1},
        ],
        "search_status": "incomplete",
        "limitations": metrics["limits"] + [
            "Verification and national searches are continuing. The first ten profiles were assigned, not completed; initial direct-web shards are partial and add no admissions.",
            "Uncaptured metadata, malformed original search records and access gaps remain unresolved. These are not absence evidence.",
            "Funding, partner, edition and whole-inventory relationship checks remain unfinished. Internal Tribal resources are unknown for all three reviewed relationships.",
            "Two inherited files remain format-unvalidated; inventory presence does not establish a readable or reviewed plan.",
        ],
        "provenance": {
            "metrics_sha256": METRICS_SHA256,
            "source_manifest_sha256": MANIFEST_SHA256,
            "input_hashes": [{"source": label, "sha256": item["sha256"]}
                             for label, item in zip(INPUT_LABELS, metrics["input_manifest"])],
        },
    }
    serialized = json.dumps(output, ensure_ascii=False)
    for forbidden in ("local_path", "tribe_slug", "producer_id", "review_path", "I:/", "I:\\", "H:/", "C:/"):
        if forbidden in serialized:
            raise ValueError(f"Private field leaked: {forbidden}")
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=Path("I:/plan-assessor"))
    args = parser.parse_args()
    result = build(ROOT / "docs/discovery/plan-discovery-metrics-20261022.json", args.source_root)
    (ROOT / "site/data/plan-update.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Projected 6 overlapping labels and 3 unjoined reviewed relationships.")


if __name__ == "__main__":
    main()
