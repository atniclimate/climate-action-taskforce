// Presenter no-scroll check: every slide (and every walkthrough step) must fit between header and footer.
// Usage: node tests/presenter-fit.mjs [chapter-id ...] [--shots]   (needs the local preview on 127.0.0.1:8765)
import { spawn } from 'node:child_process';
import { mkdir, writeFile, rm } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const args = process.argv.slice(2);
const shots = args.includes('--shots');
const only = new Set(args.filter(arg => !arg.startsWith('--')));
const viewports = [[1366, 768], [1440, 800], [1920, 970]];
const output = fileURLToPath(new URL('../work/review/presenter-fit/', import.meta.url));
const profile = path.join(output, `profile-${process.pid}`);
await mkdir(profile, { recursive: true });

const browser = spawn('C:/Program Files/Google/Chrome/Application/chrome.exe', [
  '--headless=new', '--remote-debugging-port=0', `--user-data-dir=${profile}`, '--no-first-run',
  '--no-default-browser-check', '--disable-background-networking', '--disable-sync', '--disable-component-update', 'about:blank'
], { windowsHide: true });
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
const problems = [];
socket.onmessage = event => {
  const message = JSON.parse(event.data);
  if (message.id && pending.has(message.id)) {
    const { resolve, reject } = pending.get(message.id);
    pending.delete(message.id);
    message.error ? reject(new Error(JSON.stringify(message.error))) : resolve(message.result);
  }
  if (message.method === 'Runtime.exceptionThrown') problems.push(`exception: ${message.params.exceptionDetails.exception?.description || message.params.exceptionDetails.text}`);
  if (message.method === 'Runtime.consoleAPICalled' && message.params.type === 'error') problems.push(`console.error: ${message.params.args.map(arg => arg.value ?? arg.description).join(' ')}`);
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
await call('Network.setCacheDisabled', { cacheDisabled: true });
await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] });
const evaluate = async expression => {
  const result = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (result.exceptionDetails) throw new Error(result.exceptionDetails.exception?.description || result.exceptionDetails.text);
  return result.result.value;
};
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));

// Height of the visible slide versus the space between the sticky header and the fixed footer.
const measure = `(() => {
  const section = [...document.querySelectorAll('.chapter')].find(item => !item.hidden);
  const avail = innerHeight - document.querySelector('.site-header').offsetHeight - document.querySelector('.presentation-controls').offsetHeight;
  const bottom = Math.max(...[...section.querySelectorAll('.chapter-content *, .chapter-heading')].filter(el => el.offsetParent).map(el => el.getBoundingClientRect().bottom + scrollY));
  return { avail, height: section.scrollHeight, contentBottom: Math.round(bottom - section.getBoundingClientRect().top - scrollY),
    wide: document.documentElement.scrollWidth > innerWidth, eyebrow: section.querySelector('.eyebrow').textContent };
})()`;

const results = [];
for (const [width, height] of viewports) {
  await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
  await call('Page.navigate', { url: `http://127.0.0.1:8765/?mode=presenter&fit=${Date.now()}#welcome` });
  await pause(2500);
  await evaluate('document.fonts.ready.then(() => true)');
  const slides = await evaluate(`import('./chapters/index.js').then(({ chapters }) => chapters.flatMap(c => (c.slides?.length ? c.slides : [{ id: '' }]).map((s, i) => ({ chapter: c.id, slide: s.id, first: i === 0 }))))`);
  for (const { chapter, slide, first } of slides) {
    if (only.size && !only.has(chapter)) continue;
    await evaluate(`location.hash = ${JSON.stringify(`#${chapter}${first ? '' : `/${slide}`}`)}; true`);
    await pause(350);
    const states = [];
    for (let stepCount = 0; stepCount < 8; stepCount++) {
      const state = await evaluate(measure);
      states.push(state);
      if (shots) {
        const { data } = await call('Page.captureScreenshot', { format: 'png' });
        await writeFile(path.join(output, `${width}-${chapter}${slide ? `-${slide}` : ''}${stepCount ? `-step${stepCount + 1}` : ''}.png`), Buffer.from(data, 'base64'));
      }
      // Walk internal steppers (scenarios, policy) so every step is measured.
      const advanced = await evaluate(`(() => { const s = [...document.querySelectorAll('.chapter')].find(i => !i.hidden); const b = s.querySelector('[data-next]'); if (!b || !b.offsetParent || b.disabled) return false; b.click(); return true; })()`);
      if (!advanced) break;
      await pause(250);
    }
    const worst = states.reduce((a, b) => (b.height > a.height ? b : a));
    const fits = worst.height <= worst.avail + 1 && !worst.wide;
    results.push({ viewport: `${width}x${height}`, chapter, slide: slide || '(single)', steps: states.length, avail: worst.avail, height: worst.height, ratio: +(worst.height / worst.avail).toFixed(2), wide: worst.wide, fits });
  }
}
socket.close();
browser.kill();
await pause(500);
await rm(profile, { recursive: true, force: true }).catch(() => {});
await writeFile(path.join(output, `results${only.size ? `-${[...only].join('-')}` : ''}.json`), JSON.stringify({ checkedAt: new Date().toISOString(), results, problems }, null, 2) + '\n');
for (const r of results) console.log(`${r.fits ? 'ok  ' : 'OVER'} ${r.viewport.padEnd(9)} ${`${r.chapter}/${r.slide}`.padEnd(40)} ${String(r.height).padStart(5)} / ${r.avail}  (${r.ratio}x)${r.steps > 1 ? `  ${r.steps} steps` : ''}${r.wide ? '  HORIZONTAL OVERFLOW' : ''}`);
for (const problem of [...new Set(problems)]) console.log(`PROBLEM ${problem}`);
const failed = results.filter(r => !r.fits).length;
console.log(`${results.length - failed}/${results.length} slide checks fit; ${new Set(problems).size} page problems.`);
process.exitCode = failed || problems.length ? 1 : 0;
