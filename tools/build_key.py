"""Measured reference PDF layout. See docs/explanation-format.md."""
import html, math, os, re, shutil, sys, tempfile
from pathlib import Path
import pymupdf as fitz

CIRC = '①②③④⑤'
W, H = 841., 1190.
# User-approved spacing: compact section header, 2mm extra right inset per column.
RIGHT_INSET = 5.67
COLS = tuple((left, right-RIGHT_INSET) for left,right in
             ((87.84,302.88),(314.64,529.68),(541.32,756.36)))
SUBJECT_BASELINE = 231.753
GRID_TOP, GRID_ROW_HEIGHT = 242.187, 12.834
BODY_AFTER_GRID = 25.1
TOP, BOTTOM = 169.966,1068.493
FONT_DIR = Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'


def font_paths():
    candidates = [FONT_DIR/'HBATANG.TTF']
    hnc = Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))/'Hnc'
    candidates += sorted(hnc.glob('**/TTF/All/HBATANG.TTF'))
    body = next((p for p in candidates if p.exists()), None)
    if not body:
        raise FileNotFoundError('한컴 바탕(HBATANG.TTF)이 필요합니다. 함초롬바탕으로 대체하지 않습니다.')
    paths = dict(body=body,head=FONT_DIR/'H2HDRM.TTF',myeong=FONT_DIR/'H2MJRE.TTF',gothic=FONT_DIR/'H2GTRE.TTF')
    for p in paths.values():
        if not p.is_file(): raise FileNotFoundError(p)
    return paths

CSS = '''
@font-face { font-family: hb; src: url(body.ttf); }
body { margin: 0; font-family: hb; font-size: 8.76pt; line-height: 1.54566; text-align: justify; }
p { margin: 0 0 0 9.96pt; }
h3 { font-size: 8.647pt; line-height: 1.565; font-weight: bold; text-align: left; margin: 7pt 0 2pt 0; }
.start { margin-top: 0; }
table { border-collapse: collapse; margin: 3pt 0 3pt 9.96pt; width: 95%; }
td, th { border: 0.36pt solid black; font-size: 8.1pt; font-weight: normal; text-align: center; padding: 1pt 1.5pt; }
sub, sup { font-size: 70%; }
'''

def read_meta_answers(md):
    s = Path(md).read_text(encoding='utf8')
    meta = dict(re.findall(r'^(\w+):\s*(.+)$',s.split('\n---',1)[0],re.M))
    ans = {}
    for q in re.split(r'(?m)^(?=## \d+\.)',s)[1:]:
        n = int(re.match(r'## (\d+)\.',q).group(1))
        a = re.findall(r'^@answer\s+([1-5])\s*$',q,re.M)
        if n in ans or len(a)!=1: raise ValueError(f'{md}: {n}번 중복 또는 @answer 오류')
        ans[n] = int(a[0])
    if not ans or sorted(ans)!=list(range(1,len(ans)+1)):
        raise ValueError(f'{md}: 문항 번호가 1부터 연속하지 않습니다')
    return meta,ans

def read_explanations(path):
    s = Path(path).read_text(encoding='utf8')
    out = {}
    for q in re.split(r'(?m)^(?=## \d+\.)',s)[1:]:
        head,_,body = q.partition('\n')
        n = int(re.match(r'## (\d+)\.',head).group(1))
        if n in out: raise ValueError(f'{path}: {n}번 중복')
        title = re.sub(r'^## \d+\.\s*','',head)
        m = re.match(r'\s*@answer ([1-5])\s*\n',body)
        a = int(m.group(1)) if m else None
        body = body[m.end():] if m else body
        paras = [p.strip() for p in re.split(r'\n\s*\n',body.strip()) if p.strip()]
        out[n] = (title,a,paras)
    return out

def esc_keep_tags(t):
    t = html.escape(t,quote=False)
    return re.sub(r'&lt;(/?(?:b|i|sub|sup)|br\s*/?)&gt;',r'<\1>',t)

