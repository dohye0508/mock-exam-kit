"""Isolated adapter: original HWP styles + automatic layout, never Hancom COM."""
from copy import deepcopy
import json
import os
from pathlib import Path
import re
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
ENGINE = Path(request['engine'])
sys.path.insert(0, str(ENGINE / 'scripts'))


def forbid_hancom(event, args):
    if event == 'import' and str(args[0]).startswith(('win32com', 'pythoncom')):
        raise RuntimeError('Typst 빌드에서 한글 COM을 호출할 수 없습니다.')


sys.addaudithook(forbid_hancom)
from compose import Composer, command_bottom
from extract_headers import Header, chars
from flow import paginate
from examkit.native_math import equation
from examkit.typst_body import REVIEW_COLORS

ASSETS = Path(request['assets'])
ROOT = Path(request['root'])
INLINE = re.compile(r'(\{\{frac\|[^|}]+\|[^}]+\}\}|\$[^$]+\$|__[^_]+__|[₀₁₂₃₄₅₆₇₈₉]+|[⁰¹²³⁴⁵⁶⁷⁸⁹]+)')


def resource(path):
    return '/' + Path(path).resolve().relative_to(ROOT).as_posix()


class Engine(Composer):
    def original_charshape(self, shape):
        # Overlay IDs belong to the science source, even on a social sheet.
        owner = self if self.subject == 'science' else Engine('science')
        original = owner.root.find(f'.//CHARSHAPE[@Id="{int(shape)}"]')
        if original is None: raise ValueError(f'없는 원본 글자 모양: {shape}')
        cs = deepcopy(original)
        if owner is not self:
            for lang, fid in list(cs.find('FONTID').attrib.items()):
                name = owner.root.find(f'.//FONTFACE[@Lang="{lang}"]/FONT[@Id="{fid}"]').get('Name')
                target = self.root.find(f'.//FONTFACE[@Lang="{lang}"]/FONT[@Name="{name}"]')
                if target is None: raise ValueError(f'원본 글꼴 정의가 없습니다: {name}')
                cs.find('FONTID').set(lang, target.get('Id'))
        return cs

    def tokens(self, runs, role, para_shape=None):
        if isinstance(runs, dict): runs = [runs]
        if isinstance(runs, str): runs = [runs]
        result = []
        for run in runs:
            if isinstance(run, dict) and 'styled' in run:
                if 'char_shape' in run:
                    previous = self.styles[role]
                    self.styles[role] = (self.original_charshape(run['char_shape']), previous[1])
                    try: tokens = self.tokens(run['styled'], role, para_shape)
                    finally: self.styles[role] = previous
                else: tokens = self.tokens(run['styled'], role, para_shape)
                for token in tokens:
                    if 'color' in run:
                        token['color'] = run['color']
                        if 'commands' in token:
                            token['commands'] = [c | {'color': run['color']} for c in token['commands']]
                result.extend(tokens)
                continue
            if not isinstance(run, str):
                result.extend(super().tokens([run], role, para_shape)); continue
            for part in INLINE.split(run.replace('~', '∼').replace('\u00a0', '\x1e')):
                if not part: continue
                if part[0] in '₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹':
                    from lxml import etree as E
                    lower=part[0] in '₀₁₂₃₄₅₆₇₈₉'
                    alphabet='₀₁₂₃₄₅₆₇₈₉' if lower else '⁰¹²³⁴⁵⁶⁷⁸⁹'
                    cs,ps=self.styles[role];cs=deepcopy(cs)
                    for tag in ('SUBSCRIPT','SUPERSCRIPT'):
                        for node in cs.findall(tag):cs.remove(node)
                    E.SubElement(cs,'SUBSCRIPT' if lower else 'SUPERSCRIPT')
                    self.styles['@script']=(cs,ps)
                    result.extend(super().tokens(part.translate(str.maketrans(alphabet,'0123456789')),'@script',para_shape))
                    continue
                if part.startswith('$'):
                    size = int(self.styles[role][0].get('Height')) / 100
                    eq = equation(part[1:-1], size, str(ENGINE / 'fonts/HancomEQN.ttf'))
                    result.append(self.inline(eq)); continue
                if part.startswith('{{frac|'):
                    a, b = part[7:-2].split('|', 1)
                    rows = [super(Engine, self).tokens(t, role, para_shape) for t in (a, b)]
                    height = int(self.styles[role][0].get('Height'))
                    widths = [sum(t['advance'] for t in row) for row in rows]
                    width = max(widths) + height * .3
                    commands = [dict(kind='line', x=0, y=height*1.12, width=width, height=0, pen=height/28, dash=False)]
                    for j, row in enumerate(rows):
                        x = (width-widths[j])/2
                        for t in row:
                            if t['kind'] == 'text' and not t['char'].isspace():
                                commands.append(t | dict(x=x, y=height*(.85+1.4*j)))
                            x += t['advance']
                    result.append(self.inline(dict(commands=commands, width=width, height=height*2.45, baseline=height*1.52))); continue
                underline = part.startswith('__')
                tokens = super().tokens(part[2:-2] if underline else part, role, para_shape)
                if underline:
                    for t in tokens: t['underline'] = dict(Type='Bottom', Shape='Solid', Color='0')
                result.extend(tokens)
        return result

    @staticmethod
    def inline(eq):
        return dict(kind='inline-table', commands=eq['commands'], width=eq['width'], height=eq['height'],
                    left_margin=56, top_margin=0, advance=eq['width']+112,
                    above=eq['baseline'], below=eq['height']-eq['baseline'], can_break=True)

    def source_box(self, block, x, y, width):
        table=self.root.findall('./BODY/SECTION//TABLE')[block.get('box_template',14 if self.subject=='science' else 10)]
        size=table.find('./SHAPEOBJECT/SIZE');old=size.get('Width')
        if int(old)>width:
            p=next(table.iterancestors('P'))
            margin=self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]/PARAMARGIN')
            inset=self.source_object_left(table,0,width)+int(margin.get('Right'))/2
            size.set('Width',str(int(width-inset)))
        try:return super().source_box(block,x,y,width)
        finally:size.set('Width',old)

    def data_table(self, block, x, y, width):
        if self.subject != 'social' and 'char_shape' not in block:
            owner = Engine('social')
            end = owner.data_table(block, x, y, width)
            self.commands.extend(owner.commands)
            return end
        rows = block['rows']; columns = len(rows[0])
        assert rows and all(len(row) == columns for row in rows), '표 열 수가 일치하지 않습니다.'
        weights = block.get('widths') or [1]*columns
        assert len(weights) == columns and all(w > 0 for w in weights)
        widths = [width*w/sum(weights) for w in weights]
        cs, ps = self.styles['choices']
        if 'char_shape' in block: cs = self.original_charshape(block['char_shape'])
        ps = deepcopy(ps)
        ps.find('PARAMARGIN').attrib.update(dict(Left='0', Right='0', Indent='0', Prev='0', Next='0'))
        self.styles['@grid'] = (cs, ps)
        cells = []; occupied = {}; heights = [block.get('row_h', 1400)]*len(rows)
        for r, row in enumerate(rows):
            for c, text in enumerate(row):
                if text == '^':
                    assert r > 0 and (r-1, c) in occupied, '첫 행을 위로 병합할 수 없습니다.'
                    cell = occupied[r-1, c]; cell['span'] += 1; occupied[r,c] = cell; continue
                saved = self.commands; self.commands = []
                end = self.paragraph(text, '@grid', 0, 0, widths[c]-400, align='Center', trim_end=True)
                commands = self.commands; self.commands = saved
                cell = dict(row=r, col=c, span=1, end=end, commands=commands)
                cells.append(cell); occupied[r,c] = cell
        for cell in cells:
            r, span = cell['row'], cell['span']
            missing = cell['end'] + 300 - sum(heights[r:r+span])
            if missing > 0: heights[r+span-1] += missing
        for cell in cells:
            r,c,span = cell['row'],cell['col'],cell['span']
            cx,cy = x+sum(widths[:c]), y+sum(heights[:r]); h=sum(heights[r:r+span])
            if block.get('rules', True):
                self.commands.append(dict(kind='rect', x=cx,y=cy,width=widths[c],height=h,pen=28,radius=0))
            self.commands.extend(cmd | dict(x=cx+200+cmd['x'],y=cy+(h-cell['end'])/2+cmd['y']) for cmd in cell['commands'])
        return y+sum(heights)

    def figure(self, block, x, y, width):
        w,h=block['size']
        assert 0 < w <= width and h > 0, '그림이 단 폭보다 넓습니다.'
        left=x+(width-w)/2
        self.commands.append(dict(kind='image',path=resource(block['file']),x=left,y=y,width=w,height=h,
                                  full_width=w,full_height=h,crop_x=0,crop_y=0,flip_x=False,flip_y=False))
        self.overlays(block.get('params',{}),left,y)
        if block.get('caption'):
            return self.paragraph(block['caption'],'choices',x,y+h,width,align='Center')
        return y+h

    def overlays(self, params, x, y):
        mm=7200/25.4
        for key in sorted(params):
            if not re.fullmatch(r'(text|label|bubble|table)\d+|board',key): continue
            spec=params[key]; content=''
            if '|' in spec: spec,content=spec.split('|',1)
            geo=[v.strip() for v in spec.split(',')]
            px,py=map(float,geo[:2]); ox=x+px*mm+float(params.get('_pad_x',0)); oy=y+(py+float(params.get('oy',0)))*mm+float(params.get('_pad_y',0))
            w=(float(geo[2]) if len(geo)>2 else 10)*mm
            h=(float(geo[3]) if len(geo)>3 else 8)*mm
            if key.startswith('table') or key=='board':
                rows=[[c.strip() for c in r.split('|')] for r in params.get(key+'_rows',params.get('board_table','')).split(';') if r.strip()]
                assert rows, f'{key}: 표 내용이 없습니다.'
                if key=='board':self.commands.append(dict(kind='rect',x=ox,y=oy,width=w,height=h,pen=28,radius=0))
                saved=self.commands;self.commands=[]
                end=self.data_table(dict(rows=rows,char_shape=params.get(key+'_font','56'),row_h=float(params.get(key+'_rowh',0))*mm or 1000,widths=[float(v) for v in params[key+'_widths'].split(',')] if key+'_widths' in params else None),0,0,w-200)
                cmds=self.commands;self.commands=saved
                assert end<=h-200, f'{key}: 그림 위 표가 지정 높이를 넘습니다.'
                valign=params.get(key+'_valign','CENTER')
                dy=(h-200-end)/(2 if valign=='CENTER' else 1) if valign in ('CENTER','BOTTOM') else 0
                self.commands.extend(c|dict(x=c['x']+ox+100,y=c['y']+oy+100+dy) for c in cmds)
                continue
            boxed=key.startswith('bubble') or params.get(key+'_box')=='1'
            if boxed:
                self.commands.extend([dict(kind='fill',x=ox,y=oy,width=w,height=h,color='#ffffff'),dict(kind='rect',x=ox,y=oy,width=w,height=h,pen=28,radius=.08 if key.startswith('bubble') else 0)])
            if key.startswith('bubble'):
                tx,ty=map(float,geo[4:6]); tip=(x+tx*mm,y+ty*mm)
                for start in ((ox+w*.4,oy+h),(ox+w*.6,oy+h)):
                    self.commands.append(dict(kind='line',x=start[0],y=start[1],width=tip[0]-start[0],height=tip[1]-start[1],pen=28,dash=False))
            _,ps=self.styles['passage']; cs=self.original_charshape(params.get(key+'_font',params.get('font','39')))
            ps=deepcopy(ps);ps.find('PARAMARGIN').attrib.update(dict(Left='0',Right='0',Indent='0',Prev='0',Next='0'))
            self.styles['@overlay']=(cs,ps)
            alignment=geo[4] if key.startswith('text') and len(geo)>4 else params.get('bubble_align','left') if key.startswith('bubble') else 'center' if key.startswith('label') else 'left'
            alignment,_,spacing=alignment.partition('@')
            ps.find('PARAMARGIN').set('LineSpacing',spacing or '140')
            if alignment=='item': ps.find('PARAMARGIN').attrib.update(Left=str(int(3.2*mm*2)),Indent=str(-int(3.2*mm*2)))
            saved=self.commands;self.commands=[]
            end=self.paragraph(content.strip().replace(' / ','\n').replace('<br>','\n'),'@overlay',0,0,w-200,align={'left':'Left','item':'Left','justify':'Justify','center':'Center','right':'Right'}[alignment],trim_end=True)
            cmds=self.commands;self.commands=saved
            assert end<=h-200, f'{key}: 그림 위 글이 지정 높이를 넘습니다.'
            valign=params.get(key+'_valign','CENTER' if key.startswith(('bubble','label')) else 'TOP')
            dy=(h-200-end)/(2 if valign=='CENTER' else 1) if valign in ('CENTER','BOTTOM') else 0
            self.commands.extend(c|dict(x=c['x']+ox+100,y=c['y']+oy+100+dy) for c in cmds)

    def source_artwork(self, block, x, y, width):
        left, right = block['pair']; rw=right['size'][0]; gap=600; lw=width-rw-gap
        assert lw>1500
        end1=self.render(left,x,y,lw)
        end2=self.figure(right,x+lw+gap,y,rw)
        return max(end1,end2)

    def render(self, block, x, y, width):
        if block['kind']=='box':
            # Reuse source character/paragraph/border styles; fit its width to a side column.
            start=len(self.commands);end=self.source_box(block,x,y,width)
            actual=max((c['x']+c.get('width',0) for c in self.commands[start:] if c['kind']=='line'),default=x+width)
            assert actual<=x+width+1, '나란히 놓은 상자가 단 폭을 넘습니다.'
            return end
        return self.data_table(block,x,y,width)


