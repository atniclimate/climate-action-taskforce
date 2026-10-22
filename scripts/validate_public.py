"""Focused release-boundary checks for the deliberate static artifact and reports."""
import csv
from hashlib import sha256
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import fitz

ROOT=Path(__file__).resolve().parents[1]; SITE=ROOT/'site'
ALLOWED={'.html','.css','.js','.json','.svg','.png','.jpg','.jpeg','.pdf','.csv','.ttf','.woff2','.txt'}
LOCAL=re.compile(r'(?i)(?:\b[CIH]:[\\/]|file:///|\\Users\\|/Users/|AppData[\\/])')
SECRET=re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{30,}|sk-[A-Za-z0-9]{35,}')

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if attrs.get('id'):self.ids.add(attrs['id'])
        self.links.extend(attrs[k] for k in ('href','src') if attrs.get(k))

def main():
    errors=[];files=list(SITE.rglob('*'));files=[p for p in files if p.is_file()]
    for path in files:
        relative=path.relative_to(SITE).as_posix()
        if path.name!='.nojekyll' and path.suffix not in ALLOWED:errors.append('Unexpected public type: '+relative)
        if any(p in {'.git','work','node_modules','__pycache__'} for p in path.relative_to(SITE).parts):errors.append('Private directory: '+relative)
        if path.suffix in {'.html','.css','.js','.json','.svg','.csv','.txt'}:
            body=path.read_text(encoding='utf-8-sig')
            if LOCAL.search(body):errors.append('Local path in '+relative)
            if SECRET.search(body):errors.append('Credential-like content in '+relative)
            if '\ue200' in body or '[wordlim:' in body:errors.append('Raw search tool markup in '+relative)
        if path.suffix=='.html':
            parsed=Links();parsed.feed(body)
            for url in parsed.links:
                parts=urlsplit(url)
                if parts.scheme or parts.netloc or not parts.path:continue
                target=(path.parent/unquote(parts.path)).resolve()
                if not target.is_relative_to(SITE.resolve()) or not target.is_file():errors.append(f'Broken/escaping local link: {relative} -> {url}')
        if path.suffix=='.pdf':
            with fitz.open(path) as pdf:
                if len(pdf)==0:errors.append('Empty PDF: '+relative)
                text='\n'.join(page.get_text() for page in pdf)
                if LOCAL.search(text):errors.append('Local path in PDF: '+relative)
                if '\ufffd' in text:errors.append('Replacement glyph in PDF: '+relative)
    data={name:json.loads((SITE/'data'/f'{name}.json').read_text(encoding='utf-8')) for name in ['risk','funding','plans','context','sources','qr-targets']}
    risk,plans=data['risk'],data['plans']
    opportunities=json.loads((SITE/'data/opportunities.json').read_text(encoding='utf-8'))
    assert opportunities['checked_at']=='2026-10-21'
    assert opportunities['programs'][0]['envelope_usd']==3500000
    assert all(p['envelope_usd'] is None for p in opportunities['programs'][1:])
    assert len(risk['nations'])==len(plans['nations'])==575
    assert set(n['tribe_id'] for n in risk['nations'])==set(n['tribe_id'] for n in plans['nations'])
    assert plans['coverage']['nations_attempted_all_classes']==575, 'Unfinished sweep cannot pass final artifact check'
    assert plans['coverage']['batches_completed']==23
    assert sum(plans['coverage']['category_outcomes'].values())==1725
    assert not re.search(r'(?i)(?<![/\w])work[\\/]|docs[\\/]discovery|catalog.{0,20}(?:hash|sha256)',json.dumps(plans)), 'Internal plan evidence reference in public projection'
    catalog=json.loads((SITE/'data/explorer/catalog.json').read_text(encoding='utf-8'))
    nations=[p for p in catalog['places'] if p['kind']=='nation']
    assert len(nations)==575 and {p['tribe_id'] for p in nations}=={n['tribe_id'] for n in risk['nations']}
    assert sum(p['mapping_status']=='unmapped' for p in nations)==28
    assert sum(p.get('proxy',False) for p in nations)==34
    for key,asset in catalog['files'].items():
        assert re.fullmatch(r'(data|assets)/explorer/[a-zA-Z0-9_./-]+',asset['path']) and '..' not in asset['path'].split('/'),key
        path=(SITE/asset['path']).resolve()
        assert path.is_relative_to(SITE.resolve()) and path.is_file(),key
        assert path.stat().st_size==asset['bytes'] and sha256(path.read_bytes()).hexdigest()==asset['sha256'],key
    for place in catalog['places']:
        assert all(a in catalog['areas'] for a in place['area_ids']),place['id']
    for area in catalog['areas'].values():
        assert area['file_id'] in catalog['files'] and area.get('geometry_file') in catalog['files'],area['id']
    for cohort in catalog['cohorts']:
        assert len(cohort['county_fips'])==len(set(cohort['county_fips']))
        assert cohort['costs']['county_count']+len(cohort['costs']['unmatched_county_fips'])==cohort['costs']['expected_counties']
    incremental=[p for p in files if '/explorer/' in p.as_posix() or '/leaflet-1.9.4/' in p.as_posix() or p.parent.name in {'components','state'} or p.name in {'explorer.js','catalog.js'}]
    assert sum(p.stat().st_size for p in incremental)<16*1024*1024,'Incremental explorer payload exceeds16MiB'
    with (SITE/'literature/nation-searches.csv').open(encoding='utf-8-sig',newline='') as f:assert len(list(csv.DictReader(f)))==1725
    with (SITE/'literature/nation-hazards.csv').open(encoding='utf-8-sig',newline='') as f:
        rows=list(csv.DictReader(f));assert len(rows)==sum(len(n['hazards']) for n in risk['nations'])
        assert any(r['value']=='' and r['status']=='unavailable' for r in rows),'Missing values must survive CSV projection'
    report_names=['catf-assessment.html','catf-assessment.pdf','plan-discovery.html','plan-discovery.pdf','nation-hazards.csv','regional-costs.csv','plan-candidates.csv','nation-searches.csv']
    report_names += ['place-pathways.html','place-pathways.pdf','climate-window-values.csv','geography-coverage.csv','cohort-costs.csv']
    for name in report_names:
        assert (ROOT/'literature'/name).read_bytes()==(SITE/'literature'/name).read_bytes(),name
    for filename in ['catf-assessment.pdf','plan-discovery.pdf']:
        with fitz.open(SITE/'literature'/filename) as pdf:
            body=' '.join(page.get_text() for page in pdf)
            assert '575' in body and 'not' in body and 'Tribal' in body,filename
            assert len(body)>10000,filename
    assert not errors,'\n'.join(errors)
    report={'passed':True,'public_files':len(files),'public_bytes':sum(p.stat().st_size for p in files),'nation_ids':575,'class_outcomes':1725,'report_copies':len(report_names),'explorer_places':len(catalog['places']),'explorer_incremental_bytes':sum(p.stat().st_size for p in incremental),'checks':['file allowlist','no local paths or credential patterns','HTML local links confined to site','PDF text/glyph scan','risk/plan ID join','complete bounded sweep','CSV missingness and row counts','report byte-identical copies','explorer asset paths, hashes and sizes','575 climate mapping outcomes','unique county cohort joins','16 MiB incremental explorer budget'],'artifact_files':[{'path':p.relative_to(SITE).as_posix(),'sha256':sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
    target=ROOT/'work/review/public-validation.json';target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='artifact_files'}))

if __name__=='__main__':main()
