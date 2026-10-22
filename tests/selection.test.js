const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const source = fs.readFileSync(path.join(__dirname, '../site/state/selection.js'), 'utf8');
  const { selectionFromHash, selectionQuery, resolveSelection, createSelectionStore } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
  const catalog = {
    release_id: 'r1', default_selection: { release: 'r1', place: 'nation:a', area: 'one', family: 'native', metric: 'temp', baseline: '1995-2014', period: '2040-2059', lens: 'ecology' },
    places: [{ id: 'nation:a', name: 'A', area_ids: ['one'] }, { id: 'nation:b', name: 'B', area_ids: ['two', 'three'] }],
    families: [{ id: 'native' }], metrics: [{ id: 'temp' }], baselines: [{ id: '1995-2014' }], periods: [{ id: '2040-2059' }], lenses: [{ id: 'ecology' }],
  };
  const selected = { ...catalog.default_selection, compare: 'nation:b', compareArea: 'two' };
  assert.deepEqual(selectionFromHash(`#risks/place?${selectionQuery(selected)}`), selected);
  assert.deepEqual(selectionFromHash('#risks'), {});
  assert.ok(selectionFromHash('#risks?s=2&place=nation:a').invalid);
  assert.ok(selectionFromHash('#risks?s=1&place=nation:a&place=nation:b').invalid);
  assert.equal(selectionQuery({ ...selected, note: 'private note', path: '../private' }).includes('private'), false);
  assert.equal(resolveSelection(selected, catalog).errors.length, 0);
  assert.ok(resolveSelection({ ...selected, area: 'three' }, catalog).errors.length);
  assert.ok(resolveSelection({ ...selected, release: 'old' }, catalog).errors.length);
  assert.ok(resolveSelection({ ...selected, metric: 'dollars' }, catalog).errors.length);
  assert.equal(resolveSelection({ ...selected, place: 'unknown' }, catalog).selection.place, 'unknown');
  const store = createSelectionStore(catalog, selected);
  let calls = 0;
  const off = store.subscribe((value, options) => { calls++; assert.equal(value.selection.compare, ''); assert.equal(options.history, false); });
  store.set({ compare: '', compareArea: '' }, { history: false });
  off(); store.set(selected, { replace: true });
  assert.equal(calls, 1);
  const withStory = { ...catalog, default_selection: { ...catalog.default_selection, story: 'columbia' }, cohorts: [{ id: 'columbia' }] };
  assert.equal(resolveSelection(selectionFromHash(`#risks/place?${selectionQuery({ ...selected, story: '' })}`), withStory).selection.story, '', 'reload does not restore the default story over a separately selected place');
  console.log('Selection checks passed: round trip, old links, invalid IDs, source area ownership, private-field exclusion and atomic restore.');
})().catch(error => { console.error(error); process.exitCode = 1; });
