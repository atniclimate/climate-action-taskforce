// Focused integrated explorer review. Serve only site/ on 127.0.0.1:8765.
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import path from 'node:path';

const base='http://127.0.0.1:8765/';
const out=fileURLToPath(new URL('../work/review/explorer-browser/',import.meta.url));
const catalog=JSON.parse(await readFile(new URL('../site/data/explorer/catalog.json',import.meta.url),'utf8'));
await mkdir(out,{recursive:true});
const browser=spawn('C:/Program Files/Google/Chrome/Application/chrome.exe',[
  '--headless=new','--remote-debugging-port=0',`--user-data-dir=${path.join(out,`profile-${process.pid}`)}`,
  '--no-first-run','--no-default-browser-check','--disable-background-networking','--disable-sync','--disable-component-update','about:blank'
],{windowsHide:true});
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
const checks=[],exceptions=[],network=[];
const only=new Set((process.argv.find(arg=>arg.startsWith('--only='))||'').slice(7).split(',').filter(Boolean));
let socket,diagnostic,stage='first-map',heldRequest,holdURL,failLeafletOnce=false;
const relevant=url=>/\/(?:data\/explorer\/|assets\/explorer\/|assets\/vendor\/leaflet|components\/|state\/selection\.js|data\/catalog\.js|explorer\.js)/.test(url);
const check=async(name,run)=>{if(only.size&&!only.has(name.split(' ')[0]))return;try{const evidence=await run();checks.push({name,pass:true,evidence});console.log(`ok ${name}`);}catch(error){checks.push({name,pass:false,error:error.message});console.log(`FAIL ${name}: ${error.message}`);}};
try{
  const endpoint=await new Promise((resolve,reject)=>{
    let stderr='';const timer=setTimeout(()=>reject(Error(`No browser endpoint: ${stderr}`)),15000);
    browser.stderr.on('data',chunk=>{stderr+=chunk;const found=stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);if(found){clearTimeout(timer);resolve(found[1]);}});
    browser.once('error',reject);
  });
  socket=new WebSocket(endpoint);await new Promise((resolve,reject)=>{socket.onopen=resolve;socket.onerror=reject;});
  let serial=0,sessionId;const pending=new Map(),requests=new Map();
  const send=(method,params={},session=sessionId)=>new Promise((resolve,reject)=>{const id=++serial;pending.set(id,{resolve,reject});socket.send(JSON.stringify({id,method,params,...(session?{sessionId:session}:{})}));});
  socket.onmessage=event=>{
    const message=JSON.parse(event.data);
    if(pending.has(message.id)){const item=pending.get(message.id);pending.delete(message.id);message.error?item.reject(Error(JSON.stringify(message.error))):item.resolve(message.result);}
    const p=message.params;
    if(message.method==='Runtime.exceptionThrown')exceptions.push(p.exceptionDetails.exception?.description||p.exceptionDetails.text);
    if(message.method==='Network.requestWillBeSent'&&relevant(p.request.url)){const row={id:p.requestId,url:p.request.url,stage,bytes:0,complete:false};network.push(row);requests.set(p.requestId,row);}
    if(message.method==='Network.loadingFinished'&&requests.has(p.requestId))Object.assign(requests.get(p.requestId),{bytes:p.encodedDataLength,complete:true});
    if(message.method==='Network.loadingFailed'&&requests.has(p.requestId))Object.assign(requests.get(p.requestId),{error:p.errorText,complete:true});
    if(message.method==='Fetch.requestPaused'){if(failLeafletOnce&&p.request.url.includes('/leaflet.js')){failLeafletOnce=false;send('Fetch.failRequest',{requestId:p.requestId,errorReason:'Failed'}).catch(()=>{});}else if(holdURL&&p.request.url.includes(holdURL))heldRequest=p.requestId;else send('Fetch.continueRequest',{requestId:p.requestId}).catch(()=>{});}
  };
  const target=await send('Target.createTarget',{url:'about:blank'},null);
  ({sessionId}=await send('Target.attachToTarget',{targetId:target.targetId,flatten:true},null));
  await send('Page.enable');await send('Runtime.enable');await send('Network.enable');
  // Capture the real Leaflet instance through its public init hook, including reloads.
  await send('Page.addScriptToEvaluateOnNewDocument',{source:"Object.defineProperty(window,'L',{configurable:true,get(){return undefined},set(value){delete window.L;window.L=value;value.Map.addInitHook(function(){window.__reviewMap=this})}})"});
  await send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-motion',value:'reduce'}]});
  const evaluate=async expression=>{const value=await send('Runtime.evaluate',{expression,returnByValue:true,awaitPromise:true});if(value.exceptionDetails)throw Error(value.exceptionDetails.exception?.description||value.exceptionDetails.text);return value.result.value;};
  const wait=async(expression,timeout=12000)=>{const started=Date.now();while(Date.now()-started<timeout){if(await evaluate(expression))return;await pause(80);}throw Error(`Timed out: ${expression}`);};
  const quiet=async()=>{await pause(350);const started=Date.now();while(network.some(row=>!row.complete)&&Date.now()-started<12000)await pause(80);await pause(200);};
  const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click();true`);
  const change=(selector,value)=>evaluate(`(()=>{const el=document.querySelector(${JSON.stringify(selector)});el.value=${JSON.stringify(value)};el.dispatchEvent(new Event('change',{bubbles:true}));return true;})()`);
  const text=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)})?.textContent||''`);
  const shot=async name=>{const value=await send('Page.captureScreenshot',{format:'png'});await writeFile(path.join(out,`${name}.png`),Buffer.from(value.data,'base64'));};
  diagnostic=async()=>{await shot('failure');return evaluate("({hash:location.hash,place:document.querySelector('[data-explorer-component=place]')?.innerText,slots:[...document.querySelectorAll('[data-explorer-component]')].map(el=>({kind:el.dataset.explorerComponent,top:el.getBoundingClientRect().top,text:el.innerText.slice(0,600)}))})");};
  const route=async hash=>{if(!hash.includes('?')){const query=(await evaluate('location.hash')).split('?')[1];if(query)hash+='?'+query;}await evaluate(`location.hash=${JSON.stringify(hash)};true`);await pause(150);};
  const selectionHash=(place,extra={})=>{const area=catalog.areas[place.area_ids[0]];const raw={...catalog.default_selection,place:place.id,area:place.area_ids.length===1?place.area_ids[0]:'',family:area?.family||'native-nex',baseline:area?.baseline_id||'1995-2014',story:'',compare:'',compareArea:'',...extra};return '#scenarios/pathways?'+new URLSearchParams({s:'1',...raw});};
  const mapRoute=async()=>{await route('#risks/place');await evaluate("document.querySelector('[data-explorer-component=place]').scrollIntoView({block:'start'});true");await wait("!!document.querySelector('[data-place]')");};
  const choose=async place=>{await mapRoute();await click('[data-list-toggle]');await evaluate("(()=>{const el=document.querySelector('[data-search]');el.value='';el.dispatchEvent(new Event('input',{bubbles:true}));})()");await change('[data-place]',place.id);await wait(`document.querySelector('[data-place-readout] h2')?.textContent===${JSON.stringify(place.name)}`);await quiet();};
  const pathway=async()=>{const name=await text('[data-place-readout] h2');await click('.place-next');await evaluate("document.querySelector('[data-explorer-component=pathway]').scrollIntoView({block:'start'});true");await wait(`!!document.querySelector('[data-pathway-result]')&&document.querySelector('[data-pathway-result]').textContent.includes(${JSON.stringify(name)})`);};
  const completeChart=()=>wait("!!document.querySelector('[data-pathway-result] [data-export]')");
  const exportCSV=async()=>{
    await evaluate("(()=>{window.__exportText='';if(window.__captureExport)return;window.__captureExport=true;const original=URL.createObjectURL,click=HTMLAnchorElement.prototype.click;URL.createObjectURL=blob=>{blob.text().then(text=>window.__exportText=text);return original(blob)};HTMLAnchorElement.prototype.click=function(){if(!this.download)click.call(this)};})()");
    await click('[data-export]');await wait('!!window.__exportText');return evaluate('window.__exportText');
  };
  const nation=catalog.places.find(item=>item.id===catalog.default_selection.place);
  const proxy=catalog.places.find(item=>item.proxy&&item.area_ids.length===1);
  const missing=catalog.places.find(item=>item.kind==='nation'&&!item.area_ids.length);
  const multi=catalog.places.find(item=>item.area_ids.length>1);
  const navajo=catalog.places.find(item=>/Navajo/i.test(item.name));
  const alaska=catalog.places.find(item=>item.kind==='nation'&&item.area_ids.length===1&&catalog.areas[item.area_ids[0]]?.view==='alaska');
  const hawaii=catalog.places.find(item=>item.view==='hawaii'||item.area_ids.some(id=>catalog.areas[id]?.view==='hawaii'));
  const regional=catalog.places.find(item=>item.kind==='region'&&catalog.areas[item.area_ids[0]]?.family==='usgs-nccv-loca2');
  const native=catalog.places.filter(item=>item.kind==='nation'&&item.area_ids.length===1&&!item.proxy&&catalog.areas[item.area_ids[0]]?.status==='available');
  await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});
  await send('Page.navigate',{url:base+'#risks/place'});
  await wait("!!document.querySelector('#risks [data-risk-result] h2')");await pause(400);
  await check('initial place deep link remains in view after data loads',async()=>assert.ok(await evaluate("(()=>{const box=document.querySelector('[data-explorer-component=place]').getBoundingClientRect();return box.top<innerHeight&&box.bottom>document.querySelector('.site-header').offsetHeight})()"),'async chapter growth moved named place target offscreen'));
  await evaluate("document.querySelector('[data-explorer-component=place]').scrollIntoView({block:'start'});true");
  await wait("!!document.querySelector('.leaflet-container')&&!!document.querySelector('[data-map-source]')?.textContent");await quiet();
  await check('first map network budget',async()=>{const rows=network.filter(row=>row.stage==='first-map');const bytes=rows.reduce((sum,row)=>sum+row.bytes,0);assert.ok(rows.length<=12,`${rows.length} requests exceeds12`);assert.ok(bytes<=2*1024*1024,`${bytes} bytes exceeds2MiB`);return {requests:rows.length,bytes};});
  await check('map, readout and list agree',async()=>{assert.equal(await text('[data-place-readout] h2'),nation.name);assert.equal(await evaluate("document.querySelector('[data-place]').value"),nation.id);assert.ok(await evaluate("document.querySelectorAll('.place-map .leaflet-overlay-pane path').length>0"));await shot('desktop-map');});
  stage='next-selection';await choose(native.find(item=>item.id!==nation.id));
  await check('typical next selection budget',async()=>{const rows=network.filter(row=>row.stage==='next-selection');const bytes=rows.reduce((sum,row)=>sum+row.bytes,0);assert.ok(bytes<=512*1024,`${bytes} bytes exceeds512KiB`);return {requests:rows.length,bytes};});
  stage='interactions';
  await check('shared source-area marker preserves explicit Nation identity',async()=>{
    const shared=catalog.places.find(place=>place.shared&&place.area_ids.length===1&&catalog.places.find(item=>item.area_ids.includes(place.area_ids[0]))?.id!==place.id);
    assert.ok(shared);await choose(shared);
    await evaluate("(()=>{const marker=document.querySelector('.place-map path.leaflet-interactive[stroke=\"#a84018\"][stroke-width=\"3\"]');if(!marker)throw Error('Selected shared marker absent');marker.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true}));})()");
    await pause(250);assert.equal(await text('[data-place-readout] h2'),shared.name,'marker must not silently substitute another Nation sharing this source area');
  });
  await choose(nation);await pathway();await completeChart();
  await check('Native pathways, table, export and planning action',async()=>{
    assert.equal(await evaluate("document.querySelectorAll('.pathway-row').length"),2);
    assert.match(await text('.pathway-scope'),/Native Resilience/);
    assert.match(await text('[data-pathway-result]'),/SSP2-4\.5/);assert.match(await text('[data-pathway-result]'),/SSP3-7\.0/);
    await click('.pathway-details summary');assert.equal(await evaluate("document.querySelectorAll('.pathway-details tbody tr').length"),2);
    const csv=await exportCSV();assert.ok(csv.includes(nation.name));assert.match(csv,/SSP2-4\.5/);assert.match(csv,/SSP3-7\.0/);
    await shot('desktop-pathways');await click('[data-pathway-result] a[href="#priorities"]');assert.equal(await evaluate("document.querySelector('#priority-note').value"),'');assert.ok((await evaluate('location.hash')).startsWith('#priorities?'));assert.ok(!(await evaluate('location.hash')).includes('note='));
  });
  await check('proxy disclosure survives place to pathway and CSV',async()=>{await choose(proxy);assert.match(await text('[data-place-readout]'),/proxy/i);await pathway();await completeChart();assert.match(await text('[data-pathway-result] .pathway-proxy'),/proxy|borrowed/i);const csv=await exportCSV();assert.match(csv,/mapping_status,mapping_caution/);assert.ok(csv.includes(proxy.mapping_caution));assert.match(csv,/,"proxy",/);});
  await check('unmapped Nation remains listed without fabricated chart',async()=>{await choose(missing);await pathway();await wait("document.querySelector('[data-pathway-result] .notice')");assert.ok(!(await evaluate("!!document.querySelector('[data-pathway-result] .pathway-track')")));assert.match(await text('[data-pathway-result]'),/match|unavailable|unmapped|No unambiguous.*association/i);});
  await check('multiple source areas require explicit choice',async()=>{assert.ok(multi);await choose(multi);assert.equal(await evaluate("document.querySelector('[data-area]').value"),'');await pathway();await wait("document.querySelector('[data-pathway-result] .notice')");assert.match(await text('[data-pathway-result]'),/several source areas/);await mapRoute();await change('[data-area]',multi.area_ids[0]);await pathway();await completeChart();});
  for(const [name,place] of [['navajo',navajo],['alaska',alaska],['hawaii',hawaii]])await check(`${name} geographic support`,async()=>{
    assert.ok(place,`${name} fixture exists`);await choose(place);assert.equal(await text('[data-place-readout] h2'),place.name);assert.ok(await evaluate("!!document.querySelector('[data-map-source]').textContent"));
    if(name==='hawaii'){
      assert.equal(place.kind,'reference');assert.match(await text('[data-place-readout]'),/Reference geography only; no Nation association or climate projection/);
      assert.ok(await evaluate("document.querySelectorAll('.place-map .leaflet-overlay-pane path[stroke=\"#586f39\"]').length>=12"),'all twelve climate-division reference shapes render');
    }
    await evaluate("document.querySelector('.place-map').scrollIntoView({block:'center'});true");await shot(`map-${name}`);
    if(name==='hawaii'){await pathway();await wait("document.querySelector('[data-pathway-result] .notice')");assert.ok(!(await evaluate("!!document.querySelector('[data-pathway-result] .pathway-track')")),'reference view must not fabricate climate projections');}
    return {place:place.id,areas:place.area_ids};
  });
  await check('regional and Native families remain distinct; annual axis reflows',async()=>{
    await choose(nation);await pathway();await completeChart();await change('[data-compare]',regional.id);await wait("document.querySelector('[data-pathway-result] .notice')");assert.match(await text('[data-pathway-result]'),/different source families or baselines/);
    await choose(regional);await pathway();await change('[data-compare]','');await completeChart();assert.match(await text('.pathway-scope'),/USGS NCCV/);assert.ok(await evaluate("!!document.querySelector('.annual-chart')"));assert.match(await text('[data-place-readout]'),/Regional context/);
    const evidence=[];
    for(const width of [1440,320,390]){
      await send('Emulation.setDeviceMetricsOverride',{width,height:900,deviceScaleFactor:1,mobile:false});await pause(200);
      const axis=await evaluate("(()=>{const spans=[...document.querySelectorAll('.annual-axis span')].map(el=>el.getBoundingClientRect()),chart=document.querySelector('.annual-chart').getBoundingClientRect();return {labels:spans.map(b=>({left:b.left,right:b.right,top:b.top,bottom:b.bottom})),chart:{left:chart.left,right:chart.right,top:chart.top,bottom:chart.bottom},overflow:document.documentElement.scrollWidth>innerWidth+1}})()");
      assert.equal(axis.overflow,false,`${width}px annual document has no horizontal overflow`);assert.equal(axis.labels.length,2);assert.ok(axis.labels.every(label=>label.right<=axis.chart.left),`${width}px values sit left of annual chart`);assert.ok(axis.labels[0].bottom<axis.labels[1].top,`${width}px high/low values are vertically separated`);assert.ok(Math.abs(axis.labels[0].top-axis.chart.top)<2&&Math.abs(axis.labels[1].bottom-axis.chart.bottom)<2,`${width}px axis endpoints align with plot bounds`);
      await evaluate("document.querySelector('[data-pathway-result]').scrollIntoView({block:'start'});true");await shot(width===1440?'regional-annual':`${width}-regional-annual`);evidence.push({width,...axis});
    }
    await send('Emulation.setDeviceMetricsOverride',{width:1440,height:900,deviceScaleFactor:1,mobile:false});return evidence;
  });
  await check('selection reload and Back/Forward restore readout and Alaska extent',async()=>{
    const mapState=()=>evaluate("(()=>{const map=window.__reviewMap,b=map.getBounds(),c=map.getCenter();return {bounds:[b.getSouth(),b.getWest(),b.getNorth(),b.getEast()],center:[c.lat,c.lng],zoom:map.getZoom()}})()");
    await choose(nation);await choose(proxy);const before=await evaluate('location.hash');await choose(alaska);
    await evaluate('history.back();true');await wait(`document.querySelector('[data-place-readout] h2')?.textContent===${JSON.stringify(proxy.name)}`);assert.equal(await evaluate('location.hash'),before);
    await evaluate('history.forward();true');await wait(`document.querySelector('[data-place-readout] h2')?.textContent===${JSON.stringify(alaska.name)}`);await quiet();
    const expected=await mapState();assert.ok(expected.center[0]>50&&expected.center[1]<-129,'selected map is centered on Alaska before reload');
    const area=await evaluate("document.querySelector('[data-area]').value");assert.equal(area,alaska.area_ids[0]);
    assert.ok(!new URLSearchParams((await evaluate('location.hash')).split('?')[1]).has('story'),'cleared story is omitted from shared URL');
    await send('Page.reload');await wait(`document.querySelector('[data-place-readout] h2')?.textContent===${JSON.stringify(alaska.name)}`);await wait("!!document.querySelector('[data-map-source]')?.textContent");await quiet();
    assert.equal(await evaluate("document.querySelector('[data-area]').value"),area,'source area survives reload');
    const restored=await mapState();assert.equal(restored.zoom,expected.zoom);restored.bounds.forEach((value,i)=>assert.ok(Math.abs(value-expected.bounds[i])<1e-6,'actual Leaflet bounds remain Alaska after reload'));
    assert.ok(!(await text('[data-map-status]')).includes('Columbia'),'default story must not return after reload');return {place:alaska.id,area,before:expected,after:restored};
  });
  await check('retry recovers after one Leaflet script failure',async()=>{
    failLeafletOnce=true;await send('Network.setCacheDisabled',{cacheDisabled:true});await send('Fetch.enable',{patterns:[{urlPattern:'*/leaflet.js',requestStage:'Request'}]});
    await send('Page.navigate',{url:base+'?review-map-retry=1#risks/place'});await wait("!!document.querySelector('[data-map-retry]')");assert.equal(failLeafletOnce,false,'Leaflet request was deliberately failed');
    assert.match(await text('[data-map-status]'),/could not load/);assert.ok(await evaluate("!document.querySelector('.place-search').hidden"),'place list remains available');
    await choose(proxy);assert.equal(await text('[data-place-readout] h2'),proxy.name);await click('[data-map-retry]');await wait("!!document.querySelector('.leaflet-container')&&!!document.querySelector('[data-map-source]')?.textContent");await quiet();
    assert.equal(await text('[data-place-readout] h2'),proxy.name);assert.equal(await evaluate("document.querySelector('[data-area]').value"),proxy.area_ids[0]);assert.ok(!(await evaluate("!!document.querySelector('[data-map-retry]')")));await shot('map-retry-recovered');
    await send('Fetch.disable');await send('Network.setCacheDisabled',{cacheDisabled:false});return {place:proxy.id,area:proxy.area_ids[0]};
  });
  await check('invalid shared selection is explicit and recoverable',async()=>{await route('#risks/place?s=1&release=old&place=missing');await wait("!!document.querySelector('[data-place-readout] .notice')");assert.match(await text('[data-place-readout]'),/different data release|not in this release/);await choose(nation);assert.equal(await text('[data-place-readout] h2'),nation.name);});
  await check('late selection response cannot replace current result',async()=>{
    const [slow,fast]=native.slice(-2);holdURL=catalog.files[catalog.areas[slow.area_ids[0]].file_id].path;
    await send('Fetch.enable',{patterns:[{urlPattern:'*'+holdURL,requestStage:'Request'}]});
    await route(selectionHash(slow));await wait('!!document.querySelector("[data-pathway-result]")');
    const started=Date.now();while(!heldRequest&&Date.now()-started<8000)await pause(80);assert.ok(heldRequest,'uncached request intercepted');
    await route(selectionHash(fast));await completeChart();assert.ok((await text('[data-pathway-result] h2')).includes(fast.name));
    await send('Fetch.continueRequest',{requestId:heldRequest}).catch(()=>{});holdURL=null;await send('Fetch.disable');await pause(500);assert.ok((await text('[data-pathway-result] h2')).includes(fast.name));
  });
  await check('loaded data works offline; uncached data fails honestly and retries',async()=>{
    const cached=native.at(-1),cold=native.at(-3);await route(selectionHash(cached));await completeChart();
    await send('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:-1,uploadThroughput:-1});
    await change('[data-period]',catalog.periods[0].id);await completeChart();
    await route(selectionHash(cold));await wait("!!document.querySelector('[data-retry]')");assert.ok(!(await evaluate("!!document.querySelector('[data-pathway-result] .pathway-track')")));
    await send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});await click('[data-retry]');await completeChart();
  });
  await send('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  await check('reduced motion and map keyboard isolation',async()=>{
    await send('Page.navigate',{url:base+'?mode=presenter#risks/place'});await wait("!!document.querySelector('.leaflet-container')");
    assert.ok(await evaluate("matchMedia('(prefers-reduced-motion: reduce)').matches"));assert.equal(await evaluate("document.querySelectorAll('.chapter.is-entering').length"),0);
    await evaluate("document.querySelector('[data-map-keys]').focus();true");const hash=await evaluate('location.hash');
    await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});assert.equal(await evaluate('location.hash'),hash);
    await evaluate("document.activeElement.blur();true");await send('Input.dispatchKeyEvent',{type:'keyDown',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});await send('Input.dispatchKeyEvent',{type:'keyUp',key:'ArrowRight',code:'ArrowRight',windowsVirtualKeyCode:39});await wait("location.hash.startsWith('#risks/reading')");
  });
  for(const width of [320,390])await check(`${width}px participant map to pathway to action`,async()=>{
    await send('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:false});await send('Page.navigate',{url:base+'#risks/place'});await wait("!!document.querySelector('.leaflet-container')");await choose(nation);
    assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'map document has no horizontal overflow');
    await evaluate("document.querySelector('.place-map').scrollIntoView({block:'start'});true");await shot(`${width}-map`);await pathway();await completeChart();assert.ok(await evaluate('document.documentElement.scrollWidth<=innerWidth+1'),'pathway document has no horizontal overflow');await evaluate("document.querySelector('[data-pathway-result]').scrollIntoView({block:'start'});true");await shot(`${width}-pathways`);await click('[data-pathway-result] a[href="#priorities"]');assert.ok((await evaluate('location.hash')).startsWith('#priorities?'));
  });
  await check('no uncaught page exceptions',async()=>assert.deepEqual([...new Set(exceptions)],[]));
}catch(error){const detail=await diagnostic?.().catch(()=>null);checks.push({name:'review setup/completion',pass:false,error:error.stack,detail});console.error(error.stack);if(detail)console.error(JSON.stringify(detail));}
finally{socket?.close();browser.kill();await writeFile(path.join(out,only.size?`results-${[...only].join('-')}.json`:'results.json'),JSON.stringify({checkedAt:new Date().toISOString(),release:catalog.release_id,checks,network,exceptions},null,2)+'\n');}
const failed=checks.filter(item=>!item.pass);console.log(`${checks.length-failed.length}/${checks.length} explorer checks passed.`);process.exitCode=failed.length?1:0;