def image_block(payload, qn, index):
    from examkit import figures, materials
    from examkit.build import _external_png
    from matplotlib import font_manager, rcParams
    faces=[ENGINE/'fonts'/name for name in ('TEJMJHG-verified.otf','ENSMJ.otf','SPSMJ.otf')]
    for face in faces:font_manager.fontManager.addfont(str(face))
    rcParams['font.family']=[font_manager.FontProperties(fname=str(face)).get_name() for face in faces]
    kv,params=payload['kv'],dict(payload['params']); width=int(kv.get('w',19000))
    target=ASSETS/f'figure-{qn}-{index}.png'
    if payload['kind']=='file' or 'file' in kv:
        path=Path(kv.get('path') or kv.get('file',''))
        if not path.is_absolute():path=REPO/path
        file,pw,ph,pad=_external_png(str(path),width,kv.get('h'),str(target),cx=kv.get('cx'),crop=kv.get('crop'))
        params.update(_pad_x=pad[0]*width/pw,_pad_y=pad[1]*width/pw)
    elif payload['kind'] in materials.KINDS:
        css=''
        for i,filename in enumerate(('TEJMJHG-verified.otf','ENSMJ.otf','SPSMJ.otf','TEJGTHG.otf','TEJGTEN.otf','SPJGT.otf')):
            css+=f'@font-face{{font-family:Original{i};src:url("{(ENGINE/"fonts"/filename).as_uri()}")}}'
        css+='body,.serif{font-family:Original0,Original1,Original2}.head,.gothic,.nt th,.ft th,figcaption{font-family:Original3,Original4,Original5}'
        file,pw,ph=materials.render(payload['kind'],params,str(target),width,font_css=css)
    else:
        params.setdefault('inch_w',str(width/7200*1.25))
        file,pw,ph=figures.render(payload['kind'],params,str(target))
    return dict(kind='figure',file=file,size=[width,width*ph/pw],params=params,caption=kv.get('caption'))


