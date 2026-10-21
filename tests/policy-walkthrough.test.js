const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const shared = fs.readFileSync(path.join(__dirname, '../site/chapters/shared.js'), 'utf8');
  const sharedUrl = `data:text/javascript;base64,${Buffer.from(shared).toString('base64')}`;
  const chapter = fs.readFileSync(path.join(__dirname, '../site/chapters/tools.js'), 'utf8')
    .replace("from './shared.js'", `from '${sharedUrl}'`);
  const {policy} = await import(`data:text/javascript;base64,${Buffer.from(chapter).toString('base64')}`);

  let requests = 0;
  global.fetch = () => { requests++; throw new Error('walkthrough tried a live request'); };
  global.matchMedia = () => ({matches:false});
  global.document = {addEventListener(){},hidden:false};
  global.window = {addEventListener(){}};
  const element = () => ({textContent:'',innerHTML:'',disabled:false,value:'',dataset:{},handlers:{},
    addEventListener(type,handler){this.handlers[type]=handler;},removeAttribute(){},
    click(){this.handlers.click();},change(value){this.value=value;this.handlers.change();}});
  const elements = Object.fromEntries(['data-back','data-next','data-play','data-step-status',
    'data-demo-title','data-demo-body','data-demo-screen','data-policy-pane'].map(key=>[`[${key}]`,element()]));
  const section = {querySelector:selector=>elements[selector]};
  const previous = elements['[data-back]'], next = elements['[data-next]'];
  const screen = elements['[data-demo-screen]'];
  const status = elements['[data-step-status]'];
  const chooser = elements['[data-policy-pane]'];
  const titles = ['Open NCAI from the header','Enter the participant code',
    'Choose a reference from the grouped menu','Inspect the record and its provenance',
    'Retain a passage and add a note','Review the export preview'];
  const panes = ['sources','sources','sources','results','report','report'];
  const check = index => {
    assert.equal(status.textContent,`Step ${index+1} of 6`);
    assert.equal(elements['[data-demo-title]'].textContent,titles[index]);
    assert.equal((screen.innerHTML.match(/class="policy-pane"/g)||[]).length,4);
    assert.equal(screen.innerHTML.match(/data-pane="([^"]+)" data-active="true"/g)?.length,1);
    assert.match(screen.innerHTML,new RegExp(`data-pane="${panes[index]}" data-active="true"`));
    assert.equal(screen.dataset.focusPane,panes[index],'each step focuses its own panel');
    assert.equal(chooser.value,panes[index],'panel selector agrees with the step');
    assert.equal((screen.innerHTML.match(/class="policy-current"/g)||[]).length,1,'current step has a text cue');
    assert.equal(screen.innerHTML.includes('<textarea'),index===4,'temporary note appears only at step 5');
    assert.equal(previous.disabled,index===0);
    assert.equal(next.disabled,index===5);
    assert.doesNotMatch(screen.innerHTML,/<(?:button|a)[^>]*(?:export|download)/i);
    assert.doesNotMatch(screen.innerHTML,/Source availability checked/);
    assert.match(screen.innerHTML,/No policy search, vault access or export occurs/);
  };

  assert.match(policy.render(),/<label for="policy-pane-choice">Illustrated panel<\/label>/);
  assert.match(policy.render(),/aria-describedby="policy-pane-help"/);
  policy.mount(section);
  check(0);
  for(let index=1;index<6;index++){
    const before=screen.innerHTML;
    for(const panel of ['sources','results','issues','report']){
      chooser.change(panel);
      assert.equal(screen.dataset.focusPane,panel,'all illustrated panels remain reachable');
      assert.equal(screen.innerHTML,before,'panel switching preserves the temporary note and current example');
      assert.equal(status.textContent,`Step ${index} of 6`,'panel selection does not change the walkthrough step');
    }
    chooser.change('unknown');
    assert.equal(screen.dataset.focusPane,'report','unknown panel values do not hide all content');
    next.click();check(index);
  }
  next.click();check(5);
  for(let index=4;index>=0;index--){previous.click();check(index);}
  previous.click();check(0);
  assert.equal(requests,0);
  console.log('Policy walkthrough checks passed: six steps, labeled panel selection, step/panel synchronization, temporary note preserved on panel change, boundaries and no live request/export.');
})().catch(error => { console.error(error); process.exitCode=1; });
