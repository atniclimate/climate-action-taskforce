"""Project verified primary observations and reconcile the pinned roster by exact names."""
import csv
import hashlib
import html
import io
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/context'

def normalize(value):
    value = unicodedata.normalize('NFKD', value).casefold()
    return ''.join(c for c in value if c.isalnum())

def main():
    receipts = json.loads((WORK / 'receipts.json').read_text(encoding='utf-8'))
    by_name = {row['name']: row for row in receipts}
    raw = (WORK / 'gistemp-global.csv').read_text(encoding='utf-8')
    rows = list(csv.DictReader(io.StringIO(raw.split('\n', 1)[1])))
    selected = [{'year': int(row['Year']), 'anomaly_c': float(row['J-D'])}
                for row in rows if row['Year'] in {'2020','2021','2022','2023','2024'}]
    assert [row['year'] for row in selected] == list(range(2020,2025))
    assert all(-5 < row['anomaly_c'] < 5 for row in selected)
    context = {
        'schema_version':'catf-context.v1', 'generated_at':by_name['gistemp-global.csv']['accessed_at'],
        'accessed_at':by_name['gistemp-global.csv']['accessed_at'], 'data_as_of':'2024-12-31',
        'source_tool':'NASA GISTEMP v4 / NOAA NCEI / IPCC AR6', 'package_version':None,
        'source_commit':None, 'source_dirty':False, 'method_version':'catf-context-1',
        'input_manifest_sha256':hashlib.sha256((WORK/'receipts.json').read_bytes()).hexdigest(),
        'coverage':{'years':[2020,2021,2022,2023,2024], 'temperature_geography':'global', 'cost_geography':'United States'},
        'temperature':selected,
        'temperature_method':{'variable':'annual mean global surface temperature anomaly','unit':'degree Celsius','baseline':'1951-1980','column':'J-D','source_url':by_name['gistemp-global.csv']['url'],'input_sha256':by_name['gistemp-global.csv']['sha256']},
        'scenarios':{'source_url':by_name['ipcc-ar6-spm.pdf']['url'],'input_sha256':by_name['ipcc-ar6-spm.pdf']['sha256'],'locator':'Table SPM.1','variable':'global surface temperature change','baseline':'1850-1900','window':'2081-2100','unit':'degree Celsius','uncertainty':'very likely range','values':[{'scenario':'SSP2-4.5','best':2.7,'low':2.1,'high':3.5},{'scenario':'SSP3-7.0','best':3.6,'low':2.8,'high':4.6}]},
        'cost_context':{'amount':182700000000,'currency':'USD','price_year':2024,'period_start':'2024-01-01','period_end':'2024-12-31','event_count':27,'geography':'United States','scope':'Billion-dollar weather and climate disaster events; all-U.S. context, not Tribal estimates','source_url':'https://www.ncei.noaa.gov/news/national-climate-202413','source_publication':'2025-01-10','method':'NOAA January 2025 assessment; CPI-adjusted 2024 dollars; later revisions possible'},
        'limitations':['The selected five-year window ends in 2024 to align with the NOAA archive, although GISTEMP contains later observations.','Global temperature is not a local hazard projection.','All-U.S. disaster costs are not Tribal losses or a climate-attribution measure.','Selected SSP pathways are conditional futures, not probability bounds.'],
        'sources':[{'title':'NASA GISTEMP v4','url':'https://data.giss.nasa.gov/gistemp/'},{'title':'NOAA U.S. climate assessment 2024','url':'https://www.ncei.noaa.gov/news/national-climate-202413'},{'title':'IPCC AR6 Working Group I, Table SPM.1','url':by_name['ipcc-ar6-spm.pdf']['url']}],
    }
    output = ROOT/'site/data/context.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(context,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    roster = json.loads((ROOT/'data/plan-discovery/roster.json').read_text(encoding='utf-8'))
    official = html.unescape(re.sub('<[^>]+>','',(WORK/'federal-register-2026.html').read_text(encoding='utf-8')))
    compact = normalize(official)
    matched, unmatched = [], []
    for nation in roster['nations']:
        names = [nation['name'], *nation['alternate_names']]
        evidence = next((name for name in names if normalize(name) in compact),None)
        (matched if evidence else unmatched).append({'tribe_id':nation['tribe_id'],'name':nation['name'],'matched_text':evidence})
    reconciliation = {'schema_version':'catf-roster-reconciliation.v1','official_notice':'2026-01899','official_count':575,
        'source_url':by_name['federal-register-2026.html']['url'],'source_sha256':by_name['federal-register-2026.html']['sha256'],
        'baseline_count':575,'baseline_sha256':roster['source_registry_sha256'],'method':'Exact punctuation/whitespace/diacritic-normalized names or existing roster aliases in official notice; unresolved names require manual relationship evidence.',
        'matched':matched,'unmatched':unmatched,'status':'manual_review_required' if unmatched else 'all_baseline_names_present',
        'limitations':['Name presence is checked; one-to-one official-entry reconciliation must also account for aliases and jointly listed bands.']}
    (ROOT/'data/plan-discovery/roster-reconciliation.json').write_text(json.dumps(reconciliation,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'temperature':selected,'roster_matched':len(matched),'roster_unmatched':unmatched},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
