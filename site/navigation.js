// Hashes are `#chapter` or `#chapter/slide`; unknown parts fall back to the first valid position.
export function positionFromHash(hash, chapters) {
  let id;
  try { id = decodeURIComponent(hash.replace(/^#/, '')); } catch { return { chapter: 0, slide: 0 }; }
  const [chapterId, slideId] = id.split('/');
  const chapter = Math.max(0, chapters.findIndex(item => item.id === chapterId));
  const slide = Math.max(0, (chapters[chapter].slides || []).findIndex(item => item.id === slideId));
  return { chapter, slide };
}

export function indexFromHash(hash, chapters) {
  return positionFromHash(hash, chapters).chapter;
}

export function hashFor(chapters, chapter, slide) {
  const slides = chapters[chapter].slides || [];
  return `#${chapters[chapter].id}${slide > 0 && slides[slide] ? `/${slides[slide].id}` : ''}`;
}

// Presenter deck: every chapter contributes one entry per authored slide, or one entry when it has none.
export function buildDeck(chapters) {
  return chapters.flatMap((item, chapter) => (item.slides?.length ? item.slides : [null]).map((_, slide) => ({ chapter, slide })));
}

export function stepIndex(index, step, count) {
  return Math.max(0, Math.min(count - 1, index + step));
}

export function modeFromSearch(search) {
  return new URLSearchParams(search).get('mode') === 'presenter' ? 'presenter' : 'participant';
}

export function keyboardStep(event, index, count) {
  if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) return null;
  if (event.target?.closest?.('input, textarea, select, button, a, summary, [contenteditable]:not([contenteditable="false"]), [role="slider"], [role="tab"]')) return null;
  if (['ArrowRight', 'PageDown'].includes(event.key)) return stepIndex(index, 1, count);
  if (['ArrowLeft', 'PageUp'].includes(event.key)) return stepIndex(index, -1, count);
  if (event.key === 'Home') return 0;
  if (event.key === 'End') return count - 1;
  return null;
}
