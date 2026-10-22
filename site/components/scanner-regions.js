import { dataset, esc, number } from '../chapters/shared.js';
import { rangePlot } from './pathway-chart.js';

export function regionalClimateRows(region, metric, period) {
  return [['ssp245','SSP2-4.5'],['ssp370','SSP3-7.0']].map(([id,label])=>{
    const value=region.projections?.find(row=>row.metric_id===metric&&row.scenario===id&&row.period.join('-')===period);
    return {place:region.region_name,pathway:label,pathway_id:id,unit:value?.unit||'',median:value?.change.p50??null,
      lower:value?.change.p10??null,upper:value?.change.p90??null,status:region.missing_reason||region.status,
      projection:value};
  });
}

export function regionalRiskTable(region) {
  const score=value=>Number.isFinite(value)?value.toFixed(3):'Unavailable';
  const rows=(region?.temporal||[]).filter(row=>row.scenario==='ssp370'&&(row.horizon==='baseline'||row.horizon==='2080'));
  const coverage=region?.hazard_statuses||[];
  const support=`<details><summary>Hazard coverage and regional gaps</summary><ul>${coverage.map(row=>`<li>${esc(row.hazard_name)}: ${number(row.contributing_nations)} of ${number(row.denominator)} supported · ${Object.entries(row.status_counts).map(([status,count])=>`${esc(status)}: ${number(count)}`).join('; ')}</li>`).join('')}</ul><p>Contributor count does not mean every hazard is supported. In Alaska, sea ice, subsistence and access pathways are additional unresolved evidence gaps. Sea-level rise, coastal erosion and permafrost have no supported scores here. Forward support means at least one disclosed factor, not every hazard.</p></details>`;
  return `<h3>Whole-Nation physical screening scores</h3><p>Descriptive medians and interquartile ranges across associated Nations. These are not regional probability bands or a risk estimate for the entire region.</p><div class="table-scroll" tabindex="0"><table><caption>Risk screening uses Nation contributors, independently of climate source areas</caption><thead><tr><th scope="col">Horizon</th><th scope="col">Contributors / missing</th><th scope="col">Median</th><th scope="col">p25–p75</th></tr></thead><tbody>${rows.map(row=>`<tr><th scope="row">${esc(row.horizon)}${row.horizon==='baseline'?'':' · SSP3-7.0'}</th><td>${number(row.support.n_supported)} / ${number(row.support.n_missing)}</td><td>${score(row.physical_score.median)}</td><td>${score(row.physical_score.p25)}–${score(row.physical_score.p75)}</td></tr>`).join('')}</tbody></table></div><p class="caption">Future screening support is limited to disclosed 2080/SSP3-7.0 factors. Other future cells have no verified support for this summary. Frozen composites retain source placeholder assumptions. Overlapping regional memberships cannot be added into a national total.</p>${support}`;
}