def paragraph_html(p):
    lines = p.splitlines()
    if len(lines)>1 and lines[0].startswith('|') and re.fullmatch(r'[\s|:\-]+',lines[1]):
        rows = [line for i,line in enumerate(lines) if i!=1]
        return '<table>'+''.join('<tr>'+''.join('<td>'+esc_keep_tags(c.strip())+'</td>' for c in line.strip().strip('|').split('|'))+'</tr>' for line in rows)+'</table>'
    return '<p>'+esc_keep_tags(' '.join(lines))+'</p>'

def section_html(expl):
    parts=[]
    for n,(title,_,paras) in sorted(expl.items()):
        cls = ' class="start"' if not parts else ''
        parts.append(f'<h3{cls}>{n}. {esc_keep_tags(title)}</h3>')
        parts.extend(paragraph_html(p) for p in paras)
    return ''.join(parts)

def text_center(page,text,x,baseline,size,key,fonts,italic=False):
    font,_ = fonts[key]
    pos=fitz.Point(x-font.text_length(text,fontsize=size)/2,baseline)
    morph=(pos,fitz.Matrix(1,0,.18,1,0,0)) if italic else None
    page.insert_text(pos,text,fontsize=size,fontname=key,morph=morph)

def draw_title(page,meta,fonts):
    page.draw_rect(fitz.Rect(89.782,83.723,753.256,155.692),width=1.678,radius=.10)
    title=' '.join(filter(None,(meta.get('year'),meta.get('exam'))))
    text_center(page,title,421.519,108,21.3549,'head',fonts)
    text_center(page,'정답 및 해설',421.519,146.16,27.234,'head',fonts)

def draw_section(page,meta,ans,fonts):
    for y in (184.240,185.319,207.749,208.829):
        page.draw_line((101.649,y),(286.007,y),width=.36)
    area=meta.get('area','탐구')
    if not area.endswith('영역'): area+=' 영역'
    period=meta.get('period','').replace('제','').strip()
    label=f'{period} {area}'
    text_center(page,label,193.828,201.872,14.5049,'head',fonts)
    half=fonts['head'][0].text_length(label,fontsize=14.5049)/2
    for x in (193.828-half-9,193.828+half+9):
        page.draw_circle((x,196.8),2.15,color=None,fill=(0,0,0))
    # No empty placeholder for the reference publisher's notice.
    text_center(page,f'[{meta.get("subject","")}]',193.828,SUBJECT_BASELINE,13.545,'myeong',fonts)
    x,y,cw,rh=98.412,GRID_TOP,190.951/10,GRID_ROW_HEIGHT
    rows=math.ceil(len(ans)/5)
    for n,a in sorted(ans.items()):
        row,pair=divmod(n-1,5)
        xx,yy=x+pair*2*cw,y+row*rh
        page.draw_rect(fitz.Rect(xx,yy,xx+cw,yy+rh),color=None,fill=(.898,)*3)
        text_center(page,str(n),xx+cw/2,yy+9.73,8.76,'gothic',fonts,italic=True)
        text_center(page,CIRC[a-1],xx+1.5*cw,yy+9.73,8.76,'body',fonts)
    for c in range(1,10): page.draw_line((x+c*cw,y),(x+c*cw,y+rows*rh),width=.36)
    for r in range(1,rows): page.draw_line((x,y+r*rh),(x+10*cw,y+r*rh),width=.36)
    page.draw_rect(fitz.Rect(x,y,x+10*cw,y+rows*rh),width=1.079)

