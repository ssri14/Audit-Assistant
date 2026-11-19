"""PDF intake, native-span highlighting and deterministic bounded calculations."""
import ast
from decimal import Decimal
import hashlib
from pathlib import Path
import re
import threading
import pypdfium2 as pdfium
from pypdf import PdfReader,PdfWriter
from pypdf.annotations import Highlight
from pypdf.generic import ArrayObject,FloatObject,NameObject,TextStringObject

LOCK=threading.RLock()
def canonical(text):return ' '.join(text.split())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inspect_pdf(path):
    reader=PdfReader(path)
    if reader.is_encrypted:raise ValueError('Use unlocked PDFs for this pre-release.')
    if not len(reader.pages):raise ValueError('An uploaded PDF has no pages.')
    return [{'page':i+1,'native_text':p.extract_text() or '',
             'needs_vision':len((p.extract_text() or '').strip())<80 or bool(list(p.images))} for i,p in enumerate(reader.pages)]

def render(path,page,scale=300/72):
    with LOCK:
        doc=pdfium.PdfDocument(str(path))
        try:
            p=doc[page-1];bitmap=p.render(scale=scale)
            try:image=bitmap.to_pil().convert('RGB').copy()
            finally:bitmap.close();p.close()
            return image,len(doc)
        finally:doc.close()

def windows(text,size=7000,overlap=700):
    start=0
    while start<len(text):
        end=min(len(text),start+size)
        if end<len(text):
            boundary=text.rfind('\n',start+size//2,end)
            if boundary>start:end=boundary
        yield {'text':text[start:end],'start_offset':start,'end_offset':end}
        if end==len(text):break
        start=max(start+1,end-overlap)

def calculate(expression):
    if not isinstance(expression,str) or len(expression)>200:raise ValueError('Calculation is too long.')
    root=ast.parse(expression,mode='eval')
    if sum(1 for _ in ast.walk(root))>70:raise ValueError('Calculation is too complex.')
    def visit(node):
        if isinstance(node,ast.Expression):return visit(node.body)
        if isinstance(node,ast.Constant) and type(node.value) in [int,float]:
            result=Decimal(ast.get_source_segment(expression,node))
        elif isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            result=visit(node.operand)*(1 if isinstance(node.op,ast.UAdd) else -1)
        elif isinstance(node,ast.BinOp):
            a,b=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Add):result=a+b
            elif isinstance(node.op,ast.Sub):result=a-b
            elif isinstance(node.op,ast.Mult):result=a*b
            elif isinstance(node.op,ast.Div):result=a/b
            else:raise ValueError('Only +, -, *, / and parentheses are supported.')
        else:raise ValueError('Only numeric arithmetic is supported.')
        if not result.is_finite() or abs(result)>Decimal('1e30'):raise ValueError('Calculation exceeds supported range.')
        return result
    return str(visit(root))

def annotate(source,candidates,reviews,destination):
    """Only verified, uniquely located native text receives a highlight."""
    mapping=[];byid={r['candidate_id']:r for r in reviews};writer=PdfWriter();writer.append(PdfReader(source))
    with LOCK:
        doc=pdfium.PdfDocument(str(source))
        try:
            for c in candidates:
                entry={'id':c['id'],'page':c['page'],'status':'page-only'};mapping.append(entry)
                if not c.get('quote_verified') or c.get('reading_route')!='native':continue
                p=doc[c['page']-1];tp=p.get_textpage();search=tp.search(canonical(c['quote']),match_case=True)
                try:
                    match=search.get_next()
                    if match is None or search.get_next() is not None:continue
                    tp.count_rects();rects=[tp.get_rect(i) for i in range(tp.count_rects(*match))]
                    if not rects:continue
                    bounds=(min(r[0] for r in rects),min(r[1] for r in rects),max(r[2] for r in rects),max(r[3] for r in rects))
                    quads=ArrayObject([FloatObject(v) for l,b,r,t in rects for v in [l,t,r,t,l,b,r,b]])
                    ann=Highlight(rect=bounds,quad_points=quads,highlight_color='fff1a8')
                    r=byid.get(c['id'],{})
                    ann[NameObject('/Contents')]=TextStringObject(f'Audit Assistant lead {c["id"]}\n{r.get("disposition","Awaiting review")}\n{r.get("audit_note",c["possible_concern"])}\nFor human examination; not a verdict.')
                    writer.add_annotation(page_number=c['page']-1,annotation=ann);entry.update(status='highlighted',rectangles=rects)
                finally:search.close();tp.close();p.close()
        finally:doc.close()
    writer.write(destination);return mapping
