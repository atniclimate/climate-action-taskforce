# Source notes for the implementation

This file preserves only evidence needed to avoid repeating preparation research. Detailed local paths and findings are in `docs/discovery/`. Recheck freshness for live application state, funding and new climate claims during implementation.

## Public scientific sources

- [WMO State of the Global Climate 2025](https://wmo.int/publication-series/state-of-global-climate/state-of-global-climate-2025), published 2026-03-23, successfully read during preparation. It identifies 2015–2025 as the hottest eleven years on record, with 2025 second or third depending on dataset. Use the report's actual series and definitions for any five-year plot. Do not manufacture a 2026 full-year observation.
- [U.S. Climate Resilience Toolkit: Billion-Dollar Weather and Climate Disasters](https://toolkit.climate.gov/tool/billion-dollar-weather-and-climate-disasters), successfully read during preparation. It describes NCEI coverage from 1980 through 2024. Do not extend that source's series into 2025/2026 or describe it as complete disaster losses.
- [IPCC AR6 Working Group I Summary for Policymakers](https://www.ipcc.ch/report/ar6/wg1/chapter/summary-for-policymakers/) and [Chapter 1](https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-1/) are primary sources for scenario definitions. Search results were located, but direct chapter retrieval returned HTTP 403 in preparation. Read an accessible official PDF/HTML before final claims or chart reproduction. Selected SSP scenarios are conditional pathways; the plan does not treat CMIP5 as universally invalid.

## TSDF and tool links

The supplied [ATNI Resolution 2026-034](https://atnitribes.org/wp-content/uploads/2026/09/20260917_26-34_TIERED%20SOVEREIGN%20DATA%20FRAMEWORK.pdf) initially failed through web retrieval, then succeeded via one bounded direct HTTP fetch. It is the adoption/authorization resolution, **not the full v1.0 standard**. The retained copy is `work/tools/resolution-26-34.pdf`. It authorizes v1.0 and leaves adoption voluntary for individual Tribes.

Canonical [TSDF repository](https://github.com/atniclimate/TieredSovereignDataFramework) and [framework website](https://atniclimate.github.io/TieredSovereignDataFramework/) are identified in the local standard/source evidence. Local v0.9.8 text supports four named domains, AI/ML protections and CC BY-NC-SA 4.0. The owner's statement that v1.0 language is unchanged is retained as owner context; the complete v1.0 standard was not compared.

[Policy Sentinel](https://atniclimate.github.io/policy-sentinel/) and [DDM](https://atniclimate.github.io/dynamic-drought-module/) web fetches failed through the web retrieval tool. Local source discovery establishes implementation paths, not present live uptime. The future walkthrough should work from approved capture/synthetic content even if those services are unavailable.

## Model-specific preparation

The actual [GPT-6 Astra prompting guidance](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#prompting-best-practices) and [Codex subagent effort guidance](https://learn.chatgpt.com/docs/agent-configuration/subagents#reasoning-effort-model_reasoning_effort) were fetched. The launch prompt makes autonomy, delegation and proportional verification explicit. Requested role settings are not a claim that runtime capacity or model selection has changed.
