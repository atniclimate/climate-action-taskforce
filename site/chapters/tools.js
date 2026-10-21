import {bindStepper, source} from './shared.js';

const POLICY='https://atniclimate.github.io/policy-sentinel/';
const DDM='https://atniclimate.github.io/dynamic-drought-module/';
const TSDF='https://github.com/atniclimate/TieredSovereignDataFramework';
const RESOLUTION='https://atnitribes.org/wp-content/uploads/2026/09/20260917_26-34_TIERED%20SOVEREIGN%20DATA%20FRAMEWORK.pdf';
const toolLink=(url,name,qr)=>`<div class="tool-link"><a href="${url}" target="_blank" rel="noopener noreferrer"><img class="qr" src="assets/qr/${qr}.svg" alt="QR code for ${name}" width="160" height="160"></a><div><strong>${name}</strong><p>${source(url,url)}</p><p class="caption">The QR code and text link open the same external destination. Opening it leaves this presentation; it does not submit participant notes.</p></div></div>`;

export const available={
  id:'tools',sourceSlide:8,title:'Tools for Tribal climate work',theme:'atni',
  render:()=>`<p class="lead">Built by Tribal members for Tribes, these applications help reduce the cost, capacity and usability barriers around information work.</p><div class="resource-list"><div class="resource-row"><span class="ordinal">1</span><div><h2>Policy Sentinel</h2><p>Find policy and legal source records, preserve citations, annotate passages and preview an export.</p><p class="status">Public tool · in development · source package 0.9.0</p></div><a href="#policy-demo">See the walkthrough →</a></div><div class="resource-row"><span class="ordinal">2</span><div><h2>Dynamic Drought Module</h2><p>Explore drought, wildfire, heat and El Niño–Southern Oscillation (ENSO) indicators for a selected place, with briefings that identify their sources.</p><p class="status">Public tool · in development · source package 0.7.8</p></div><a href="#ddm">Explore a briefing →</a></div><div class="resource-row"><span class="ordinal">3</span><div><h2>Tiered Sovereign Data Framework</h2><p>Set the governance conditions for information, networks, platforms and computation.</p><p class="status">v1.0 release authorized · supplied illustrated edition v0.9.8</p></div><a href="#sovereignty">Examine the foundation →</a></div></div><p class="notice">Tools augment Tribal institutions. Demonstrated functionality, live source availability and future integration are different states. Package versions describe the inspected source; they do not prove the deployed version.</p>`,
};
const policySteps=[
  {title:'Open NCAI from the header',body:'In the public Policy Sentinel, choose the NCAI button in the header. It opens a password modal; this is a menu flow, not a special URL.',screen:`<p class="status">Header action</p><p>Choose <strong>NCAI</strong> in the top bar to open the access dialog.</p>`},
  {title:'Enter the participant code',body:'Enter NCAI2026 in the Access password field, then choose Open. This owner-supplied shared demo code is a light access barrier, not a personal account or strong security control.',screen:`<div class="demo-modal"><h3>NCAI access</h3><p>Access password</p><div class="demo-field">NCAI2026</div><span class="demo-highlight">Open</span></div>`},
  {title:'Choose a reference from the grouped menu',body:'Select a listed draft or resolution reference. The tool runs grouped policy, legislation, bill and court searches and explains source outcomes. State sources may be external research links.',screen:`<h3>NCAI reference map</h3><p class="status">Synthetic training content</p><div class="demo-field">Climate and infrastructure committee</div><div class="demo-highlight">Demonstration reference: community resilience</div><p>No real vault title, text or policy record is reproduced here.</p>`},
  {title:'Inspect the record and its provenance',body:'Open a result, inspect the issuing body, date and source link, and check whether it supports the question. A retrieved record is evidence for review; it is not automatically an authoritative interpretation.',screen:`<h3>Example public-source record</h3><dl class="demo-record"><dt>Source</dt><dd>Synthetic training record</dd><dt>Question</dt><dd>Which provisions need follow-up?</dd><dt>Outcome</dt><dd>Record selected for review</dd></dl>`},
  {title:'Retain a passage and add a note',body:'Use My Citations to retain the source, a selected passage and a user note. Notes and citations stay local to the tab unless exported or printed.',screen:`<h3>My Citations</h3><blockquote>“Illustrative passage for demonstration only.”</blockquote><label for="policy-demo-note">Try a local demonstration note</label><textarea id="policy-demo-note" rows="2" placeholder="What should the Tribal policy team verify?"></textarea><p class="caption">This field is temporary and is never submitted or saved.</p>`},
  {title:'Review the export preview',body:'The real tool asks for participant identity and purpose fields before exporting a PDF with source links and retrieval details. Those fields are user supplied, not verified identities. This walkthrough stops at a synthetic preview; it creates no real export.',screen:`<div class="demo-paper"><p class="eyebrow">Export preview · synthetic</p><h3>Policy research notes</h3><p>Source link · retrieval date · selected passage · user note</p><hr><p>Identity and purpose information would be supplied by the participant.</p><p class="status">Preview only · no file exported</p></div>`},
];

