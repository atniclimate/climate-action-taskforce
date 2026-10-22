// Focused UI regressions; preview must serve site/ at 127.0.0.1:8765.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const output = fileURLToPath(new URL('../work/review/ui-reflow/', import.meta.url));
await mkdir(output, { recursive: true });
const browser = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${path.join(output, `profile-${process.pid}`)}`,
  '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
  '--disable-sync', '--disable-component-update', 'about:blank'
], { windowsHide: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const results = [];
let socket;
try {
  const endpoint = await new Promise((resolve, reject) => {
    let stderr = '';
    const timer = setTimeout(() => reject(new Error(`Browser endpoint unavailable: ${stderr}`)), 15000);
    browser.stderr.on('data', chunk => {
      stderr += chunk;
      const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (match) { clearTimeout(timer); resolve(match[1]); }
    });
    browser.once('error', reject);
  });
  socket = new WebSocket(endpoint);
  await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
  let serial = 0;
  const pending = new Map();
  socket.onmessage = event => {
    const message = JSON.parse(event.data);
    if (!pending.has(message.id)) return;
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
  };
  const send = (method, params = {}, sessionId) => new Promise((resolve, reject) => {
    const id = ++serial;
    pending.set(id, { resolve, reject });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
  const call = (method, params) => send(method, params, sessionId);
  await call('Page.enable');
  await call('Runtime.enable');
  await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
  const evaluate = async expression => {
    const value = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
    if (value.exceptionDetails) throw new Error(value.exceptionDetails.text);
    return value.result.value;
  };
  const ddmOnly=process.argv.includes('--ddm-only');
  if(ddmOnly) for(const width of [320,390]){
    await call('Emulation.setDeviceMetricsOverride',{width,height:844,deviceScaleFactor:1,mobile:false});
    await call('Page.navigate',{url:`http://127.0.0.1:8765/?reflow=${Date.now()}#ddm`});
    await pause(750);
    await evaluate('document.fonts.ready.then(() => true)');
    const briefing=await evaluate(`(() => {const root=document.querySelector('#ddm');const rows=[...root.querySelectorAll('.ddm-workflow li')];return {count:rows.length,stacked:rows.every((row,index)=>!index||row.getBoundingClientRect().top>=rows[index-1].getBoundingClientRect().bottom),contained:rows.every(row=>row.getBoundingClientRect().right<=innerWidth),launch:root.querySelector('.lead a')?.href,docWidth:document.documentElement.scrollWidth};})()`);
    assert.equal(briefing.count,3);
    assert.ok(briefing.stacked&&briefing.contained,'DDM briefing reads as three phone-width steps');
    assert.ok(briefing.launch?.startsWith('https://'),'DDM launches directly from its introduction');
    assert.ok(briefing.docWidth<=width+1,'DDM phone has no document overflow');
    if(process.argv.includes('--shots')){
      await evaluate("document.querySelector('#ddm .ddm-briefing').scrollIntoView({block:'start'});true");
      const shot=await call('Page.captureScreenshot',{format:'png'});
      await writeFile(path.join(output,`${width}-ddm.png`),Buffer.from(shot.data,'base64'));
    }
    results.push({width,chapter:'ddm',...briefing});
    console.log(`ok ${width}px DDM: stacked briefing and early launch`);
  }
  for (const [width, stress] of ddmOnly?[]:[[320, 'normal'], [390, 'normal'], [800, 'normal'], [1440, 'normal'], [320, 'text200'], [390, 'text200'], [390, 'spacing']]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height: 844, deviceScaleFactor: 1, mobile: false });
    await call('Page.navigate', { url: `http://127.0.0.1:8765/?reflow=${Date.now()}#funding` });
    await pause(750);
    await evaluate(`document.fonts.ready.then(() => true)`);
    await evaluate(`new Promise((resolve, reject) => { const started=Date.now(); const poll=()=>document.querySelectorAll('#funding .risk-row').length===9&&document.querySelector('#plans .plan-facts') ? resolve(true) : Date.now()-started>10000 ? reject(Error('Chapter data did not load')) : setTimeout(poll,50); poll(); })`);
    await evaluate(`(() => {const style=document.createElement('style');style.textContent=${JSON.stringify(stress === 'text200' ? ':root{font-size:200%!important}' : stress === 'spacing' ? '*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}' : '')};document.head.append(style);})()`);
    const charts = await evaluate(`(() => {
      const within=el=>{const r=el.getBoundingClientRect();return r.left>=-1&&r.right<=innerWidth+1};
      const rows=[...document.querySelectorAll('#funding .risk-row')];
      const axes=[...document.querySelectorAll('#funding .risk-axis')].map(axis=>[...axis.children].filter(el=>getComputedStyle(el).display!=='none').map(el=>({left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right,text:el.textContent})));
      return {rows:rows.length,complete:rows.every(row=>row.querySelector('.risk-value').textContent&&row.querySelector('.risk-note').textContent),contained:[...document.querySelectorAll('#funding .risk-row,#funding .risk-row>*,#funding .risk-axis')].every(within),axes,documentWidth:document.documentElement.scrollWidth,overflow:[...document.querySelectorAll('body *')].filter(el=>el.offsetParent&&!el.closest('.table-scroll')&&!within(el)).slice(-20).map(el=>el.tagName+'.'+el.className+' '+el.textContent.slice(0,65))};
    })()`);
    assert.equal(charts.rows, 9);
    assert.ok(charts.complete, `${width}/${stress}: amounts and coverage retained`);
    assert.ok(charts.contained, `${width}/${stress}: funding rows stay within the viewport`);
    for (const axis of charts.axes) for (let i = 1; i < axis.length; i++) assert.ok(axis[i].left >= axis[i-1].right + 4, `${width}/${stress}: axis ticks do not overlap`);
    if (stress === 'normal') assert.ok(charts.documentWidth <= width + 1, `${width}: no document overflow (${charts.documentWidth}): ${JSON.stringify(charts.overflow)}`);
    await evaluate(`location.hash='#plans';true`);
    const facts = await evaluate(`(() => [...document.querySelectorAll('#plans .plan-facts>div')].every(row=>{const [dt,dd]=row.children;return innerWidth>800||dd.getBoundingClientRect().top>=dt.getBoundingClientRect().bottom-1}))()`);
    assert.ok(facts, `${width}/${stress}: plan values stack under labels`);
    await evaluate(`location.hash='#policy-demo';true`);
    for (let i = 0; i < 5; i++) await evaluate(`document.querySelector('#policy-demo [data-next]').click();true`);
    const preview = await evaluate(`(() => { const el=document.querySelector('#policy-demo .demo-paper');const r=el.getBoundingClientRect();return {width:r.width,inside:r.left>=-1&&r.right<=innerWidth+1,scroll:el.scrollWidth<=el.clientWidth+1}; })()`);
    assert.ok(preview.inside && preview.scroll, `${width}/${stress}: Policy preview contained`);
    if (width <= 390) assert.ok(preview.width >= width * .52, `${width}/${stress}: Policy retains usable text width (${preview.width})`);
    if(width===390&&stress==='normal'){
      const annotation='Verify heat & smoke <capacity> with the facility lead.';
      await evaluate(`(() => {document.querySelector('#policy-demo [data-back]').click();const input=document.querySelector('[data-policy-note]');input.value=${JSON.stringify(annotation)};input.dispatchEvent(new Event('input',{bubbles:true}));document.querySelector('#policy-demo [data-next]').click();})()`);
      assert.equal(await evaluate(`document.querySelector('#policy-demo .policy-saved-note').textContent`),annotation);
      await evaluate(`document.querySelector('#policy-demo [data-policy-reset]').click();document.querySelector('#policy-demo [data-next]').click();true`);
      assert.equal(await evaluate(`document.querySelector('[data-policy-note]').value`),'');
      await evaluate(`document.querySelector('#policy-demo [data-next]').click();true`);
    }
    if (process.argv.includes('--shots') && width === 390) {
      await evaluate(`document.querySelector('#policy-demo .demo-paper').scrollIntoView({block:'center'});true`);
      const { data } = await call('Page.captureScreenshot', { format: 'png' });
      await writeFile(path.join(output, `${width}-${stress}-policy.png`), Buffer.from(data, 'base64'));
      await evaluate(`document.querySelector('#funding .region-columns').scrollIntoView({block:'start'});true`);
      const shot = await call('Page.captureScreenshot', { format: 'png' });
      await writeFile(path.join(output, `${width}-${stress}-funding.png`), Buffer.from(shot.data, 'base64'));
    }
    results.push({ width, stress, charts: charts.rows, previewWidth: preview.width, documentWidth: charts.documentWidth, overflow:charts.overflow });
    console.log(`ok ${width}px ${stress}: funding ticks/rows, plan facts, Policy preview`);
  }
  await writeFile(path.join(output,ddmOnly?'results-ddm.json':'results.json'), JSON.stringify({ checkedAt: new Date().toISOString(), results }, null, 2) + '\n');
} finally {
  socket?.close();
  browser.kill();
}
