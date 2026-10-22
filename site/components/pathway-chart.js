import { esc, number } from '../chapters/shared.js';

const pathways = [['ssp245', 'SSP2-4.5'], ['ssp370', 'SSP3-7.0']];
export function windowRows(area, metric, period, placeName) {
  const selected = area.metrics[metric];
  return pathways.map(([id, label]) => {
    const value = selected?.windows?.[period]?.[id];
    return { place: placeName, area: area.name, pathway: label, pathway_id: id, metric: selected?.label || metric,
      unit: selected?.unit || '', baseline: area.baseline_id, period, source: area.source?.url || '',
      status: value?.status || (Number.isFinite(value?.median) ? 'available' : 'unavailable'),
      median: value?.median ?? null, lower: value?.lower ?? null, upper: value?.upper ?? null, models: value?.models ?? null };
  });
}

export function rowsCSV(rows) {
  const keys = ['place', 'area', 'mapping_status', 'mapping_caution', 'pathway', 'metric', 'unit', 'baseline', 'period', 'year', 'status', 'median', 'lower', 'upper', 'models', 'source'];
  const cell = value => `"${(typeof value === 'string' && /^\s*[=+@\-\t\r]/.test(value) ? `'${value}` : String(value ?? '')).replaceAll('"', '""')}"`;
  return [keys.join(','), ...rows.map(row => keys.map(key => cell(row[key])).join(','))].join('\r\n');
}

export function annualRows(area, metric, period, placeName) {
  const selected = area.metrics[metric], [start, end] = period.split('-').map(Number);
  return pathways.flatMap(([id, label]) => {
    const series = selected?.series?.[id];
    if (!series) return [{ ...windowRows(area, metric, period, placeName).find(row => row.pathway_id === id), year: null }];
    return series.years.flatMap((year, i) => year < start || year > end ? [] : [{
      place: placeName, area: area.name, pathway: label, pathway_id: id, metric: selected.label,
      unit: selected.unit, baseline: area.baseline_id, period, year, source: area.source.url,
      status: Number.isFinite(series.median[i]) ? 'available' : 'unavailable',
      median: series.median[i], lower: series.lower[i], upper: series.upper[i], models: series.models ?? series.model_count,
    }]);
  });
}

export function annualPlot(rows) {
  const valid = rows.filter(row => Number.isFinite(row.median) && Number.isFinite(row.year));
  if (!valid.length) return '<p class="notice">No validated annual series for this metric.</p>';
  const years = valid.map(row => row.year), start = Math.min(...years), end = Math.max(...years);
  const low = Math.min(0, ...valid.map(row => Number.isFinite(row.lower) ? row.lower : row.median)), high = Math.max(0, ...valid.map(row => Number.isFinite(row.upper) ? row.upper : row.median));
  const span = high - low || 1, bottom = low - span * .05, top = high + span * .05;
  const x = row => ((row.year - start) / (end - start || 1) * 1000).toFixed(2);
  const y = value => (200 - (value - bottom) / (top - bottom) * 200).toFixed(2);
  const groups = [...new Set(valid.map(row => `${row.place}|${row.pathway_id}`))].map(key => valid.filter(row => `${row.place}|${row.pathway_id}` === key));
  const places = [...new Set(valid.map(row => row.place))];
  const styleIndex = group => places.indexOf(group[0].place) * 2 + (group[0].pathway_id === 'ssp245' ? 0 : 1);
  return `<div class="annual-plot"><div class="annual-axis"><span>${number(top)} ${esc(valid[0].unit)}</span><span>${number(bottom)}</span></div><svg class="annual-chart" viewBox="0 0 1000 200" preserveAspectRatio="none" role="img" aria-label="Annual median changes and model ranges; exact values follow in the data table"><line x1="0" x2="1000" y1="${y(0)}" y2="${y(0)}" stroke="#777" stroke-dasharray="4 4"/>${groups.map(group => {
    const color = group[0].pathway_id === 'ssp245' ? '#155f65' : '#a84018';
    const completeBand = group.every((row, index) => Number.isFinite(row.lower) && Number.isFinite(row.upper) && (!index || row.year === group[index - 1].year + 1));
    const band = completeBand ? `<path d="M${group.map(row => `${x(row)},${y(row.upper)}`).join(' L')} L${[...group].reverse().map(row => `${x(row)},${y(row.lower)}`).join(' L')} Z" fill="${color}" opacity=".13"/>` : '';
    const curve = group.map((row, index) => `${index && row.year === group[index - 1].year + 1 ? 'L' : 'M'}${x(row)},${y(row.median)}`).join(' ');
    const dash = ['none', '8 4', '2 4', '12 4 2 4'][styleIndex(group) % 4];
    return `${band}<path d="${curve}" fill="none" stroke="${color}" stroke-width="3" vector-effect="non-scaling-stroke" stroke-dasharray="${dash}"/>`;
  }).join('')}</svg></div><div class="pathway-axis"><span>${start}</span><span>${end}</span></div><p class="annual-legend">${groups.map(group => `${esc(group[0].place)} · ${group[0].pathway}: ${['solid teal', 'dashed rust', 'dotted teal', 'dash-dot rust'][styleIndex(group) % 4]}`).join(' · ')}</p>`;
}

export function rangePlot(rows) {
  const valid = rows.filter(row => Number.isFinite(row.median));
  const low = Math.min(0, ...valid.map(row => row.lower ?? row.median));
  const high = Math.max(0, ...valid.map(row => row.upper ?? row.median));
  const span = high - low || 1;
  const min = low - span * .08, max = high + span * .08;
  const pct = value => (value - min) / (max - min) * 100;
  return `<div class="pathway-axis" aria-hidden="true"><span>${number(min)}</span><span>${number((min + max) / 2)}</span><span>${number(max)}</span></div><div class="pathway-ranges">${rows.map(row => `<div class="pathway-row" data-pathway="${row.pathway_id}"><p><strong>${esc(row.pathway)}</strong>${rows.length > 2 ? ` · ${esc(row.place)}` : ''} <span>${row.median === null ? 'Unavailable' : `${number(row.median)} ${esc(row.unit)}`}</span></p>${row.median === null ? `<p class="caption">${esc(row.status)}; no value is filled in.</p>` : `<div class="pathway-track" aria-hidden="true"><i class="pathway-zero" style="left:${pct(0)}%"></i>${row.lower !== null && row.upper !== null ? `<i class="pathway-band" style="left:${pct(row.lower)}%;width:${pct(row.upper) - pct(row.lower)}%"></i>` : ''}<i class="pathway-point" style="left:${pct(row.median)}%"></i></div>`}</div>`).join('')}</div>`;
}

export function mountPathwayChart(element, { catalog, store, loadAsset }) {
  element.classList.add('pathway-explorer');
  element.innerHTML = `<div class="pathway-controls"><label>Metric<select data-metric>${catalog.metrics.map(item => `<option value="${esc(item.id)}">${esc(item.label)}</option>`).join('')}</select></label><label>Period<select data-period>${catalog.periods.map(item => `<option value="${esc(item.id)}">${esc(item.label)}</option>`).join('')}</select></label><label>Compare with<select data-compare><option value="">One place</option>${catalog.places.map(place => `<option value="${esc(place.id)}">${esc(place.name)}</option>`).join('')}</select></label><label data-compare-area-label hidden>Comparison source area<select data-compare-area></select></label></div><div data-pathway-result aria-live="polite"></div>`;
  const result = element.querySelector('[data-pathway-result]');
  let controller, revision = 0, rows = [];
  const update = async ({ selection, primary, comparison, errors }) => {
    controller?.abort(); controller = new AbortController(); const current = ++revision;
    element.querySelector('[data-metric]').value = selection.metric;
    element.querySelector('[data-period]').value = selection.period;
    element.querySelector('[data-compare]').value = selection.compare || '';
    const compareSelect = element.querySelector('[data-compare-area]');
    compareSelect.innerHTML = `<option value="">Choose a source area</option>${(comparison?.area_ids || []).map(id => `<option value="${esc(id)}">${esc(catalog.areas[id]?.name || id)}</option>`).join('')}`;
    compareSelect.value = selection.compareArea || '';
    element.querySelector('[data-compare-area-label]').hidden = !comparison || comparison.area_ids.length < 2;
    rows = [];
    if (errors.length) { result.innerHTML = `<p class="notice">${errors.map(esc).join(' ')}</p><button data-current>Use this release</button>`; return; }
    if (!primary || !selection.area) { result.innerHTML = `<h2>${esc(primary?.name || 'Choose a place')}</h2><p class="notice">${primary?.area_ids.length > 1 ? 'This Nation has several source areas. Choose one in the place explorer.' : esc(primary?.missing_reason || 'No validated climate source-area match is available.')}</p><a href="#risks/place">Choose a place →</a>`; return; }
    const selections = [[primary, selection.area], ...(comparison ? [[comparison, selection.compareArea]] : [])];
    if (selections.some(([, id]) => !id)) { result.innerHTML = '<p class="notice">Choose the comparison source area. Shared or multiple areas are not averaged automatically.</p>'; return; }
    const descriptors = selections.map(([, id]) => catalog.areas[id]);
    if (descriptors.some(area => !area || area.family !== selection.family || area.baseline_id !== selection.baseline)) { result.innerHTML = '<p class="notice">These places use different source families or baselines. Choose places from the same family for a shared comparison; regional context is never substituted for a Nation.</p>'; return; }
    result.innerHTML = `<h2>${esc(primary.name)}</h2><p role="status">Loading ${esc(catalog.metrics.find(metric => metric.id === selection.metric)?.label)} for this selection…</p>`;
    try {
      const areas = await Promise.all(descriptors.map(area => loadAsset(catalog, area.file_id, { signal: controller.signal })));
      if (current !== revision) return;
      const annual = selection.family === 'usgs-nccv-loca2';
      rows = areas.flatMap((area, i) => (annual ? annualRows : windowRows)(area, selection.metric, selection.period, selections[i][0].name).map(row => ({ ...row, mapping_status: selections[i][0].mapping_status, mapping_caution: selections[i][0].mapping_caution || '' })));
      const metric = areas[0].metrics[selection.metric];
      const scope = `${areas.map(area => area.name).join(' / ')} · ${catalog.families.find(item => item.id === selection.family)?.label} · ${selection.period} minus ${selection.baseline}`;
      result.innerHTML = `<h2>${esc(primary.name)}${comparison ? ` / ${esc(comparison.name)}` : ''}</h2><p class="pathway-scope">${esc(scope)}</p><figure><figcaption>${esc(metric?.definition || 'This metric is unavailable for the source area.')}</figcaption>${annual ? annualPlot(rows) : rangePlot(rows)}<p class="caption">${annual ? 'Annual lines are provider medians; shading shows' : 'Points are medians; bars show'} ${esc(areas[0].spread)}. ${rows.map(row => `${row.pathway}: ${row.models ?? 'unknown'} models`).filter((text, i, all) => all.indexOf(text) === i).join(' · ')}. Model spread is not a probability interval.</p></figure><div class="action-row"><button data-export>Download these values</button><a href="#priorities">Record a planning question →</a><a href="#risks/place">Change place →</a></div><details class="pathway-details"><summary>Values, sources and coverage</summary><div class="table-scroll" tabindex="0"><table><caption>${esc(scope)}</caption><thead><tr><th>Place / pathway ${annual ? '/ year' : ''}</th><th>Median</th><th>10th–90th</th><th>Models</th></tr></thead><tbody>${rows.map(row => `<tr><th scope="row">${esc(row.place)} · ${row.pathway}${row.year ? ` · ${row.year}` : ''}</th><td>${number(row.median)} ${esc(row.unit)}</td><td>${number(row.lower)} – ${number(row.upper)}</td><td>${row.models ?? 'Unavailable'}</td></tr>`).join('')}</tbody></table></div>${areas.map(area => `<p>${esc(area.name)}: ${esc(area.status || 'accepted')} · ${esc(area.geometry_role || 'climate source area')}. <a href="${esc(area.source.url)}" target="_blank" rel="noopener noreferrer">${esc(area.source.label)}</a></p><ul>${area.limitations.map(text => `<li>${esc(text)}</li>`).join('')}</ul>`).join('')}</details>`;
      const proxies = selections.filter(([place]) => place.proxy).map(([place]) => place.name);
      if (proxies.length) result.querySelector('.pathway-scope').insertAdjacentHTML('afterend', `<p class="notice pathway-proxy"><strong>Borrowed climate-area proxy:</strong> ${proxies.map(esc).join(' / ')}. These values do not resolve the Nation’s own geography.</p>`);
    } catch (error) { if (current !== revision || error.name === 'AbortError') return; result.innerHTML = `<h2>${esc(primary.name)}</h2><p class="notice">${esc(error.message)}</p><button data-retry>Try this selection again</button>`; }
  };
  element.onchange = event => {
    const target = event.target;
    if (target.matches('[data-metric]')) store.set({ metric: target.value });
    if (target.matches('[data-period]')) store.set({ period: target.value });
    if (target.matches('[data-compare]')) { const place = catalog.places.find(item => item.id === target.value); store.set({ compare: target.value, compareArea: place?.area_ids.length === 1 ? place.area_ids[0] : '' }); }
    if (target.matches('[data-compare-area]')) store.set({ compareArea: target.value });
  };
  element.onclick = event => {
    if (event.target.closest('[data-retry]')) update(store.get());
    if (event.target.closest('[data-current]')) store.set(catalog.default_selection, { replace: true });
    if (event.target.closest('[data-export]') && rows.length) { const url = URL.createObjectURL(new Blob([rowsCSV(rows)], { type: 'text/csv;charset=utf-8' })); const link = document.createElement('a'); link.href = url; link.download = 'catf-selected-pathways.csv'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  };
  const unsubscribe = store.subscribe(update); update(store.get());
  return () => { ++revision; controller?.abort(); unsubscribe(); element.onchange = null; element.onclick = null; };
}
