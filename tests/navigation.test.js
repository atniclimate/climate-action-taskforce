const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const source = fs.readFileSync(require('node:path').join(__dirname, '../site/navigation.js'), 'utf8');
  const { indexFromHash, positionFromHash, hashFor, buildDeck, stepIndex, modeFromSearch, keyboardStep } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
  const chapters = [{ id: 'mission' }, { id: 'risk' }, { id: 'tools' }];
  // Presenter slides: flattened deck, suffixed hashes, legacy and malformed fallbacks.
  const split = [{ id: 'mission' }, { id: 'funding', slides: [{ id: 'records' }, { id: 'regions' }, { id: 'leads' }] }, { id: 'tools' }];
  assert.deepEqual(buildDeck(split), [{ chapter: 0, slide: 0 }, { chapter: 1, slide: 0 }, { chapter: 1, slide: 1 }, { chapter: 1, slide: 2 }, { chapter: 2, slide: 0 }]);
  assert.deepEqual(positionFromHash('#funding/regions', split), { chapter: 1, slide: 1 });
  assert.deepEqual(positionFromHash('#funding', split), { chapter: 1, slide: 0 });
  assert.deepEqual(positionFromHash('#funding/unknown', split), { chapter: 1, slide: 0 });
  assert.deepEqual(positionFromHash('#tools/regions', split), { chapter: 2, slide: 0 });
  assert.deepEqual(positionFromHash('#nowhere/regions', split), { chapter: 0, slide: 0 });
  assert.deepEqual(positionFromHash('#%E0%A4', split), { chapter: 0, slide: 0 });
  assert.equal(hashFor(split, 1, 0), '#funding');
  assert.equal(hashFor(split, 1, 2), '#funding/leads');
  assert.equal(hashFor(split, 2, 0), '#tools');
  assert.deepEqual(positionFromHash('#funding/regions?s=1&place=nation%3Aone', split), { chapter: 1, slide: 1 });
  assert.equal(hashFor(split, 1, 1, 's=1&place=nation%3Aone'), '#funding/regions?s=1&place=nation%3Aone');
  assert.equal(indexFromHash('#risk', chapters), 1);
  assert.equal(indexFromHash('#%72isk', chapters), 1);
  assert.equal(indexFromHash('#unknown', chapters), 0);
  assert.equal(indexFromHash('#%E0%A4', chapters), 0);
  assert.equal(stepIndex(0, -1, 3), 0);
  assert.equal(stepIndex(2, 1, 3), 2);
  assert.equal(stepIndex(1, 1, 3), 2);
  assert.equal(modeFromSearch('?mode=presenter'), 'presenter');
  assert.equal(modeFromSearch('?mode=other'), 'participant');
  assert.equal(keyboardStep({ key: 'ArrowRight' }, 1, 3), 2);
  assert.equal(keyboardStep({ key: 'Home' }, 2, 3), 0);
  assert.equal(keyboardStep({ key: 'End' }, 0, 3), 2);
  assert.equal(keyboardStep({ key: 'ArrowRight', ctrlKey: true }, 1, 3), null);
  assert.equal(keyboardStep({ key: 'ArrowRight', target: { closest: () => ({}) } }, 1, 3), null);
  assert.equal(keyboardStep({ key: ' ' }, 1, 3), null);

  const appSource = fs.readFileSync(require('node:path').join(__dirname, '../site/app.js'), 'utf8');
  const selectorSource = appSource.match(/function chapterAtViewportPosition\([\s\S]*?\n\}/)?.[0];
  assert.ok(selectorSource, 'participant chapter selector exists');
  assert.match(appSource, /chapterAtViewportPosition\(sections, window\.innerHeight\)/);
  const chapterAtViewportPosition = Function(`return (${selectorSource})`)();
  const sections = [
    { getBoundingClientRect: () => ({ top: -27000, bottom: -26000 }) },
    { getBoundingClientRect: () => ({ top: -1200, bottom: -330 }) },
    { getBoundingClientRect: () => ({ top: -330, bottom: 900 }) },
  ];
  assert.equal(chapterAtViewportPosition(sections, 844), 2, 'current policy chapter wins over stale strategy observation');
  assert.equal(chapterAtViewportPosition(sections.slice(0, 2), 844), -1, 'no visible chapter leaves current selection unchanged');
  console.log('Navigation checks passed: deep links, malformed hashes, boundaries, modes, keyboard controls, participant viewport position.');
})().catch(error => { console.error(error); process.exitCode = 1; });
