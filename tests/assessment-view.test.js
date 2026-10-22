const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const read = file => fs.readFileSync(path.join(__dirname, '..', file), 'utf8');
  const url = text => `data:text/javascript;base64,${Buffer.from(text).toString('base64')}`;
  const sharedUrl = url(read('site/chapters/shared.js'));
  const chapter = read('site/chapters/assessment.js').replace("from './shared.js'", `from '${sharedUrl}'`);
  const {hazardStatusRows,hazardIndexTable,hazardCoverage,temporalTable,risks,costs,funding} = await import(url(chapter));
  const nation=(region_id,value,status='modeled')=>({region_id,hazards:[{hazard_id:'a',hazard_name:'A',status,value}]});
  const data={national:{nation_count:4},nations:[nation('r',0),nation('r',0.1,'placeholder'),nation('r',null,'unavailable'),nation('other',1)]};
  const rows=hazardStatusRows(data,{region_id:'r',nation_count:3});
  assert.equal(rows[0].value,1,'zero is supported; placeholders are excluded');
  assert.match(rows[0].note,/1 of 3 Nations supported/);
  assert.match(rows[0].note,/placeholder: 1/);
  assert.equal(hazardStatusRows(data,data.national)[0].value,2);
  const table=hazardIndexTable([{label:'Z',value:null,note:'placeholder'},{label:'A',value:0}],'Each hazard separately','Supported score');
  assert.ok(table.indexOf('>A<')<table.indexOf('>Z<'));
  assert.match(table,/>Unavailable<\/td>/);
  assert.match(table,/>0.000<\/td>/);
  assert.doesNotMatch(table,/risk-fill|risk-track/);
  assert.match(hazardCoverage(data),/1 placeholder rows/);
  const temporal=temporalTable({assessment_uncertainty:{score_range_low:0,score_range_high:1,assessed_band:{p5:.2,p50:.3,p95:.4}},temporal:[
    {horizon:'2030',scenario:'ssp245',status:'cell_support_unverified',physical_score:.999,reason:'retained evidence insufficient'},
    {horizon:'2080',scenario:'ssp370',status:'forward_supported',physical_score:0},
    {horizon:'2080',scenario:'ssp585',status:'scenario_unsupported',physical_score:.888},
  ]});
  assert.doesNotMatch(temporal,/0.999|0.888|ssp585/);
  assert.match(temporal,/0.000/);
  assert.match(temporal,/cell_support_unverified/);
  assert.match(temporal,/Missing-hazard/);
  assert.match(temporal,/p5 0.200/);
  assert.doesNotMatch(chapter,/meanHazardScores|data-risk-metric|\.top_hazards/);
  const frozen=JSON.parse(read('site/data/risk.json'));
  assert.equal(frozen.nations.length,575);
  assert.ok(frozen.nations.every(n=>n.hazards.length===9));
  for(const c of [risks,costs,funding])for(const slide of c.slides)for(const block of slide.blocks)
    assert.ok(c.render().includes(`data-block="${block}"`),`${c.id}/${slide.id}: ${block}`);
  assert.match(risks.render(),/data-explorer-component="scanner-regions"/);
  assert.equal((costs.render().match(/data-cost-region/g)||[]).length,1);
  assert.deepEqual(funding.slides.map(s=>s.id),['records','regions','leads']);
  const planning=read('site/chapters/planning.js').replace("from './shared.js'",`from '${sharedUrl}'`);
  const {planningAgeGroups}=await import(url(planning));
  const ages=planningAgeGroups([{document_classes:['a','b'],age_bin:'Unknown'},{document_classes:['a'],age_bin:'Unknown'},{document_classes:['b'],age_bin:'0–5 years'}],['a','b']);
  assert.equal(ages.ceiling,2);
  assert.deepEqual(ages.groups.map(g=>g.rows.map(r=>r.value)),[[0,0,0,2],[1,0,0,1]]);
  assert.equal(planningAgeGroups([],['a']).ceiling,1);
  const chart=read('site/components/pathway-chart.js').replace("from '../chapters/shared.js'",`from '${sharedUrl}'`);
  const regional=read('site/components/scanner-regions.js').replace("from '../chapters/shared.js'",`from '${sharedUrl}'`).replace("from './pathway-chart.js'",`from '${url(chart)}'`);
  const {regionalClimateRows,regionalRiskTable}=await import(url(regional));
  const projection={metric_id:'temp_mean',scenario:'ssp245',period:[2040,2059],unit:'°C',change:{p50:0,p10:-1,p90:1}};
  const climate=regionalClimateRows({region_name:'Example',projections:[projection]},'temp_mean','2040-2059');
  assert.equal(climate[0].median,0);
  assert.equal(climate[1].median,null);
  assert.equal(regionalClimateRows({projections:null},'temp_mean','2040-2059')[0].median,null);
  const riskTable=regionalRiskTable({temporal:[{horizon:'2080',scenario:'ssp370',support:{n_supported:0,n_missing:5},physical_score:{median:null,p25:null,p75:null}}]});
  assert.match(riskTable,/0 \/ 5/);
  assert.match(riskTable,/Unavailable/);
  console.log('Assessment checks passed: hazard states, zero/placeholder/missing coverage, temporal support, regional climate/risk, slide blocks and planning scales.');
})().catch(error=>{console.error(error);process.exitCode=1;});
