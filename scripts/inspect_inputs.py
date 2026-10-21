"""Read-only source snapshot and narrative extraction for local implementation."""
import importlib.util
import json
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work'
repos = ['policy-sentinel', 'dynamic-drought-module', 'plan-assessor', 'atni-design-system',
         'ATNI-CAST', 'land-use-analyzer', 'ATNI-GeoBase', 'community-connector']
state = {}
for name in repos:
    path = Path('I:/') / name
    result = {}
    for key, args in [('head', ['rev-parse', 'HEAD']), ('dirty', ['status', '--porcelain=v1'])]:
        run = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True,
                             encoding='utf-8', creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        result[key] = run.stdout.strip() if run.returncode == 0 else {'error': run.stderr.strip()}
    state[name] = result
(WORK / 'source-state.json').write_text(json.dumps(state, indent=2), encoding='utf-8')
print(json.dumps(state, indent=2))
print('available', {name: importlib.util.find_spec(name) is not None
                    for name in ['reportlab', 'fitz', 'pypdf', 'qrcode', 'cv2', 'PIL', 'pptx', 'playwright']})
ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
      'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
deck = next(ROOT.glob('*.pptx'))
with zipfile.ZipFile(deck) as archive:
    slides = []
    for number in [1, 2, 3]:
        tree = ET.fromstring(archive.read(f'ppt/slides/slide{number}.xml'))
        shapes = []
        for shape in tree.findall('.//p:sp', ns):
            paragraphs = [' '.join(t.text or '' for t in p.findall('.//a:t', ns))
                          for p in shape.findall('.//a:p', ns)]
            text = '\n'.join(p for p in paragraphs if p)
            if text:
                shapes.append({'text': text, 'xml': ET.tostring(shape, encoding='unicode')})
        slides.append({'slide': number, 'shapes': shapes})
    (WORK / 'deck' / 'narrative.json').write_text(json.dumps(slides, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps([{**slide, 'shapes': [s['text'] for s in slide['shapes']]} for slide in slides], ensure_ascii=False, indent=2))
catalog = json.loads(Path('I:/plan-assessor/data/library/catalog.json').read_text(encoding='utf-8'))
print('catalog keys', list(catalog))
for key in ['tribes', 'candidates']:
    value = catalog.get(key)
    print(key, type(value).__name__, len(value) if value else 0)
    print(json.dumps(value[:1] if isinstance(value, list) else dict(list(value.items())[:1]) if isinstance(value, dict) else value, ensure_ascii=False, indent=2))
