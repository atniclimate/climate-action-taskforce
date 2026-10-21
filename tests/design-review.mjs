// Focused native-Chromium review of revised layouts. No packages or server startup.
import { spawn } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const phase = process.argv[2] || 'after';
const output = fileURLToPath(new URL('../work/review/design-review-artifacts/', import.meta.url));
const profile = path.join(output, 'browser-profile');
await mkdir(profile, { recursive: true });
const browser = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`,
  `--disk-cache-dir=${path.join(profile, 'cache')}`, '--no-first-run',
  '--no-default-browser-check', '--disable-background-networking', '--disable-sync',
  '--disable-breakpad', '--disable-crash-reporter', '--disable-component-update',
  '--disable-gpu-shader-disk-cache', '--password-store=basic', 'about:blank'
], { windowsHide: true, env: { ...process.env, TEMP: profile, TMP: profile } });
let stderr = '';
const endpoint = await new Promise((resolve, reject) => {
  const timer = setTimeout(() => reject(new Error(`Browser endpoint unavailable: ${stderr}`)), 15000);
  browser.stderr.on('data', chunk => {
    stderr += chunk;
    const match = stderr.match(/DevTools listening on (ws:\/\/[^\s]+)/);
    if (match) { clearTimeout(timer); resolve(match[1]); }
  });
  browser.once('error', reject);
});
const socket = new WebSocket(endpoint);
await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
let serial = 0;
const pending = new Map();
const exceptions = [];
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.id) {
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    clearTimeout(request.timer);
    message.error ? request.reject(new Error(JSON.stringify(message.error))) : request.resolve(message.result);
  }
  if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails);
};
function send(method, params = {}, sessionId) {
  return new Promise((resolve, reject) => {
    const id = ++serial;
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)); }, 15000);
    pending.set(id, { resolve, reject, timer });
    socket.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
  });
}
const { targetId } = await send('Target.createTarget', { url: 'about:blank' });
const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true });
const call = (method, params) => send(method, params, sessionId);
await call('Page.enable');
await call('Runtime.enable');
await call('Network.enable');
await call('Network.setCacheDisabled', { cacheDisabled: true });
const evaluate = async expression => {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(JSON.stringify(result.exceptionDetails));
  return result.result.value;
};
const waitFor = async expression => {
  for (let i = 0; i < 80; i++) {
    if (await evaluate(expression)) return;
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error(`Page condition not met: ${expression}`);
};
const shots = [];
const checks = [];
async function screenshot(name) {
  const { data } = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const filename = `${phase}-${name}.png`;
  await writeFile(path.join(output, filename), Buffer.from(data, 'base64'));
  shots.push(filename);
}
async function visit(mode, id) {
  await call('Page.navigate', { url: `http://127.0.0.1:8765/?mode=${mode}#${id}` });
  await waitFor(`document.querySelectorAll('.chapter').length === 18 && !!document.querySelector('#risks select') && !document.querySelector('.load-error')`);
  await evaluate('document.fonts.ready.then(() => true)');
  await new Promise(resolve => setTimeout(resolve, 150));
  await evaluate(`document.querySelector('#${id}').scrollIntoView({block:'start'})`);
}
try {
  if (phase === 'focused') {
    for (const width of [1440, 1920, 390, 720]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: width === 390 ? 844 : 1080, deviceScaleFactor: 1, mobile: false });
      await visit('participant', 'welcome');
      for (const stress of ['default', 'spacing', 'text200']) {
        await evaluate(`(() => {
          document.getElementById('review-spacing')?.remove();
          document.documentElement.style.fontSize='${stress === 'text200' ? '200%' : ''}';
          if ('${stress}' === 'spacing') {const style=document.createElement('style');style.id='review-spacing';style.textContent='*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}';document.head.append(style);}
          document.querySelectorAll('.domain-detail').forEach(el=>el.open=true);
        })()`);
        await evaluate('document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))');
        await new Promise(resolve => setTimeout(resolve, 100));
        checks.push(await evaluate(`({kind:'settled reflow',width:innerWidth,stress:'${stress}',scrollWidth:document.documentElement.scrollWidth,pageOverflow:document.documentElement.scrollWidth>innerWidth+1,headerHeight:Math.ceil(document.querySelector('.site-header').getBoundingClientRect().height),headerOffset:parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-height')),footerHeight:Math.ceil(document.querySelector('.presentation-controls').getBoundingClientRect().height),footerOffset:parseInt(getComputedStyle(document.documentElement).getPropertyValue('--control-height'))})`));
        if (width === 390) await screenshot(`390-${stress}`);
      }
      await evaluate('document.documentElement.style.fontSize="";document.getElementById("review-spacing")?.remove()');
      if (width !== 720) {
        for (const id of ['plans', 'recent-change', 'policy-demo']) {
          await visit('presenter', id);
          const selector = id === 'plans' ? '.recency-grid' : id === 'recent-change' ? '.context-comparison' : '.demo';
          await evaluate(`document.querySelector('${selector}').scrollIntoView({block:'start'})`);
          await screenshot(`${width}-${id}`);
        }
      }
    }
  }
  if (phase === 'debug') {
    for (const width of [390, 720]) {
    await call('Emulation.setDeviceMetricsOverride', { width, height: 844, deviceScaleFactor: 1, mobile: false });
    await visit('participant', 'welcome');
    await evaluate(`document.documentElement.style.fontSize='200%';document.querySelectorAll('.domain-detail').forEach(el=>el.open=true)`);
    await evaluate('document.fonts.ready.then(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))');
    await new Promise(resolve => setTimeout(resolve, 100));
    checks.push(await evaluate(`(() => {
      return {width:innerWidth,documentWidth:document.documentElement.scrollWidth,elements:[...document.querySelectorAll('body *')].filter(el => { const r=el.getBoundingClientRect();return r.width && (r.right>innerWidth+1 || r.left<0 || el.scrollWidth>el.clientWidth+1) && !el.closest('.table-scroll,.sr-only,dialog,.skip-link'); }).map(el=>({tag:el.tagName,cls:el.className,text:el.textContent.slice(0,100),width:el.getBoundingClientRect().width,right:el.getBoundingClientRect().right,scrollWidth:el.scrollWidth,clientWidth:el.clientWidth})).slice(0,80)};
    })()`));
    await screenshot(`${width}-root-text-200`);
    }
  }
  for (const [width, height] of (['debug','focused'].includes(phase) ? [] : [[1440, 900], [1920, 1080], [390, 844]])) {
    await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
    for (const mode of ['presenter', 'participant']) {
      for (const id of ['sequence', 'knowledge', 'risks', 'policy-demo', 'sovereignty', 'resources']) {
        await visit(mode, id);
        checks.push(await evaluate(`(() => {
          const section = document.getElementById('${id}');
          const nodes = [...section.querySelectorAll('.source-node')].map(el => ({top: el.getBoundingClientRect().top, height: el.getBoundingClientRect().height}));
          return {width: innerWidth, mode: document.body.dataset.mode, chapter:'${id}', pageOverflow: document.documentElement.scrollWidth > innerWidth + 1, nodes};
        })()`));
        await screenshot(`${width}-${mode}-${id}`);
      }
    }
  }
  if (phase === 'after') {
    // These are resize/reflow and spacing stress checks, not an assistive-technology audit.
    for (const width of [1440, 1920, 390]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: width === 390 ? 844 : 1080, deviceScaleFactor: 1, mobile: false });
      await visit('participant', 'welcome');
      checks.push(await evaluate(`(() => {
        const style = document.createElement('style'); style.id='review-spacing';
        style.textContent='*{line-height:1.5!important;letter-spacing:.12em!important;word-spacing:.16em!important}p{margin-bottom:2em!important}';
        document.head.append(style);
        return {width:innerWidth, stress:'WCAG text spacing', pageOverflow:document.documentElement.scrollWidth>innerWidth+1};
      })()`));
      await evaluate('document.getElementById("review-spacing").remove()');
      checks.push(await evaluate(`(() => {
        document.documentElement.style.fontSize='200%';
        return {width:innerWidth, stress:'200% root text size', pageOverflow:document.documentElement.scrollWidth>innerWidth+1};
      })()`));
      await new Promise(resolve => setTimeout(resolve, 100));
      checks.push(await evaluate(`(() => ({width:innerWidth, kind:'resized controls', headerHeight:Math.ceil(document.querySelector('.site-header').getBoundingClientRect().height), headerOffset:parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-height')), footerHeight:Math.ceil(document.querySelector('.presentation-controls').getBoundingClientRect().height), footerOffset:parseInt(getComputedStyle(document.documentElement).getPropertyValue('--control-height'))}))()`));
      if (width === 390) await screenshot('390-root-text-200');
      await evaluate('document.documentElement.style.fontSize=""');
    }
    for (const width of [1440, 1920, 390]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: width === 390 ? 844 : 1080, deviceScaleFactor: 1, mobile: false });
      await visit('presenter', 'policy-demo');
      for (let step = 0; step < 6; step++) {
        checks.push(await evaluate(`(() => ({width:innerWidth,kind:'policy step', step:${step+1}, visiblePanes:[...document.querySelectorAll('.policy-pane')].filter(el=>getComputedStyle(el).display!=='none').map(el=>el.dataset.pane), activePane:document.querySelector('.policy-pane[data-active="true"]').dataset.pane}))()`));
        await evaluate('document.querySelector("[data-demo-screen]").scrollIntoView({block:"start"})');
        await screenshot(`${width}-policy-step-${step+1}`);
        if (step < 5) await evaluate('document.querySelector("#policy-demo [data-next]").click()');
      }
      if (width === 390) {
        await evaluate('document.querySelector("#policy-demo [data-back]").click(); document.getElementById("policy-demo-note").value="Review source dates"');
        for (const pane of ['sources', 'results', 'issues', 'report']) {
          checks.push(await evaluate(`(() => { const select=document.querySelector('[data-policy-pane]');select.value='${pane}';select.dispatchEvent(new Event('change'));return {kind:'phone panel choice',pane:'${pane}',visiblePanes:[...document.querySelectorAll('.policy-pane')].filter(el=>getComputedStyle(el).display!=='none').map(el=>el.dataset.pane),note:document.getElementById('policy-demo-note').value};})()`));
        }
        await evaluate('document.querySelector(".policy-pane-selector").scrollIntoView({block:"start"})');
        await screenshot('390-policy-selector');
      }
      await visit('participant', 'risks');
      for (const region of ['national', 'southwest', 'alaska']) {
        for (const metric of ['frequency', 'mean']) {
          checks.push(await evaluate(`(() => {const region=document.querySelector('[data-region]');region.value='${region}';region.dispatchEvent(new Event('change'));const metric=document.querySelector('[data-risk-metric]');metric.value='${metric}';metric.dispatchEvent(new Event('change'));document.querySelector('[data-risk-result]').scrollIntoView({block:'start'});return {width:innerWidth,kind:'risk view',region:'${region}',metric:'${metric}',pageOverflow:document.documentElement.scrollWidth>innerWidth+1,rows:document.querySelectorAll('#risks .risk-row,#risks tbody tr').length};})()`));
          await screenshot(`${width}-risks-${region}-${metric}`);
        }
      }
      checks.push(await evaluate(`(async () => {const data=await fetch('data/risk.json').then(r=>r.json());const n=data.nations.find(n=>n.top_hazards.length===4);const select=document.querySelector('[data-nation]');select.value=n.tribe_id;select.dispatchEvent(new Event('change'));document.querySelector('[data-risk-result]').scrollIntoView({block:'start'});return {width:innerWidth,kind:'Nation missing hazards',name:n.display_name,unavailable:document.querySelector('.risk-missing').innerText,rows:document.querySelectorAll('#risks tbody tr').length,pageOverflow:document.documentElement.scrollWidth>innerWidth+1};})()`));
      await screenshot(`${width}-risks-nation-missing`);
      for (const id of ['welcome','strategy','costs','funding','plans','recent-change','ddm','development']) {
        await visit('presenter', id);
        if (['costs','funding','plans','recent-change'].includes(id)) await evaluate(`document.querySelector('#${id} .data-figure,#${id} .context-comparison').scrollIntoView({block:'start'})`);
        await screenshot(`${width}-additional-${id}`);
      }
    }
    await call('Emulation.setEmulatedMedia', { features: [{name:'prefers-reduced-motion',value:'reduce'}] });
    checks.push(await evaluate(`({kind:'reduced motion',matches:matchMedia('(prefers-reduced-motion: reduce)').matches,chapterAnimation:getComputedStyle(document.querySelector('.chapter')).animationName})`));
  }
  const result = { phase, shots, checks, exceptions, note:'Native headless Chrome. Physical projector, camera QR scan and screen reader not verified.' };
  await writeFile(path.join(output, `${phase}-results.json`), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({phase, screenshotCount: shots.length, checks, exceptions}));
} finally {
  await send('Browser.close').catch(() => {});
  socket.close();
}