def blocks(questions):
    result=[]
    for q in questions:
        if q['pb'] or q['cb']:result.append(dict(kind='page_break' if q['pb'] else 'column_break'))
        ask=q['ask'].rstrip()+('\u00a0[3점]' if q['three'] else '')
        only_prompt=not q['head'] and not q['blocks']
        group=[dict(runs=ask if only_prompt else q['head'],number=q['n'],style='question')]
        for i,(kind,payload) in enumerate(q['blocks']):
            if kind=='figure':
                block=image_block(payload,q['n'],i)
                if payload['kv'].get('side') and group[-1].get('kind') in ('box','data_table'):
                    group[-1]=dict(kind='artwork',pair=[group[-1],block]);continue
            elif kind=='table':block=dict(kind='data_table',rows=[payload['headers']]+payload['rows'],widths=payload['widths'],row_h=payload['row_h'])
            elif kind=='box':
                items=[]
                for line in payload:
                    match=re.match(r'^@(?:center|c)\s+(.*)',line)
                    content=match[1] if match else line
                    if line.startswith(('@center ','[')): content=[dict(styled=content,char_shape=52)]
                    items.append(dict(runs=content,align='Center') if match else content)
                block=dict(kind='box',items=items,fit_content=True)
            elif kind=='dialog':block=dict(kind='box',items=[dict(runs=(name+': '+text if name else text),align='Left' if name else 'Center') for name,text in payload],fit_content=True)
            elif kind=='text':block=dict(runs=payload,style='question')
            else:raise ValueError('지원하지 않는 문항 블록: '+kind)
            group.append(block)
        if not only_prompt: group.append(dict(runs=ask,style='question'))
        color=REVIEW_COLORS[q.get('status','keep')] if request['review'] else None
        def marked(text,index):return dict(styled=text,color=color) if color and index==q['answer']-1 else text
        if 'bogi' in q:
            group.append(dict(kind='example',items=[label+'. '+text for label,text in zip('ㄱㄴㄷ',q['bogi'])],fit_content=True))
        if 'grid' in q:
            headers,rows=q['grid'];cells=[['']+headers]+[[marked(chr(0x2460+i),i)]+[marked(t,i) for t in row] for i,row in enumerate(rows)]
            group.append(dict(kind='data_table',rows=cells,widths=[.35]+[1]*len(headers),rules=False))
        else:
            items=q.get('opts',q.get('set'))
            columns=5 if q.get('inline_opts') or all(len(t)<=6 and '$' not in t and '{{' not in t for t in items) else 1
            choices=[marked(text,i) for i,text in enumerate(items)]
            group.append(dict(kind='choices',items=[[t] if isinstance(t,dict) else t for t in choices],columns=columns,equal_columns=columns==5))
        for b in group:b['keep_with_next']=True;b.setdefault('after_mm',1)
        group[-1]['keep_with_next']=False;group[-1]['after_mm']=q['gap']*4
        result.extend(group)
    return result


