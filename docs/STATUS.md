# Current status

## Presenter no-scroll deck (2026-10-21, owner edits round 2)

**Supersedes the slide-structure parts of the pass below.**
- **31 presenter slides, 18 chapters, nothing scrolls.**
  - The structure follows the Codex review:
    `C:\dev\_reviews\climate-action-taskforce\2026-10-21_presenter-scroll-review.md`.
  - A chapter may declare `slides:[{id,title,blocks}]`, and `render()` marks
    those blocks with `data-block`.
  - Presenter view shows only the current slide's blocks. Unlisted top-level
    content is participant detail.
  - Deep links use `#chapter/slide`. The footer counts slides, and the eyebrow
    shows "Slide title · 2 of 3".
  - Any slide change pauses walkthroughs.
  - Participant view keeps every detail. The only presenter-only element is the
    risk summary strip.
- **Owner edits applied.**
  - Removed the top-right number and source label, and the photo captions.
  - Wider desktop measure, so short text stays on one line.
  - A shared interactive color (`--interactive`), chevron disclosures and an
    aligned filter toggle.
  - Single-digit ordinals.
  - ATNI Climate logo at the bottom right.
  - TSDF chapter rewritten from the public framework site, with a locally
    redrawn tier-ring diagram. It is attributed in the slide and in
    `sources.json` (claim added in `scripts/prepare_sources.py`).
- **Files.** Chapter layouts live in `site/chapters/{narrative,assessment,planning,tools}.css`.
  Four agents built them, with disjoint file ownership.
- **Checks, 2026-10-21, after integration.**
  - `node tests/presenter-fit.mjs` (new) passed 93/93: every slide and every
    walkthrough step fits at 1366×768, 1440×800 and 1920×970, with 0 page problems.
  - The navigation tests now cover deck, hash and fallback cases. Source-fidelity,
    assessment-view and policy-walkthrough tests pass, as does `validate_public.py`
    (54 files).
  - In Chrome: 31 keyboard steps with no console errors. A participant scroll
    revealed 107/107 blocks with no horizontal overflow.
- **Open data question for the owner.** Some
  `site/data/plans.json` `relationships[].evidence` strings cite internal work
  references (for example `work/discovery/D11/...` receipts and catalog hashes).
  They predate this round, and were not edited because the data is frozen.
  Stripping them needs a data-extraction rerun.
- **Not verified:**
  - A real projector, or Safari/Firefox.
  - A screen reader.
  - Presenter view below 1050px wide.
  - QR scans from a phone.

## Second visual pass (2026-10-21, Codex revision + Opus final pass)

**This supersedes the "fresh rendered review is still needed" note below.**
1. Codex `gpt-6-astra`/ultra ran an adversarial critique and the first design
   revision. Changes include a type scale (18px body, 16px notes, 44px titles,
   tabular figures); alphabetical index tables instead of cross-hazard bars;
   frequency as the default risk view; labeled axes; a shared planning count
   scale; and captions on every chart, table and metric (pf-voice).
   The Policy Sentinel walkthrough now has a labeled pane selector on phones,
   and source slide 3 uses subgrid alignment. Report:
   `C:\dev\_reviews\climate-action-taskforce\2026-10-21_design-revision-1.md`.
2. Opus final pass (labeled block at the end of `site/styles.css`, plus
   `site/app.js`):
   - Full-width photo bands with a scrim, and a floated photo caption.
   - Counters and axes in display/body faces, no longer monospace.
   - Readable footer counter on dark chapters.
   - Source slides 1–3 vertically centered in presenter view at desktop size.
   - Motion: crossfade view transitions between presenter chapters, a staggered
     rise that follows the navigation direction, and a slow photo settle.
   - Sequence nodes and connectors draw in order, and bars grow from their
     baseline.
   - Participant view reveals each block on scroll. Revealing a block also
     reveals everything above it, so content is never left hidden.
   - Animated menu dialog, disclosures and walkthrough panes, plus hover cues.
   - All motion is gated on `prefers-reduced-motion: no-preference`. The print
     stylesheet forces revealed content.