def build(out_pdf,mds,answers_only=False):
    '''Return (document, []) for build_final.py compatibility; fail before rendering invalid sources.'''
    sections=[]
    for md in mds:
        meta,ans=read_meta_answers(md)
        expl={} if answers_only else read_explanations(str(Path(md).with_name(Path(md).stem+'_해설.md')))
        if not answers_only:
            if set(ans)!=set(expl): raise ValueError(f'{md}: 문항/해설 번호 불일치: {sorted(set(ans)^set(expl))}')
            for n,(_,a,paras) in expl.items():
                if a!=ans[n] or not paras: raise ValueError(f'{md} {n}번: 정답 불일치 또는 빈 해설 ({ans[n]} / {a})')
        sections.append((meta,ans,expl))
    paths=font_paths()
    fonts={k:(fitz.Font(fontfile=str(p)),p) for k,p in paths.items()}
    doc=fitz.open()
    with tempfile.TemporaryDirectory(prefix='examkit-key-',ignore_cleanup_errors=True) as tmp:
        shutil.copyfile(paths['body'],Path(tmp)/'body.ttf')
        archive=fitz.Archive(tmp)
        for si,(meta,ans,expl) in enumerate(sections):
            tmp_pdf=Path(tmp)/f'section{si}.pdf'
            writer=fitz.DocumentWriter(str(tmp_pdf))
            pg,col=0,0
            dev=writer.begin_page(fitz.Rect(0,0,W,H))
            top=GRID_TOP+math.ceil(len(ans)/5)*GRID_ROW_HEIGHT+BODY_AFTER_GRID
            for n,item in sorted(expl.items()):
                story=fitz.Story(section_html({n:item}),user_css=CSS,archive=archive)
                _,whole=story.place(fitz.Rect(0,0,COLS[0][1]-COLS[0][0],10000))
                full_height=whole[3]
                story.reset()
                # Keep the heading and at least two body lines in the same column.
                # MuPDF Story does not reliably implement CSS break-after: avoid.
                if BOTTOM-top<57:
                    col+=1
                    top=TOP
                while True:
                    if col==3:
                        writer.end_page()
                        dev=writer.begin_page(fitz.Rect(0,0,W,H))
                        pg,col=pg+1,0
                    left,right=COLS[col]
                    bottom=BOTTOM
                    # Do not push a lone final line (e.g. '이다.') into the next column.
                    spill=full_height-(BOTTOM-top)
                    if 0<spill<27.08:
                        bottom-=27.08-spill
                    more,filled=story.place(fitz.Rect(left,top,right,bottom))
                    story.draw(dev)
                    if not more:
                        top=filled[3]+7
                        break
                    col+=1
                    top=TOP
                    full_height=10000  # the remaining story is already in continuation
                    if pg>100: raise RuntimeError('해설이 지면에 들어가지 않습니다')
            writer.end_page()
            writer.close()
            del writer
            with fitz.open(tmp_pdf) as sec:
                for k,page in enumerate(sec):
                    # The reference uses stroked Haansoft Batang for question heads.
                    # Set text render mode once per font-size run, not a duplicate overlay.
                    for xref in page.get_contents():
                        stream=sec.xref_stream(xref)
                        def weight(m):
                            size=float(m.group(1))
                            return m.group(0)+(b' 0.16 w 2 Tr' if abs(size-8.647)<.001 else b' 0 Tr')
                        sec.update_stream(xref,re.sub(rb'/F\d+ ([\d.]+) Tf',weight,stream))
                    for key,(_,path) in fonts.items(): page.insert_font(fontname=key,fontfile=str(path))
                    if k==0:
                        draw_title(page,meta,fonts)
                        draw_section(page,meta,ans,fonts)
                    for x in (307.224,533.656): page.draw_line((x,TOP),(x,BOTTOM),width=.36)
                    text_center(page,str(k+1),421.519,1101.962,20.0247,'myeong',fonts,italic=True)
                doc.insert_pdf(sec)
    doc.set_metadata({'title':'정답 및 해설','creator':'mock-exam-kit / build_key.py'})
    doc.subset_fonts()
    return doc,[]

if __name__=='__main__':
    args=sys.argv[1:]
    only='--answers-only' in args
    args=[a for a in args if a!='--answers-only']
    if len(args)<2: raise SystemExit('사용법: python tools/build_key.py out.pdf content/1교시.md …')
    doc,_=build(args[0],args[1:],only)
    doc.subset_fonts()
    doc.save(args[0],garbage=4,deflate=True)
    print(args[0],doc.page_count,'쪽')
