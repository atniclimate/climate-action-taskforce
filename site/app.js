import { chapters } from './chapters/index.js';
import { positionFromHash, hashFor, buildDeck, stepIndex, modeFromSearch, keyboardStep } from './navigation.js';
import { createExplorerRuntime } from './explorer.js';
import { settledDatasets } from './chapters/shared.js';

const $ = selector => document.querySelector(selector);
const escape = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[character]);
const main = $('#presentation');
const menu = $('#chapter-menu');
let { chapter: index, slide } = positionFromHash(location.hash, chapters);
let mode = modeFromSearch(location.search);
const onLeave = new Map();
const deck = buildDeck(chapters);
const deckIndex = () => deck.findIndex(entry => entry.chapter === index && entry.slide === slide);

// Keep chapter anchors and bottom padding clear of controls after text resizing.
const chromeObserver = new ResizeObserver(entries => {
  for (const { target } of entries) {
    const property = target.matches('.site-header') ? '--header-height' : '--control-height';
    document.documentElement.style.setProperty(property, `${Math.ceil(target.getBoundingClientRect().height)}px`);
  }
});
chromeObserver.observe($('.site-header'));
chromeObserver.observe($('.presentation-controls'));

if (!chapters.length || new Set(chapters.map(chapter => chapter.id)).size !== chapters.length || chapters.some(chapter => !/^[a-z][a-z0-9-]*$/.test(chapter.id))) {
  throw new Error('Presentation chapters must have unique, stable chapter IDs.');
}
if (chapters.some(chapter => chapter.slides && (new Set(chapter.slides.map(item => item.id)).size !== chapter.slides.length || chapter.slides.some(item => !/^[a-z][a-z0-9-]*$/.test(item.id) || !item.blocks?.length)))) {
  throw new Error('Presenter slides need unique, stable IDs and at least one block.');
}

main.innerHTML = chapters.map((chapter, position) => `<section class="chapter${position === 0 ? ' chapter-opening' : ''}" id="${chapter.id}" data-theme="${chapter.theme === 'atni' ? 'atni' : 'catf'}" data-source-slide="${escape(chapter.sourceSlide)}" aria-labelledby="${chapter.id}-title">
  <div class="chapter-topline"><p class="eyebrow">${escape(chapter.eyebrow || (chapter.theme === 'atni' ? 'Tools for sovereign action' : 'Climate Action Task Force'))}</p></div>
  <header class="chapter-heading"><h1 id="${chapter.id}-title" tabindex="-1">${escape(chapter.title)}</h1></header>
  <div class="chapter-content">${chapter.render()}</div>
  ${position + 1 < chapters.length ? `<a class="chapter-onward" href="#${chapters[position + 1].id}"><span>Continue exploring</span><strong>${escape(chapters[position + 1].title)} <span aria-hidden="true">↗</span></strong></a>` : ''}
  ${chapter.theme === 'atni' ? '<img class="atni-chapter-logo" src="assets/design/atni-climate-on-dark.png" alt="ATNI Climate Change">' : ''}
</section>`).join('');

const sections = [...main.querySelectorAll('.chapter')];
const explorer = createExplorerRuntime(main, query => history.pushState(null, '', hashFor(chapters, index, slide, query)));
sections.forEach((section, position) => {
  const eyebrow = section.querySelector('.eyebrow');
  eyebrow.dataset.default = eyebrow.textContent;
  for (const { blocks } of chapters[position].slides || []) {
    for (const name of blocks) if (!section.querySelector(`[data-block="${name}"]`)) console.error(`Missing presenter block "${name}" in ${chapters[position].id}`);
  }
});

// Presenter view shows only the current slide's named blocks; unlisted top-level content is participant detail.
function applySlide() {
  sections.forEach((section, position) => {
    const slides = chapters[position].slides;
    const eyebrow = section.querySelector('.eyebrow');
    const current = mode === 'presenter' && position === index && slides?.length ? slides[slide] : null;
    eyebrow.textContent = current && slides.length > 1 ? `${current.title} · ${slide + 1} of ${slides.length}` : eyebrow.dataset.default;
    if (!current) return;
    const visible = new Set(current.blocks);
    const content = section.querySelector('.chapter-content');
    content.querySelectorAll('[data-block]').forEach(block => block.toggleAttribute('data-slide-off', !visible.has(block.dataset.block)));
    for (const child of content.children) {
      if (child.matches('[data-block], .load-error')) continue;
      child.toggleAttribute('data-slide-off', !child.querySelector([...visible].map(name => `[data-block="${name}"]`).join(',')));
    }
  });
}
$('#chapter-links').innerHTML = chapters.map((chapter, position) => `<a href="#${chapter.id}"><span class="menu-index">${position + 1}</span><span>${escape(chapter.title)}<small>Source slide ${escape(chapter.sourceSlide)}</small></span><span aria-hidden="true">↗</span></a>`).join('');
$('.brand').href = `#${chapters[0].id}`;