3. Checks, 2026-10-21, after the final edits. Four focused node tests and
   `node --check` passed, and `scripts/validate_public.py` passed (50 files).
   A live Chrome review covered 1440px, the maximum window (about 1516px
   logical) and 390px iframes. All 18 presenter chapters were stepped with
   rapid keys with zero console errors. A participant full scroll revealed
   93/93 blocks with no horizontal overflow.
4. Not verified: a real 1920×1080 projector, OS reduced-motion toggling,
   Safari/Firefox, a screen reader, phone-camera QR scans.
5. Codex's screenshots and headless profile moved to
   `work/review/design-review-artifacts/`, which is ignored.
6. No commit, push or publication.

## Visual revision and Opus handoff

The owner-requested local design changes and fresh-session handoff are saved in
`docs/OPUS-5-5-HANDOFF.md` (2026-10-21). Start there for the next visual pass.
Smaller generated titles, aligned sequence headings, a single gradient menu,
four photographic backgrounds, a mean/frequency risk chart switch, a four-pane
Policy Sentinel illustration, TSDF domain disclosures and compact QR surrounds
are implemented. Source slides 1–3 retain their wording and emphasis.

Focused assessment, six-step Policy walkthrough, navigation and source-fidelity
checks pass. Public validation covers 50 files (21,838,941 bytes), and all 50
preview URLs return their expected sizes; private workspace paths return 404.
Frozen data, reports and discovery receipts remain unchanged. Original photos
are untouched; four metadata-checked copies are public, with exclusions recorded
in `work/review/scene-assets.json`. The unused large sunset copy stays in work/.

**A fresh rendered review is still needed.** The browser connection was
unavailable and the browser inventory empty during this revision. Earlier
browser evidence below applies to the prior layout. Opus should first inspect
desktop/projector/phone balance, 200% zoom, text-spacing overrides, photo scrims,
all Policy states, chart interpretation and QR scanning. Detailed typography and
frontend-design skill findings are in `docs/discovery/SECOND-PASS-TYPOGRAPHY.md`.
No publication, Git mutation, external-service change or new model launch occurred.

## Original implementation baseline

Updated 2026-10-21. **The full local implementation, nationwide metadata sweep,
frozen datasets, reports and focused verification are complete and reviewable.**
The final participant-navigation correction passed its regression and phone check. The preparation
stage is superseded; do not reinitialize, rerun discovery or restart source pipelines.
No commit, remote creation, push, publication or external-service change is authorized.

## Local deliverable

- Presenter preview: <http://127.0.0.1:8765/?mode=presenter#welcome>.
- Participant preview: <http://127.0.0.1:8765/?mode=participant#welcome>.
- Only `site/` is served. It is a buildless, GitHub Pages-ready artifact with
  relative links and `.nojekyll`. The preview is bound to `127.0.0.1`.
- Eighteen chapters cover CATF mission, strategy and sequence; knowledge gathering;
  national/regional/Nation risks; supported aggregate costs; funding and dated
  opportunities; planning coverage and follow-up; scenario demonstration; recent
  warming/disasters; local discussion notes; Policy Sentinel; DDM; TSDF; continued
  development; and resources. The original 13-slide deck identity and source map
  remain explicit. Stages 3–6 remain identified as not implemented.
- Participant exploration includes region/Nation and planning filters, independent
  document-class outcomes, missing-data detail, deterministic manual/playable
  walkthroughs, keyboard navigation, responsive layout and local-only notes.
  No backend, analytics, accounts or shared submissions were introduced.

## Final owner-directed design

- Source slides 1–3 preserve their wording, composition, League Spartan variants,
  spacing and bold emphasis. The sole authorized wording correction replaces
  `XXXX` with **ATNI Resolution 2026-034**, linked to the verified resolution.
