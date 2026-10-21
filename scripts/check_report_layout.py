"""Check authored PDF text boundaries and render representative pages for visual review."""
import json
from pathlib import Path
import subprocess
import fitz

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'work/reports/rendered';out.mkdir(parents=True,exist_ok=True)
receipts=[]
for name in ['catf-assessment','plan-discovery']:
    with fitz.open(ROOT/'site/literature'/f'{name}.pdf') as pdf:
        issues=[]
        for index,page in enumerate(pdf):
            for block in page.get_text('dict')['blocks']:
                for line in block.get('lines',[]):
                    for span in line['spans']:
                        x0,y0,x1,y1=span['bbox']
                        if x0<30 or x1>page.rect.width-30 or y0<20 or y1>page.rect.height-10:
                            issues.append({'page':index+1,'text':span['text'],'bounds':span['bbox']})
        assert not issues,issues
        pages=sorted({0,1,2,len(pdf)//2,len(pdf)-1})
        for index in pages:
            subprocess.run(['pdftoppm','-f',str(index+1),'-l',str(index+1),'-singlefile','-scale-to','1200','-png',str(ROOT/'site/literature'/f'{name}.pdf'),str(out/f'{name}-{index+1}')],check=True,capture_output=True)
        receipts.append({'report':name,'pages':len(pdf),'text_boundary_check':'pass','rendered_pages':[i+1 for i in pages]})
(ROOT/'work/reports/layout-check.json').write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipts))
