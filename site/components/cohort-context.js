import { esc, number, money } from '../chapters/shared.js';

export function mountCohortContext(element, { catalog, store }) {
  element.classList.add('cohort-context');
  element.innerHTML = `<label class="field">County context for a story<select data-cohort>${catalog.cohorts.map(row => `<option value="${esc(row.id)}">${esc(row.label)}</option>`).join('')}</select></label><div data-cohort-result aria-live="polite"></div>`;
  const select = element.querySelector('select'), result = element.querySelector('[data-cohort-result]');
  const update = () => {
    const cohort = catalog.cohorts.find(row => row.id === select.value) || catalog.cohorts[0];
    const cost = cohort.costs, rows = cost.county_top_hazards, max = Math.max(1, ...rows.map(row => row.value || 0));
    result.innerHTML = `<div class="cohort-comparison"><div><div class="stat-band"><div class="stat"><strong>${money(cost.climate_county_eal)}</strong><span>Annual climate-sensitive loss model · USD/year</span></div><div class="stat"><strong>${number(cost.county_count)} / ${number(cost.expected_counties)}</strong><span>Intersecting counties with NRI rows, counted once</span></div></div><p class="notice">Whole-county assets and residents. <strong>Not Tribal loss or funding need.</strong></p></div><div class="cohort-bars"><h2>Largest components · USD/year</h2>${rows.map(row => `<p><span>${esc(row.hazard_name)}</span><strong>${money(row.value)}</strong><i style="width:${(row.value || 0) / max * 100}%" aria-hidden="true"></i></p>`).join('')}</div></div><p class="caption">FEMA NRI December 2025 v1.20 · annual model expectation · common dollar price year unavailable. Story footprints overlap; do not add their totals.</p><details><summary>County coverage and membership rule</summary><p>${esc(cohort.rule)} ${esc(cohort.scope)}</p><p>${cohort.tribe_ids.length} associated Nation identities; ${cohort.area_ids.length} distinct source areas. These are separate denominators.</p><p>Unmatched county FIPS: ${cost.unmatched_county_fips.length ? cost.unmatched_county_fips.map(esc).join(', ') : 'None'}.</p><ul>${rows.map(row => `<li>${esc(row.hazard_name)}: ${row.contributing_counties} of ${row.denominator} county values available.</li>`).join('')}</ul></details><p class="cohort-actions"><a href="literature/cohort-costs.csv" download>Download county context</a> · <a href="#risks/place">Explore this story on the map →</a></p>`;
  };
  select.value = store.get().selection.story || catalog.cohorts[0].id;
  select.onchange = () => { const row = catalog.cohorts.find(item => item.id === select.value); store.set({ story: row.id, place: row.default_place, area: row.default_area, family: 'native-nex', baseline: '1995-2014' }); update(); };
  const unsubscribe = store.subscribe(({ selection }) => { if (selection.story) select.value = selection.story; update(); });
  update();
  return () => { unsubscribe(); select.onchange = null; };
}
