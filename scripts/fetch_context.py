"""Fetch a small, explicit set of primary-source context inputs; never a corpus."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'work' / 'context'
SOURCES = {
    'federal-register-2026.html': 'https://www.govinfo.gov/content/pkg/FR-2026-01-30/html/2026-01899.htm',
    'gistemp-global.csv': 'https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv',
    'ipcc-ar6-spm.pdf': 'https://www.ipcc.ch/report/ar6/wg1/downloads/report/IPCC_AR6_WGI_SPM_final.pdf',
}

def main():
    DEST.mkdir(parents=True, exist_ok=True)
    receipts = []
    for name, url in SOURCES.items():
        path = DEST / name
        row = {'name': name, 'url': url, 'accessed_at': datetime.now(timezone.utc).isoformat()}
        try:
            with urlopen(Request(url, headers={'User-Agent': 'CATF-public-evidence/1.0'}), timeout=45) as response:
                raw = response.read()
                row.update(final_url=response.url, mime=response.headers.get_content_type())
            path.write_bytes(raw)
            row.update(status='accessed', sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))
        except Exception as error:
            row.update(status='blocked', reason=str(error))
        receipts.append(row)
        print(json.dumps(row))
    (DEST / 'receipts.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')

if __name__ == '__main__':
    main()
