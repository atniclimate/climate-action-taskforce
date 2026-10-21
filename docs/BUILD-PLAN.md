# Autonomous implementation plan

## Working shape

Use buildless HTML/CSS/JavaScript in `site/` unless a demonstrated need requires something larger. Local Python/Node scripts can prepare snapshots and reports. Reuse the existing design tokens, fonts, scanner aggregate functions and plan-assessor metadata conventions; do not copy whole application stacks. The final artifact needs no server, key, LLM call or scanner installation.

Before editing, list affected entry points, data, assets and tests. Keep the original deck/literature and sibling repositories unchanged. Record meaningful decisions and verification once in `docs/STATUS.md`; do not create competing plans or per-edit ledgers.

Suggested concrete paths, created when their work begins:

| Path | Responsibility |
| --- | --- |
| `site/index.html`, `site/styles.css`, `site/app.js` | Accessible presentation shell, chapters and navigation |
| `site/chapters/` | Separate content modules only if needed to give writers disjoint ownership |
| `site/assets/` | Fonts/licenses, approved marks, QR SVGs and screenshot assets |
| `site/data/` | Sanitized frozen assessment JSON, public sources and status metadata |
| `site/literature/` | Deliberate copies of source PDFs and generated participant downloads |
| `data/plan-discovery/` | Canonical roster manifest, batch manifests, reviewed public metadata sidecar |
| `scripts/` | Small extraction/report/public-artifact validation scripts |
| `tests/` | Focused fixtures and checks for data transformations and UI state |
| `literature/` | Source literature and generated report originals |
| `work/` | Ignored captures, read-only-source receipts and intermediate extracts |

## Roles and model selection

Use supported native collaboration tools. Requested models are intent, not evidence that a runtime has switched. Record the actual assigned model when available. Do not edit global configuration or restart active clients to satisfy a role.

| Role | Requested model/effort | Scope |
| --- | --- | --- |
| Orchestrator/integrator | `gpt-6-astra`, `ultra` | Own status, narrative/data decisions, integration and completion |
| National discovery workers | `gpt-6-luna`, `high` | Bounded public searches and structured metadata, no architecture or factual invention |
| Source/file/asset microtasks | `gpt-6-luna`, `high` | Locate exact sources, verify links/QRs, small repeatable extraction |
| UI and deterministic data implementation | `gpt-6.1-sol`, `high` | Build disjoint modules and focused tests |
| Cost methodology / difficult joins | `gpt-6-astra`, `high` or `ultra` for unresolved reasoning | Trace definitions, deduplication and reconciliation |
| Cooperative synthesis | `gpt-6-astra`, `high` | Find a simpler complete solution and missing integration steps |
| Adversarial check | `gpt-6-astra`, `high` | Challenge denominators, scientific claims, misleading status and exposure |

The owner has confirmed Luna for the discovery swarm; no further model-choice confirmation is needed. The preparation runtime exposes `gpt-6-luna` and has four total concurrency slots. Use native collaboration in waves up to the actual cap; do not claim 30 simultaneous workers. Preserve home isolation and serialization. Reuse idle agents and their specific context.

## Preassigned work

The 575-Nation roster yields 23 discovery assignments. Together with the seven work packages below, that gives up to 30 bounded assignments for the main build. Reviewer roles can be assigned to reused agents when the corresponding integrated result exists; the count is a planning ceiling, not a requirement to spawn unnecessary agents.

### D01–D23: national public-plan discovery

Input: prepared `data/plan-discovery/roster.json`, `manifest.json` and `batches/Dxx.assignment.json`, sorted by `tribe_id`, 25 Nations per batch; relevant existing public candidate metadata and `docs/DATA-CONTRACTS.md`. Each task owns only a new `data/plan-discovery/batches/Dxx.results.json` and `work/discovery/Dxx/`. Keep assignments immutable; the orchestrator owns the shared roster, manifest and merged dataset. Track execution outcomes in the result files rather than overwriting the prepared assignment state.

Use official Tribal websites first, followed by official government catalogs and reliable public repositories. Search CCAP/climate adaptation/action plans, climate vulnerability assessments and hazard mitigation/management plans. Capture public metadata, verifiable Nation-document relationship, URLs, dates and search outcomes. Do not collect private records, send messages, download a full corpus, make legal conclusions or write to plan-assessor. Return counts, uncertain matches, blocked sources and the owned file. Preserve partial results if an external source fails. Every assigned Nation must receive a record, including no-match or blocked outcomes.

### W01: presentation shell and design

Model: Sol high. Own `site/index.html`, `site/styles.css`, `site/app.js` and navigation-focused checks. Read the deck/design discovery and source tokens. Build presenter/participant views, hash/deep-link navigation, chapter menu, keyboard operation, responsive layout, focus visibility and reduced motion. Establish content interfaces before parallel chapter work. No dependencies just for slide transitions.

### W02: scanner assessment and costs

