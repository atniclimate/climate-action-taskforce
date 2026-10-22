// Focused plan update review; serve only site/ on 127.0.0.1:8765.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const out=fileURLToPath(new URL('../work/review/plan-update-browser/',import.meta.url));
const read=async name=>JSON.parse(await readFile(new URL('../site/data/'+name+'.json',import.meta.url),'utf8'));
const data=await read('plan-update'),sweep=await read('plans');
await mkdir(out,{recursive:true});
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',['--headless=new','--remote-debugging-port=0',`--user-data-dir=${path.join(out,`profile-${process.pid}`)}`,'--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','about:blank'],{windowsHide:true});
const checks=[],exceptions=[],pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const only=new Set((process.argv.find(x=>x.startsWith('--only='))||'').slice(7).split(',').filter(Boolean));
let socket,diagnostic;
const check=async(name,run)=>{if(only.size&&!only.has(name.split(' ')[0]))return;try{const evidence=await run();checks.push({name,pass:true,evidence});console.log('ok '+name);}catch(error){checks.push({name,pass:false,error:error.stack,detail:await diagnostic?.().catch(()=>null)});console.error('FAIL '+name+': '+error.message);}};
try{
  const endpoint=await new Promise((resolve,reject)=>{let stderr='';const timer=setTimeout(()=>reject(Error('No browser endpoint: '+stderr)),15000);browser.stderr.on('data',chunk=>{stderr+=chunk;const match=stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(match){clearTimeout(timer);resolve(match[1]);}});browser.once('error',reject);});
  socket=new WebSocket(endpoint);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let serial=0,sessionId;const pending=new Map();
  const send=(method,params={},session=sessionId)=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params,...(session?{sessionId:session}:{})}));});
  socket.onmessage=event=>{const message=JSON.parse(event.data);if(pending.has(message.id)){const p=pending.get(message.id);pending.delete(message.id);message.error?p.reject(Error(JSON.stringify(message.error))):p.resolve(message.result);}if(message.method==='Runtime.exceptionThrown')exceptions.push(message.params.exceptionDetails.exception?.description||message.params.exceptionDetails.text);};
  const target=await send('Target.createTarget',{url:'about:blank'},null);({sessionId}=await send('Target.attachToTarget',{targetId:target.targetId,flatten:true},null));
  await send('Page.enable');await send('Runtime.enable');await send('Network.enable');await send('Network.setCacheDisabled',{cacheDisabled:true});await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  const evaluate=async expression=>{const value=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||value.exceptionDetails.text);return value.result.value;};
  const wait=async expression=>{const start=Date.now();while(Date.now()-start<12000){if(await evaluate(expression))return;await pause(80);}throw Error('Timed out: '+expression);};
  const text=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)})?.textContent||''`);
  const route=async hash=>{await evaluate(`location.hash=${JSON.stringify(hash)}`);await pause(180);};
  const scroll=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})`);
  const shot=async name=>{const result=await send('Page.captureScreenshot',{format:'png'});await writeFile(path.join(out,name+'.png'),Buffer.from(result.data,'base64'));};
  const width=async value=>{await send('Emulation.setDeviceMetricsOverride',{width:value,height:900,deviceScaleFactor:1,mobile:false});await pause(100);};
  const change=async(selector,value)=>{await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('change',{bubbles:true}));})()`);await pause(100);};
  diagnostic=()=>evaluate("({hash:location.hash,mode:document.body.dataset.mode,text:document.querySelector('#plans')?.innerText,overflow:document.documentElement.scrollWidth-innerWidth})");
  await width(1440);await send('Page.navigate',{url:'http://127.0.0.1:8765/#plans/inventory'});await wait("document.querySelector('[data-plan-inventory] tbody tr')");
  await check('inventory counts six overlapping labels and unresolved roster',async()=>{
    const value=await text('[data-plan-inventory]');assert.equal(data.inventory.operational_profiles_with_local_documents,254);assert.equal(data.inventory.byte_distinct_files,234);assert.match(value,/254 Tribal profiles/);assert.match(value,/234 byte-distinct files/);assert.match(value,/unresolved/);assert.match(value,/unknown/);assert.doesNotMatch(value,/254\s*\/\s*575/);
    const labels=await evaluate("[...document.querySelectorAll('[data-plan-inventory] tbody th')].map(el=>el.textContent)");assert.equal(labels.length,6);assert.deepEqual(labels,data.plan_types.map(t=>t.label));assert.match(value,/do not sum either column/);await scroll('[data-plan-inventory]');await shot('desktop-inventory');return {profiles:254,files:234,labels};
  });
  await route('#plans/reviewed');await wait("!!document.querySelector('[data-reviewed-profile]')");
  await check('reviewed three selected source relationships dates funding and links',async()=>{
    const options=await evaluate("[...document.querySelector('[data-reviewed-profile]').options].map(el=>({id:el.value,name:el.textContent}))");assert.equal(options.length,3);
    const evidence=[];for(const option of options){await change('[data-reviewed-profile]',option.id);const value=await text('[data-reviewed-result]'),row=data.relationships.find(row=>row.id===option.id);assert.ok(value.includes(row.source_profile_name));assert.ok(value.includes(row.plan_title));assert.ok(value.includes(row.relationship_summary));assert.ok(value.includes(row.federal_support.explanation));assert.ok(value.includes(row.dates.date_basis));assert.match(value,/Award ID and amount unknown/);assert.match(value,/Adoption and current edition unknown/);assert.doesNotMatch(value,/254\s*\/\s*575/);await scroll('[data-plan-reviewed]');await shot('desktop-reviewed-'+option.id);await evaluate("document.querySelector('[data-reviewed-result] details summary').click()");const links=await evaluate("[...document.querySelectorAll('[data-reviewed-result] a[href^=\"http\"]')].filter(el=>el.getClientRects().length).map(el=>el.href)");assert.deepEqual(links,row.citations.map(c=>new URL(c.url).href));await scroll('[data-reviewed-result] details');await shot('desktop-citations-'+option.id);evidence.push({profile:option.id,links});}return evidence;
  });
  await check('separate frozen575 sweep and outreach queue',async()=>{
    await route('#plans/coverage');await wait("document.querySelector('[data-plan-coverage]')?.textContent.includes('575')");const value=await text('[data-plan-coverage]');assert.ok(value.includes(sweep.coverage.nations_attempted_all_classes+' / '+sweep.coverage.baseline_nations));assert.match(value,/Separate bounded metadata sweep/);assert.match(value,/not merged/);await scroll('[data-plan-coverage]');await shot('desktop-old-sweep');
    await route('#follow-up/flag');await wait("document.querySelector('[data-follow-count]')?.textContent!=='…'");assert.equal(Number((await text('[data-follow-count]')).replaceAll(',','')),sweep.coverage.followup_nations);assert.match(await text('#follow-up'),/not joined to this queue/);return {baseline:sweep.coverage.baseline_nations,followup:sweep.coverage.followup_nations};
  });
  await check('phone390 inventory and source review reflow',async()=>{
    await width(390);for(const [hash,selector,name] of [['#plans/inventory','[data-plan-inventory]','inventory'],['#plans/reviewed','[data-plan-reviewed]','reviewed']]){await route(hash);await scroll(selector);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),hash+' horizontal overflow');await shot('phone390-'+name);}
  });
  await check('presenter controls keyboard and initial caveats',async()=>{
    await width(1440);await send('Page.navigate',{url:'http://127.0.0.1:8765/?mode=presenter#plans/inventory'});await wait("document.body.dataset.mode==='presenter'&&!!document.querySelector('[data-plan-inventory] tbody tr')");await shot('presenter-inventory');assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'));
    const visible=selector=>evaluate(`(()=>{const box=document.querySelector(${JSON.stringify(selector)}).getBoundingClientRect();return {selector:${JSON.stringify(selector)},initiallyVisible:box.top>=document.querySelector('.site-header').offsetHeight&&box.bottom<=document.querySelector('.presentation-controls').getBoundingClientRect().top,top:box.top,bottom:box.bottom};})()`);
    const evidence=[await visible('[data-plan-inventory] .notice')];
    await route('#plans/reviewed');await wait("!!document.querySelector('[data-reviewed-profile]')");await evaluate("document.querySelector('[data-reviewed-profile]').focus()");const before=await evaluate('location.hash');await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});assert.equal(await evaluate('location.hash'),before);await shot('presenter-reviewed');assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'));
    evidence.push(await visible('[data-plan-reviewed] .notice'));evidence.push(await visible('[data-reviewed-profile]'));assert.ok(evidence.every(row=>row.initiallyVisible),'important caveats and reviewed profile selector visible initially above fixed footer');return evidence;
  });
  await check('exceptions no uncaught page errors',async()=>assert.deepEqual([...new Set(exceptions)],[]));
}catch(error){checks.push({name:'setup/completion',pass:false,error:error.stack,detail:await diagnostic?.().catch(()=>null)});console.error(error.stack);}
finally{socket?.close();browser.kill();await writeFile(path.join(out,only.size?'results-'+[...only].join('-')+'.json':'results.json'),JSON.stringify({checkedAt:new Date().toISOString(),checks,exceptions},null,2)+'\n');}
const failed=checks.filter(c=>!c.pass);console.log(`${checks.length-failed.length}/${checks.length} plan update checks passed.`);process.exitCode=failed.length?1:0;