- Original gradient structures now use the owner's reference palette: dark green
  `#155F65`, light green `#D0E8DA`, orange `#E5885D`, sky blue `#78BAD0`.
  This supersedes the original blue/gold color requirement. Orange identifies
  current focus, not completed decisions; pending stages remain gray.
- ATNI chapters use dark ATNI reds/blacks/grays and the authentic gray Climate
  lockup. The supplied white NCAI logo replaces the invented CATF mark. No
  unfinished seal, generated logo or watermarked reference is shipped.
- Sol audits checked both the archived `ATNI_design-system` material and maintained
  `atni-design-system` repository. Thirteen copied assets pass source-hash checks.
  Google Fonts are requested with licensed local fallbacks and retained OFL notices.
- Brand, source-layout and contrast evidence: `work/review/brand-audit.md`,
  `dark-mark.md` and `source-fidelity.md`.

## Completed national discovery

- Verified pinned 575-Nation roster, reconciled names/aliases to the 30 January
  2026 federal notice including Lumbee, and preserved 23 immutable assignments
  of 25 Nations. Roster SHA-256:
  `5db8f52cf44d3a3853f8403cd6dc845a59088f07f42b40a3488575b5cbe7cece`.
- Luna/high workers executed bounded waves within four total runtime slots.
  All **1,725 Nation/class searches** have outcomes across adaptation/action plans,
  climate vulnerability assessments, and hazard management/mitigation plans.
  All 575 Nations have all three attempts completed without a blocked class.
- **323 found category outcomes; 1,402 no-public-match category outcomes.**
  **379 raw candidate records consolidate to 335 unique source URLs**, covering
  224 Nations. There are **zero reviewed unique editions**, 240 URLs of unknown
  age, and 113 high-risk Nations flagged for at least one class requiring follow-up.
- Raw search receipts and seed-catalog reconciliation are retained locally. An
  adversarial data review identified omitted candidates, seed evidence gaps,
  invalid nested timestamps and relationship loss during URL consolidation.
  Corrections are complete; the strict final merge passes. Date-only normalization
  preserves unknown timezone rather than inventing one. Original values have a
  receipt under `work/discovery/D10/`.
- Local reusable metadata: `data/plan-discovery/metadata-sidecar.json`.
  Sanitized participant projection: `site/data/plans.json`. Per-relationship
  provenance, source URLs, uncertain adoption and access status remain available.
  Public discovery does not establish that a Tribe lacks a plan. This is a bounded
  metadata search, not a document census, full harvest or substantive plan review.

## Frozen assessment decisions

- All 575 Nations have supported risk profiles: 356 provide five ranked hazards
  and 219 provide four. Missingness is not filled with zero or an invented fifth
  hazard. Indices are screening evidence, not probabilities or sovereign priorities.
- Existing scanner aggregation functions and cached inputs support national and
  regional costs. The climate-sensitive annualized county EAL is **$126.11 billion**
  across 3,232 distinct county equivalents, covering all residents, buildings and
  agriculture in those counties. It is **not a Tribal loss or funding-need estimate**.
- The scanner's **$26.70 billion** representative-place context is shown separately
  across 565 places with overlap/non-additivity caveats. The historical NCEI series
  has 403 unique events, 1980–2024, totaling **$2.918 trillion**. Neither measure
  is added to county EAL. A common cached inflation price year is unavailable.
- Historical award obligations total **$2.854 billion** across 1,851 unique
  exact-name/alias matches and 269 Nations. Five negative adjustments remain;
  ambiguous awards are excluded. FY2022–2026 describes the cache query, not annual
  spending. Current opportunity leads were checked separately on 2026-10-21.
- Presentation regions are exclusive state-derived groups, not Tribal jurisdiction,
  NCAI or BIA regions. Source versions, hashes, definitions and denominators are
  preserved in public JSON, the claim ledger and reports.
