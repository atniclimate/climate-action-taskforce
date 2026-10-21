"""Copy deliberate participant resources and verify locally encoded QR targets."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'work/tooling'))
import fitz
import zxingcpp
from PIL import Image
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.graphics import renderSVG

TARGETS = {
    'policy-sentinel':'https://atniclimate.github.io/policy-sentinel/',
    'ddm':'https://atniclimate.github.io/dynamic-drought-module/',
    'tsdf':'https://github.com/atniclimate/TieredSovereignDataFramework',
}
def main():
    assets = ROOT/'site/assets'
    literature = ROOT/'site/literature'
    literature.mkdir(parents=True,exist_ok=True)
    (assets/'qr').mkdir(parents=True,exist_ok=True)
    (assets/'images').mkdir(parents=True,exist_ok=True)
    copies = [(ROOT/'literature/Looking Back... the legacy of the  NCAI Climate Action Task Force.pdf',literature/'catf-legacy.pdf'),
        (ROOT/'literature/TSDF-Standard-v0.9.8-illustrated-print.pdf',literature/'tsdf-v0.9.8.pdf'),
        (ROOT/'work/reference/ddm-impact-briefing-2026-10-21.png',assets/'images/ddm-impact-briefing-2026-10-21.png')]
    receipt = {'copies':[], 'qr':[]}
    for origin, target in copies:
        shutil.copyfile(origin,target)
        digest=hashlib.sha256(origin.read_bytes()).hexdigest()
        assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
        receipt['copies'].append({'file':str(target.relative_to(ROOT/'site')).replace('\\','/'),'sha256':digest})
    for name,url in TARGETS.items():
        qr=QrCodeWidget(url,barWidth=240,barHeight=240,barBorder=4,barLevel='M')
        drawing=Drawing(240,240)
        drawing.add(qr)
        svg=renderSVG.drawToString(drawing)
        # Do not expose serializer attribution; the geometry remains unchanged.
        svg=svg.replace('<!-- Created with the Python library ReportLab -->','')
        path=assets/'qr'/f'{name}.svg'
        path.write_text(svg,encoding='utf-8')
        doc=fitz.open(stream=svg.encode(),filetype='svg')
        raster=fitz.open('pdf',doc.convert_to_pdf())[0].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False)
        decoded=zxingcpp.read_barcodes(Image.frombytes('RGB',(raster.width,raster.height),raster.samples))
        assert len(decoded)==1 and decoded[0].text==url, (name,decoded)
        receipt['qr'].append({'file':f'assets/qr/{name}.svg','target':url,'decoded':decoded[0].text,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    (ROOT/'work/assets-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    (ROOT/'site/data/qr-targets.json').write_text(json.dumps(receipt['qr'],indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'verified_copies':len(copies),'decoded_qr_targets':len(TARGETS)}))

if __name__=='__main__':
    main()