Model: Astra high, escalate unresolved aggregation reasoning to ultra. Own `scripts/prepare-risk-data.*`, `site/data/risk*`, `site/data/funding*` and their focused tests. Read source manifests and the exact existing regional EAL aggregation. Generate the requested national/regional aggregates, up-to-five hazard rows and funding context from cached inputs. Verify cost definitions and 575/592 reconciliation. Inspect actual code/tests before assuming old restrictions apply. Do not execute a full scanner run. Leave precise missingness where an input cannot support a figure.

### W03: plan merge, recency and risk join

Model: Sol high after D batches are available. Own merge/validation scripts, reviewed metadata sidecar, `site/data/plans*` and focused tests. Check every roster ID is accounted for, merge duplicate candidates/editions carefully, retain review and date uncertainty, and produce national/region recency views. Coordinate W02's risk ID/metric contract before priority joins. Sidecar output supports a later plan-assessor access pass; no upstream importer is in scope.

### W04: CATF narrative and climate evidence

Model: Astra high for claims, Luna high for citation microtasks. Own strategy/knowledge/priority/scenario/development chapter content and `site/data/sources*`. Read source deck and legacy literature. Use current primary evidence for climate claims. Build the conceptual scenario comparison only after choosing whether real comparable numeric series exist. Label the selected SSP pair as a demonstration. Integrate the new metadata sweep's actual coverage, not historical catalog counts, into participant language.

### W05: tool demos and resource assets

Model: Sol high, Luna high for link/QR microtasks. Own policy/DDM/TSDF chapter modules and `site/assets/` excluding shared design tokens owned by W01. Create a deterministic pauseable walkthrough with permitted captured or synthetic content; real export unnecessary. Use `NCAI2026` as the owner-provided participant code, with the actual verified NCAI menu flow. Preserve TSDF version and domain-language distinctions. Generate QR codes locally and decode-verify their targets; do not use a tracking QR service.

### W06: simple reports

Model: Sol high, with PDF/document skills as applicable. Own report-generation scripts and `literature/` new outputs, then intentional copies to `site/literature/`. Consume W02/W03 finalized data. Produce per-Nation supported hazard tables plus separately defined regional/national risk and cost summaries, and plan metadata reports, in HTML/CSV and a legible PDF. Include a per-Nation monetary measure only when its underlying source supports that allocation and meaning. Retain caveats, definitions, citations and source versions. Render the PDF and inspect representative pages plus wide/long tables. No full packet engine or elaborate document theme.

### W07: integration and bounded review

Orchestrator owns integration; assign distinct cooperative and adversarial reviews to reused agents when needed. Review the complete presentation for evidence, figures, sovereignty language, accessibility and usability. Each reviewer returns concrete defects with path, evidence, severity and smallest correction. Fix real findings once; no repeated broad review loop. Validate the final public artifact and prepare relative-path, `site/`-only GitHub Pages packaging locally. Defer only target-specific settings and publication until the target/action is authorized.

Every writing assignment includes: **You are not alone in the codebase. Own only these paths; preserve other edits and adapt to shared contracts. Do not stage, commit, publish, modify source repositories or spawn nested writers without orchestration.** Readers may inspect dependencies but must report overlapping ownership before editing.

## Execution order

1. Read current status and verify referenced snapshots/roster; reuse unchanged discovery. Use the owner-authorized Luna high discovery assignments. Establish the site shell, data field contract and source/claim list.
2. Start discovery waves and risk extraction. In parallel, build strategy content, tool demonstrations and licensed assets. Show the first local presentation once coherent; do not call it finished.
3. Merge metadata incrementally after validating each batch. Generate final plan statistics only with the completed roster outcome manifest. Add risks/funding/costs, regional comparisons and priority joins.
4. Generate reports from the same finalized JSON used by the charts. Integrate, perform focused checks and one full presentation walkthrough at desktop/projector and phone widths.
5. Fix observed issues. Update status with precise source versions, dataset/roster hashes, checks, unresolved evidence and the continuing checkout. Prepare a concrete deployment artifact; request only the exact missing publication action if the user wants to publish and it has not already been authorized.

## Evidence proportional to the work

- Preparation: Markdown local links, required files, whitespace/diff, source reference existence and no unintended source mutations.
- Data: tiny tests for missingness, duplicate IDs/editions, cost totals, risk ties, dates and unmatched joins; aggregate totals reconcile to inputs.
- UI: targeted navigation/region-toggle/walkthrough tests and manual keyboard verification. Inspect screenshots at projector/desktop and phone sizes, including reduced motion and large text.
- Final local boundary: every slide/chapter, links/downloads/QR targets, public data allowlist, no console-breaking errors, relevant automated accessibility checks, and actual report visual inspection. State the integration reason before any expensive run. No repeated sibling full suites.

## Current documentation basis

The prompt's explicit persistence, bounded delegation and proportional checks reflect the fetched [GPT-6 Astra prompting guidance](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#prompting-best-practices). Model roles are task-specific choices, not claims of universal model superiority. [Codex subagent guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents#reasoning-effort-model_reasoning_effort) requires a reasoning setting supported by the selected model/client. Preserve requested Astra ultra; disclose unavailability rather than replacing it.
