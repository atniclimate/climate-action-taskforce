// Focused scanner integration smoke; serve only site/ on 127.0.0.1:8765.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';
const out=fileURLToPath(new URL('../work/review/scanner-integration-browser/',import.meta.url));
const read=async file=>JSON.parse(await readFile(new URL('../site/'+file,import.meta.url),'utf8'));
const catalog=await read('data/explorer/catalog.json'),risk=await read('data/risk.json');
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
  await send('Page.enable');await send('Runtime.enable');await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  const evaluate=async expression=>{const value=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||value.exceptionDetails.text);return value.result.value;};
  const wait=async(expression)=>{const start=Date.now();while(Date.now()-start<12000){if(await evaluate(expression))return;await pause(80);}throw Error('Timed out: '+expression);};
  const text=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)})?.textContent||''`);
  const change=async(selector,value)=>{await evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('change',{bubbles:true}));})()`);await pause(100);};
  const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
  const route=async hash=>{await evaluate(`location.hash=${JSON.stringify(hash)}`);await pause(200);};
  const scroll=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).scrollIntoView({block:'start'})`);
  const shot=async name=>{const result=await send('Page.captureScreenshot',{format:'png'});await writeFile(path.join(out,name+'.png'),Buffer.from(result.data,'base64'));};
  const width=async value=>{await send('Emulation.setDeviceMetricsOverride',{width:value,height:900,deviceScaleFactor:1,mobile:false});await pause(100);};
  diagnostic=()=>evaluate("({hash:location.hash,text:document.querySelector('.chapter.is-active')?.innerText||document.body.innerText,overflow:document.documentElement.scrollWidth-innerWidth})");
  const regionReady=async row=>{await wait(`document.querySelector('[data-scanner-result] h3')?.textContent===${JSON.stringify(row.region_name)}`);};
  await width(1440);await send('Page.navigate',{url:'http://127.0.0.1:8765/#risks/explore'});await wait("!!document.querySelector('[data-nation]')");
  await check('hazards all nine states and excluded placeholder',async()=>{
    const nation=risk.nations.find(n=>n.hazards.some(h=>h.status==='placeholder'));
    await route('#risks/explore');await change('[data-nation]',nation.tribe_id);await wait(`document.querySelector('[data-risk-result] h2')?.textContent===${JSON.stringify(nation.display_name)}`);
    const rows=await evaluate("[...document.querySelectorAll('[data-risk-result] .hazard-index-table tbody tr')].map(el=>({label:el.querySelector('th').textContent,value:el.querySelector('td').textContent}))");
    assert.equal(rows.length,9);for(const hazard of nation.hazards){const row=rows.find(row=>row.label.startsWith(hazard.hazard_name));assert.ok(row);assert.ok(row.label.includes(hazard.status));assert.equal(row.value,hazard.status==='modeled'&&hazard.value!==null?hazard.value.toFixed(3):'Unavailable');}
    await scroll('[data-risk-result]');await shot('desktop-hazards');return {nation:nation.tribe_id,statuses:nation.hazards.map(h=>h.status)};
  });
  await route('#risks/regions');await wait("!!document.querySelector('[data-scanner-region]')");
  await check('regional populated empty Water and Alaska support',async()=>{
    const populated=catalog.scanner_climate.ecoregions.find(r=>r.region_id==='10.1.2'),empty=catalog.scanner_climate.ecoregions.find(r=>r.status!=='available'),water=catalog.scanner_climate.ecoregions.find(r=>r.category==='water');
    await change('[data-taxonomy]','ecoregions');await change('[data-scanner-region]',populated.region_id);await regionReady(populated);
    assert.equal(await evaluate("document.querySelectorAll('[data-scanner-result] .pathway-track').length"),2);assert.match(await text('[data-scanner-result]'),/8 unique climate source areas/);assert.match(await text('[data-scanner-result]'),/not a probability interval/);await scroll('[data-explorer-component=scanner-regions]');await shot('desktop-region');
    await change('[data-scanner-region]',empty.region_id);await regionReady(empty);assert.equal(await evaluate("document.querySelectorAll('[data-scanner-result] .pathway-track').length"),0);assert.match(await text('[data-scanner-result]'),/No supported climate source areas/);assert.match(await text('[data-scanner-result]'),/Unavailable/);await shot('desktop-empty');
    await change('[data-scanner-region]',water.region_id);await regionReady(water);assert.match(await text('[data-scanner-result]'),/Water is a separate source category/);await shot('desktop-water');
    const alaska=catalog.scanner_climate.advocacy_regions.find(r=>/alaska/i.test(r.region_name));await change('[data-taxonomy]','advocacy_regions');await change('[data-scanner-region]',alaska.region_id);await regionReady(alaska);assert.match(await text('[data-scanner-result]'),/218 unique climate source areas/);assert.match(await text('[data-scanner-result]'),/sea ice, subsistence and access/);assert.match(await text('[data-scanner-result]'),/Whole-Nation physical screening scores/);await shot('desktop-alaska');return {populated:populated.region_id,empty:empty.region_id,water:water.region_id,alaska:alaska.region_id};
  });
  await check('keyboard region controls retain route and accept arrows',async()=>{
    await evaluate("document.querySelector('[data-scanner-metric]').focus()");const before=await evaluate('location.hash');
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowDown',code:'ArrowDown',windowsVirtualKeyCode:40});await pause(150);assert.equal(await evaluate("document.querySelector('[data-scanner-metric]').value"),'pr_annual');assert.equal(await evaluate('location.hash'),before);
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'Tab',code:'Tab',windowsVirtualKeyCode:9});assert.equal(await evaluate("document.activeElement.hasAttribute('data-scanner-period')"),true);
  });
  await check('pathway accepted levels extrema and export',async()=>{
    const place=catalog.places.find(p=>p.id===catalog.default_selection.place),area=catalog.areas[place.area_ids[0]];
    const selection={...catalog.default_selection,place:place.id,area:place.area_ids[0],family:area.family,baseline:area.baseline_id,compare:'',compareArea:'',story:''};
    await route('#scenarios/pathways?'+new URLSearchParams({s:'1',...selection}));await wait("!!document.querySelector('[data-pathway-result] [data-export]')");
    assert.match(await text('.pathway-details'),/Accepted paired-model levels and full model span/);assert.equal(await evaluate("document.querySelectorAll('.pathway-details table').length"),2);
    await evaluate("(()=>{window.__exportText='';URL.createObjectURL=blob=>{blob.text().then(text=>window.__exportText=text);return 'blob:review'};HTMLAnchorElement.prototype.click=function(){};})()");await click('[data-export]');await wait('!!window.__exportText');const csv=await evaluate('window.__exportText');
    const accepted=await read(catalog.files[area.scanner_climate_file].path),projection=accepted.projections.find(p=>p.metric_id===selection.metric&&p.scenario==='ssp245'&&p.period.join('-')===selection.period);
    assert.match(csv,/baseline_median,period_median,change_min,change_max,spread_meaning/);for(const value of [projection.baseline_level.p50,projection.period_level.p50,projection.change.min,projection.change.max])assert.ok(csv.includes(String(value)),`CSV retains ${value}`);
    await click('.pathway-details summary');await scroll('[data-pathway-result]');await shot('desktop-pathway');await scroll('.pathway-details table:last-of-type');await evaluate("document.querySelectorAll('.pathway-details table')[1].scrollIntoView({block:'center'})");await shot('desktop-pathway-levels');return {place:place.id,area:place.area_ids[0]};
  });
  await check('costs hazard cell coverage and source version',async()=>{
    await route('#costs/county');await wait("document.querySelector('[data-cost-total]')?.textContent.includes('Hazard-cell coverage')");assert.match(await text('[data-cost-total]'),/unavailable is not zero/i);await scroll('[data-cost-total]');await shot('desktop-costs');
    await route('#costs/cohorts');await wait("!!document.querySelector('[data-cohort]')");
    for(const cohort of catalog.cohorts){await change('[data-cohort]',cohort.id);const coverage=cohort.costs.climate_county_eal_coverage;const value=await text('[data-cohort-result]');assert.ok(value.includes(coverage.supported_cells.toLocaleString('en-US')+' of '+coverage.possible_cells.toLocaleString('en-US')));assert.ok(value.includes(coverage.status));assert.ok(value.includes(cohort.costs.source_version));assert.match(value,/Missing cells are omitted, not zero/);}return catalog.cohorts.map(c=>({id:c.id,coverage:c.costs.climate_county_eal_coverage}));
  });
  await check('phone390 changed scanner views reflow',async()=>{
    await width(390);
    for(const [hash,selector,name] of [['#risks/explore','[data-risk-result]','hazards'],['#risks/regions','[data-explorer-component=scanner-regions]','regions'],['#scenarios/pathways','[data-pathway-result]','pathway'],['#costs/cohorts','[data-cohort-result]','costs']]){await route(hash);await wait(`!!document.querySelector(${JSON.stringify(selector)})`);await pause(200);await scroll(selector);assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),hash+' has horizontal overflow');await shot('phone390-'+name);if(name==='regions'){await scroll('[data-scanner-result] figure');await shot('phone390-region-chart');}}
  });
  await check('exceptions no uncaught page errors',async()=>assert.deepEqual([...new Set(exceptions)],[]));
}catch(error){checks.push({name:'setup/completion',pass:false,error:error.stack,detail:await diagnostic?.().catch(()=>null)});console.error(error.stack);}
finally{socket?.close();browser.kill();await writeFile(path.join(out,only.size?'results-'+[...only].join('-')+'.json':'results.json'),JSON.stringify({checkedAt:new Date().toISOString(),release:catalog.release_id,checks,exceptions},null,2)+'\n');}
const failed=checks.filter(c=>!c.pass);console.log(`${checks.length-failed.length}/${checks.length} scanner checks passed.`);process.exitCode=failed.length?1:0;