const policyPaneForStep = index => index < 3 ? 'sources' : index === 3 ? 'results' : 'report';

function policyWorkspace(step, index) {
  const active = policyPaneForStep(index);
  const panes = [
    ['sources', 'Search Policy', '<p class="caption">Source selection example. No search or source check runs here.</p><div class="policy-tabs"><span>Federal sources</span><span>State legislature</span></div><ul class="policy-source-list"><li><strong>Federal Register</strong><span>Shown selected</span></li><li>GovInfo</li><li>Congress.gov</li><li>Regulations.gov</li></ul><p class="eyebrow">Example search terms</p><div class="policy-field">community resilience</div>'],
    ['results', 'Results', '<p class="caption">The live tool groups source results here. This illustration retrieves no records.</p><p>Review the issuing body, date and original source before using a result.</p>'],
    ['issues', 'Rule review', '<p class="eyebrow">Issues the Demo Rules Identified</p><p class="caption">Automated rule flags need review. A passage flag quotes the extracted text; an absence check is a rule assessment.</p><p class="policy-empty">No rule findings are supplied in this example.</p>'],
    ['report', 'Report', '<p class="eyebrow">My citations</p><p class="caption">Selected passages and notes belong here. This example exports no file.</p><p class="eyebrow">Data actors</p><p class="caption">The participant supplies their name, role, organization or Nation, intended recipient and purpose. These entries do not verify identity.</p><span class="policy-export">Export PDF preview</span>'],
  ];
  return `<div class="policy-workspace"><div class="policy-appbar"><strong>Policy Sentinel</strong><span class="caption">Illustrated controls only</span><span class="policy-header-actions"><span class="${index < 2 ? 'demo-highlight' : ''}">NCAI</span><span>About and Limits</span></span></div><div class="policy-columns" id="policy-workspace-panes">${panes.map(([id,title,body])=>`<section class="policy-pane" data-pane="${id}" data-active="${id===active}" aria-label="${title}"><div class="policy-pane-heading"><h3>${title}</h3>${id===active ? '<span class="policy-current">Current step</span>' : ''}</div>${id===active ? `<div class="policy-active-content">${step.screen}</div>${index===0 ? `<div class="policy-pane-context">${body}</div>` : ''}` : body}</section>`).join('')}</div><p class="policy-footer">Synthetic content. No policy search, vault access or export occurs here.</p></div>`;
}

