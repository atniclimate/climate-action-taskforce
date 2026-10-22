export const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
export const number = value => value == null ? 'Unavailable' : new Intl.NumberFormat('en-US', {maximumFractionDigits: 1}).format(value);
export const money = value => value == null ? 'Unavailable' : new Intl.NumberFormat('en-US', {style:'currency', currency:'USD', notation:'compact', maximumFractionDigits: 2}).format(value);
const pending = new Map();
export const settledDatasets = () => Promise.allSettled([...pending.values()]);
export function dataset(name) {
  if (!pending.has(name)) pending.set(name, fetch(new URL(`../data/${name}.json`, import.meta.url)).then(response => {
    if (!response.ok) throw new Error(`The ${name} snapshot is unavailable (${response.status}).`);
    return response.json();
  }));
  return pending.get(name);
}
export function failure(element, error) {
  element.innerHTML = `<p class="notice" role="alert">${esc(error.message)} Use the downloadable reports in Resources.</p>`;
}
export const source = (url, label) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)} <span class="sr-only">(opens a new tab)</span></a>`;
export function bars(rows, {label='label', value='value', format=number, max=null}={}) {
  const ceiling = max ?? Math.max(1, ...rows.map(row => row[value] ?? 0));
  return `<ol class="bar-chart">${rows.map(row => `<li><span class="bar-label">${esc(row[label])}</span><span class="bar-track" aria-hidden="true"><span class="bar-fill" style="width:${Math.max(0,Math.min(100,(row[value]??0)/ceiling*100))}%"></span></span><strong>${esc(format(row[value]))}</strong>${row.note ? `<small>${esc(row.note)}</small>`:''}</li>`).join('')}</ol>`;
}
export function bindStepper(section, steps, paint) {
  let current = 0, timer = null;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)');
  const play = section.querySelector('[data-play]');
  play?.removeAttribute('aria-pressed');
  const status = section.querySelector('[data-step-status]');
  const stop = () => {clearInterval(timer); timer=null; if(play) play.textContent='Play walkthrough';};
  const show = index => {
    current = Math.max(0, Math.min(steps.length-1, index));
    paint(steps[current], current);
    if(status) status.textContent = `Step ${current+1} of ${steps.length}`;
    section.querySelector('[data-back]').disabled = current===0;
    section.querySelector('[data-next]').disabled = current===steps.length-1;
    if(current===steps.length-1) stop();
  };
  section.querySelector('[data-back]').addEventListener('click',()=>{stop();show(current-1);});
  section.querySelector('[data-next]').addEventListener('click',()=>{stop();show(current+1);});
  if(play) play.addEventListener('click',()=>{
    if(timer) {stop();return;}
    if(current===steps.length-1) show(0);
    play.textContent='Pause walkthrough';
    timer=setInterval(()=>show(current+1),reduced.matches?12000:8000);
  });
  document.addEventListener('visibilitychange',()=>{if(document.hidden) stop();});
  window.addEventListener('hashchange', stop);
  show(0);
  return stop;
}
