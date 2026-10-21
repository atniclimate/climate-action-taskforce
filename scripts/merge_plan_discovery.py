"""Validate bounded search receipts and project public metadata; never infer plan absence."""
import argparse
from copy import deepcopy
from collections import Counter
from datetime import date, datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
CLASSES = ('climate_adaptation_plan', 'climate_vulnerability_assessment', 'hazard_mitigation_or_management_plan')
COMPLETE = {'found', 'no_matching_public_document_located'}
OUTCOMES = COMPLETE | {'blocked', 'not_searched', 'partially_searched'}
AS_OF = date(2026, 10, 21)
PUBLIC_FIELDS = ('title','issuing_body','canonical_landing_page_url','document_url','relationship_evidence','host_relationship','publication_year','adoption_date','update_year','plan_period','date_basis','date_evidence','source_access_date','review_state','access_outcome','mime_type','redistribution_terms','source_confidence','dedup_relation','discovery_note','access_instructions')

def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

def public_url(value):
    if not value:
        return None
    parts = urlsplit(value)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError(f'Unsafe source URL: {value!r}')
    if parts.hostname in {'localhost','127.0.0.1','0.0.0.0'}:
        raise ValueError('Local source URL cannot enter public projection')
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path, parts.query, ''))

def validate_times(value):
    """Permit honest date-only precision; reject impossible provenance dates."""
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {'searched_at','checked_utc','source_access_date'} and item is not None:
                datetime.fromisoformat(item.replace('Z','+00:00'))
            validate_times(item)
    elif isinstance(value, list):
        for item in value:
            validate_times(item)

def add_relationship(public, candidate):
    public.setdefault('relationships', []).append({
        'source_candidate_id':candidate['id'], 'tribe_ids':candidate['tribe_ids'],
        'document_class':candidate['document_class'],
        'evidence':candidate['relationship_evidence'],
        'host_relationship':candidate.get('host_relationship')})
    evidence = candidate['relationship_evidence']
    evidence = evidence if isinstance(evidence, list) else [evidence]
    existing = public.get('relationship_evidence', [])
    existing = existing if isinstance(existing, list) else [existing]
    public['relationship_evidence'] = list(dict.fromkeys(existing + evidence))

def public_evidence(value):
    """Keep search excerpts in the working record, not participant downloads."""
    if isinstance(value, list):
        return [public_evidence(item) for item in value]
    if not isinstance(value, str) or not any(marker in value for marker in ('\ue200', '[wordlim:', 'search excerpt:')):
        return value
    if ' is named in the search excerpt:' in value:
        name = value.split(' is named in the search excerpt:', 1)[0]
        if 'placeholder' in value.lower():
            return f'{name} is named in a placeholder section of the regional record; a completed Nation-specific plan is not verified.'
        return f'{name} was associated with this candidate by the search result; participation and document scope require confirmation.'
    if value.startswith('Search excerpt identifies '):
        return value.split(' [wordlim:', 1)[0].split('\ue200', 1)[0].strip()
    return 'Search-result evidence is retained in the discovery record; confirm the relationship, scope and dates against the linked source.'

def participant_projection(result):
    public = deepcopy(result)
    for candidate in public['candidates']:
        candidate.pop('discovery_note', None)
        for key in ('relationship_evidence', 'host_relationship', 'date_evidence'):
            candidate[key] = public_evidence(candidate.get(key))
        for relationship in candidate['relationships']:
            relationship['evidence'] = public_evidence(relationship['evidence'])
            relationship['host_relationship'] = public_evidence(relationship['host_relationship'])
    return public

def age(candidate, as_of=AS_OF):
    """Adoption year, then explicit update year, then publication year; no URL dates."""
    if not candidate.get('date_evidence'):
        return {'date_year':None,'date_measure':None,'age_bin':'Unknown'}
    for key in ('adoption_date','update_year','publication_year'):
        raw = candidate.get(key)
        if raw is None:
            continue
        try:
            year = int(str(raw)[:4])
        except (ValueError, TypeError):
            continue
        if not 1900 <= year <= as_of.year:
            continue
        years = as_of.year - year
        return {'date_year':year,'date_measure':key,'age_bin':'0–5 years' if years<=5 else '6–10 years' if years<=10 else 'Over 10 years'}
    return {'date_year':None,'date_measure':None,'age_bin':'Unknown'}