export const policy={
  id:'policy-demo',sourceSlide:9,title:'Policy Sentinel walkthrough',theme:'atni',
  slides:[
    {id:'walkthrough',title:'Policy research walkthrough',blocks:['walkthrough']},
    {id:'open',title:'Open Policy Sentinel',blocks:['access']},
  ],
  render:()=>`<p class="lead">Follow a policy research task from the NCAI menu to a citation and export preview.</p><div class="demo" data-block="walkthrough"><div class="demo-toolbar"><span data-step-status aria-live="polite"></span><span class="status">Synthetic demonstration</span></div><div class="demo-body policy-demo-body"><div class="policy-step-side"><div class="policy-step-intro"><h2 data-demo-title></h2><p data-demo-body></p></div><div class="action-row policy-step-controls"><button type="button" data-back>Previous step</button><button type="button" data-next>Next step</button><button type="button" data-play aria-pressed="false">Play walkthrough</button></div><div class="policy-pane-selector"><label for="policy-pane-choice">Illustrated panel</label><select id="policy-pane-choice" data-policy-pane aria-controls="policy-workspace-panes" aria-describedby="policy-pane-help"><option value="sources">Search Policy</option><option value="results">Results</option><option value="issues">Rule review</option><option value="report">Report</option></select><p class="caption" id="policy-pane-help">Next step returns to that step’s panel. No policy search runs.</p></div></div><div class="demo-screen" data-demo-screen></div></div></div><p class="caption policy-demo-caption">The labeled panel follows the current step. These six examples show a research workflow, not retrieved policy evidence or a legal interpretation.</p><div class="policy-access" data-block="access"><div><h2>Open the public tool</h2><ol class="policy-route"><li>Choose <strong>NCAI</strong> in the header of the public Policy Sentinel.</li><li>Enter <strong>NCAI2026</strong> as the access password and choose Open.</li><li>Choose a reference from the grouped menu.</li></ol><p class="notice">Live vault unlock has not been tested for this presentation. NCAI2026 is a shared demonstration code, a light access barrier rather than strong security. The walkthrough in this chapter is synthetic: it contains no policy-vault contents and runs no search or export.</p></div>${toolLink(POLICY,'Policy Sentinel','policy-sentinel')}</div>`,
  mount:section=>{
    const screen=section.querySelector('[data-demo-screen]');
    const chooser=section.querySelector('[data-policy-pane]');
    const stop=bindStepper(section,policySteps,(step,index)=>{
      section.querySelector('[data-demo-title]').textContent=step.title;
      section.querySelector('[data-demo-body]').textContent=step.body;
      screen.innerHTML=policyWorkspace(step,index);
      screen.dataset.focusPane=policyPaneForStep(index);
      chooser.value=policyPaneForStep(index);
    });
    chooser.addEventListener('change',()=>{
      stop();
      if(['sources','results','issues','report'].includes(chooser.value)) screen.dataset.focusPane=chooser.value;
    });
    return stop;
  },
};
export const ddm={
  id:'ddm',sourceSlide:10,title:'Dynamic Drought Module',theme:'atni',
  slides:[
    {id:'briefing',title:'Read a place briefing',blocks:['intro','briefing']},
    {id:'coverage',title:'Coverage and source limits',blocks:['lanes','limits']},
  ],
  render:()=>`<p class="lead" data-block="intro">Tribal staff can examine drought, wildfire and extreme heat alongside El Niño–Southern Oscillation (ENSO), a recurring ocean and atmosphere pattern that affects seasonal conditions.</p>
    <div class="ddm-overview" data-block="briefing">
      <figure class="wide-figure"><a href="assets/images/ddm-impact-briefing-2026-10-21.png" target="_blank" rel="noopener noreferrer"><img src="assets/images/ddm-impact-briefing-2026-10-21.png" alt="Dated DDM interface with Colville selected, mapped wildfire perimeters, a Kaiser Canyon source popup, and an ENSO impact briefing that exposes observation dates and uncertainty." loading="lazy" width="1919" height="1079"></a><figcaption>Dated still image, 21 October 2026 (owner-supplied screenshot): Colville selected, with wildfire layers and an ENSO briefing. It is a selected-place example, not current conditions. Open the image to read source dates and coverage at full size.</figcaption></figure>
      <aside class="ddm-reading-guide" aria-labelledby="ddm-reading-title"><h2 id="ddm-reading-title">Read a place briefing</h2><ol class="compact-steps"><li>Select a Tribe or other typed place.</li><li>Choose a hazard and time horizon.</li><li>Open the impact briefing; inspect source dates, coverage and unavailable states.</li></ol><p class="caption">These steps describe the external tool. The image is a still; selecting a place in it does not run an assessment.</p></aside>
    </div>
    <div class="ddm-lanes" data-block="lanes"><p class="caption">Source products identified in the inspected DDM runtime. Read each lane with its coverage limitation; listing a product does not establish current availability or complete coverage of a Nation.</p><ul class="ddm-lane-list">
      <li><h3>Drought</h3><p class="ddm-lane-products">U.S. Drought Monitor, DSCI, CPC outlooks, water-supply indicators</p><p>Editions remain separate; place and product coverage vary.</p></li>
      <li><h3>Wildfire</h3><p class="ddm-lane-products">NIFC perimeters, NWS fire-weather alerts, SPC Day 1–8 outlooks</p><p>No long-range NIFC outlook in the briefing; issuer material is PDF-only.</p></li>
      <li><h3>Extreme heat</h3><p class="ddm-lane-products">NWS alerts, point HeatRisk and forecast, CPC seasonal temperature</p><p>Point products and gridded context do not imply complete coverage of a Nation.</p></li>
      <li><h3>ENSO</h3><p class="ddm-lane-products">NOAA CPC observed indices, weekly updates, seasonal probabilities</p><p>Observation age and preliminary values matter; seasonal tendency is not a local forecast.</p></li>
    </ul></div>
    <details><summary>Full product names for each lane</summary><div class="table-scroll"><table><caption>Source products identified in the inspected DDM runtime. Read each lane with its coverage limitation; listing a product does not establish current availability or complete coverage of a Nation.</caption><thead><tr><th scope="col">Lane</th><th scope="col">Examples of supporting products</th><th scope="col">Coverage limitation</th></tr></thead><tbody><tr><th scope="row">Drought</th><td>U.S. Drought Monitor, Drought Severity and Coverage Index (DSCI), Climate Prediction Center (CPC) outlooks and water-supply indicators</td><td>Editions remain separate; place and product coverage vary.</td></tr><tr><th scope="row">Wildfire</th><td>National Interagency Fire Center (NIFC) perimeters, National Weather Service (NWS) fire-weather alerts, Storm Prediction Center (SPC) Day 1–8 outlooks</td><td>Long-range NIFC outlook is unavailable in the briefing integration; issuer material is PDF-only.</td></tr><tr><th scope="row">Extreme heat</th><td>NWS alerts, point HeatRisk/forecast, CPC seasonal temperature</td><td>Point products and gridded context do not imply complete coverage of a Nation.</td></tr><tr><th scope="row">ENSO</th><td>National Oceanic and Atmospheric Administration (NOAA) CPC observed indices, weekly updates and seasonal probabilities</td><td>Observation age and preliminary values matter; seasonal tendency is not a local forecast.</td></tr></tbody></table></div></details>
    <div class="ddm-limits" data-block="limits"><p class="notice">Briefings describe the selected place using available products. Observed, derived, partial and unavailable states must remain visible. An ENSO observation is not a long-term local climate projection.</p>${toolLink(DDM,'Dynamic Drought Module','ddm')}</div>`,
};
// Concentric tier rings redrawn from the TSDF public site's published geometry (seeded wobble, Catmull-Rom curves).
function ringPath(r, wobble, seed, pts, c = 270) {
  let s = seed;
  const rand = () => (s = (s * 16807) % 2147483647, (s - 1) / 2147483646);
  const offs = Array.from({ length: pts }, () => (rand() - .5) * 2 * wobble);
  const sm = offs.map((o, i) => (offs[(i - 1 + pts) % pts] + o * 2 + offs[(i + 1) % pts]) / 4);
  const xs = sm.map((o, j) => c + Math.cos(j / pts * Math.PI * 2) * (r + o));
  const ys = sm.map((o, j) => c + Math.sin(j / pts * Math.PI * 2) * (r + o));
  const at = k => (k + pts) % pts;
  let d = `M${xs[0].toFixed(1)} ${ys[0].toFixed(1)}`;
  for (let k = 0; k < pts; k++) {
    const [a, b, n, m] = [at(k - 1), k, at(k + 1), at(k + 2)];
    d += `C${(xs[b] + (xs[n] - xs[a]) / 6).toFixed(1)} ${(ys[b] + (ys[n] - ys[a]) / 6).toFixed(1)} ${(xs[n] - (xs[m] - xs[b]) / 6).toFixed(1)} ${(ys[n] - (ys[m] - ys[b]) / 6).toFixed(1)} ${xs[n].toFixed(1)} ${ys[n].toFixed(1)}`;
  }
  return d + 'Z';
}
const tsdfTiers=[
  {key:'t0',code:'T0',name:'Open',radius:250,labelY:48,color:'#e6e6e6',opacity:.08,text:'Released explicitly for public access by an authorized source. Public data keep their original conditions and licensing.'},
  {key:'t1',code:'T1',name:'Network',radius:192,labelY:105,color:'#9aa0a7',opacity:.14,text:'Shared among known and trusted network members through standing reciprocity protocols.'},
  {key:'t2',code:'T2',name:'Negotiated',radius:136,labelY:161,color:'#d98a91',opacity:.24,text:'Used only under documented requirements and a legally defensible sharing agreement, with the right to revoke.'},
  {key:'t3',code:'T3',name:'Sovereign',radius:80,labelY:262,color:'#c9303c',opacity:.5,text:'Never leaves the community. Governed according to Traditional Knowledge and its rightsholders.'},
];
const tsdfBasin=()=>`<svg class="tsdf-basin" viewBox="0 0 540 540" role="img" aria-label="Concentric tier diagram: T0 Open outermost, then T1 Network, T2 Negotiated, and T3 Sovereign at the protected center.">${[271,222,165,109,52].map((r,i)=>`<path d="${ringPath(r,5,40+i*7,26)}" fill="none" stroke="rgba(255,255,255,.08)"/>`).join('')}${tsdfTiers.map((t,i)=>`<g class="tsdf-ring" data-tier="${t.key}"><path d="${ringPath(t.radius,7,11+i*13,22)}" fill="${t.color}" fill-opacity="${t.opacity}" stroke="${t.color}" stroke-width="2"/></g><text x="270" y="${t.labelY}" text-anchor="middle" class="tsdf-ring-code">${t.code}</text><text x="270" y="${t.labelY+17}" text-anchor="middle" class="tsdf-ring-name">${t.name}</text>`).join('')}</svg>`;

