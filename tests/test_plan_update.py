"""Focused acceptance checks for the separate, pinned plan inventory."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare_plan_update", ROOT / "scripts/prepare_plan_update.py")
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class PlanUpdateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protected = {name: (ROOT / "site/data" / name).read_bytes()
                         for name in ("plans.json", "risk.json", "funding.json")}
        cls.explorer = {path: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in (ROOT / "site/data/explorer").rglob("*") if path.is_file()}
        cls.result = adapter.build(ROOT / "docs/discovery/plan-discovery-metrics-20261022.json", Path("I:/plan-assessor"))

    def test_exact_frozen_counts_and_overlapping_labels(self):
        result = self.result
        self.assertEqual(result["data_as_of"], "2026-10-22T12:20:10.158087+00:00")
        inventory = result["inventory"]
        self.assertEqual([inventory[k] for k in ("operational_profiles_with_local_documents", "byte_distinct_files", "unique_profile_object_pairs", "lead_records", "files_placed_under_multiple_profiles")], [254, 234, 306, 404, 20])
        self.assertEqual([(p["byte_distinct_files"], p["operational_profiles_with_label"]) for p in result["plan_types"]], [(56, 78), (40, 58), (84, 82), (24, 24), (17, 33), (18, 23)])
        self.assertEqual(inventory["format_validation_counts"], {"validated_application/pdf": 232, "unvalidated_application/pdf": 1, "unvalidated_application/json": 1})
        self.assertEqual(sum(x["count"] for x in result["format_unvalidated"]), 2)
        self.assertEqual(result["search_status"], "incomplete")

    def test_identity_and_missingness_are_not_forced(self):
        self.assertIsNone(self.result["inventory"]["verified_national_numerator"])
        self.assertIsNone(self.result["identity"]["national_prevalence"])
        self.assertEqual(self.result["identity"]["operational_roster_size"], 577)
        self.assertEqual(self.result["identity"]["catf_roster_size"], 575)
        for row in self.result["relationships"]:
            self.assertIsNone(row["catf_tribe_id"])
            self.assertEqual(row["identity_status"], "unreconciled")
            self.assertIsNone(row["federal_support"]["amount"])
            self.assertIsNone(row["federal_support"]["award_id"])
            self.assertEqual(row["dates"]["adoption_status"], "unknown")
            self.assertEqual(row["dates"]["current_edition_status"], "unknown")
        yocha = next(r for r in self.result["relationships"] if "yocha" in r["id"])
        self.assertEqual(yocha["eligibility"]["climate_specific"], "withheld_unresolved")
        self.assertEqual(yocha["federal_support"]["status"], "unknown")

    def test_citation_and_component_provenance(self):
        rows = {r["id"]: r for r in self.result["relationships"]}
        self.assertEqual(len(rows), 3)
        ambler = rows["national-ambler-nwab-pcap-2024"]
        self.assertEqual(ambler["document_identity"]["component_pdf_pages"], {"first": 1075, "last": 1130})
        self.assertEqual(ambler["federal_support"]["recipient"], "Tanana Chiefs Conference")
        self.assertEqual(ambler["federal_support"]["subawardee"], "Northwest Arctic Borough")
        self.assertEqual(ambler["dates"]["cover_date"], "2024-03-01")
        self.assertIsNone(ambler["dates"]["publication_date"])
        self.assertEqual(rows["national-naknek-bbna-ccap-2025"]["dates"]["completion_date"], "2025-09")
        for row in rows.values():
            citation = row["citations"][0]
            self.assertTrue(citation["url"].startswith("https://"))
            self.assertTrue(citation["physical_pdf_pages"])
            self.assertRegex(citation["object_sha256"], r"^[a-f0-9]{64}$")
        self.assertEqual(self.result["provenance"]["metrics_sha256"], adapter.METRICS_SHA256)
        self.assertEqual(len(self.result["provenance"]["input_hashes"]), 7)

    def test_hash_and_identity_drift_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "changed.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                adapter.build(path, Path(temp))
        fixture = {"national_government_membership_status": "unresolved", "operational_profiles": 577,
                   "official_headline_entities": 575, "applied_exclusions": [], "applied_merges": [],
                   "rows": [{"operational_id": "source-a", "government_id": None}]}
        adapter.check_identity(fixture, [{"tribe_slug": "source-a"}])
        with self.assertRaises(ValueError):
            adapter.check_identity(fixture, [{"tribe_slug": "missing"}])
        changed = copy.deepcopy(fixture)
        changed["rows"][0]["government_id"] = "guessed-catf-id"
        with self.assertRaises(ValueError):
            adapter.check_identity(changed, [{"tribe_slug": "source-a"}])
        changed = copy.deepcopy(fixture)
        changed["applied_exclusions"] = ["two-to-force-count"]
        with self.assertRaises(ValueError):
            adapter.check_identity(changed, [])

    def test_allowlisted_public_projection_and_protected_assets(self):
        text = json.dumps(self.result)
        for private in ("local_path", "producer_id", "review_path", "tribe_slug", "I:/", "I:\\", "H:/", "C:/"):
            self.assertNotIn(private, text)
        for name, raw in self.protected.items():
            self.assertEqual((ROOT / "site/data" / name).read_bytes(), raw, name)
        self.assertEqual({path: hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in (ROOT / "site/data/explorer").rglob("*") if path.is_file()}, self.explorer)
        self.assertEqual(hashlib.sha256(self.protected["plans.json"]).hexdigest(), "1426c98ddfa84064aac46016c481220cdc9f6c3412e803035c90365ad3ba6f0f")
        self.assertEqual(hashlib.sha256(self.protected["funding.json"]).hexdigest(), "527f856037f7a081e5eaa58287a609e91b848f0dd99db1901eb397bf5cc5bdd2")


if __name__ == "__main__":
    unittest.main()
