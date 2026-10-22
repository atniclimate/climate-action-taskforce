"""Produce matching HTML, PDF and CSV reports from the frozen public JSON only."""
import argparse
import csv
from hashlib import sha256
from html import escape
import json
from pathlib import Path
import shutil

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, LongTable, TableStyle, PageBreak, KeepTogether

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'literature'; PUBLIC=ROOT/'site/literature'
LABELS={'climate_adaptation_plan':'Climate adaptation / action','climate_vulnerability_assessment':'Climate vulnerability','hazard_mitigation_or_management_plan':'Hazard mitigation / management'}
STATUS={'found':'Candidate located','no_matching_public_document_located':'No public match located','blocked':'Blocked','not_searched':'Not searched','partially_searched':'Partial search'}

def load(name):return json.loads((ROOT/'site/data'/f'{name}.json').read_text(encoding='utf-8'))
def text(value):return 'Unavailable' if value is None else str(value)
def money(value):return 'Unavailable' if value is None else f'${value:,.2f}'
def h(value):return escape(text(value),quote=True)
def link(url,label):return f'<a href="{h(url)}">{h(label)}</a>'
def year(c):return f"{c['date_year']} ({c['date_measure'].replace('_',' ')})" if c.get('date_year') is not None else 'Unknown'
def nation_names(candidate,names):
    selected=[names[tid] for tid in candidate['tribe_ids']]
    return '; '.join(selected[:4])+(f'; and {len(selected)-4} more (full list in CSV / JSON)' if len(selected)>4 else '')
def section(title,paragraphs=(),table=None,widths=None):return {'title':title,'paragraphs':list(paragraphs),'table':table,'widths':widths}

def write_csv(name,fields,rows):
    with (OUT/name).open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.writer(stream);writer.writerow(fields)
        for row in rows:
            values=[]
            for value in row:
                if isinstance(value,(dict,list)):value=json.dumps(value,ensure_ascii=False)
                if value is None:value=''
                if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):value="'"+value
                values.append(value)
            writer.writerow(values)

