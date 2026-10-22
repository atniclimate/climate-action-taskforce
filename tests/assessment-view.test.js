const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const shared = fs.readFileSync(path.join(__dirname, '../site/chapters/shared.js'), 'utf8');
  const sharedUrl = `data:text/javascript;base64,${Buffer.from(shared).toString('base64')}`;
  const chapter = fs.readFileSync(path.join(__dirname, '../site/chapters/assessment.js'), 'utf8')
    .replace("from './shared.js'", `from '${sharedUrl}'`);
  const {meanHazardScores,hazardIndexTable,hazardCoverage,risks,costs,funding} = await import(`data:text/javascript;base64,${Buffer.from(chapter).toString('base64')}`);
  const row = {region_id:'r',nation_count:3,top_hazards:[
    {hazard_id:'a',hazard_name:'A'}, {hazard_id:'b',hazard_name:'B'}]};
  const nation = (region_id, a, b) => ({region_id,hazards:[
    {hazard_id:'a',status:a==null?'unavailable':'modeled',value:a},
    {hazard_id:'b',status:'modeled',value:b}]});
  const data = {national:{top_hazards:row.top_hazards,nation_count:4},nations:[
    nation('r',0.8,0.2),nation('r',null,0.4),nation('r',0.2,0.6),nation('other',1,1)]};
  const regional = meanHazardScores(data,row);
  assert.deepEqual(regional.map(h=>h.label),['A','B']);
  assert.equal(regional[0].value,0.5);
  assert.ok(Math.abs(regional[1].value-0.4)<1e-12);
  assert.match(regional[0].note,/2 of 3 Nations scored · 1 unavailable/);
  assert.ok(Math.abs(meanHazardScores(data,data.national)[0].value-2/3)<1e-12);
  const indexRows=[{label:'Z hazard',value:null,note:'0 of 3 Nations scored · 3 unavailable'},{label:'A hazard',value:0.4}];
  const indexTable=hazardIndexTable(indexRows,'Read each hazard separately.','Mean score');
  assert.ok(indexTable.indexOf('A hazard')<indexTable.indexOf('Z hazard'),'index values appear alphabetically, not by magnitude');
  assert.match(indexTable,/>Unavailable<\/td>/,'missing indices are not displayed as zero');
  assert.match(indexTable,/0 of 3 Nations scored · 3 unavailable/,'coverage accompanies the hazard');
  assert.doesNotMatch(indexTable,/risk-fill|risk-track/,'different hazard indices do not share quantitative bars');
  assert.equal(indexRows[0].label,'Z hazard','table display does not reorder its input');

  const frozen = JSON.parse(fs.readFileSync(path.join(__dirname, '../site/data/risk.json'), 'utf8'));
  assert.equal(hazardCoverage(frozen),'356 Nations have five-item displayed lists; 219 have four-item lists. These are list lengths, not all supported hazard counts: 348 Nations have six supported scores.');
  assert.match(chapter,/coverage saturation, not equal exposure/);
  assert.ok(risks.render().indexOf('data-block="explore"')<risks.render().indexOf('data-block="reading"'),'results precede glossary');
  assert.match(risks.render(),/<section data-block="place" data-explorer-component="place">/);
  assert.ok(risks.slides.some(s=>s.id==='place'&&s.blocks.includes('place')));
  assert.match(costs.render(),/<section data-block="cohorts" data-explorer-component="cohort">/);
  assert.ok(costs.slides.some(s=>s.id==='cohorts'&&s.blocks.includes('cohorts')));
  const southwest = frozen.regions.find(r=>r.region_id==='southwest');
  assert.ok(southwest.top_hazards.every(h=>h.value===southwest.nation_count));
  const means = meanHazardScores(frozen,southwest);
  assert.equal(means.length,5);
  assert.ok(means.some(h=>Math.abs(h.value-means[0].value)>0.01), 'mean view distinguishes the five Southwest hazards');
  assert.ok(means.every(h=>h.note.includes('0 unavailable')));
  assert.match(chapter, /<option value="frequency">Top-five frequency<\/option><option value="mean">/);
  const alaska=frozen.regions.find(r=>r.region_id==='alaska');
  assert.ok(meanHazardScores(frozen,alaska).some(h=>!h.note.includes('· 0 unavailable')),'Alaska mean coverage keeps unavailable hazard scores visible');
  for (const chapter of [risks,costs,funding]) {
    const html=chapter.render();
    for (const slide of chapter.slides) for (const block of slide.blocks)
      assert.ok(html.includes(`data-block="${block}"`),`${chapter.id}/${slide.id} block "${block}" exists in render()`);
  }
  assert.ok(costs.slides.filter(s=>s.id!=='cohorts').every(s=>s.blocks.includes('geo')),'one cost geography select drives county cost slides');
  assert.equal((costs.render().match(/data-cost-region/g)||[]).length,1,'cost geography is a single shared control');
  assert.deepEqual(funding.slides.map(s=>s.id),['records','regions','leads']);
  const planning=fs.readFileSync(path.join(__dirname,'../site/chapters/planning.js'),'utf8')
    .replace("from './shared.js'",`from '${sharedUrl}'`);
  const {planningAgeGroups}=await import(`data:text/javascript;base64,${Buffer.from(planning).toString('base64')}`);
  const ages=planningAgeGroups([
    {document_classes:['a','b'],age_bin:'Unknown'},
    {document_classes:['a'],age_bin:'Unknown'},
    {document_classes:['b'],age_bin:'0–5 years'},
  ],['a','b']);
  assert.equal(ages.ceiling,2,'all visible age charts share one count ceiling');
  assert.deepEqual(ages.groups.map(g=>g.rows.map(r=>r.value)),[[0,0,0,2],[1,0,0,1]],'unknown dates and multi-class URLs remain separate');
  assert.equal(planningAgeGroups([],['a']).ceiling,1,'empty filters retain a usable count axis');
  console.log('Assessment view checks passed: supported-score means, missingness, regional membership, Southwest and Alaska coverage, alphabetical index tables, frequency default, presenter slide blocks, shared cost geography and shared planning count scales.');
})().catch(error => { console.error(error); process.exitCode=1; });