- Scanner 0.8.9 at `e5336da2f79c0e386aadb2aab7f25f041441ca15`, profile schema
  0.1.0 / formula 3.2.0, supplied the frozen inputs. Full scanner/assessor pipelines
  were not run. Original deck, supplied literature and sibling repositories remain
  unchanged. Source-state evidence is `work/source-state.json`.
- NASA 2020–2024 GISTEMP and IPCC AR6 Table SPM.1 use explicit baselines;
  SSP2-4.5/SSP3-7.0 are conditional global pathways, not local forecasts. The
  five-year window ends with the selected NOAA 2024 archive, not the current year.
- Policy Sentinel is a synthetic six-step walkthrough, with the owner-supplied
  participant code displayed. No vault contents were unlocked, copied or decrypted.
  DDM uses the owner's dated screenshot. TSDF distinguishes the supplied illustrated
  v0.9.8 from the v1.0 release authorized by ATNI Resolution 2026-034; its four
  formal domains and Indigenous Data Sovereignty theme are accurately separated.

## Reports and verification

- Eight generated files are available identically in `literature/` and
  `site/literature/`: `catf-assessment.html`, `catf-assessment.pdf` (43 pages),
  `plan-discovery.html`, `plan-discovery.pdf` (71 pages), `nation-hazards.csv`
  (5,175 rows), `regional-costs.csv`, `plan-candidates.csv` (335 rows), and
  `nation-searches.csv` (1,725 rows).
- Passed focused risk/cost/funding aggregation checks, six merge regressions,
  source-slide wording/emphasis/asset checks, JavaScript syntax and navigation
  checks. Passing unchanged evidence was reused; no unrelated/full source suites
  were launched. The final strict merge used `--require-complete`.
- Public validation passed: 50 intentional files, exact report-copy matching,
  allowed public fields, all 575 joins, complete class outcomes, relative links,
  CSV missingness/formula protection, PDF text, and no local paths or credential
  patterns. Receipt: `work/review/public-validation.json`.
- Both PDFs passed text-boundary checks on every page. Ten representative pages
  were rendered; coverage, methods, tables and source-index pages were visually
  inspected. Receipt: `work/reports/layout-check.json`.
- All 50 public URLs returned expected file lengths; three private workspace URLs
  returned 404. Receipt: `work/review/preview-http.json`. All three QR codes decode
  to their visible HTTPS destinations. Supplied asset copies are byte-identical.
- The prior-layout integrated browser review covered all 18 chapters, presenter/participant modes,
  1920×1080 and 390×844 layouts, keyboard/focus, filters, missingness, walkthrough
  controls and notes save/restore/clear. No captured script warnings/errors or
  horizontal page overflow were found. Latest palette surfaces were rechecked.
  Review: `work/review/integrated-review.md`.
- A stale IntersectionObserver entry could overwrite the active participant chapter.
  The final correction uses current viewport geometry. Its focused regression
  passed, and a fresh phone deep link retained the correct title and 14/18 counter
  before and after the responsive screenshot. Presenter navigation is unchanged.
- Browser automation timed out waiting for saved note/report download receipts.
  Valid download links and HTTP delivery were verified; a browser-saved copy is
  not claimed. Reduced-motion logic was inspected, not tested by changing the OS
  preference. This is not exhaustive browser/assistive-technology certification.

## Exact next deployment step

After the local handoff, obtain the owner's explicit authorization naming the
GitHub repository and Pages target. Then commit/push only the authorized material
and publish **the contents of `site/`**, with `index.html` at the artifact root.
Do not publish the workspace root, raw discovery receipts, source inventories or
original private working materials. No repository target has been assumed.

If the preview stops, use the README's local HTTP command through the required
Windows execution route. Reuse completed discovery and verification evidence
unless its inputs change. Do not rerun full source applications for deployment.

