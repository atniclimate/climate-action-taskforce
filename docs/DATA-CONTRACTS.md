# Assessment and discovery contracts

All assessment outputs are frozen for presentation delivery. Browser interactions filter and explain local data; they do not fetch a new scanner analysis. Retain provenance locally, project only needed public fields, and give participants source dates and limitations.

## Shared snapshot

Each generated dataset carries `schema_version`, `generated_at`, `data_as_of`, `source_tool`, `package_version`, `source_commit`, `source_dirty`, `input_manifest_sha256`, `method_version`, `coverage`, `limitations` and source citations. A source file's modification time is not its data-as-of date. Missing dates remain null with a reason. Record hashes of exact input files and any relevant uncommitted source used.

Nation IDs come from one pinned registry, joined through explicit crosswalks. Preserve formal display names and historical aliases. No fuzzy matching directly publishes a Nation relationship. A regional membership crosswalk includes its taxonomy/version and mapping basis; do not mix ATNI, NCAI, BIA or scanner regions without labels. For totals, use one exclusive aggregation assignment or disclose overlaps and use a separate non-overlapping national method.

Use JSON for site data, CSV for inspectable tabular downloads and a small manifest for lineage. Choose concrete schemas during extraction based on actual source fields; these are semantic requirements, not permission to fabricate source columns.

## Risk and cost

Risk rows require `tribe_id`, `hazard_id`, `hazard_name`, `metric`, `value`, `unit`, `status`, `source_ref` and uncertainty/coverage where supplied. `status` distinguishes measured, modeled, unavailable, not applicable and unreviewed. Missing is never zero. Rank only comparable, supported climate-hazard measures. Document inclusion/exclusion (for example, earthquake is not a climate hazard), sort direction, ties and coverage. Do not pad two/three source hazards into a purported top five.

For regional/national top five, choose a defensible aggregation of the same measure. Do not average ordinal ranks or sum normalized composite scores as dollars. State whether the figure describes total EAL, affected Nations, or another metric. Keep a count of contributing Nations and the covered denominator next to each chart. Different metric views may be useful only when their difference is explained.

The owner explicitly confirms that **scanner aggregated costs are required and available**. Locate and reuse the existing economic aggregation path and cached source inputs. A source packet renderer withholding per-Nation allocation does not forbid a valid national or regional aggregate. Keep the distinction between source aggregate costs and unsupported allocation of those totals to individual Nations. Do not use old handoff language as an automatic block on this deliverable.

Cost rows require `metric`, `amount`, `currency`, `price_year`, `period_start`, `period_end`, `geography`, `scope`, `method`, `source_ref` and any uncertainty. Expected Annual Loss is an annualized expectation, not a forecast of next year's loss, total historical damage or a funding need. Keep EAL, historical event loss and projected costs separate. Do not sum the same event across overlapping geographies or add components already included in a total. Verify the actual scanner tests/formulas for cache normalization and aggregation. Use public national disaster cost figures only as explicitly labeled context.

The current dashboard is not by itself enough: its `top_hazards` fields contain only two or three entries. Inspect the underlying per-hazard fields for the requested five without running a full model pipeline. The 575-Nation risk cohort and legacy 592-file award/economic caches require an explicit ID and duplicate reconciliation. Neither file count nor an equal-looking name proves a matched record.

## Funding and eligibility

Separate datasets and UI labels for:

1. **Recorded awards/obligations:** award ID, recipient identity/match evidence, period, amount, source and retrieval date. Deduplicate transactions/awards using the source semantics; account for negative adjustments and shared/consortium awards. Do not imply these are unspent balances.
2. **Program opportunity/envelope:** program and notice IDs, published budget, dates, status and official link. A program total is not a Tribal award total.
3. **Eligibility information:** exact published criteria, eligible applicant classes, geography, requirements and deadline as of a verified date. Candidate matches remain preliminary and require program review. Do not turn a past award or geographic overlap into a legal eligibility conclusion.

Archived program lists can establish historical context. They cannot establish currently open funding. Verify current official notices during the build or visibly mark freshness unavailable.

## Nationwide public-plan discovery

The owner requests a **full Nation sweep**, using `gpt-6-luna` agents with `high` reasoning, for climate adaptation/action plans (CCAP), climate vulnerability assessments and hazard management/mitigation plans. Plan-assessor's existing 67-Tribe roster and imported historical material are useful seeds, not the coverage denominator. The future build must assign and record a search outcome for every Nation in the pinned national roster.