def heading(profile, page, meta):
    h=Header(profile)
    area=meta.get('area','과학탐구');area=area if area.endswith('영역') else area+' 영역'
    name=meta.get('subject','')
    if name: h.set_inquiry_name(name)
    h.set_area_title(area,keep_subject=bool(name))
    for p in h.root.iter('P'):
        text=''.join(chars(c) for c in p.findall('./TEXT/CHAR'))
        compact=''.join(text.split())
        replacement=None
        if re.fullmatch(r'제\d+교시',compact):
            replacement=meta.get('period',text)
            match=re.fullmatch(r'제\s*(\d+)\s*교시',replacement)
            if match: replacement='제\x1f'+match[1]+'\x1f교시'
        elif re.match(r'\d{4}학년도',compact):replacement=meta.get('body_title',f"{meta.get('year','2027학년도')} {meta.get('exam','모의고사')} 문제지")
        if replacement is not None:
            shape=p.find('TEXT').get('CharShape')
            for run in p.findall('TEXT'):
                for c in run.findall('CHAR'):run.remove(c)
            from lxml import etree as E
            run=E.SubElement(p,'TEXT',CharShape=shape);char=E.SubElement(run,'CHAR')
            pieces=replacement.split('\x1f');char.text=pieces[0]
            for piece in pieces[1:]:E.SubElement(char,'FWSPACE').tail=piece
            h.edited_headings.add(p)
    return h.extract(write=False) if page==1 else h.continuation(write=False)['even' if page%2==0 else 'odd']


