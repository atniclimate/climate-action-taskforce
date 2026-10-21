import {bars,dataset,esc,failure,number,source} from './shared.js';

export const classLabels={climate_adaptation_plan:'Climate adaptation / action plans',climate_vulnerability_assessment:'Climate vulnerability assessments',hazard_mitigation_or_management_plan:'Hazard mitigation / management plans'};
const outcomes={found:'Public candidate located',no_matching_public_document_located:'No matching public source located',blocked:'Search or source blocked',not_searched:'Not searched',partially_searched:'Search incomplete'};
const regionOptions=data=>`<option value="">All presentation regions</option>${data.regions.map(r=>`<option value="${esc(r.region_id)}">${esc(r.name)}</option>`).join('')}`;
const ageBins=['0–5 years','6–10 years','Over 10 years','Unknown'];
export function planningAgeGroups(candidates,classes){
  const groups=classes.map(key=>({key,rows:ageBins.map(bin=>({label:bin,value:candidates.filter(c=>c.document_classes.includes(key)&&c.age_bin===bin).length}))}));
  return {groups,ceiling:Math.max(1,...groups.flatMap(group=>group.rows.map(row=>row.value)))};
}
const sourceUrl=c=>c.canonical_landing_page_url||c.document_url;
const words=value=>esc(String(value??'').replaceAll('_',' '));
// Presenter display only: long recorded text is cut at a word and labeled; the full record stays in participant view.
function clip(text,max){
  text=String(text??'');
  if(text.length<=max) return {text,cut:false};
  const space=text.lastIndexOf(' ',max);
  return {text:`${text.slice(0,space>max*.6?space:max).replace(/[\s,;:.]+$/,'')}…`,cut:true};
}
const clipped=(text,max)=>{const c=clip(text,max);return `${esc(c.text)}${c.cut?' <span class="plan-shortened">(shortened)</span>':''}`;};
const evidenceFor=(c,id)=>c.relationships.filter(r=>r.tribe_ids.includes(id));
const dateLine=c=>c.date_year==null?'Unknown · no verified date':`${esc(c.date_year)} · ${words(c.date_measure)}`;
const reviewLine=c=>`${c.review_state==='initial_search_result_only'?'Search result only, not reviewed':words(c.review_state)} · ${esc(c.source_confidence||'unrated')} confidence`;
// One concise source summary (title, classes, date basis, review) and one selected Nation relationship.
const classLine=c=>c.document_classes.map(k=>esc(classLabels[k])).join('; ');
const titleLink=c=>{const title=clip(c.title,100);return `<h3>${source(sourceUrl(c),title.text)}${title.cut?` <span class="plan-shortened">(title shortened; ${number(c.title.length)} characters recorded)</span>`:''}</h3>`;};
const fullButton='<button type="button" class="plan-link-button" data-full-open>Full recorded title and evidence</button>';
const sourceSummary=c=>`${titleLink(c)}<dl class="plan-facts"><div><dt>Class</dt><dd>${classLine(c)}</dd></div><div><dt>Date</dt><dd>${dateLine(c)}</dd></div><div><dt>Review</dt><dd>${reviewLine(c)}</dd></div></dl>${fullButton}`;
function nationRelation(c,id,lead=''){
  const rels=evidenceFor(c,id),evidence=rels.flatMap(r=>[].concat(r.evidence??[]));
  const relation=rels[0]?.host_relationship||c.host_relationship||'Relationship requires source review';
  const first=evidence.find(text=>text!==relation);
  return `<p class="plan-relation">${lead?`<strong>${lead}</strong>`:''}${clipped(relation,140)}</p>${first?`<p class="plan-relation">Evidence${evidence.length>1?` (1 of ${evidence.length} notes)`:''}: ${clipped(first,110)}</p>`:''}`;
}
// Participant detail: the complete record behind a source card.
function fullRecord(c,names){
  return `<h2>Full source record</h2><p>${source(sourceUrl(c),c.title)}</p><dl class="plan-facts"><div><dt>Issuer</dt><dd>${esc(c.issuing_body||'Issuer unconfirmed')}</dd></div><div><dt>Class</dt><dd>${c.document_classes.map(k=>esc(classLabels[k])).join('; ')}</dd></div><div><dt>Date</dt><dd>${dateLine(c)}${c.date_basis?`. ${esc(c.date_basis)}`:''}</dd></div><div><dt>Review</dt><dd>${reviewLine(c)}. ${esc(c.access_instructions||'')}</dd></div></dl><h3>Recorded Nation relationships (${c.tribe_ids.length} Nations)</h3><ul class="plan-relationships">${c.relationships.map(r=>`<li><strong>${r.tribe_ids.map(id=>esc(names.get(id))).join('; ')}</strong> · ${esc(classLabels[r.document_class]||r.document_class)}<br>${esc(r.host_relationship||c.host_relationship||'Relationship requires source review')}<br><small>Evidence: ${[].concat(r.evidence??[]).map(esc).join(' | ')||'None recorded'}</small></li>`).join('')}</ul>`;
}
// Show the participant-detail destination, switching out of presenter view when needed.
function openDetail(element){
  if(document.body.dataset.mode==='presenter') document.querySelector('#mode-toggle')?.click();
  if(element.tagName==='DETAILS') element.open=true;
  element.scrollIntoView({block:'start'});
  element.focus({preventScroll:true});
}
const pagerButtons=(name,index,total,label)=>`<span class="plan-pager-buttons"><button type="button" data-${name}="-1" ${index<=0?'disabled':''}>Previous${label?` ${label}`:''}</button><button type="button" data-${name}="1" ${name==='page'?'data-next':''} ${index>=total-1?'disabled':''}>Next${label?` ${label}`:''}</button></span>`;
const refocus=(root,selector)=>{const button=root.querySelector(selector);(button&&!button.disabled?button:root.querySelector('button:not(:disabled)'))?.focus();};
function candidateRows(rows,names){return rows.map(c=>`<tr><td>${source(sourceUrl(c),c.title)}<br><small>${esc(c.issuing_body||'Issuer unconfirmed')}</small></td><td>${c.tribe_ids.map(id=>esc(names.get(id))).join('; ')}<br><small>${esc(c.host_relationship||'Relationship requires source review')}</small></td><td>${c.document_classes.map(k=>esc(classLabels[k])).join('; ')}</td><td>${esc(c.date_year??'Unknown')}<br><small>${esc(c.date_measure?.replaceAll('_',' ')||'No verified date')}</small></td><td>${esc(c.review_state?.replaceAll('_',' '))}<br><small>${esc(c.source_confidence||'Unreviewed')} confidence</small></td></tr>`).join('');}
export const plans={
  id:'plans',sourceSlide:5,title:'Public planning coverage',theme:'catf',
  slides:[
    {id:'coverage',title:'What the search covered',blocks:['intro','coverage','limits']},
    {id:'age',title:'Age of located sources',blocks:['filters','ages']},
    {id:'inspect',title:'Inspect a public candidate',blocks:['filters','inspect']},
  ],
  render:()=>`<p class="lead" data-block="intro">Search climate adaptation/action plans, vulnerability assessments, and hazard plans separately across the pinned national roster.</p><div data-block="coverage"><div data-plan-coverage><p>Loading the metadata sweep…</p></div></div><p class="notice" data-block="limits">Public discovery does not establish that a Tribe lacks a plan. A search-result candidate is not a reviewed plan edition, and a regional plan is not automatically a Tribe-authored plan.</p><div data-block="filters"><div class="toolbar plan-toolbar" data-plan-filters></div></div><div data-block="ages"><div data-plan-ages aria-live="polite"></div></div><div data-block="inspect"><div data-plan-inspect aria-live="polite"></div></div><section class="plan-full-record" tabindex="-1" data-plan-full></section><div data-plan-table></div><div data-plan-methods></div><p><a href="literature/plan-discovery.html">Read the discovery report</a> · <a href="literature/plan-candidates.csv" download>Download candidate metadata (CSV)</a> · <a href="literature/nation-searches.csv" download>Download every Nation/class outcome (CSV)</a></p>`,
  mount(section){const $=selector=>section.querySelector(selector),target=$('[data-plan-coverage]');dataset('plans').then(data=>{
    const coverage=data.coverage,names=new Map(data.nations.map(n=>[n.tribe_id,n.display_name]));
    target.innerHTML=`<figure class="data-figure plan-coverage"><div class="stat-band"><div class="stat"><strong>${number(coverage.nations_attempted_all_classes)} / ${number(coverage.baseline_nations)}</strong><span>Nations with all three class searches attempted</span></div><div class="stat"><strong>${number(coverage.unique_source_urls)}</strong><span>Unique candidate source URLs located</span></div><div class="stat"><strong>${number(coverage.reviewed_unique_editions)}</strong><span>Reviewed plan editions</span></div><div class="stat"><strong>${number(coverage.nations_with_candidate)}</strong><span>Nations with at least one candidate</span></div></div><figcaption class="caption">Snapshot ${esc(data.data_as_of)}. Each Nation on the ${number(coverage.baseline_nations)}-Nation roster was searched separately in three document classes; ${number(coverage.nations_completed_all_classes)} Nations have all three searches completed without a blocked class. A located URL is not a reviewed plan, and this bounded search is not an exhaustive record of Tribal planning.</figcaption></figure>`;
    $('[data-plan-filters]').innerHTML=`<label class="field">Region<select data-plan-region>${regionOptions(data)}</select></label><label class="field">Document class<select data-plan-class><option value="">All three classes</option>${Object.entries(classLabels).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><label class="field">Find a Nation or title<input type="search" data-plan-query placeholder="Nation, title or issuer"></label>`;
    $('[data-plan-methods]').innerHTML=`<details><summary>Search, dates and counting rules</summary>${Object.values(data.methods).map(v=>`<p>${esc(v)}</p>`).join('')}<p>Counts use source URLs, not confirmed plan families. Exact URL duplicates consolidate while retaining all Nation relationships and classes. A multi-type source is counted in each applicable type; do not sum class bars into an edition count.</p><p><a href="data/plans.json" download>Download full public metadata and methods</a></p></details>`;
    const inspect=$('[data-plan-inspect]'),full=$('[data-plan-full]');
    let candidates=[],ids=new Set(),q='',page=0,assoc=0;
    // Start each source on the Nation the filters point at: a text match first, then the selected region.
    const firstNation=c=>{const text=q?c.tribe_ids.findIndex(id=>names.get(id).toLocaleLowerCase().includes(q)):-1;return text>=0?text:Math.max(0,c.tribe_ids.findIndex(id=>ids.has(id)));};
    const showSource=()=>{
      const c=candidates[page];
      if(!c){inspect.innerHTML='<p class="empty-state">No candidate matches these filters. This is not evidence of absent planning.</p>';full.innerHTML='';return;}
      const id=c.tribe_ids[assoc];
      const nav=c.tribe_ids.length>1?pagerButtons('assoc',assoc,c.tribe_ids.length,'Nation'):'';
      inspect.innerHTML=`<article class="plan-card"><div class="plan-pager"><p><strong>${number(page+1)} of ${number(candidates.length)} matching sources</strong></p>${pagerButtons('page',page,candidates.length,'source')}</div><div class="plan-pager"><p><strong>Nation association ${assoc+1} of ${c.tribe_ids.length}</strong></p>${nav}</div><div>${sourceSummary(c)}</div><div><p class="plan-nation-name">${esc(names.get(id))}</p>${nationRelation(c,id)}</div></article>`;
      full.innerHTML=fullRecord(c,names);
    };
    const update=()=>{
      const region=$('[data-plan-region]').value,category=$('[data-plan-class]').value;q=$('[data-plan-query]').value.trim().toLocaleLowerCase();
      const nations=data.nations.filter(n=>!region||n.region_id===region);ids=new Set(nations.map(n=>n.tribe_id));
      candidates=data.candidates.filter(c=>c.tribe_ids.some(id=>ids.has(id))&&(!category||c.document_classes.includes(category))&&(!q||[c.title,c.issuing_body,...c.tribe_ids.map(id=>names.get(id))].join(' ').toLocaleLowerCase().includes(q)));
      const {groups,ceiling}=planningAgeGroups(candidates,category?[category]:data.classes);
      $('[data-plan-ages]').innerHTML=`<p class="plan-result-count"><strong>${number(candidates.length)} candidate source URLs</strong> match among <strong>${number(nations.length)} Nations</strong> in this region view; text search narrows sources only. Bars share one count scale, 0 to ${number(ceiling)}.</p><div class="recency-grid">${groups.map(({key,rows})=>`<figure class="data-figure"><h2>${esc(classLabels[key])}</h2>${bars(rows,{format:number,max:ceiling})}</figure>`).join('')}</div><p class="caption plan-age-caption">Ages as of ${esc(data.data_as_of)} use adoption year first, then an evidenced update year, then publication year; Unknown means no verified date (${number(coverage.unknown_date_sources)} of ${number(coverage.unique_source_urls)} URLs nationally). A source can sit in more than one class, so class counts do not add to a total. A recent date does not confirm current adoption, and a source’s age is not a judgment of a Nation’s planning.</p>`;
      page=0;assoc=candidates[0]?firstNation(candidates[0]):0;showSource();
      $('[data-plan-table]').innerHTML=candidates.length?`<details><summary>All ${number(candidates.length)} matching public sources</summary><div class="table-scroll" tabindex="0" role="region" aria-label="Matching public source records"><table><caption>Located public candidates with recorded Nation relationships, document classes and dates. Follow the source link to confirm these relationships; these records are not reviewed plan editions.</caption><thead><tr><th scope="col">Source / link</th><th scope="col">Nation relationship</th><th scope="col">Class</th><th scope="col">Date</th><th scope="col">Review</th></tr></thead><tbody>${candidateRows(candidates,names)}</tbody></table></div></details>`:'';
    };
    inspect.addEventListener('click',event=>{
      const button=event.target.closest('button');if(!button) return;
      if(button.matches('[data-full-open]')) return openDetail(full);
      if(button.dataset.page){page+=+button.dataset.page;assoc=firstNation(candidates[page]);showSource();refocus(inspect,`[data-page="${button.dataset.page}"]`);}
      if(button.dataset.assoc){assoc+=+button.dataset.assoc;showSource();refocus(inspect,`[data-assoc="${button.dataset.assoc}"]`);}
    });
    section.querySelectorAll('[data-plan-filters] select').forEach(el=>el.onchange=update);$('[data-plan-query]').oninput=update;update();
  }).catch(error=>failure(target,error));},
};
export const followup={
  id:'follow-up',sourceSlide:5,title:'Planning follow-up',theme:'catf',
  slides:[
    {id:'flag',title:'A flag for evidence follow-up',blocks:['intro','rule','meaning']},
    {id:'confirm',title:'Confirm with the Nation',blocks:['explorer']},
  ],
  render:()=>`<p class="lead" data-block="intro">Inspect high supported risk alongside each document class’s search outcome. The result is an outreach and research aid.</p><div class="followup-rule" data-block="rule"><p class="followup-count"><strong data-follow-count>…</strong><span>Nations meet this screening rule for at least one document class</span></p><ol class="followup-conditions"><li>Evaluated scanner physical risk percentile of 80 or higher</li><li>All three class searches complete</li><li>No matching public source located in the flagged class</li></ol><p>Blocked, unsearched or incomplete classes prevent a definite flag. The percentile gives a Nation’s relative position in this 575-Nation assessment, with unequal hazard coverage; it is not a probability.</p></div><p class="notice" data-block="meaning">A flag means “confirm the public evidence with the Nation.” It does not mean absent planning, limited capacity, a funding entitlement or a sovereign priority.</p><div class="followup-explorer" data-block="explorer"><div class="toolbar" data-follow-filters></div><div data-follow-result aria-live="polite"><p>Loading the joined snapshot…</p></div></div><details class="followup-detail" tabindex="-1" data-follow-detail><summary>Located sources and search limitations</summary><div data-follow-sources></div></details>`,
  mount(section){const $=selector=>section.querySelector(selector),target=$('[data-follow-result]');dataset('plans').then(data=>{
    const names=new Map(data.nations.map(n=>[n.tribe_id,n.display_name]));
    $('[data-follow-count]').textContent=number(data.coverage.followup_nations);
    $('[data-follow-filters]').innerHTML=`<label class="field">Region<select data-follow-region>${regionOptions(data)}</select></label><label class="field">Nation<select data-follow-nation></select></label><label><input type="checkbox" data-only-follow> Show only flagged Nations</label>`;
    const region=$('[data-follow-region]'),select=$('[data-follow-nation]'),only=$('[data-only-follow]'),detail=$('[data-follow-detail]');
    let page=-1;// -1 shows the three class outcomes; 0+ shows one located source.
    const show=()=>{
      const n=data.nations.find(n=>n.tribe_id===select.value);
      if(!n){target.innerHTML='<p class="empty-state">No Nation meets these filters.</p>';$('[data-follow-sources]').innerHTML='';return;}
      const located=data.candidates.filter(c=>c.tribe_ids.includes(n.tribe_id));
      const panel=page<0?`<table class="followup-table"><caption class="sr-only">Public search outcome and research flag for each of the three independent document classes</caption><thead><tr><th scope="col">Document class</th><th scope="col">Public search outcome</th><th scope="col">Research flag</th></tr></thead><tbody>${data.classes.map(c=>`<tr><th scope="row">${esc(classLabels[c])}</th><td>${esc(outcomes[n.categories[c].outcome])}${n.categories[c].candidate_ids.length?` · ${n.categories[c].candidate_ids.length} URL${n.categories[c].candidate_ids.length>1?'s':''}`:''}</td><td>${n.followup_classes.includes(c)?'<strong>Confirm with Nation</strong>':'No flag from this rule'}</td></tr>`).join('')}</tbody></table>`
        :(c=>`<div class="plan-pager"><p><strong>Source ${page+1} of ${located.length}</strong> for this Nation</p>${pagerButtons('source',page,located.length,'')}${fullButton}</div>${titleLink(c)}<p class="plan-relation">${classLine(c)} · ${dateLine(c)} · ${c.review_state==='initial_search_result_only'?'search result only, not reviewed':words(c.review_state)}</p>${nationRelation(c,n.tribe_id,`Nation association ${c.tribe_ids.indexOf(n.tribe_id)+1} of ${c.tribe_ids.length}: `)}`)(located[page]);
      const toggle=page<0?(located.length?`<button type="button" class="plan-link-button" data-source="1">Inspect ${located.length} located source${located.length>1?'s':''}</button>`:''):'<button type="button" class="plan-link-button" data-outcomes>Back to all three outcomes</button>';
      target.innerHTML=`<h2 class="followup-name">${esc(n.display_name)}</h2><div class="followup-grid"><div class="followup-nation"><p>Physical risk percentile <strong>${n.percentile_rank==null?'unavailable':n.percentile_rank.toFixed(1)}</strong> · ${n.high_risk?'meets':'below'} the threshold</p><p>Searched ${esc(n.searched_at?.slice(0,10)||'not yet')} · ${n.search_complete?'all three classes complete':'search incomplete'}</p>${toggle}</div><div class="followup-panel">${panel}</div></div><p class="caption followup-reminder">Flag rule: percentile 80 or higher (a relative position, not a probability), all three searches complete and no public match in that class. No match does not establish that a Nation lacks a plan; a flag asks for confirmation, not a capacity or priority finding.</p>`;
      $('[data-follow-sources]').innerHTML=`<p class="caption">These records retain the recorded relationship evidence and review status. Confirm authorship, adoption and current use with the Nation before relying on a candidate.</p>${located.map(c=>`<p>${source(sourceUrl(c),c.title)}<br>${evidenceFor(c,n.tribe_id).flatMap(r=>[].concat(r.evidence??[])).map(esc).join(' | ')}<br><small>${reviewLine(c)} · ${classLine(c)} · date ${dateLine(c)}</small></p>`).join('')||'<p>No matching public source located within the recorded search budget.</p>'}<p>${esc(Array.isArray(n.limitations)?n.limitations.join(' '):n.limitations)}</p>`;
    };
    const filter=()=>{const previous=select.value;const rows=data.nations.filter(n=>(!region.value||n.region_id===region.value)&&(!only.checked||n.followup_classes.length));select.innerHTML=rows.map(n=>`<option value="${esc(n.tribe_id)}">${esc(n.display_name)}</option>`).join('');if(rows.some(n=>n.tribe_id===previous))select.value=previous;page=-1;show();};
    target.addEventListener('click',event=>{
      const button=event.target.closest('button');if(!button) return;
      if(button.matches('[data-full-open]')) return openDetail(detail);
      if(button.matches('[data-outcomes]')){page=-1;show();return refocus(target,'[data-source]');}
      if(button.dataset.source){page=Math.max(0,page)+(page<0?0:+button.dataset.source);show();refocus(target,`[data-source="${button.dataset.source}"]`);}
    });
    region.onchange=filter;only.onchange=filter;select.onchange=()=>{page=-1;show();};filter();
  }).catch(error=>failure(target,error));},
};