export const sovereignty={
  id:'sovereignty',sourceSlide:11,title:'Tiered Sovereign Data Framework',theme:'atni',
  slides:[
    {id:'tiers',title:'Four tiers of responsibility',blocks:['intro','tiers']},
    {id:'authority',title:'Authority follows the data',blocks:['domains','sharing']},
  ],
  render:()=>`<p class="lead" data-block="intro">TSDF gives Tribes and Indigenous Nations a working way to govern data in digital spaces, through four tiers of responsibility.</p>
    <div class="tsdf-overview" data-block="tiers">${tsdfBasin()}<div><ol class="tsdf-tiers">${tsdfTiers.map(t=>`<li data-tier="${t.key}"><strong>${t.code} · ${t.name}</strong><span>${t.text}</span></li>`).join('')}</ol><p class="caption">T3 is the protective default for unclassified Indigenous data. Only authorized people may downgrade a classification; systems may add protection automatically, never remove it.</p><p class="caption tsdf-attribution">Tier, domain and sharing language condensed and diagram redrawn from the ${source('https://atniclimate.github.io/TieredSovereignDataFramework/','TSDF public site')} (accessed 21 October 2026). ATNI Resolution 2026-034 authorizes v1.0; adoption is each Tribe’s choice. The illustrated download is v0.9.8.</p></div></div>
    <div class="tsdf-authority" data-block="domains">
    <h2 class="tsdf-domains-title">Sovereignty across four domains</h2>
    <p class="caption">Classification alone protects nothing; authority has to follow data wherever it moves. Open a domain for its question and a discussion prompt. Indigenous Data Sovereignty runs through all four.</p>
    <div class="sovereignty-domains">
      <details class="domain-detail" name="tsdf-domain" open><summary><svg class="domain-symbol" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M5 5h14v14H5z M8 9h8 M8 13h8 M8 17h5"/></svg><span>Data</span></summary><div class="domain-body"><p>What data is stored, and under whose authority?</p><p class="caption">The governance layer, where CARE, OCAP® and the four tiers apply. Discuss who can authorize reuse of a planning document.</p></div></details>
      <details class="domain-detail" name="tsdf-domain"><summary><svg class="domain-symbol" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M5 12h14 M12 5v14 M3 10h4v4H3z M10 3h4v4h-4z M17 10h4v4h-4z M10 17h4v4h-4z"/></svg><span>Network</span></summary><div class="domain-body"><p>What infrastructure carries our data, and under whose terms?</p><p class="caption">The transmission layer: fiber, spectrum, towers and mesh. Discuss the conditions for sending information to a partner.</p></div></details>
      <details class="domain-detail" name="tsdf-domain"><summary><svg class="domain-symbol" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M3 4h18v13H3z M8 21h8 M12 17v4"/></svg><span>Digital</span></summary><div class="domain-body"><p>Which services hold our data, and under whose jurisdiction?</p><p class="caption">The service layer. Where a server sits is not the same as whose law governs it. Discuss who controls access when staff or partners change.</p></div></details>
      <details class="domain-detail" name="tsdf-domain"><summary><svg class="domain-symbol" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" aria-hidden="true"><path d="M7 7h10v10H7z M9 3v4 M15 3v4 M9 17v4 M15 17v4 M3 9h4 M3 15h4 M17 9h4 M17 15h4"/></svg><span>Computational</span></summary><div class="domain-body"><p>Who transforms our data, and for what purpose?</p><p class="caption">The analysis layer, including statistical models and artificial intelligence (AI). Discuss whether a proposed analysis has explicit authorization.</p></div></details>
    </div>
    </div>
    <div class="tsdf-sharing" data-block="sharing"><div><p class="large-statement">Sharing opens a window, not the whole house.</p><p>Partners see rendered views and run approved analyses at the source. The underlying data never leaves its origin, and every derivative carries its provenance home.</p></div>
    <p class="notice">Public availability alone does not authorize artificial intelligence or machine learning (AI/ML) training on Indigenous data. The framework calls for explicit authorization, provenance and tier-specific processing controls.</p></div>
    <details><summary>Adoption, edition and standards context</summary><p>ATNI Resolution 2026-034 authorizes release of TSDF v1.0 and states that individual Tribes are not obligated to adopt it. The illustrated download provided here is <strong>v0.9.8, revised 15 September 2026</strong>; the owner reports the v1.0 website edition is forthcoming.</p><p>IEEE 2890-2025 is referenced for provenance-related structures. No independent IEEE certification or automatic governance compliance is claimed.</p><p>TSDF is licensed CC BY-NC-SA 4.0. Its license does not apply to every application shown in this presentation.</p></details><div class="action-row"><a class="button" href="literature/tsdf-v0.9.8.pdf" download>Download illustrated v0.9.8 (PDF)</a>${source(RESOLUTION,'Read ATNI Resolution 26-34')}</div>${toolLink(TSDF,'TSDF source and development','tsdf')}`,
};
export const development={
  id:'development',sourceSlide:12,title:'Tools in development',theme:'atni',
  slides:[
    {id:'research',title:'Research and planning tools',blocks:['research','boundary']},
    {id:'screening',title:'Screening and coordination tools',blocks:['screening','boundary']},
  ],
  render:()=>`<p class="lead">Tribal institutions determine which tools serve their work and what information may be shared.</p>
    <div class="table-scroll" tabindex="0" role="region" aria-label="Development status table"><table class="development-table"><caption>Development status from inspected source material, 21 October 2026. Read current evidence separately from intended direction; these entries do not establish a live service or permission to reuse it.</caption><thead><tr><th scope="col">Tool</th><th scope="col">Current evidence</th><th scope="col">Intended direction</th><th scope="col">Reuse and release terms</th></tr></thead><tbody>
      <tr data-block="research"><th scope="row">ATNI-CAST</th><td>Research directory; no live application identified</td><td>Intended online application</td><td>Release and license not established</td></tr>
      <tr data-block="research"><th scope="row">Land-use-analyzer</th><td>Local demonstration; public deployment paused</td><td>Intended online application</td><td>PolyForm Noncommercial 1.0.0</td></tr>
      <tr data-block="research"><th scope="row">Plan-assessor</th><td>Local planning-document catalog and assessment development</td><td>Local / federated work</td><td>All rights reserved; no general reuse license granted</td></tr>
      <tr data-block="screening"><th scope="row">TCR policy scanner</th><td>Cached risk, award and economic screening outputs; in development</td><td>Local / federated screening</td><td>All rights reserved; source software is not redistributed here</td></tr>
      <tr data-block="screening"><th scope="row">ATNI-GeoBase</th><td>Local synthetic demonstration; public distribution not approved</td><td>Local / federated geographic infrastructure</td><td>PolyForm Noncommercial plus supplementary terms</td></tr>
      <tr data-block="screening"><th scope="row">Community-connector</th><td>Local synthetic demonstration; no live community service established</td><td>Local / federated coordination</td><td>PolyForm Noncommercial 1.0.0</td></tr>
    </tbody></table></div>
    <p class="caption">Local operation keeps work on the institution’s own system. Federated work means institutions exchange authorized information while retaining separate systems; the table describes intended arrangements, not completed connections.</p>
    <p class="notice" data-block="boundary">Planned hosting and integration are not deployed capabilities. Source availability and reuse permissions differ by tool. Obtain the applicable license and governance authorization before adaptation or distribution.</p><p>Next development should address the needs identified with Tribes: maintain reliable public evidence, make uncertainty understandable, reduce repeated work, and support authorized exchange between institutions.</p>`,
};
export const resources={
  id:'resources',sourceSlide:13,title:'Reports and next steps',theme:'atni',
  slides:[
    {id:'reports',title:'Reports to take forward',blocks:['intro','library']},
    {id:'decision',title:'From evidence to a decision',blocks:['decision']},
  ],
  render:()=>`<p class="lead" data-block="intro">Take the reports back to your Nation’s planning and policy work. Check what each source supports before using it in a decision.</p>
    <div class="resource-list resource-library" data-block="library">
      <div class="resource-row"><div><h2>Frozen assessments</h2><p class="caption">The assessment records definitions, coverage and source dates for the figures shown here. The CSV files are tables for further review, not a new assessment or a statement of Tribal priorities.</p></div><ul class="resource-links"><li><a href="literature/catf-assessment.html">Read the full assessment</a></li><li><a href="literature/catf-assessment.pdf" download>Download assessment PDF</a></li><li><a href="literature/nation-hazards.csv" download>Nation hazard CSV</a></li><li><a href="literature/regional-costs.csv" download>Regional / national cost CSV</a></li></ul></div>
      <div class="resource-row"><div><h2>Public planning leads</h2><p class="caption">The discovery report and tables record public search outcomes for later access and review. A no-match outcome does not establish that a Nation has no plan.</p></div><ul class="resource-links"><li><a href="literature/plan-discovery.html">Read discovery report</a></li><li><a href="literature/plan-discovery.pdf" download>Download discovery PDF</a></li><li><a href="literature/plan-candidates.csv" download>Candidate metadata CSV</a></li><li><a href="literature/nation-searches.csv" download>Nation / class search outcomes CSV</a></li></ul></div>
      <div class="resource-row"><div><h2>Governance and sources</h2><p class="caption">Read the original documents for their scope, edition and terms. Public access to a document does not authorize every use or establish a Nation’s adoption of a framework.</p></div><ul class="resource-links"><li><a href="literature/catf-legacy.pdf" download>CATF legacy account</a></li><li><a href="literature/tsdf-v0.9.8.pdf" download>TSDF illustrated v0.9.8</a></li><li>${source(RESOLUTION,'ATNI Resolution 26-34')}</li><li><a href="data/sources.json">Source and claim ledger</a></li></ul></div>
    </div>
    <div class="resources-decision" data-block="decision"><div class="next-actions"><h2>From evidence to a decision</h2><ol><li>Identify the decision, responsible institution and sovereign authority.</li><li>Check the relevant evidence and document the unanswered questions.</li><li>Scope a manageable action, partners, resources and a date to revisit it.</li></ol><p class="caption">Use these prompts to structure follow-up within your institution. They do not set priorities or replace a Nation’s decision process.</p></div>
    <div class="resources-closing"><p class="large-statement">Tribal institutions determine priorities and the conditions for sharing.</p><p class="caption">This static presentation has no analytics, accounts, shared submissions or browser-run assessor. Participant notes remain local unless the participant downloads them. Fonts retain their OFL notices; source materials and tools retain their respective attribution and license terms.</p></div></div><details><summary>Original deck identity and source-slide map</summary><p>The narrative foundation is the owner-supplied <cite>CATF_strategic plan.pptx</cite>, 13 source slides. Slides 4–13 were substantive-content placeholders. This web edition expands them into evidence and demonstration chapters while retaining each source slide number in the chapter menu.</p><p>Facilitation order: 1 → 2 → 3 → 4 → 7 (risk, regional costs, funding) → 5 (plans, follow-up, scenarios, recent change) → 6 → 8 → 9 → 10 → 11 → 12 → 13.</p></details>`,
};
