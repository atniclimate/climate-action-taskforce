const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const read=file=>fs.readFileSync(path.join(__dirname,'..',file),'utf8');
  const url=text=>`data:text/javascript;base64,${Buffer.from(text).toString('base64')}`;
  const shared=url(read('site/chapters/shared.js'));
  const {planInventoryView,reviewedPlanView,plans}=await import(url(read('site/chapters/planning.js').replace("from './shared.js'",`from '${shared}'`)));
  const data=JSON.parse(read('site/data/plan-update.json'));
  const inventory=planInventoryView(data);
  assert.match(inventory,/254 Tribal profiles/);
  assert.match(inventory,/234 byte-distinct files/);
  assert.equal((inventory.match(/<th scope="row">/g)||[]).length,6);
  assert.match(inventory,/577 identities/);
  assert.match(inventory,/unresolved/);
  assert.doesNotMatch(inventory,/254\s*\/\s*575|254 Tribes have/);
  assert.match(inventory,/not counts of plans or editions/);
  for(const row of data.relationships){
    const html=reviewedPlanView(row);
    assert.match(html,/Award ID and amount unknown/);
    assert.match(html,/Adoption and current edition unknown/);
    assert.match(html,/not been joined/);
    assert.match(html,/physical PDF pages/);
    for(const c of row.citations)assert.ok(html.includes(c.url.replaceAll('&','&amp;')));
  }
  const yocha=data.relationships.find(r=>r.source_profile_name.includes('Yocha'));
  assert.match(reviewedPlanView(yocha),/withheld/);
  assert.match(reviewedPlanView(yocha),/exclud/i);
  const hostile=structuredClone(yocha);hostile.source_profile_name='<script>bad</script>';
  assert.doesNotMatch(reviewedPlanView(hostile),/<script>/);
  assert.ok(plans.slides.some(s=>s.id==='inventory')&&plans.slides.some(s=>s.id==='reviewed'));
  assert.match(plans.render(),/data-plan-inventory/);
  console.log('Plan update views: inventory units, six labels, unresolved identities, three citations and unknowns pass');
})().catch(error=>{console.error(error);process.exitCode=1;});