function updatePosition() {
  const presenting = mode === 'presenter';
  const [position, count] = presenting ? [deckIndex(), deck.length] : [index, chapters.length];
  document.body.dataset.currentTheme = chapters[index].theme;
  $('#chapter-position').textContent = `${position + 1} / ${count}`;
  $('#chapter-current').textContent = chapters[index].title;
  $('#previous').disabled = position === 0;
  $('#next').disabled = position === count - 1;
  $('#previous').setAttribute('aria-label', presenting ? 'Previous slide' : 'Previous chapter');
  $('#next').setAttribute('aria-label', presenting ? 'Next slide' : 'Next chapter');
  $('#progress-fill').style.width = `${(position + 1) / count * 100}%`;
  $('#chapter-links').querySelectorAll('a').forEach((link, position) => position === index ? link.setAttribute('aria-current', 'location') : link.removeAttribute('aria-current'));
  document.title = `${chapters[index].title} · Climate Action Task Force`;
}

function updateMode() {
  document.body.dataset.mode = mode;
  $('#mode-toggle').textContent = mode === 'presenter' ? 'Participant view' : 'Presenter view';
  sections.forEach((section, position) => { section.hidden = mode === 'presenter' && position !== index; });
  applySlide();
  updatePosition();
  requestAnimationFrame(() => explorer.refresh());
}

const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
let navigationEpoch = 0;
for (const type of ['wheel', 'touchstart', 'pointerdown', 'keydown']) document.addEventListener(type, () => { ++navigationEpoch; }, { passive: true });

// Restart the staggered entrance each time a presenter chapter is shown.
function playEntrance(section, direction) {
  if (reduceMotion.matches) return;
  section.dataset.enter = direction;
  section.classList.remove('is-entering');
  void section.offsetWidth;
  section.classList.add('is-entering');
  clearTimeout(section.entranceTimer);
  section.entranceTimer = setTimeout(() => section.classList.remove('is-entering'), 1600);
}

function goTo(nextChapter, nextSlide = 0, { historyEntry = true, focus = true } = {}) {
  const epoch = ++navigationEpoch;
  const changed = nextChapter !== index || nextSlide !== slide;
  const direction = nextChapter < index || (nextChapter === index && nextSlide < slide) ? 'back' : 'forward';
  // Any slide change pauses the outgoing walkthrough, even inside one chapter.
  if (changed) onLeave.get(index)?.();
  index = nextChapter;
  slide = nextSlide;
  if (historyEntry) history.pushState(null, '', hashFor(chapters, index, slide, explorer.query()));
  const show = () => {
    updateMode();
    if (focus) sections[index].querySelector('h1').focus({ preventScroll: true });
    const target = mode === 'participant' && slide > 0 ? sections[index].querySelector(`[data-block="${chapters[index].slides[slide].blocks[0]}"]`) : null;
    (target || sections[index]).scrollIntoView({ behavior: 'instant', block: 'start' });
    // A direct participant link must survive content above it finishing its load.
    if (mode === 'participant') Promise.allSettled([settledDatasets(), document.fonts.ready]).then(() => {
      if (epoch !== navigationEpoch || mode !== 'participant') return;
      (target || sections[nextChapter]).scrollIntoView({ behavior: 'instant', block: 'start' });
      explorer.refresh();
    });
  };
  // Rapid key presses skip the pending crossfade; its callback still runs, so the rejection is expected.
  if (changed && mode === 'presenter' && document.startViewTransition && !reduceMotion.matches) document.startViewTransition(show).ready.catch(() => {});
  else show();
  if (changed && mode === 'presenter') playEntrance(sections[index], direction);
  const part = chapters[index].slides?.[slide];
  $('#announcement').textContent = mode === 'presenter'
    ? `Slide ${deckIndex() + 1} of ${deck.length}: ${chapters[index].title}${part && chapters[index].slides.length > 1 ? `, ${part.title}` : ''}`
    : `Chapter ${index + 1} of ${chapters.length}: ${chapters[index].title}`;
}

