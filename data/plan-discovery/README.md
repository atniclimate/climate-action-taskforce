# National plan-discovery assignments

Prepared from the scanner's active public reference registry on 2026-10-21. The source SHA-256 is recorded in every artifact. These are **assignments, not search results**.

- `roster.json`: 575 unique Nation IDs, formal names, public aliases, states and source EPA-region metadata. EPA region is source context, not an automatic CATF aggregation region.
- `manifest.json`: all baseline IDs assigned exactly once across 23 batches of 25.
- `batches/D01.assignment.json` through `D23.assignment.json`: owner-authorized `gpt-6-luna` model with `high` reasoning and three independently tracked search classes for every Nation, all `not_started`.

The class keys cover climate adaptation/action plans (CCAP), climate vulnerability assessments, and hazard mitigation/management plans. Search completion must be established for each class. A located hazard plan does not establish that adaptation-plan discovery is complete.

Workers consume an assignment and create a separate `Dxx.results.json` using `docs/DATA-CONTRACTS.md`. Keep these initial assignments unchanged. The orchestrator merges results after validating provenance, ID coverage, duplicates, dates and class-level outcome states. No national searches have run yet.

`scripts/prepare_plan_batches.py` regenerates the same files from the exact source input and refuses to replace different existing output. Its `--self-test` checks partition completeness and overlap rejection. The explicit generation arguments are `--source-registry PATH --output-dir PATH`; follow the project's Windows command route when invoking Python. No third-party Python packages are required.

This baseline matches the scanner's 575-Nation cohort. Compare it to the current authoritative roster before a current-national-coverage claim; record supplemental additions separately. A legacy 592-row source file is not interchangeable with this registry.
