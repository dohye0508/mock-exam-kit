"""Measured reference PDF layout. See docs/explanation-format.md."""
import hashlib, html, math, os, re, shutil, sys, tempfile
from pathlib import Path
import pymupdf as fitz
try:
    from .key_math import render_math
    from .key_tables import plan_columns
except ImportError:
    from key_math import render_math
    from key_tables import plan_columns

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
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def font_paths():
    if os.environ.get('EXAMKIT_TYPST_ROOT'):
        directory = Path(os.environ['EXAMKIT_TYPST_ROOT']) / 'fonts'
        paths = dict(body=directory/'HBATANG-native-fallback.ttf', head=directory/'H2HDRM.TTF',
                     myeong=directory/'H2MJRE.TTF', gothic=directory/'H2GTRE.TTF')
        for path in paths.values():
            if not path.is_file(): raise FileNotFoundError(path)
        return paths
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
table { border-collapse: collapse; margin: 3pt 0 3pt 9.96pt; width: auto; }
td, th { border: 0.36pt solid black; font-size: 8.76pt; font-weight: normal; text-align: center; vertical-align: middle; line-height: 11.8pt; padding: 0 1.5pt; }
sub, sup { font-size: 70%; }
.equation { text-align: left; margin: 4pt 0 4pt 9.96pt; }
.illustration { text-align: center; margin: 5pt 0 4pt 9.96pt; }
.caption { text-align: center; font-size: 7.8pt; margin: 1pt 0 4pt 9.96pt; }
'''

def read_meta_answers(md):
    s = Path(md).read_text(encoding='utf8')
    meta = dict(re.findall(r'^(\w+):\s*(.+)$',s.split('\n---',1)[0],re.M))
    ans = {}
    for q in re.split(r'(?m)^(?=## \d+\.)',s)[1:]:
        n = int(re.match(r'## (\d+)\.',q).group(1))
        a = re.findall(r'^@answer\s+([1-5])\s*$',q,re.M)
        if n in ans: raise ValueError(f'{md}: {n}번 중복')
        if len(a)!=1:
            bad = re.findall(r'^@answer\s+(\S+)',q,re.M)
            raise ValueError(f'{md}: {n}번 @answer는 정답 선택지 번호(1~5) 하나여야 합니다 (지금: {bad or "없음"})')
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
        bad = re.match(r'\s*@answer\s+(\S+)',body)
        if bad and not m:
            raise ValueError(f'{path}: {n}번 @answer에는 문항 번호가 아니라 정답 선택지 번호(1~5)를 적습니다 (지금: {bad.group(1)})')
        a = int(m.group(1)) if m else None
        body = body[m.end():] if m else body
        paras = [p.strip() for p in re.split(r'\n\s*\n',body.strip()) if p.strip()]
        out[n] = (title,a,paras)
    return out

def esc_keep_tags(t):
    t = html.escape(t,quote=False)
    return re.sub(r'&lt;(/?(?:b|i|sub|sup)|br\s*/?)&gt;',r'<\1>',t)

class ExplanationAssets:
    """Local, reproducible 600dpi mathtext images and existing illustration assets for Story.

    LaTeX math syntax is rendered with matplotlib (no TeX installation/network).
    Unknown commands and over-wide equations fail instead of printing raw markup.
    """
    def __init__(self, directory):
        self.directory = Path(directory)
        self.cache = {}
        self.heights = {}
        self.depths = {}
        self.widths = {}
        self.bodyfont = fitz.Font(fontfile=str(font_paths()['body']))

    def math(self, expression, display=False):
        expression = expression.strip()
        key = (expression, display)
        if key in self.cache:
            return self.cache[key]
        chemical=re.fullmatch(r'\\mathrm\{([A-Za-z0-9()]+)\}((?:[_^](?:\{[0-9+\-]+\}|[0-9]))*)',expression)
        if chemical and not display:
            base,tail=chemical.groups()
            result=html.escape(base)
            width=self.bodyfont.text_length(base,fontsize=8.76)
            for op,value in re.findall(r'([_^])(\{[^}]+\}|[0-9])',tail):
                value=value.strip('{}').replace('-','−')
                tag='sub' if op=='_' else 'sup'
                result+=f'<{tag}>'+html.escape(value)+f'</{tag}>'
                width+=self.bodyfont.text_length(value,fontsize=6.132)
            height,depth=8.76,0.0
        else:
            width,height,depth,name = render_math(expression,display,self.directory)
            if width > COLS[0][1]-COLS[0][0]-12:
                raise ValueError(f'수식이 단 폭을 넘습니다. 계산을 여러 줄로 나누세요: {expression}')
            vertical='bottom' if display else f'-{depth:.3f}pt'
            result = (f'<img src="{name}" width="{width:.3f}" height="{height:.3f}" '
                      f'style="width:{width:.3f}pt;height:{height:.3f}pt;vertical-align:{vertical}" '
                      f'alt="{html.escape(expression,quote=True)}"/>')
            if not display:
                line_height=max(13.54,height+2*depth+1)
                result=f'<span style="line-height:{line_height:.3f}pt">'+result+'</span>'
        self.cache[key] = result
        self.heights[key] = height
        self.depths[key] = depth
        self.widths[key] = width
        return result

    def inline(self, text):
        if '$$' in text:
            raise ValueError('$$ 수식은 위아래에 빈 줄을 둔 단독 문단으로 씁니다. 문장 안에서는 $…$를 쓰세요: ' + text[:60])
        pieces = re.split(r'(?<!\\)(\$[^$]+\$)', text)
        return ''.join(self.math(s[1:-1]) if s.startswith('$') and s.endswith('$')
                       else esc_keep_tags(s) for s in pieces)

    def measure(self, text):
        width=0
        for part in re.split(r'(?<!\\)(\$[^$]+\$)',text):
            if part.startswith('$') and part.endswith('$'):
                expression=part[1:-1].strip()
                self.math(expression)
                width+=self.widths[(expression,False)]
            else:
                plain=html.unescape(re.sub(r'<[^>]*>','',part))
                width+=self.bodyfont.text_length(plain,fontsize=8.76)
        return width

    def illustration(self, label, path):
        from PIL import Image, ImageOps
        source = (ROOT/path).resolve()
        if not source.is_relative_to(ROOT) or not source.is_file():
            raise ValueError(f'해설 그림은 저장소 안의 실제 파일이어야 합니다: {path}')
        name = 'figure-' + hashlib.sha256(source.read_bytes()).hexdigest()[:20] + '.png'
        with Image.open(source) as im:
            im = ImageOps.exif_transpose(im).convert('RGBA')
            white = Image.new('RGBA', im.size, 'white')
            white.alpha_composite(im)
            im = white.convert('L')
            width = min(COLS[0][1]-COLS[0][0]-12, im.width*72/300)
            height = width*im.height/im.width
            if height > 260:
                scale = 260/height
                width, height = width*scale, 260
            im.thumbnail((int(width*600/72), int(height*600/72)))
            im.save(self.directory/name, optimize=True)
        return (f'<p class="illustration"><img src="{name}" '
                f'style="width:{width:.3f}pt;height:{height:.3f}pt" '
                f'width="{width:.3f}" height="{height:.3f}"/></p>'
                + (f'<p class="caption">{esc_keep_tags(label)}</p>' if label else ''))


def paragraph_html(p, assets=None):
    inline = assets.inline if assets else esc_keep_tags
    if p.startswith('$$') and p.endswith('$$'):
        if not assets: raise ValueError('수식 자산 렌더러가 필요합니다')
        expression=p[2:-2].strip()
        content=assets.math(expression, display=True)
        height=assets.heights[(expression,True)]
        depth=assets.depths[(expression,True)]
        return f'<p class="equation" style="line-height:{height+2:.2f}pt">'+content+'</p>'
    figure = re.fullmatch(r'!\[([^\]]*)\]\(([^)]+)\)', p.strip())
    if figure:
        if not assets: raise ValueError('그림 자산 렌더러가 필요합니다')
        return assets.illustration(*figure.groups())
    lines = p.splitlines()
    if len(lines)>1 and lines[0].startswith('|') and re.fullmatch(r'[\s|:\-]+',lines[1]):
        rows = [line for i,line in enumerate(lines) if i!=1]
        cells = [[c.strip() for c in line.strip().strip('|').split('|')] for line in rows]
        nc = len(cells[0])
        if any(len(row)!=nc for row in cells): raise ValueError('해설 표의 열 수가 일치하지 않습니다')
        if not assets: raise ValueError('해설 표는 글폭 측정 렌더러가 필요합니다')
        widths=plan_columns(cells,assets.measure,width=COLS[0][1]-COLS[0][0]-9.96)
        rendered=[]
        for row in cells:
            cols=[]
            for ci,c in enumerate(row):
                content=inline(c)
                content=re.sub(r'vertical-align:-[\d.]+pt','vertical-align:middle',content)
                cell_line_height=11.8
                if re.fullmatch(r'\$[^$]+\$',c) and '<img ' in content:
                    expression=c[1:-1].strip()
                    height=assets.heights[(expression,False)]
                    if height>10:
                        content=re.sub(r'</?span[^>]*>','',content)
                        # Measured correction for a tall formula in 8.76pt body
                        # table text; ordinary one-line expressions keep baseline.
                        content=content.replace('vertical-align:middle',f'vertical-align:{6.5-height/2:.3f}pt')
                        cell_line_height=max(11.8,height+4)
                cols.append(f'<td width="{widths[ci]:.2f}" style="width:{widths[ci]:.2f}pt;line-height:{cell_line_height:.2f}pt">{content}</td>')
            rendered.append('<tr>'+''.join(cols)+'</tr>')
        return '<table>'+''.join(rendered)+'</table>'
    text=' '.join(lines)
    content=inline(text)
    # Expand only the line containing a tall formula, not the whole paragraph.
    align='left' if '$' in text else 'justify'
    return f'<p style="line-height:13.54pt;text-align:{align}">'+content+'</p>'


def section_html(expl, assets=None):
    parts=[]
    for n,(title,_,paras) in sorted(expl.items()):
        cls = ' class="start"' if not parts else ''
        parts.append(f'<h3{cls}>{n}. {esc_keep_tags(title)}</h3>')
        parts.extend(paragraph_html(p,assets) for p in paras)
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
        assets=ExplanationAssets(tmp)
        archive=fitz.Archive(tmp)
        for si,(meta,ans,expl) in enumerate(sections):
            # Render each explanation once, then place its complete PDF fragment.
            # Repeated Story.place/reset/continuation lost tail lines at column ends
            # in MuPDF; never rely on that continuation for solution content.
            sec=fitz.open()
            page=sec.new_page(width=W,height=H)
            col=0
            top=GRID_TOP+math.ceil(len(ans)/5)*GRID_ROW_HEIGHT+BODY_AFTER_GRID
            for n,item in sorted(expl.items()):
                fragment_path=Path(tmp)/f'section{si}-question{n}.pdf'
                markup=section_html({n:item},assets)
                story=fitz.Story(markup,user_css=CSS,archive=archive)
                width=COLS[0][1]-COLS[0][0]
                more,filled=story.place(fitz.Rect(0,0,width,10000))
                if more:
                    raise ValueError(f'{meta.get("period")} {n}번 해설이 너무 깁니다')
                height=math.ceil(filled[3])+1
                if height>BOTTOM-TOP:
                    raise ValueError(f'{meta.get("period")} {n}번: 한 단보다 긴 해설을 먼저 나누세요')
                writer=fitz.DocumentWriter(str(fragment_path))
                dev=writer.begin_page(fitz.Rect(0,0,width,10000))
                story.draw(dev)
                writer.end_page()
                writer.close()
                if top+height>BOTTOM:
                    col+=1
                    top=TOP
                if col==3:
                    page=sec.new_page(width=W,height=H)
                    col=0
                left,right=COLS[col]
                with fitz.open(fragment_path) as fragment:
                    for xref in fragment[0].get_contents():
                        stream=fragment.xref_stream(xref)
                        def weight(m):
                            size=float(m.group(1))
                            return m.group(0)+(b' 0.16 w 2 Tr' if abs(size-8.647)<.001 else b' 0 Tr')
                        fragment.update_stream(xref,re.sub(rb'/F\d+ ([\d.]+) Tf',weight,stream))
                    page.show_pdf_page(fitz.Rect(left,top,right,top+height),fragment,0,
                                       clip=fitz.Rect(0,0,width,height))
                top+=height+7
            for k,page in enumerate(sec):
                for key,(_,path) in fonts.items(): page.insert_font(fontname=key,fontfile=str(path))
                if k==0:
                    draw_title(page,meta,fonts)
                    draw_section(page,meta,ans,fonts)
                for x in (307.224,533.656): page.draw_line((x,TOP),(x,BOTTOM),width=.36)
                text_center(page,str(k+1),421.519,1101.962,20.0247,'myeong',fonts,italic=True)
            doc.insert_pdf(sec)
            sec.close()
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