function step(direction) {
  if (mode === 'presenter') {
    const target = deck[stepIndex(deckIndex(), direction, deck.length)];
    goTo(target.chapter, target.slide);
  } else goTo(stepIndex(index, direction, chapters.length));
}

document.addEventListener('click', event => {
  const link = event.target.closest('a[href^="#"]');
  if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const hash = link.getAttribute('href');
  if (!chapters.some(chapter => hash === `#${chapter.id}` || hash.startsWith(`#${chapter.id}/`) || hash.startsWith(`#${chapter.id}?`))) return;
  event.preventDefault();
  if (menu.open) menu.close();
  const target = positionFromHash(hash, chapters);
  if (hash.includes('?')) explorer.restore(hash);
  goTo(target.chapter, target.slide);
});
$('#previous').addEventListener('click', () => step(-1));
$('#next').addEventListener('click', () => step(1));
$('#mode-toggle').addEventListener('click', () => {
  onLeave.get(index)?.();
  mode = mode === 'presenter' ? 'participant' : 'presenter';
  // Entering presenter view starts the current chapter at its first slide.
  if (mode === 'presenter') slide = 0;
  const url = new URL(location.href);
  if (mode === 'presenter') url.searchParams.set('mode', mode); else url.searchParams.delete('mode');
  url.hash = hashFor(chapters, index, slide, explorer.query());
  history.replaceState(null, '', url);
  updateMode();
  sections[index].scrollIntoView({ behavior: 'instant', block: 'start' });
});
$('#menu-open').addEventListener('click', () => menu.showModal());
document.querySelectorAll('[data-close]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close()));
document.addEventListener('keydown', event => {
  if (mode !== 'presenter' || document.querySelector('dialog[open]')) return;
  const nextIndex = keyboardStep(event, deckIndex(), deck.length);
  if (nextIndex === null) return;
  event.preventDefault();
  goTo(deck[nextIndex].chapter, deck[nextIndex].slide);
});
function goToHash() {
  explorer.restore(location.hash);
  const target = positionFromHash(location.hash, chapters);
  goTo(target.chapter, target.slide, { historyEntry: false });
}
window.addEventListener('hashchange', goToHash);
window.addEventListener('popstate', () => {
  mode = modeFromSearch(location.search);
  goToHash();
});
window.addEventListener('pagehide', event => { if (!event.persisted) explorer.destroy(); });

function chapterAtViewportPosition(sections, viewportHeight) {
  const marker = viewportHeight * .25;
  return sections.findIndex(section => {
    const { top, bottom } = section.getBoundingClientRect();
    return top <= marker && marker < bottom;
  });
}

const observer = new IntersectionObserver(() => {
  if (mode !== 'participant') return;
  const nextIndex = chapterAtViewportPosition(sections, window.innerHeight);
  if (nextIndex < 0 || nextIndex === index) return;
  onLeave.get(index)?.();
  index = nextIndex;
  updatePosition();
}, { rootMargin: '-15% 0px -65% 0px' });
sections.forEach(section => observer.observe(section));

// Participant view: fade each evidence block in once as it reaches the viewport.
// Everything above a revealed block is revealed too, so fast scrolls and menu jumps leave no hidden gaps.
const reveals = [...main.querySelectorAll('.chapter-heading, .chapter-content > *')];
let revealedThrough = -1;
const revealObserver = new IntersectionObserver(entries => entries.forEach(entry => {
  if (!entry.isIntersecting) return;
  const position = reveals.indexOf(entry.target);
  for (let next = revealedThrough + 1; next <= position; next += 1) {
    reveals[next].classList.add('in-view');
    revealObserver.unobserve(reveals[next]);
  }
  revealedThrough = Math.max(revealedThrough, position);
}), { rootMargin: '0px 0px -6% 0px' });
reveals.forEach(element => {
  element.classList.add('reveal');
  revealObserver.observe(element);
});

updateMode();
if (mode === 'presenter') playEntrance(sections[index], 'forward');
if (location.hash) requestAnimationFrame(() => goTo(index, slide, { historyEntry: false, focus: false }));

// Keep navigation available while independent chapter data loads.
chapters.forEach((chapter, position) => {
  Promise.resolve().then(() => chapter.mount?.(sections[position])).then(pause => {
    if (typeof pause === 'function') onLeave.set(position, pause);
  }).catch(error => {
    console.error(`Unable to initialize ${chapter.id}`, error);
    const message = document.createElement('p');
    message.className = 'callout load-error';
    message.textContent = 'This interactive section could not load. The text and source links remain available; reload to try again.';
    sections[position].querySelector('.chapter-content').prepend(message);
  });
});