def attention(risk, categories):
    if not risk.get('high_risk') or risk.get('coverage_status') != 'evaluated':
        return []
    # A full Nation search must complete before any definite research-gap flag.
    if any(categories[c]['outcome'] not in COMPLETE for c in CLASSES):
        return []
    return [c for c in CLASSES if categories[c]['outcome']=='no_matching_public_document_located']

def merge(require_complete=False):
    base=ROOT/'data/plan-discovery'
    roster=load(base/'roster.json')
    manifest=load(base/'manifest.json')
    nations=roster['nations']
    expected={n['tribe_id']:n for n in nations}
    assert len(expected)==575 and manifest['batch_count']==23
    pins={manifest.get('source_registry_sha256'),roster.get('source_registry_sha256')}-{None}
    assert len(pins)==1, 'Roster/manifest source mismatch'
    pin=pins.pop()
    assignments={n['tribe_id']:n['batch_id'] for n in manifest['nation_assignments']}
    risk=load(ROOT/'site/data/risk.json')
    risk_by_id={n['tribe_id']:n for n in risk['nations']}
    assert set(risk_by_id)==set(expected)
    inputs=[]; records={}; raw_candidates={}
    for path in sorted((base/'batches').glob('D*.results.json')):
        batch=load(path)
        validate_times(batch)
        assert batch['source_registry_sha256']==pin, path
        bid=batch['batch_id']
        assigned={tid for tid,b in assignments.items() if b==bid}
        assert len(assigned)==25 and {n['tribe_id'] for n in batch['nation_searches']}==assigned, path
        inputs.append({'batch_id':bid,'sha256':sha256(path.read_bytes()).hexdigest()})
        for candidate in batch['candidates']:
            assert candidate['id'] not in raw_candidates, candidate['id']
            assert set(candidate['tribe_ids'])<=set(expected), candidate['id']
            assert candidate['document_class'] in CLASSES
            raw_candidates[candidate['id']]=candidate
        for n in batch['nation_searches']:
            tid=n['tribe_id']; assert tid not in records
            assert set(n['categories'])==set(CLASSES), tid
            for category in CLASSES:
                c=n['categories'][category]
                assert c['outcome'] in OUTCOMES, (tid,c['outcome'])
                if c['outcome'] in COMPLETE:
                    assert c.get('receipt') and c.get('query'), (tid,category,'missing search receipt')
                if c['outcome']=='found':
                    assert c.get('candidate_ids'), (tid,category,'found without candidate')
                else:
                    assert not c.get('candidate_ids'), (tid,category,'candidate/outcome conflict')
            records[tid]=n
    reviews_path=base/'reviews.json'
    reviews=load(reviews_path) if reviews_path.exists() else {}
    editions={}; id_map={}
    for cid,original in raw_candidates.items():
        c={**original,**reviews.get(cid,{})}
        document=public_url(c.get('document_url'))
        landing=public_url(c.get('canonical_landing_page_url'))
        assert document or landing, cid
        assert c.get('relationship_evidence'), cid
        key=document or landing
        eid='plan-'+sha256(key.encode()).hexdigest()[:16]
        id_map[cid]=eid
        if eid not in editions:
            p={k:c.get(k) for k in PUBLIC_FIELDS}
            p.update(id=eid,document_url=document,canonical_landing_page_url=landing,tribe_ids=[],document_classes=[],source_candidate_ids=[],**age(c))
            editions[eid]=p
        p=editions[eid]
        add_relationship(p,c)
        for field, values in [('tribe_ids',c['tribe_ids']),('document_classes',[c['document_class']]),('source_candidate_ids',[cid])]:
            p[field]=sorted(set(p[field])|set(values))
        if p['date_year'] is None and age(c)['date_year'] is not None:
            p.update({k:c.get(k) for k in ('date_evidence','date_basis','publication_year','adoption_date','update_year')},**age(c))
        if c.get('review_state')=='reviewed_unique_edition':
            p['review_state']=c['review_state']
    output_nations=[]
    for tid,n in expected.items():
        record=records.get(tid,{})
        categories={}
        for category in CLASSES:
            c=record.get('categories',{}).get(category,{'outcome':'not_searched','candidate_ids':[]})
            ids=c.get('candidate_ids',[])
            for cid in ids:
                assert cid in raw_candidates and tid in raw_candidates[cid]['tribe_ids'], (tid,cid)
                assert raw_candidates[cid]['document_class']==category, (tid,cid,category)
            categories[category]={'outcome':c['outcome'],'candidate_ids':sorted({id_map[cid] for cid in ids}),'limitations':c.get('limitations',[])}
        complete=all(c['outcome'] in COMPLETE for c in categories.values())
        attempted=all(c['outcome'] in COMPLETE|{'blocked'} for c in categories.values())
        rn=risk_by_id[tid]
        output_nations.append({'tribe_id':tid,'display_name':n['name'],'region_id':rn['region_id'],'batch_id':assignments[tid],'searched_at':record.get('searched_at'),'search_budget_used':record.get('search_budget_used',0),'source_domains':record.get('source_domains',[]),'search_terms':record.get('search_terms',[]),'limitations':record.get('limitations',[]),'categories':categories,'search_complete':complete,'search_attempted':attempted,'high_risk':rn['high_risk'],'percentile_rank':rn['percentile_rank'],'followup_classes':attention(rn,categories)})
    candidates=sorted(editions.values(),key=lambda c:(str(c['title']).casefold(),c['id']))
    counts=Counter(c['outcome'] for n in output_nations for c in n['categories'].values())
    complete_count=sum(n['search_complete'] for n in output_nations)
    attempted=sum(n['search_attempted'] for n in output_nations)
    if require_complete:
        assert attempted==575 and len(inputs)==23, f'Sweep incomplete: {attempted}/575 attempted; {len(inputs)}/23 batches'
    result={'schema_version':'catf-plan-discovery.v1','generated_at':datetime.now(timezone.utc).isoformat(),'data_as_of':AS_OF.isoformat(),'source_tool':'Bounded public-source metadata discovery','package_version':None,'source_commit':None,'source_dirty':None,'method_version':'catf-plan-discovery-1.0','roster_sha256':pin,'input_manifest_sha256':sha256(json.dumps(inputs,sort_keys=True).encode()).hexdigest(),'batch_inputs':inputs,'classes':list(CLASSES),'regions':[{'region_id':r['region_id'],'name':r['name']} for r in risk['regions']],'nations':output_nations,'candidates':candidates,'coverage':{'baseline_nations':575,'expected_classes':1725,'batches_completed':len(inputs),'nations_attempted_all_classes':attempted,'nations_completed_all_classes':complete_count,'category_outcomes':dict(counts),'raw_candidate_records':len(raw_candidates),'unique_source_urls':len(candidates),'reviewed_unique_editions':sum(c['review_state']=='reviewed_unique_edition' for c in candidates),'nations_with_candidate':sum(any(c['outcome']=='found' for c in n['categories'].values()) for n in output_nations),'unknown_date_sources':sum(c['age_bin']=='Unknown' for c in candidates),'followup_nations':sum(bool(n['followup_classes']) for n in output_nations)},'methods':{'search':'Three separate focused class searches per Nation, plus bounded follow-up when useful. Completed no-match outcomes describe only this search budget. Blocked attempts remain unresolved.','dedup':'Exact canonical document URL, or landing URL if no document link; fragments removed. Mirrors, plan families and editions may remain unresolved. One URL may count in multiple classes.','dates':'Year difference from 2026-10-21; adoption year first, then explicitly evidenced update year, then publication year. Retrieval dates and URL filenames never supply age. Unknown remains separate.','regions':risk['methods']['regions'],'followup':'Evaluated CPRI physical percentile >=80, all three searches complete, and no matching public source located in the listed class. This identifies research/outreach work, not absent planning or capacity.','roster':'Pinned 575-Nation baseline; all names or retained aliases present in January 2026 federal notice. Exact-name reconciliation is retained separately.','review':'Search-result candidates are not reviewed plan editions. Reviewed edition count requires explicit document/title/relationship/date review; complete content assessment is out of scope.'},'limitations':['Public discovery does not establish that a Tribe lacks a plan.','No full document harvest; source links can redirect, move or restrict access.','Candidate classification and participation evidence require confirmation before a planning census or import.','Unknown dates, unresolved editions and inaccessible sources remain visible.','Risk screening is cohort-relative, development-stage and limited by hazard coverage.'],'sources':[{'title':'January 2026 federal recognition notice','url':'https://www.govinfo.gov/content/pkg/FR-2026-01-30/html/2026-01899.htm'},{'title':'Public candidate source URLs','note':'Individual sources appear with each candidate; discovery receipts remain in the working record.'}]}
    save(base/'metadata-sidecar.json',result)
    save(ROOT/'site/data/plans.json',participant_projection(result))
    print(json.dumps(result['coverage'],ensure_ascii=False))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--require-complete',action='store_true')
    merge(parser.parse_args().require_complete)
