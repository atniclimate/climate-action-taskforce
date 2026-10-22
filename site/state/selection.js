const fields = ['release', 'place', 'area', 'compare', 'compareArea', 'family', 'metric', 'baseline', 'period', 'lens', 'story'];

export function selectionFromHash(hash) {
  const query = hash.indexOf('?');
  if (query < 0) return {};
  const params = new URLSearchParams(hash.slice(query + 1));
  if (params.get('s') !== '1') return { invalid: 'This shared selection uses an unsupported version.' };
  if (fields.some(key => params.getAll(key).length > 1)) return { invalid: 'The shared selection contains duplicate fields.' };
  return Object.fromEntries(fields.filter(key => params.has(key)).map(key => [key, params.get(key)]));
}

export function selectionQuery(selection) {
  const params = new URLSearchParams({ s: '1' });
  for (const key of fields) if (selection[key]) params.set(key, selection[key]);
  return params.toString();
}

export function resolveSelection(raw, catalog) {
  const selection = { ...catalog.default_selection, ...Object.fromEntries(fields.filter(key => raw[key] !== undefined).map(key => [key, raw[key]])) };
  const errors = raw.invalid ? [raw.invalid] : [];
  if (selection.release !== catalog.release_id) errors.push('This selection belongs to a different data release. Choose a place in this release.');
  const primary = catalog.places.find(place => place.id === selection.place);
  const comparison = selection.compare ? catalog.places.find(place => place.id === selection.compare) : null;
  if (raw.place && raw.area === undefined) selection.area = primary?.area_ids.length === 1 ? primary.area_ids[0] : '';
  if (raw.place && raw.story === undefined) selection.story = '';
  if (raw.compare && raw.compareArea === undefined) selection.compareArea = comparison?.area_ids.length === 1 ? comparison.area_ids[0] : '';
  if (!primary) errors.push('The selected place is not in this release.');
  if (selection.compare && !comparison) errors.push('The comparison place is not in this release.');
  if (selection.story && !catalog.cohorts?.some(item => item.id === selection.story)) errors.push('The selected story is not in this release.');
  for (const [key, records] of [['family', catalog.families], ['metric', catalog.metrics], ['baseline', catalog.baselines], ['period', catalog.periods], ['lens', catalog.lenses]]) {
    if (!records.some(record => record.id === selection[key])) errors.push(`The selected ${key} is not supported in this release.`);
  }
  for (const [place, area] of [[primary, selection.area], [comparison, selection.compareArea]]) {
    if (place && area && !place.area_ids.includes(area)) errors.push(`The selected source area does not belong to ${place.name}.`);
  }
  return { selection, primary, comparison, errors };
}

export function createSelectionStore(catalog, initial = {}) {
  let resolved = resolveSelection(initial, catalog);
  const listeners = new Set();
  return {
    get: () => resolved,
    set(raw, { replace = false, history = true } = {}) {
      resolved = resolveSelection(replace ? raw : { ...resolved.selection, ...raw }, catalog);
      for (const listener of listeners) listener(resolved, { history });
    },
    subscribe(listener) { listeners.add(listener); return () => listeners.delete(listener); },
  };
}
