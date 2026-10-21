const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const root = path.join(__dirname, '..');
const deck = JSON.parse(fs.readFileSync(path.join(root, 'work/deck/narrative.json'), 'utf8'));
const norm = text => text.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();
const hash = file => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

(async () => {
  const script = fs.readFileSync(path.join(root, 'site/chapters/narrative.js'), 'utf8');
  const openingSource = script.slice(script.indexOf('export const opening'), script.indexOf('export const knowledge'));
  const { opening, strategy, sequence } = await import(`data:text/javascript;base64,${Buffer.from(openingSource).toString('base64')}`);
  const html = [opening, strategy, sequence].map(chapter => chapter.render());
  const source = deck.slice(0, 3).map(slide => slide.shapes.map(shape => norm(shape.text)));
  assert.equal(opening.title, source[0][0]);
  assert.equal(norm(html[0].match(/<div class="source-intro">([\s\S]*?)<\/div>/)[1]), source[0][1].replace('Resolution XXXX', 'Resolution 2026-034'));
  for (const emphasis of ['document, inform, support, and advocate', 'moving from identified needs to coordinated action', 'This overview details:']) {
    assert.match(html[0], new RegExp(`<strong>${emphasis}`));
  }
  assert.doesNotMatch(html[0], /XXXX/);
  assert.match(html[0], /Framework adoption[^]*2026-034/);

  assert.equal(strategy.title, source[1][0]);
  assert.equal(norm(html[1].match(/<p class="source-goal">([\s\S]*?)<\/p>/)[1]), source[1][1]);
  for (let i = 0; i < 4; i++) {
    assert.equal(norm(html[1].matchAll(/<section class="source-function"><h2>(.*?)<\/h2><p>(.*?)<\/p><\/section>/g).toArray()[i][1]), source[1][2 + i * 2]);
    assert.equal(norm(html[1].matchAll(/<section class="source-function"><h2>(.*?)<\/h2><p>(.*?)<\/p><\/section>/g).toArray()[i][2]), source[1][3 + i * 2]);
  }
  assert.equal((html[1].match(/class="source-function"/g) || []).length, 4);

  assert.equal(sequence.title, source[2][0]);
  const stage = [...html[2].matchAll(/<li class="(?:highlighted|remaining)"><h2>(.*?)<\/h2><span class="source-node">(\d)<\/span><p class="source-activity">(.*?)<\/p><p class="source-output"><strong>OUTPUT<\/strong><br><em>(.*?)<\/em><\/p><\/li>/g)];
  assert.equal(stage.length, 6);
  const phrases = source[2].filter(text => text && !/^\d$/.test(text));
  for (const [i, item] of stage.entries()) {
    assert.equal(norm(item[1]), phrases[1 + i * 3]);
    assert.equal(norm(item[3]), phrases[2 + i * 3]);
    assert.equal(norm(item[4]), phrases[3 + i * 3].replace(/^OUTPUT /, ''));
  }
  assert.equal((html[2].match(/class="highlighted"/g) || []).length, 2);
  assert.equal((html[2].match(/class="remaining"/g) || []).length, 4);
  assert.match(html[2], /Gray stages 3–6: not implemented/);
  assert.match(html[2], /Orange marks the current focus/);

  const styles = fs.readFileSync(path.join(root, 'site/styles.css'), 'utf8');
  assert.match(styles, /--accent:#155f65/);
  assert.match(styles, /\.chapter\[data-source-slide="3"\]\{background:linear-gradient\(90deg,#153f43 0%,#155f65 54%,#1b637b 100%\)/);
  assert.match(styles, /\.chapter\[data-theme="atni"\],\.chapter\[data-theme="atni"\]:nth-child\(2n\)[^\n]*background:#010b13/);
  assert.match(fs.readFileSync(path.join(root, 'site/app.js'), 'utf8'), /assets\/design\/atni-climate-on-dark\.png/);

  for (const [sourceFile, siteFile] of [
    ['work/deck/media/slide-05-pic-1-image5.png', 'site/assets/design/atni-climate.png'],
    ['work/deck/media/slide-01-pic-1-image1.png', 'site/assets/design/ncai-gradient-banner.png'],
    ['work/deck/media/slide-03-pic-1-image3.png', 'site/assets/design/ncai-gradient-full.png'],
  ]) assert.equal(hash(path.join(root, siteFile)), hash(path.join(root, sourceFile)));
  assert.equal(hash(path.join(root, 'site/assets/design/ncai-white-logo.png')), hash('C:/Users/PatrickFreeland/OneDrive - Affiliated Tribes of Northwest Indians/Pictures/NCAI_white logo.png'));
  assert.equal(fs.existsSync(path.join(root, 'site/assets/design/atni-seal.svg')), false);
  console.log('Source fidelity checks passed for slides 1–3 and copied design assets.');
})().catch(error => { console.error(error); process.exitCode = 1; });