Use the scanner's verified 575-Nation reference cohort as the canonical reproducible baseline, with its exact snapshot identity. Before claiming current nationwide coverage, compare it to the current authoritative federal-recognition roster. Preserve the baseline and handle additions, removals or renamed entities in a separately documented reconciliation; assign searches for any current additions rather than silently excluding them or overwriting history. Use the baseline's sorted stable-ID manifest with 23 batches of 25; extra reconciled Nations receive explicit supplemental assignments within the approximate 30-task ceiling.

For each Nation, seed from existing plan-assessor public candidates, then search official Tribal pages, agency plan catalogs and public repositories. Use aliases and the three requested document classes. Distinguish Tribal plans from county/state plans merely mentioning the Tribe. State/multi-jurisdictional plans qualify for a relationship only with explicit participation/coverage evidence. Record that relationship type. Limit each initial search to a small fixed query budget (default four focused queries per Nation), then use bounded follow-up on promising records. Log exhausted budgets and unavailable sources instead of inventing negative results. A full sweep means every Nation was processed, not that all public documents have been found.

Capture one `nation_search` record per Nation:

- `tribe_id`, `display_name`, `batch_id`, `searched_at`, `search_terms`, `source_domains`, `search_budget_used`, `outcome`, `candidate_ids`, `limitations`.
- A separate search completion/outcome and receipt for **each** of the three requested document classes. Finding a hazard plan does not complete adaptation-plan or vulnerability-assessment discovery. Derive overall search completion only after all classes have a recorded completed outcome; retain partial/blocked classes.
- `outcome`: `found`, `no_matching_public_document_located`, `blocked`, `not_searched`. Add `partially_searched` where a run ends before all planned queries complete.

Capture one public candidate record per located source:

- Stable local ID, Nation ID(s), original title, issuing body, document class, canonical landing-page URL, document URL, explicit relationship evidence and its page/section.
- Publication year, adoption date, update year and plan period as distinct nullable fields; include date basis and evidence. Do not use retrieval date, PDF file metadata or HTTP Last-Modified as adoption date.
- Source access date, access outcome, MIME type if observed, redistribution terms/status, review state, dedup relation and source confidence. A hash is populated only when bytes were lawfully accessed; no pretend hashes.
- Short factual discovery note and access instructions for a future document pass. Avoid personal contact information and full extracted document text.

Retain raw search receipts and redirects in `work/discovery/`; sanitize public metadata into `site/data/`. Store the reusable metadata sidecar under `data/plan-discovery/` for later plan-assessor import. Build no importer into the source repo in this task. Existing `pnw_library.add_candidate` semantics can inform a mapping note, but do not claim the sidecar is natively importable until validated. No speculative mass downloads: later access can follow verified metadata and terms.

Count reviewed unique editions and distinct Nations separately. Exact duplicate bytes/URLs can consolidate source entries while retaining citations; unresolved family/edition duplication stays visible. Date bins should use a stated snapshot date, for example 0–5 years, 6–10 years, over 10 years and unknown; choose adoption/publication priority explicitly. Plan type bars must say whether multi-type plans are counted more than once. Show search coverage and unknown-date counts.

## Risk/plan join and priority

Join only stable crosswalked IDs. Classify independently: supported risk level, public plan located/accessed status by document class, recency, date uncertainty and search completeness. Use a visible high-risk threshold from a defined source measure. Prioritize follow-up for high supported risk plus no matching public plan located **after that Nation's assigned searches for the relevant classes are complete**. Exclude unsearched/blocked classes from a definitive gap count and surface them as outstanding search work. An older HMP does not stand in for an unsearched CCAP or vulnerability assessment. This is an outreach/research aid, not a judgment of a Nation's capacity or planning.

## Scenarios and recent observations

Keep CMIP generation, pathway, model ensemble, variable, baseline, units, geographic scope, time window and quantile explicit. Plan scenario-use statistics require plan/page evidence. The animation may be a labeled conceptual teaching illustration when no comparable numeric series is available; fabricated numeric curves are not acceptable. SSP2-4.5/SSP3-7.0 are the owner's selected demonstration pathways, not inferred probability limits.

Use primary sources and a claim/source ledger for five-year heat and disaster-cost context. Verify common units and inflation basis. Disaster losses also reflect exposure and vulnerability; the cost series alone does not measure climate-change causation. Stop a stale series at its actual end, and label any partial year. No annual ENSO observation should be described as a long-term climate projection.

## Report/public artifact validation

Focused checks must establish duplicate handling, missing versus zero, tie ordering, cost reconciliation, cohort/region totals, plan/date counts, join statuses and source traceability using small real-schema or synthetic fixtures. Validate that every displayed figure can be traced to an input and method, every QR decodes to the visible HTTPS link, and no local path, vault, private corpus, secret or participant note enters `site/`. Required cautions travel with both charts and downloaded reports.