export function mountScannerRegions(element,{catalog,loadAsset}) {
  const index=catalog.scanner_climate;
  if(!index)throw new Error('Accepted regional export is unavailable.');
  element.classList.add('pathway-explorer');
  element.innerHTML=`<h2>Regional climate and screening evidence</h2><div class="pathway-controls"><label>Regional taxonomy<select data-taxonomy><option value="ecoregions">EPA/CEC Level III 2010</option><option value="advocacy_regions">Scanner advocacy groups</option></select></label><label>Region or source category<select data-scanner-region></select></label><label>Climate metric<select data-scanner-metric><option value="temp_mean">Annual mean temperature</option><option value="pr_annual">Mean annual precipitation total</option></select></label><label>Climate window<select data-scanner-period>${catalog.periods.map(row=>`<option value="${esc(row.id)}">${esc(row.label)}</option>`).join('')}</select></label></div><div data-scanner-result aria-live="polite"></div>`;
  const taxonomy=element.querySelector('[data-taxonomy]'),select=element.querySelector('[data-scanner-region]'),metric=element.querySelector('[data-scanner-metric]'),period=element.querySelector('[data-scanner-period]'),result=element.querySelector('[data-scanner-result]');
  let revision=0,controller;
  const options=()=>{select.innerHTML=index[taxonomy.value].map(row=>`<option value="${esc(row.region_id)}">${esc(row.region_name)}${row.category==='water'?' · Water category':''}</option>`).join('');select.value=index[taxonomy.value].find(row=>row.region_id==='10.1.2')?.region_id||index[taxonomy.value][0].region_id;};
  const update=async()=>{
    controller?.abort();controller=new AbortController();const current=++revision;
    const descriptor=index[taxonomy.value].find(row=>row.region_id===select.value);
    result.innerHTML='<p role="status">Loading accepted regional evidence…</p>';
    try{
      const [region,risk]=await Promise.all([loadAsset(catalog,descriptor.file,{signal:controller.signal}),dataset('risk')]);
      if(current!==revision)return;
      const rows=regionalClimateRows(region,metric.value,period.value),counts=region.counts;
      result.innerHTML=`<h3>${esc(region.region_name)}</h3><p class="pathway-scope">${esc(taxonomy.options[taxonomy.selectedIndex].text)} · ${esc(period.value)} minus 1995–2014 · ${metric.value==='pr_annual'?'mm, mean annual total':'°C, annual mean'}</p><p>${number(counts.climate_supported_nations)} supported Nations of ${number(counts.nations)}; ${number(counts.distinct_source_areas)} unique climate source areas; ${number(counts.proxy_nations)} proxy mappings. Shared areas are counted once.</p><p class="notice">${descriptor.category==='water'?'Water is a separate source category, not a terrestrial ecoregion. ':''}This climate summary describes associated source areas with data, not the climate of the entire region.</p><figure><figcaption>${rows.some(row=>row.projection)?'Paired-model change: points show the median; bands show p10–p90 across eight included models. Model spread is not a probability interval.':'No supported climate source areas in this cohort. No model range is shown.'}</figcaption>${rangePlot(rows)}</figure><details><summary>Absolute levels, model span and sources</summary><div class="table-scroll" tabindex="0"><table><caption>Baseline and period levels are separate from same-model changes</caption><thead><tr><th scope="col">Pathway</th><th scope="col">Baseline median</th><th scope="col">Period median</th><th scope="col">Change min–max</th><th scope="col">Models</th></tr></thead><tbody>${rows.map(row=>`<tr><th scope="row">${row.pathway}</th><td>${number(row.projection?.baseline_level.p50)}</td><td>${number(row.projection?.period_level.p50)}</td><td>${number(row.projection?.change.min)}–${number(row.projection?.change.max)}</td><td>${number(row.projection?.model_count)}</td></tr>`).join('')}</tbody></table></div><p>Equal weight for each unique source area within each model, then type 7 model quantiles. No averaging of area quantiles. Native Resilience / NASA NEX-GDDP-CMIP6 v2.0, annual metric version 1, CC0-1.0. Model identities are retained where support exists; empty cohorts retain absence. Scenario probabilities, realization IDs and calendars are not supplied.</p><p><a href="${esc(catalog.files[descriptor.file].path)}" download>Download this regional summary and support</a> · <a href="${esc(catalog.files[index.csv_file].path)}" download>Download all accepted climate windows (CSV)</a></p></details>${regionalRiskTable(risk[taxonomy.value]?.regions.find(row=>row.region_id===region.region_id))}<p class="caption">Annual temperature and precipitation do not quantify hazard events or economic losses. County loss context is shown separately in Costs.</p>`;
    }catch(error){if(current===revision&&error.name!=='AbortError')result.innerHTML=`<p class="notice" role="alert">${esc(error.message)}</p><button data-scanner-retry>Retry regional evidence</button>`;}
  };
  taxonomy.onchange=()=>{options();update();};select.onchange=metric.onchange=period.onchange=update;
  element.onclick=event=>{if(event.target.closest('[data-scanner-retry]'))update();};
  options();period.value='2040-2059';update();
  return()=>{++revision;controller?.abort();taxonomy.onchange=select.onchange=metric.onchange=period.onchange=element.onclick=null;};
}