meta=request['meta'];profile=request['profile'];all_blocks=blocks(request['questions'])
minimum=int(meta.get('pages',1)) if meta.get('pages') not in (None,'auto') else 1
document=dict(subject=profile,flow=True,min_pages=minimum,blocks=all_blocks)
pages=paginate(document,composer=Engine)
output=Path(request['output']);relative=lambda p:Path(os.path.relpath(p,output.parent)).as_posix()
source=f'#import {json.dumps(relative(ENGINE/"exam.typ"))}: exam-page\n#import {json.dumps(relative(ENGINE/"original-header.typ"))}: source-commands\n'
for i,(editor,page) in enumerate(pages,1):
    body=ASSETS/f'body-{i}.json';front=ASSETS/f'header-{i}.json'
    body.write_text(json.dumps(editor.commands,ensure_ascii=False),encoding='utf-8')
    front.write_text(json.dumps(heading(profile,i,meta),ensure_ascii=False),encoding='utf-8')
    source+=(f'#exam-page("{profile}", [], [], page-no: {i}, total: {len(pages)}, last-page: {str(i==len(pages)).lower()}, auto-flow: true, '
             f'heading-commands: json({json.dumps(relative(front),ensure_ascii=False)}), overlay: source-commands(json({json.dumps(relative(body),ensure_ascii=False)})))\n')
output.write_text(source,encoding='utf-8')
(ASSETS/'manifest.json').write_text(json.dumps(dict(pages=len(pages),questions=[q['n'] for q in request['questions']],hancom=False,profile=profile),ensure_ascii=False,indent=2),encoding='utf-8')