def html_report(name,title,subtitle,sections):
    body=''.join(f'<section><h2>{h(s["title"])}</h2>'+''.join(f'<p>{p}</p>' for p in s['paragraphs'])+(('<div class="table-scroll"><table><thead><tr>'+''.join(f'<th scope="col">{h(x)}</th>' for x in s['table'][0])+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{cell}</td>' for cell in row)+'</tr>' for row in s['table'][1:])+'</tbody></table></div>') if s['table'] else '')+'</section>' for s in sections)
    (OUT/f'{name}.html').write_text(f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{h(title)}</title><link rel="stylesheet" href="report.css"></head><body><main><nav aria-label="Report"><a href="../index.html#resources">Presentation resources</a> · <a href="{name}.pdf">Download PDF</a></nav><header><p class="eyebrow">NCAI Climate Action Task Force · working evidence</p><h1>{h(title)}</h1><p class="lead">{h(subtitle)}</p></header>{body}<footer>Frozen public-source summaries. No participant responses are collected. Use the linked source records and consult the relevant Nation before interpreting planning coverage.</footer></main></body></html>''',encoding='utf-8')

def pdf_report(name,title,subtitle,sections):
    styles={
        'title':ParagraphStyle('title',fontName='Spartan',fontSize=29,leading=32,textColor=colors.HexColor('#155f65'),spaceAfter=18),
        'heading':ParagraphStyle('heading',fontName='Spartan',fontSize=18,leading=21,spaceBefore=18,spaceAfter=10,keepWithNext=True),
        'body':ParagraphStyle('body',fontName='Noto',fontSize=10,leading=14,spaceAfter=9),
        'cell':ParagraphStyle('cell',fontName='Noto',fontSize=8.5,leading=11,spaceAfter=0),
        'headcell':ParagraphStyle('headcell',fontName='NotoBold',fontSize=8.5,leading=11,textColor=colors.white),
    }
    flow=[Paragraph(h(title),styles['title']),Paragraph(h(subtitle),styles['body'])]
    for i,s in enumerate(sections):
        if s.get('new_page'):flow.append(PageBreak())
        flow.append(Paragraph(h(s['title']),styles['heading']))
        flow.extend(Paragraph(p,styles['body']) for p in s['paragraphs'])
        if s['table']:
            rows=[[Paragraph(h(v) if row_index==0 else v,styles['headcell' if row_index==0 else 'cell']) for v in row] for row_index,row in enumerate(s['table'])]
            table=LongTable(rows,colWidths=s['widths'],repeatRows=1,hAlign='LEFT')
            table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#155f65')),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#edf5ef'),colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),.5,colors.HexColor('#155f65'))]))
            flow.extend([KeepTogether([table]) if s.get('keep_table') else table,Spacer(1,10)])
    def footer(canvas,doc):
        canvas.saveState();canvas.setFont('Noto',8);canvas.setFillColor(colors.HexColor('#49515b'))
        canvas.drawString(36,22,'CATF · 22 October 2026 · Working evidence / public discovery is not plan absence')
        canvas.drawRightString(756,22,str(doc.page));canvas.restoreState()
    doc=SimpleDocTemplate(str(OUT/f'{name}.pdf'),pagesize=landscape(letter),rightMargin=36,leftMargin=36,topMargin=34,bottomMargin=40,title=title,author='NCAI Climate Action Task Force',subject=subtitle)
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)

def assessment_sections(risk,funding):
    regions=[dict(risk['national'],name='National baseline'),*risk['regions']]
    counts={count:sum(len(n['top_hazards'])==count for n in risk['nations']) for count in sorted({len(n['top_hazards']) for n in risk['nations']},reverse=True)}
    coverage='; '.join(f'{number} display {count} items in the ranked list' for count,number in counts.items())
    result=[section('Read this first',[
        'This is a development-stage screening snapshot, not a certified risk assessment, an impact valuation, a funding need or a sovereign priority. Tribal Nations retain authority over decisions and information.',
        f"Displayed-list coverage: <b>{len(risk['nations'])} Nations</b>; {coverage}. These are list lengths, not counts of all supported hazard scores; a Nation can have more than five supported scores. Missing hazards are unavailable, not zero. Hazard scores are modeled exposure indices (0–1), not probabilities or dollars.",
        f"Scanner package {h(risk['package_version'])}; formula {h(', '.join(risk['formula_versions']))}; frozen profiles through {h(risk['data_as_of'])}. Source commit: {h(risk['source_commit'])}. Input manifest SHA-256: {h(risk['input_manifest_sha256'])}.",
        h(risk['methods']['regions'])]),
      section('National and regional supported hazard frequency',[h(risk['methods']['aggregate_ranking']),'Each row gives the number of Nations whose supported top five includes the hazard, followed by the number assessed for that hazard and the full regional denominator. Multiple hazards can occur for each Nation.'],
        [['Geography','Nations','Supported hazard frequency: count; assessed / denominator']]+[[h(r['name']),h(r['nation_count']),'<br/>'.join(f"{h(x['hazard_name'])}: {x['value']}; {x['contributing_nations']} / {x['denominator']}" for x in r['top_hazards'])] for r in regions],[150,55,515]),
      section('National and regional county cost context',[
        'These dollar figures cover all residents, buildings and agriculture in included counties. <b>They are not Tribal losses.</b> Expected Annual Loss is an annualized model expectation, not next-year loss, historical damage, projected cost or a funding request.',
        'The 15 climate-sensitive hazard subtotal excludes earthquake, tsunami and volcano. Avalanche and landslide have multiple causes. Summing available hazard cells does not attribute all loss to climate change. Each county is counted once; missing source fields are not zero.',
        'Source: FEMA NRI December 2025 v1.20. Cached input does not retain a common price year; observation periods vary by hazard. All-hazard totals and climate-sensitive subtotals use different scopes.'],
        [['Geography','Counties','Climate-sensitive EAL / year','All-hazard EAL / year']]+[[h(r['name']),h(r['county_count']),money(r['climate_county_eal']),money(r['county_eal'])] for r in regions],[180,70,235,235]),
      section('Existing scanner place-context aggregate',[
        h(risk['methods']['scanner_context_eal']),
        '<b>Non-additive context only.</b> Shared county/tract inputs can overlap across places. Do not sum the regions or interpret these figures as aggregate Tribal damage. The county totals above supply a non-overlapping all-geography comparison.'],
        [['Geography','Representative places','Overlapping context indicator (USD)']]+[[h(r['name']),h(r['scanner_context_places']),money(r['scanner_context_eal'])] for r in regions],[220,180,320]),
      section('Historical U.S. disaster costs',[
        'The cached NCEI archive ends in 2024: 403 unique billion-dollar weather/climate disaster events total '+money(next(x['amount'] for x in risk['national']['costs'] if x['metric']=='ncei_historical_event_loss'))+'. These are all-U.S. losses, not Tribal estimates. Costs remain CPI-adjusted as stored; the cache omitted its inflation base-year label.',
        'The presentation separately cites NOAA’s January 2025 national assessment, which reports $182.7 billion for 27 events in 2024, in 2024 dollars. Source revisions may differ. Neither series isolates climate-change causation. Regional historical-cost allocation is unsupported.']),
      section('Recorded funding',[
        f"{funding['national']['award_count']:,} unique exact-name/alias matched awards for {funding['national']['recipient_nation_count']} Nations total <b>{money(funding['national']['amount'])}</b>. Five negative adjustments remain in the sum.",
        *[h(x) for x in funding['limitations']],
        'Source: '+link('https://www.usaspending.gov/search','USAspending public award records')+'. Archived leads are in funding.json; the separately checked funding leads below do not alter these historical obligations.'],
        [['Region','Awards','Recipient Nations','Award-level obligations']]+[[h(next((r['name'] for r in risk['regions'] if r['region_id']==x['region_id']),x['region_id'])),h(x['award_count']),h(x['recipient_nation_count']),money(x['amount'])] for x in funding['regions']],[240,80,140,260]),
      section('Per-Nation supported top-five table',[
        h(risk['methods']['nation_ranking']),
        'Scores below are modeled exposure indices, ordered within each Nation. A displayed zero is a supplied value; an absent hazard is not zero. Coastal erosion, sea-level rise and permafrost remain unassessed. Percentiles describe the composite physical score, not the listed hazard score; differing coverage limits comparison.',
        'The 115 Nations with evaluated physical percentile ≥80 meet the research-follow-up threshold. This is a cohort-relative screen, not a probability, eligibility decision or sovereign priority. Full hazard statuses and uncertainty fields are in nation-hazards.csv and risk.json.'],
        [['Nation','Region','Supported hazards: exposure score (0–1)','Physical percentile']]+[[h(n['display_name']),h(n['region_id']),'; '.join(f"{h(x['hazard_name'])} {x['value']:.3f}" for x in n['top_hazards']),f"{n['percentile_rank']:.1f}" if n['percentile_rank'] is not None else 'Unavailable'] for n in risk['nations']],[205,65,370,80]),
      section('Sources and limitations'),]
    result[-1]['paragraphs']=[*[h(x) for x in risk['limitations']],*[link(s['url'],s['title'])+(' — '+h(s['note']) if s.get('note') else '') for s in risk['sources']],f"Pinned roster SHA-256: {h(risk['roster_sha256'])}. Frozen profile manifest: {h(risk['frozen_manifest_sha256'])}. Exact local input lineage is retained in the project work record; only public fields are published."]
    result[2]['new_page']=True;result[6]['new_page']=True
    opportunities=load('opportunities')
    result.insert(6,section('Selected funding and technical-assistance leads',[
        'Checked '+h(opportunities['checked_at'])+'. '+h(opportunities['scope']),h(opportunities['limitations'])],
        [['Program / source','Status / deadline','Funding / eligibility']]+[[link(p['source_url'],p['title'])+'<br/>'+h(p['source_version']),h(p['status'])+'<br/>'+h(p['deadline_label']),h(p['amount_label'])+'<br/>'+h(p['eligibility'])+'<br/>'+h(p['geography'])] for p in opportunities['programs']],[210,180,330]))
    return result

def planning_sections(plans):
    cov=plans['coverage']; names={n['tribe_id']:n['display_name'] for n in plans['nations']}
    rows=[['Class','Candidate URLs','0–5 years','6–10 years','Over 10','Unknown']]
    for cls,label in LABELS.items():
        selected=[c for c in plans['candidates'] if cls in c['document_classes']]
        rows.append([h(label),h(len(selected)),*[h(sum(c['age_bin']==b for c in selected)) for b in ['0–5 years','6–10 years','Over 10 years','Unknown']]])
    sections=[section('What was searched',[
        '<b>Public discovery does not establish that a Tribe lacks a plan.</b> These records describe a bounded public search, not a national census of planning held by Tribes. No full document harvest, private records or Traditional Ecological Knowledge were collected.',
        f"Baseline: 575 Nations, 23 assignments, three distinct document classes each. As of {h(plans['data_as_of'])}, {cov['nations_attempted_all_classes']} Nations have all three search attempts recorded; {cov['nations_completed_all_classes']} have all three completed without a blocked class. Completed batches: {cov['batches_completed']} / 23.",
        f"{cov['raw_candidate_records']} raw candidate records consolidate to {cov['unique_source_urls']} exact source URLs; {cov['nations_with_candidate']} Nations have at least one candidate. <b>{cov['reviewed_unique_editions']} reviewed unique editions</b> are distinguished from search-result candidates. {cov['unknown_date_sources']} candidate URLs have unknown date age.",
        'Category outcomes: '+h('; '.join(f'{k.replace("_"," ")}: {v}' for k,v in cov['category_outcomes'].items()))+'.']),
      section('Plan type by evidenced recency',[h(plans['methods']['dates']),h(plans['methods']['dedup']),'Counts are candidate URLs, not confirmed editions. A source can occur in more than one class; do not add class totals into an edition count.'],rows,[260,92,92,92,92,92]),
      section('Methods, roster and interpretation',[h(x) for x in plans['methods'].values()]+[h(x) for x in plans['limitations']]+[f"Roster SHA-256: {h(plans['roster_sha256'])}. Batch manifest SHA-256: {h(plans['input_manifest_sha256'])}. Individual source URLs appear below and in plan-candidates.csv. Full query receipts remain in the working record."]),
      section('Nation-by-class search outcomes',[
        'No public match located means none qualified within the recorded budget. Blocked, partial and unsearched classes remain unresolved. A candidate in one class does not complete another class.',
        f"{cov['followup_nations']} Nations meet the defined risk-and-public-search follow-up rule for at least one class. A blank flag is not a finding of low risk or adequate planning. Codes in the final column: CAP = adaptation/action; CVA = vulnerability; HMP = hazard plan."],
        [['Nation','Adaptation / action','Vulnerability','Hazard plan','Follow-up class']]+[[h(n['display_name']),*[h(STATUS[n['categories'][c]['outcome']]) for c in LABELS],h(', '.join({'climate_adaptation_plan':'CAP','climate_vulnerability_assessment':'CVA','hazard_mitigation_or_management_plan':'HMP'}[c] for c in n['followup_classes']) or '—')] for n in plans['nations']],[240,130,130,130,90]),
      section('Located public source index',[
        'The linked title opens the canonical landing page or document. Relationships can be Nation-authored, regional participation or other explicitly supported coverage. Mere mentions were not sufficient. Dates without explicit evidence remain unknown. Rights are not transferred by discovery; consult source terms before reuse.',
        'Public document metadata, access conditions and supported Nation relationships are retained in plan-candidates.csv and plans.json. Full query receipts and raw internal review details remain in the local working record. The metadata sidecar is not claimed to be a validated native plan-assessor import.'],
        [['Source title / access link','Nation relationship','Class','Date / review']]+[[link(c['canonical_landing_page_url'] or c['document_url'],c['title']),h(nation_names(c,names))+'<br/>'+h(c.get('host_relationship') or 'See relationship evidence in CSV / JSON'),h('; '.join(LABELS[k] for k in c['document_classes'])),h(year(c))+'<br/>'+h(c['review_state'].replace('_',' '))] for c in plans['candidates']],[225,265,115,115])]
    sections[3]['new_page']=True;sections[4]['new_page']=True
    return sections

def public_areas(catalog):
    """Resolve only the catalog's intentional public shards and verify their bytes."""
    result={}
    for area_id,area in catalog['areas'].items():
        record=catalog['files'][area['file_id']]
        path=(ROOT/'site'/record['path']).resolve()
        if not path.is_relative_to((ROOT/'site').resolve()):raise ValueError('climate shard outside public artifact')
        body=path.read_bytes()
        if len(body)!=record['bytes'] or sha256(body).hexdigest()!=record['sha256']:raise ValueError('climate shard differs from catalog')
        value=json.loads(body)
        if value['id']!=area_id:raise ValueError('climate shard ID mismatch')
        result[area_id]=value
    return result

CLIMATE_FIELDS=['area_id','source_area','family','baseline','metric','unit','period','scenario','lower_p10','median','upper_p90','models','status','statistic','spread','source_url','source_sha256']
GEO_FIELDS=['tribe_id','Nation','mapping_status','source_area_ids','source_area_count','proxy','shared_source','mapping_confidence','missing_reason','mapping_caution']
COST_FIELDS=['cohort_id','cohort','metric','hazard_id','hazard','amount','unit','available_counties','expected_counties','source_counties','unmatched_county_fips','scope','period','price_year','source_version']

def climate_rows(areas):
    rows=[]
    for area_id,area in sorted(areas.items()):
        if area['family']!='native-nex':continue
        for metric_id,metric in area['metrics'].items():
            for period,scenarios in metric['windows'].items():
                for scenario,values in scenarios.items():
                    rows.append([area_id,area['name'],area['family'],area['baseline_id'],metric_id,metric['unit'],period,scenario,values['lower'],values['median'],values['upper'],values['models'],values['status'],metric['statistic'],metric['spread'],area['source']['url'],area['source']['sha256']])
    return rows

def geography_rows(catalog):
    return [[p.get('tribe_id'),p['name'],p['mapping_status'],p['area_ids'],len(p['area_ids']),p.get('proxy',False),p.get('shared',False),p.get('mapping_confidence'),p.get('missing_reason'),p.get('mapping_caution')] for p in catalog['places'] if p['kind']=='nation']

def cohort_cost_rows(catalog):
    rows=[]
    for cohort in catalog['cohorts']:
        c=cohort['costs']
        for metric,amount in [('climate_sensitive_county_eal',c['climate_county_eal']),('all_hazard_county_eal',c['county_eal'])]:
            rows.append([cohort['id'],cohort['label'],metric,None,None,amount,c['unit'],c['county_eal_coverage'] if metric=='all_hazard_county_eal' else None,c['expected_counties'],c['county_count'],c['unmatched_county_fips'],c['scope'],c['period'],c['price_year'],c['source_version']])
        for hazard in c['county_hazards']:
            rows.append([cohort['id'],cohort['label'],'hazard_county_eal',hazard['hazard_id'],hazard['hazard_name'],hazard['value'],c['unit'],hazard['contributing_counties'],c['expected_counties'],c['county_count'],c['unmatched_county_fips'],c['scope'],c['period'],c['price_year'],c['source_version']])
    return rows

def band(value,places=2):
    if value['median'] is None:return 'Unavailable'
    return f"{value['median']:+.{places}f} [{value['lower']:+.{places}f}, {value['upper']:+.{places}f}]"

def pathway_sections(catalog,areas):
    nations=[p for p in catalog['places'] if p['kind']=='nation']
    associated=sum(p['mapping_status']=='associated' for p in nations)
    proxy=sum(bool(p.get('proxy')) for p in nations)
    unmapped=sum(not p['area_ids'] for p in nations)
    native=[a for a in areas.values() if a['family']=='native-nex']
    regional=[a for a in areas.values() if a['family']=='usgs-nccv-loca2']
    sections=[section('Read the source area before the number',[
        f"The explorer accounts for all {len(nations)} Nations: {associated} associated, {proxy} explicitly labeled proxy contexts and {unmapped} without a supported current source-area association. It publishes {len(native)} distinct Native Resilience source areas and {len(regional)} separate USGS county/watershed contexts. Shared source areas are counted once in the climate table; no Nation-weighted national climate mean is inferred.",
        'These areas support climate interpretation; they are not comprehensive sovereign territories. A proxy is neighboring or regional context, not a validated Nation mean. Several Nations may share a source area; Navajo agency areas remain separate choices. Geometry membership uses the documented public source-area intersection, not political region membership.',
        'Native Resilience uses annual NASA NEX-GDDP-CMIP6 member values at approximately 25 km source resolution. Each model is compared with its own 1995-2014 baseline before equal-model ensemble summaries are calculated. Values below are 20-year mean changes; brackets show the 10th-90th percentile of model changes, not confidence intervals or scenario probabilities.',
        'SSP2-4.5 and SSP3-7.0 are conditional pathways. Differences need not be monotonic at an individual place or time window. Temperature is degrees Celsius; precipitation is change in mean annual total, millimetres per year. Source annual tables do not retain realization IDs, calendar names or valid daily cell coverage.',
        'The three story footprints provide regional context. Each example below uses one explicitly named climate source area selected by the explorer; it is not a climate average over the story footprint.']),]
    places={p['id']:p for p in catalog['places']}
    for cohort in catalog['cohorts']:
        area=areas[cohort['default_area']]
        place=places[cohort['default_place']]
        rows=[['Metric / unit','20-year window','SSP2-4.5 median [10th, 90th]','SSP3-7.0 median [10th, 90th]','Models']]
        for metric in area['metrics'].values():
            for period,values in metric['windows'].items():
                rows.append([h(metric['label']+' ('+metric['unit']+')'),h(period),h(band(values['ssp245'])),h(band(values['ssp370'])),h(f"{values['ssp245']['models']} / {values['ssp370']['models']}")])
        sections.append(section(cohort['label'],[
            f"Selected place: <b>{h(place['name'])}</b>. Climate source area: <b>{h(area['name'])} ({h(area['id'])})</b>; association: {h(place['mapping_status'])}. Baseline: {h(area['baseline_id'])}. Source family: {h(area['source']['label'])}.",
            'Story membership rule: '+h(cohort['rule'].rstrip('.'))+'. '+h(cohort['scope']),
            'Source: '+link(area['source']['url'],area['source']['label'])+'. Annual source SHA-256: '+h(area['source']['sha256'])+'.'],rows,[145,85,205,205,80]))
        sections[-1].update(new_page=True,keep_table=True)
    rows=[['Regional source area','Year','SSP2-4.5 annual anomaly [10th, 90th]','SSP3-7.0 annual anomaly [10th, 90th]','Models']]
    for area in regional:
        metric=area['metrics']['temp_mean']
        for selected_year in (2050,2100):
            values={scenario:{key:series[key][series['years'].index(selected_year)] for key in ('lower','median','upper')} for scenario,series in metric['series'].items()}
            rows.append([h(area['name']+' ('+area['id']+')'),h(selected_year),h(band(values['ssp245'])),h(band(values['ssp370'])),h(' / '.join(str(metric['series'][s]['models']) for s in ('ssp245','ssp370')))])
    sections.append(section('Separate USGS annual regional context',[
        'USGS NCCV LOCA2 uses a separate 1981-2010 baseline. These selected annual temperature anomalies (degrees Celsius) are copied from the provider summaries; they are not 20-year averages or year-specific weather forecasts. The explorer retains the full 1950-2100 series. SSP2-4.5 has 24 models and SSP3-7.0 has 23; memberships differ.',
        'Prepared summaries are labeled October 2023 under the pinned 2026-02-03 publication path. That path does not establish incorporation of corrected 2024 precipitation. Regional precipitation is unavailable here. Annual provider quantiles have not been averaged into a new multi-year model spread.'],rows,[200,50,195,195,80]))
    sections[-1]['new_page']=True
    sections.append(section('County cost context for the three story footprints',[
        'Whole-county Expected Annual Loss covers all county assets and residents. It is an annualized model expectation, not Tribal loss, projected climate-change damage or funding need. Each county is counted once within a footprint; footprints can overlap and their totals must not be added. Missing fields remain unavailable.',
        'FEMA National Risk Index December 2025 v1.20. The climate-sensitive subtotal uses the supported 15-hazard scope; it excludes earthquake, tsunami and volcano. A common price year is not supplied by the cached input. The companion CSV retains each hazard, county coverage and unmatched county IDs.'],
        [['Story footprint','Matched / expected counties','Climate-sensitive EAL / year','All-hazard EAL / year']]+[[h(c['label']),h(f"{c['costs']['county_count']} / {c['costs']['expected_counties']}"),money(c['costs']['climate_county_eal']),money(c['costs']['county_eal'])] for c in catalog['cohorts']],[190,110,210,210]))
    sections[-1].update(new_page=True,keep_table=True)
    sections.append(section('Downloads, source versions and interpretation',[
        link('climate-window-values.csv','Climate window values')+' contains every supported public Native source-area window, metric and pathway with model counts and source hashes. '+link('geography-coverage.csv','Geography coverage')+' accounts for all 575 Nation IDs. '+link('cohort-costs.csv','Cohort costs')+' retains whole-county cost scope and missingness.',
        'Native data terms: '+link('https://data.native-resilience.com/projections/','University of Montana Native Resilience projections, CC0')+'. Current pinned producer commit: '+h(native[0]['source']['upstream_commit'])+'. Native geometry vintage: '+h(native[0]['source']['geometry_vintage'])+'.',
        *['Regional source: '+link(a['source']['url'],a['name'])+'; SHA-256 '+h(a['source']['sha256'])+'.' for a in regional],
        'Explorer release: '+h(catalog['release_id'])+'. Catalog SHA-256: '+h(sha256((ROOT/'site/data/explorer/catalog.json').read_bytes()).hexdigest())+'.',
        ' '.join(h(value) for value in catalog['limitations'])]))
    sections[-1]['new_page']=True
    return sections

def preserve_reports(names):
    baseline=ROOT/'work/baseline-2026-10-22'
    for folder in (OUT,PUBLIC):
        for name in names:
            source=folder/name
            if not source.exists():continue
            target=baseline/folder.relative_to(ROOT)/name
            if target.exists():continue
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,target)
            if sha256(target.read_bytes()).digest()!=sha256(source.read_bytes()).digest():raise ValueError('report baseline copy failed')

def main(selected='all'):
    OUT.mkdir(exist_ok=True);PUBLIC.mkdir(exist_ok=True)
    names=['catf-assessment.html','catf-assessment.pdf','plan-discovery.html','plan-discovery.pdf','nation-hazards.csv','regional-costs.csv','plan-candidates.csv','nation-searches.csv','place-pathways.html','place-pathways.pdf','climate-window-values.csv','geography-coverage.csv','cohort-costs.csv']
    preserve_reports(names)
    shutil.copy2(PUBLIC/'report.css',OUT/'report.css')
    for name,file in [('Noto','NotoSans-Regular.ttf'),('NotoBold','NotoSans-Bold.ttf'),('Spartan','LeagueSpartan-Medium.ttf')]:pdfmetrics.registerFont(TTFont(name,str(ROOT/'site/assets/fonts'/file)))
    pdfmetrics.registerFontFamily('Noto',normal='Noto',bold='NotoBold',italic='Noto',boldItalic='NotoBold')
    risk,funding,plans=load('risk'),load('funding'),load('plans')
    catalog=load('explorer/catalog');areas=public_areas(catalog)
    if selected!='all':
        options={'catf-assessment':('Climate risk, cost and funding assessment','Frozen public-source screening · 575-Nation baseline · 22 October 2026',lambda:assessment_sections(risk,funding)),
                 'plan-discovery':('Nationwide public-plan discovery','Three separate planning questions · bounded metadata sweep · 22 October 2026',lambda:planning_sections(plans)),
                 'place-pathways':('Place, pathways and regional cost context','Public climate source areas · two pathways · explicit geography and model coverage · 22 October 2026',lambda:pathway_sections(catalog,areas))}
        title,subtitle,make=options[selected]
        sections=make()
        html_report(selected,title,subtitle,sections);pdf_report(selected,title,subtitle,sections)
        manifest_path=ROOT/'work/reports/manifest.json'
        receipts=json.loads(manifest_path.read_text(encoding='utf-8'))
        for extension in ('html','pdf'):
            filename=selected+'.'+extension
            shutil.copy2(OUT/filename,PUBLIC/filename)
            body=(PUBLIC/filename).read_bytes()
            record={'file':filename,'sha256':sha256(body).hexdigest(),'bytes':len(body)}
            receipts=[record if r['file']==filename else r for r in receipts]
        manifest_path.write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'report':selected,'files':2}))
        return
    write_csv('climate-window-values.csv',CLIMATE_FIELDS,climate_rows(areas))
    write_csv('geography-coverage.csv',GEO_FIELDS,geography_rows(catalog))
    write_csv('cohort-costs.csv',COST_FIELDS,cohort_cost_rows(catalog))
    risk_rows=[]
    for n in risk['nations']:
        ranks={x['hazard_id']:i+1 for i,x in enumerate(n['top_hazards'])}
        for x in n['hazards']:risk_rows.append([n['tribe_id'],n['display_name'],n['region_id'],x['hazard_id'],x['hazard_name'],ranks.get(x['hazard_id']),x['metric'],x['value'],x['unit'],x['status'],x.get('missing_reason'),n['percentile_rank'],n['coverage_status'],x['source_ref']])
    write_csv('nation-hazards.csv',['tribe_id','Nation','region','hazard_id','hazard','top_five_rank','metric','value','unit','status','missing_reason','physical_percentile','assessment_coverage','source_ref'],risk_rows)
    cost_fields=['geography','metric','amount','currency','price_year','period_start','period_end','scope','method','source_ref']
    cost_rows=[]
    for r in [risk['national'],*risk['regions']]:
        for c in r['costs']:cost_rows.append([c.get(k) for k in cost_fields])
        cost_rows.append([r.get('name','National'),'scanner_overlapping_place_context_eal',r['scanner_context_eal'],'USD',None,None,None,'Non-additive overlapping context; not Tribal losses',risk['methods']['scanner_context_eal'],'scanner-cpri'])
    write_csv('regional-costs.csv',cost_fields,cost_rows)
    fields=['id','tribe_ids','title','document_classes','issuing_body','canonical_landing_page_url','document_url','relationship_evidence','relationships','host_relationship','publication_year','adoption_date','update_year','plan_period','date_basis','date_evidence','date_year','age_bin','source_access_date','review_state','access_outcome','source_confidence','redistribution_terms','source_candidate_ids']
    write_csv('plan-candidates.csv',fields,[[c.get(k) for k in fields] for c in plans['candidates']])
    write_csv('nation-searches.csv',['tribe_id','Nation','region','batch','document_class','outcome','candidate_ids','searched_at','all_classes_complete','followup_flag','limitations'],[[n['tribe_id'],n['display_name'],n['region_id'],n['batch_id'],cls,c['outcome'],c['candidate_ids'],n['searched_at'],n['search_complete'],cls in n['followup_classes'],c['limitations']] for n in plans['nations'] for cls,c in n['categories'].items()])
    for name,title,subtitle,sections in [('catf-assessment','Climate risk, cost and funding assessment','Frozen public-source screening · 575-Nation baseline · 22 October 2026',assessment_sections(risk,funding)),('plan-discovery','Nationwide public-plan discovery','Three separate planning questions · bounded metadata sweep · 22 October 2026',planning_sections(plans)),('place-pathways','Place, pathways and regional cost context','Public climate source areas · two pathways · explicit geography and model coverage · 22 October 2026',pathway_sections(catalog,areas))]:
        html_report(name,title,subtitle,sections);pdf_report(name,title,subtitle,sections)
    receipts=[]
    for name in names:
        shutil.copy2(OUT/name,PUBLIC/name)
        digest=sha256((OUT/name).read_bytes()).hexdigest();assert digest==sha256((PUBLIC/name).read_bytes()).hexdigest()
        receipts.append({'file':name,'sha256':digest,'bytes':(PUBLIC/name).stat().st_size})
    (ROOT/'work/reports').mkdir(exist_ok=True)
    (ROOT/'work/reports/manifest.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'files':len(receipts),'nations':len(risk['nations']),'hazard_rows':len(risk_rows),'plan_candidates':len(plans['candidates']),'search_rows':len(plans['nations'])*3}))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',choices=['all','catf-assessment','plan-discovery','place-pathways'],default='all')
    main(parser.parse_args().report)
