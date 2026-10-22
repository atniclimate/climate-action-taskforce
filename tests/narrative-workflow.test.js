const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
  const shared=fs.readFileSync(path.join(__dirname,'../site/chapters/shared.js'),'utf8');
  const sharedUrl=`data:text/javascript;base64,${Buffer.from(shared).toString('base64')}`;
  const text=fs.readFileSync(path.join(__dirname,'../site/chapters/narrative.js'),'utf8').replace("from './shared.js'",`from '${sharedUrl}'`);
  const {decisionRecord,globalEndpoints,scenarios,knowledge,priorities}=await import(`data:text/javascript;base64,${Buffer.from(text).toString('base64')}`);
  for(let i=0;i<4;i++){
    const record=decisionRecord(i);
    assert.equal((record.match(/<dt>/g)||[]).length,i+1);
    if(i)assert.ok(record.includes(decisionRecord(i-1).slice(28,-5)),'earlier decision fields persist');
    assert.match(record,/cooling|ventilation/);
  }
  assert.match(decisionRecord(3),/Next action \/ owner/);
  assert.deepEqual(globalEndpoints,[{pathway:'SSP2-4.5',best:2.7,low:2.1,high:3.5},{pathway:'SSP3-7.0',best:3.6,low:2.8,high:4.6}]);
  const html=scenarios.render();
  assert.match(html,/data-explorer-component="pathway"/);
  assert.match(html,/1850–1900/);assert.match(html,/2081–2100/);
  assert.match(html,/<table>/,'global range retains an exact numeric table');
  assert.match(knowledge.render(),/Fictional decision/);
  for(const chapter of [scenarios,knowledge,priorities])for(const slide of chapter.slides)for(const block of slide.blocks)assert.ok(chapter.render().includes(`data-block="${block}"`));
  assert.match(priorities.render(),/Fictional example/);
  assert.match(priorities.render(),/Next action \/ owner:/);
  assert.match(priorities.render(),/<\/textarea>/);
  const elements=new Map(['textarea','[data-note-status]','[data-save-note]','[data-clear-note]','[data-download-note]','[data-criteria-summary]'].map(key=>[key,{value:'',textContent:''}]));
  const saved=new Map();global.localStorage={getItem:key=>saved.get(key),setItem:(key,value)=>saved.set(key,value),removeItem:key=>saved.delete(key)};
  const section={querySelector:key=>elements.get(key),querySelectorAll:()=>[]};
  let exported,clicked=false;
  global.document={createElement:()=>({click(){clicked=true;}})};
  const create=URL.createObjectURL,revoke=URL.revokeObjectURL;
  URL.createObjectURL=blob=>(exported=blob,'blob:local-note');URL.revokeObjectURL=()=>{};
  try{
    priorities.mount(section);
    assert.equal(elements.get('textarea').value,'','the example is not prefilled');
    const note='Decision / service: center\nPlace: community\nEvidence needed: power\nNext action / owner: facility lead';
    elements.get('textarea').value=note;
    elements.get('[data-save-note]').onclick();
    assert.equal(saved.get('catf-discussion-note-v1'),note);
    elements.get('[data-download-note]').onclick();
    assert.equal(await exported.text(),note);assert.ok(clicked);
    elements.get('[data-clear-note]').onclick();
    assert.equal(elements.get('textarea').value,'');assert.equal(saved.size,0);
  }finally{URL.createObjectURL=create;URL.revokeObjectURL=revoke;}
  console.log('Narrative workflow checks passed: accumulating fictional record, exact global endpoints/table, pathway slot, blank discussion, local save/download/clear agreement.');
})().catch(error=>{console.error(error);process.exitCode=1;});
