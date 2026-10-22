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
    'data-demo-title','data-demo-body','data-demo-screen','data-policy-pane','data-policy-reset','data-policy-reset-status'].map(key=>[`[${key}]`,element()]));
  const handlers={};
  const section = {querySelector:selector=>elements[selector],addEventListener(type,handler){handlers[type]=handler;}};
  const previous = elements['[data-back]'], next = elements['[data-next]'];
  const screen = elements['[data-demo-screen]'];
  const status = elements['[data-step-status]'];
  const chooser = elements['[data-policy-pane]'];
  const titles = ['Check relevance and provenance','Annotate the same passage','Review a briefing preview'];
  const panes = ['results','report','report'];
  const check = index => {
    assert.equal(status.textContent,`Step ${index+1} of 3`);
    assert.equal(elements['[data-demo-title]'].textContent,titles[index]);
    assert.equal((screen.innerHTML.match(/class="policy-pane"/g)||[]).length,4);
    assert.equal(screen.innerHTML.match(/data-pane="([^"]+)" data-active="true"/g)?.length,1);
    assert.match(screen.innerHTML,new RegExp(`data-pane="${panes[index]}" data-active="true"`));
    assert.equal(screen.dataset.focusPane,panes[index],'each step focuses its own panel');
    assert.equal(chooser.value,panes[index],'panel selector agrees with the step');
    assert.equal((screen.innerHTML.match(/class="policy-current"/g)||[]).length,1,'current step has a text cue');
    assert.equal(screen.innerHTML.includes('<textarea'),index===1,'annotation field is in step 2');
    assert.match(screen.innerHTML,/DEMO-01/,'the same synthetic notice appears throughout');
    assert.equal(previous.disabled,index===0);
    assert.equal(next.disabled,index===2);
    assert.doesNotMatch(screen.innerHTML,/<(?:button|a)[^>]*(?:export|download)/i);
    assert.doesNotMatch(screen.innerHTML,/Source availability checked/);
    assert.match(screen.innerHTML,/No policy search, vault access or export occurs/);
  };

  assert.match(policy.render(),/<label for="policy-pane-choice">Illustrated panel<\/label>/);
  assert.match(policy.render(),/aria-describedby="policy-pane-help"/);
  policy.mount(section);
  check(0);
  assert.ok(policy.render().indexOf('data-demo-screen')<policy.render().indexOf('data-demo-title'),'output precedes instructions');
  assert.match(policy.render(),/NCAI2026/,'optional access branch preserves the owner-supplied code');
  for(let index=1;index<3;index++){
    const before=screen.innerHTML;
    for(const panel of ['sources','results','issues','report']){
      chooser.change(panel);
      assert.equal(screen.dataset.focusPane,panel,'all illustrated panels remain reachable');
      assert.equal(screen.innerHTML,before,'panel switching preserves the temporary note and current example');
      assert.equal(status.textContent,`Step ${index} of 3`,'panel selection does not change the walkthrough step');
    }
    chooser.change('unknown');
    assert.equal(screen.dataset.focusPane,'report','unknown panel values do not hide all content');
    next.click();check(index);
  }
  handlers.input({target:{matches:()=>true,value:'Verify heat & smoke <capacity> before the meeting.'}});
  previous.click();check(1);
  assert.match(screen.innerHTML,/Verify heat &amp; smoke &lt;capacity&gt;/,'annotation survives going back');
  next.click();check(2);
  assert.match(screen.innerHTML,/Verify heat &amp; smoke &lt;capacity&gt;/,'the briefing includes the escaped annotation');
  elements['[data-policy-reset]'].click();check(0);
  assert.doesNotMatch(screen.innerHTML,/Verify heat/,'reset clears the annotation');
  assert.match(elements['[data-policy-reset-status]'].textContent,/cleared/);
  next.click();handlers.input({target:{matches:()=>true,value:'Second temporary note'}});
  previous.click();elements['[data-policy-reset]'].click();
  next.click();assert.doesNotMatch(screen.innerHTML,/Second temporary note/,'reset also works from the first step');
  assert.equal(requests,0);
  console.log('Policy walkthrough checks passed: output first, three consistent steps, annotation propagation/escaping, panel selection, reset from first/final steps, boundaries and no live request/export.');
})().catch(error => { console.error(error); process.exitCode=1; });
