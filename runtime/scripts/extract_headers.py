"""Read first-page furniture directly from HWPML and stored HWP line records."""
import json
import base64
import zlib
from pathlib import Path
from lxml import etree as E
from fontTools.ttLib import TTFont
import shutil
import struct
import re

ROOT = Path(__file__).resolve().parents[1]
NAMES = dict(korean='국어', english='영어', social='사탐', science='과탐')
FACES = {'신명 신그래픽': ('TESGRHG', 'TESGREN'), '신명 디나루': ('TEDNRHG', 'TEDNREN'),
         '신명 견명조': ('TEGMJHG', 'TEGMJEN'), '한양견명조': ('HGGMJ', 'ENGMJ'),
         '한양견고딕': ('HGGGT', 'ENGGT'), '한양신명조': ('HGSMJ', 'ENSMJ'),
         '신명 중명조': ('TEJMJHG', 'TEJMJEN'), '신명 중고딕': ('TEJGTHG', 'TEJGTEN'),
         '#태고딕': ('HCHGTGT', 'HCENTGT'), '신명 태고딕': ('TETGTHG','TETGTEN'),
         '한양중고딕': ('HGJGT','ENJGT')}
# Native 22-case font-selection probe: output/verification/modern-hangul-families-native.pdf.
COMPOSED_HANGUL_FACES={family:('Gulim-native-fallback' if family=='신명 신그래픽' else
    'HMKSM' if family in ('신명 중명조','신명 견명조','한양신명조','한양견명조') else 'HMKMG') for family in FACES}
SYMBOL_FACES={'한양신명조':'SPSMJ','한양중고딕':'SPJGT','신명 태그래픽':'TETGRSP',
              '신명 견명조':'TEGMJSP','신명 견고딕':'TEGGTSP','#태고딕':'HCSPTGT',
              '#디나루':'HCSPDNR','#신그래픽':'HCSPSGRP'}


def hft_metrics(height,advance_units,upem,ratio_percent,spacing_percent,space_divisor=None):
    # HncBaseDraw 0x10058DB0 scales an integer quarter-height, then restores four units.
    if space_divisor is None:
        scaled=(int(height)//4)*advance_units
        # The 100% branch calls rounded HncIntMulDiv; other ratios use integer division.
        base=4*((scaled+upem//2)//upem if ratio_percent==100 else scaled*ratio_percent//(upem*100))
    else:
        assert space_divisor in (2,4)
        # Fixed spaces divide the height before rounding the Hangul width ratio.
        base=4*(((int(height)//(4*space_divisor))*ratio_percent+50)//100)
    numerator=(base//4)*spacing_percent
    tracking=4*((abs(numerator)+50)//100)*(1 if numerator>=0 else -1)
    return base+tracking,tracking


def justification_gaps(tokens):
    first=next((i for i,t in enumerate(tokens) if t.get('char') not in (' ', '\x1e', '\x1f') and not t.get('heading')),len(tokens))
    spaces=[i for i,t in enumerate(tokens[:-1]) if i>first and t.get('char')==' ']
    return spaces or [i for i,t in enumerate(tokens[:-1]) if i>=first and t['kind']=='text'
                      and t.get('char') not in (' ','\x1e','\x1f') and not t.get('heading')]


def character_border_padding(tokens):
    # A border reserves one pen width on each side of every line fragment.
    keys=[(t.get('char_border'),t.get('height'),t.get('offset',0)) if t.get('char_border') else None for t in tokens]
    return [(t.get('char_border_pen',0) if i==0 or keys[i-1]!=keys[i] else 0,
             t.get('char_border_pen',0) if i+1==len(tokens) or keys[i+1]!=keys[i] else 0) for i,t in enumerate(tokens)]


def condense_line(tokens,width,limit):
    occupied=sum(t['advance'] for t in tokens)+sum(sum(p) for p in character_border_padding(tokens))-(tokens[-1].get('trailing_spacing',0) if tokens else 0)
    needed=occupied-width
    if needed<=0:return tokens
    spaces=[i for i in justification_gaps(tokens) if tokens[i].get('char')==' ']
    budget=sum(tokens[i]['advance'] for i in spaces)
    # Condense is a percentage of the space before character tracking (math question 14).
    natural_budget=sum(tokens[i]['advance']-tokens[i].get('trailing_spacing',0) for i in spaces)
    # Nonbreaking spaces contribute to the allowed reduction while retaining their fixed width.
    allowed=natural_budget+sum(t['advance']-t.get('trailing_spacing',0) for t in tokens if t.get('char')=='\x1e')
    # Native bordered lines may fit using final tracking, then compress that tracking out.
    border_end=tokens[-1].get('char_border') and needed<=-tokens[-1].get('trailing_spacing',0)
    if not border_end and (not budget or needed>allowed*limit/100):return None
    result=[dict(t) for t in tokens]
    # shortcut: 20% space reduction follows the native English probe; other scripts and exact tracking need native comparison.
    space_reduction=min(needed,natural_budget*.2)
    for i in spaces:result[i]['advance']-=space_reduction*tokens[i]['advance']/budget
    remaining=needed-space_reduction
    if remaining>0:
        letters=[i for i,t in enumerate(tokens[:-1]) if t['kind']=='text' and t.get('char') not in (' ','\x1e','\x1f') and not t.get('heading')]
        if not letters or any(result[i]['advance']<remaining/len(letters) for i in letters):return None
        for i in letters:result[i]['advance']-=remaining/len(letters)
    return result


def read_root(subject):
    return E.fromstring((ROOT / f'templates/{subject}.xml').read_bytes())


def chars(element):
    if element.tag == 'AUTONUM':
        return '1'
    assert element.tag == 'CHAR'
    result = element.text or ''
    for child in element:
        assert child.tag in ('FWSPACE', 'NBSPACE', 'TAB', 'LINEBREAK'), child.tag
        result += {'FWSPACE':'\x1f','NBSPACE':'\x1e','TAB':'\t','LINEBREAK':'\n'}[child.tag] + (child.tail or '')
    return result


def underline_commands(spans,line_bottom):
    commands=[]
    for token,x,width in spans:
        style=token['underline']
        assert style.get('Type')=='Bottom' and style.get('Shape')=='Solid', 'Unsupported original underline style'
        value=int(style.get('Color','0'));pen=token['height']/24
        command=dict(kind='line',x=x,y=line_bottom+pen/4,width=width,height=0,pen=pen,dash=False,
            color='#'+''.join(f'{(value>>shift)&255:02x}' for shift in (0,8,16)),decoration='underline')
        previous=commands[-1] if commands else None
        if previous and all(previous[k]==command[k] for k in ('y','pen','color')) and abs(previous['x']+previous['width']-x)<1e-6:
            previous['width']+=width
        else:commands.append(command)
    return commands


def picture_data(root,element):
    item=root.findall('.//BINITEM')[int(element.find('IMAGE').get('BinItem'))-1]
    # HML renumbers binary items; its IDs are not original HWP stream numbers.
    data=root.find(f'.//BINDATA[@Id="{item.get("BinData")}"]')
    assert data is not None and data.get('Encoding')=='Base64', 'Missing embedded source image'
    raw=base64.b64decode(''.join(data.text.split()),validate=True)
    return zlib.decompress(raw,-15) if data.get('Compress')=='true' else raw


def picture_command(element,x,y,w,h,path):
    clip,dim=element.find('IMAGECLIP'),element.find('IMAGEDIM')
    left,top,right,bottom=[int(clip.get(k)) for k in ('Left','Top','Right','Bottom')]
    iw,ih=int(dim.get('Width')),int(dim.get('Height'))
    assert 0<=left<right<=iw and 0<=top<bottom<=ih, 'Invalid original image crop'
    component=element.find('SHAPECOMPONENT')
    assert component.find('ROTATIONINFO').get('Angle')=='0', 'Rotated source pictures need a renderer'
    assert all(float(m.get(k,'0'))==0 for m in component.findall('./RENDERINGINFO/*') for k in ('E2','E4')), 'Sheared source pictures need a renderer'
    assert element.get('Reverse','false')=='false', 'Reversed source image colors need a renderer'
    image=element.find('IMAGE')
    assert all(image.get(k,'0')=='0' for k in ('Alpha','Bright','Contrast')) and image.get('Effect')=='RealPic', 'Source picture color effects need a renderer'
    assert not len(element.find('EFFECTS')), 'Source picture effects need a renderer'
    line=element.find('LINESHAPE')
    border=None
    if line is not None and line.get('Style')!='None':
        assert line.get('Style')=='Solid' and line.get('Alpha','0')=='0', 'Unsupported source picture border style'
        value=int(line.get('Color','0'))
        border=dict(pen=int(line.get('Width','0')),color='#'+''.join(f'{(value>>shift)&255:02x}' for shift in (0,8,16)))
    return dict(kind='image',x=x,y=y,width=w,height=h,path=path,border=border,
        full_width=w*iw/(right-left),full_height=h*ih/(bottom-top),
        crop_x=w*left/(right-left),crop_y=h*top/(bottom-top),
        flip_x=component.get('HorzFlip')=='true',flip_y=component.get('VertFlip')=='true')


class Header:
    def __init__(self, subject):
        self.subject, self.root = subject, read_root(subject)
        self.raw = json.loads((ROOT / f'source-layout/{subject}.json').read_text(encoding='utf-8'))['line_segments']['Section0']
        self.records, self.fonts, self.commands = {}, {}, []
        self.page = self.root.find('.//PAGEDEF')
        self.margin = self.page.find('PAGEMARGIN')
        self.width = int(self.page.get('Width'))

    def bind(self, element, start):
        paragraphs = element.findall('.//P')
        for p, record in zip(paragraphs, self.raw[start:start+len(paragraphs)]):
            self.records[p] = record

    def position(self, element, parent):
        shape = element.find('SHAPEOBJECT')
        size, pos = shape.find('SIZE'), shape.find('POSITION')
        w, h = int(size.get('Width')), int(size.get('Height'))
        x, y, pw = parent
        if pos.get('HorzRelTo') == 'Paper':
            x, pw = 0, self.width
        elif pos.get('HorzRelTo') == 'Page':
            x, pw = int(self.margin.get('Left')), self.width-int(self.margin.get('Left'))-int(self.margin.get('Right'))
        if pos.get('VertRelTo') == 'Paper':
            y = 0
        elif pos.get('VertRelTo') == 'Page':
            y = int(self.margin.get('Top')) + int(self.margin.get('Header'))
        align = pos.get('HorzAlign')
        x += (pw-w)/2 if align == 'Center' else (pw-w if align == 'Right' else 0)
        x += int(pos.get('HorzOffset')) * (-1 if align == 'Right' else 1)
        if pos.get('HorzRelTo')=='Paper' and pos.get('FlowWithText')=='true':
            # Hancom keeps negative-offset header text boxes in the text area.
            if x<0:x+=int(self.margin.get('Left'))
            elif x+w>self.width:x-=int(self.margin.get('Right'))
        y += int(pos.get('VertOffset'))
        if pos.get('VertRelTo')=='Paper' and pos.get('VertAlign')=='Bottom':
            y=int(self.page.get('Height'))-int(pos.get('VertOffset'))-h
        elif pos.get('VertRelTo')=='Page' and pos.get('VertAlign')=='Bottom':
            y=int(self.page.get('Height'))-int(self.margin.get('Bottom'))-int(self.margin.get('Footer'))-int(pos.get('VertOffset'))-h
        return x, y, w, h

    def glyph(self, char, shape):
        code=ord(char)
        lang = ('Latin' if code < 0x2b0 or 0x2018<=code<=0x201f else 'Hangul' if 0xac00<=code<=0xd7a3
                else 'Hanja' if 0x3400<=code<=0x9fff or 0xf900<=code<=0xfaff else 'User' if 0xf0000<=code<=0xffffd else 'Symbol')
        fid = shape.find('FONTID').get(lang)
        family = self.root.find(f'.//FONTFACE[@Lang="{lang}"]/FONT[@Id="{fid}"]').get('Name')
        composed=COMPOSED_HANGUL_FACES.get(family) if lang=='Hangul' and len(char.encode('euc_kr'))!=2 else None
        native_composed_gulim=composed=='Gulim-native-fallback'
        native_dot = char=='·' and family=='신명 신그래픽'
        native_cross = char=='☓' and family=='한양신명조'
        native_user = char in '\U000f003b\U000f0854\U000f0855' and family=='명조' or char=='\U000f00da' and family=='바탕'
        native_corner = family=='DX새고딕 Std 20' and char in '「」'
        native_ttf = (family in ('함초롬바탕', '한컴바탕', 'Times New Roman', 'Arial Black', '바탕', '굴림', 'HY중고딕') or native_dot or native_cross or native_user or native_corner or native_composed_gulim) and char not in '\x1e\x1f'
        fixed_space=char in '\x1e\x1f' or char==' ' and shape.get('UseFontSpace')!='true'
        stem = 'ENSMJ' if fixed_space or native_ttf else ({'신명 중명조':'TEJMJHJ','한양신명조':'HJSMJ'}[family] if lang=='Hanja' else SYMBOL_FACES[family] if lang == 'Symbol' else FACES[family][lang == 'Latin'])
        if composed and not native_ttf:stem=composed
        if stem=='ENSMJ' and char=='·':stem='ENSMJ-native-symbols'
        if stem=='ENSMJ' and char=='×':stem='social-native-00d7'
        if stem=='SPSMJ' and char=='◦':stem='SPSMJ-native-symbols'
        if stem=='SPSMJ' and char=='○':stem='SPSMJ-circle-native-symbols'
        if stem=='SPSMJ' and char=='Ⓐ':stem='korean-native-24b6'
        if stem in ('TETGRSP','SPSMJ') and char in '｢｣':stem='SPMJ-native-bitmaps'
        if stem=='SPSMJ' and char=='⇨':stem='korean-native-21e8'
        # shortcut: these HFT choices change within paths; retain native outlines until masks preserve those transitions.
        if stem=='TEJMJHJ' and char in '開想':stem=f'korean-native-{code:04x}'
        if stem=='SPSMJ' and 0xe000<=code<=0xf8ff:stem='HGOLD'
        if stem=='SPSMJ' and code==0x200b:stem=f'korean-native-{code:04x}'
        if stem=='SPSMJ' and char in '∙—':stem=f'english-native-{ord(char):04x}'
        if stem=='SPJGT' and char in '㉠㉡㉢':stem=f'native-{ord(char):04x}'
        if stem=='SPJGT' and char=='◦':stem='english-native-25e6'
        path = ROOT / 'fonts' / ('TEJMJHG-verified.otf' if stem == 'TEJMJHG' else stem+'.otf')
        if native_ttf:
            stem = 'HBATANG-native-fallback' if native_cross or native_user or native_corner or family=='한컴바탕' else ('Gulim-native-fallback' if native_dot else (('HANBatangB' if shape.find('BOLD') is not None else 'HANBatang') if family=='함초롬바탕' else ('timesbd' if shape.find('BOLD') is not None else 'times')))
            if not native_user:stem={'Arial Black':'ariblk','바탕':'Batang-native','굴림':'Gulim-native-fallback','HY중고딕':'H2GTRM'}.get(family,stem)
            if family=='Times New Roman' and shape.find('ITALIC') is not None:
                stem='timesbi' if shape.find('BOLD') is not None else 'timesi'
            if native_composed_gulim:stem=composed
            path = ROOT / 'fonts' / (stem+'.ttf')
            if not path.is_file():raise FileNotFoundError(f'원본 글꼴을 가져오세요: {path.name} (python tools/import_typst_fonts.py --help)')
        if stem not in self.fonts:
            self.fonts[stem] = TTFont(path)
        font = self.fonts[stem]
        if char==' ' and not native_ttf and font['hmtx'][font.getBestCmap()[32]][0]==0:
            fixed_space=True
        height = int(shape.get('Height')) * int(shape.find('RELSIZE').get(lang))/100
        if fixed_space:
            height=int(shape.get('Height'))
        original_height=height
        superscript=shape.find('SUPERSCRIPT') is not None
        subscript=shape.find('SUBSCRIPT') is not None
        assert not (superscript and subscript), 'A character cannot be both superscript and subscript'
        if superscript or subscript:height*=.64
        ratio, spacing, offset = [int(shape.find(tag).get(lang))/100 for tag in ('RATIO', 'CHARSPACING', 'CHAROFFSET')]
        script_offset=original_height*(-.44 if superscript else .12 if subscript else 0)+(int(shape.get('Height'))-height)*offset
        # Native center alignment uses the shape's Latin relative size, even in Hangul-only runs.
        center_shift=int(shape.get('Height'))*int(shape.find('RELSIZE').get('Latin'))*.0035
        # PDF-recovered Hanja need +0.05em to match native screen baselines.
        if stem==f'korean-native-{code:04x}' and char in '開想':offset+=.05
        if stem=='HJSMJ':offset-=1/60
        if fixed_space:
            # HWP fixed spaces follow the Hangul width even inside Latin text.
            ratio=int(shape.find('RATIO').get('Hangul'))/100
        bold = shape.find('BOLD') is not None
        if char not in ' \x1e\x1f' and not native_ttf:
            if shape.find('ITALIC') is not None and (stem not in ('ENSMJ','TEJGTHG') or bold):
                raise NotImplementedError(f'Original HFT italic transform needs native verification: {family}')
            if bold and not (ROOT/'fonts'/f'{stem}-horizontal-bold.otf').is_file():
                raise FileNotFoundError(f'Missing original HFT bold face: {stem}')
        width = .5 if char=='\x1e' or char == ' ' and shape.get('UseFontSpace')!='true' else (.25 if char == '\x1f' else font['hmtx'][font.getBestCmap()[ord(char)]][0]/font['head'].unitsPerEm)
        if char==' ' and width==0 and not native_ttf:
            # Legacy HFT faces encode an empty zero-width space; Hancom uses half an em.
            width=.5
        advance = height * (width*(1+spacing) + (.05 if bold and not native_ttf and char not in ' \x1e\x1f' else 0))*ratio
        trailing=height*width*spacing*ratio
        if fixed_space:
            advance,trailing=hft_metrics(height,0,1,round(ratio*100),0 if char=='\x1e' else int(shape.find('CHARSPACING').get(lang)),
                space_divisor=4 if char=='\x1f' else 2)
        elif not native_ttf:
            upem=font['head'].unitsPerEm
            width_units=font['hmtx'][font.getBestCmap()[ord(char)]][0]+((upem+10)//20 if bold and char!=' ' else 0)
            advance,trailing=hft_metrics(height,width_units,upem,
                int(shape.find('RATIO').get(lang)),int(shape.find('CHARSPACING').get(lang)))
        elif native_ttf and family=='Times New Roman':
            # Native TTF measurement truncates the scaled glyph width to quarter units before tracking.
            base=int(height*width*ratio/4)*4
            spacing_percent=int(shape.find('CHARSPACING').get(lang))
            numerator=(base//4)*spacing_percent
            trailing=4*((abs(numerator)+50)//100)*(1 if numerator>=0 else -1)
            advance=base+trailing
        if char=='\u200b':advance=trailing=0
        # shortcut: font-specific TrueType spaces outside Times New Roman still need independent calibration.
        # The original Hancom output embeds this exact Gulim glyph, with 0.02em stroke.
        stroke=height*.02 if (native_dot or native_composed_gulim) and bold else 0
        decoration={'underline':dict(shape.find('UNDERLINE').attrib)} if shape.find('UNDERLINE') is not None else {}
        border=self.root.find(f'.//BORDERFILL[@Id="{shape.get("BorderFillId")}"]')
        if border is not None and any(e.get('Type')!='None' for e in border if e.tag in ('LEFTBORDER','RIGHTBORDER','TOPBORDER','BOTTOMBORDER')):
            decoration['char_border']=border.get('Id')
            edges=[e for e in border if e.tag in ('LEFTBORDER','RIGHTBORDER','TOPBORDER','BOTTOMBORDER')]
            assert len(edges)==4 and len({(e.get('Type'),e.get('Width')) for e in edges})==1 and edges[0].get('Type')=='Solid', 'Character-border spacing requires equal solid edges'
            width=float(edges[0].get('Width').removesuffix('mm'))
            assert width in (.15,.3), 'Character-border spacing needs native calibration for this width'
            decoration['char_border_pen']=round(width*280)
        # Native social pages 3/4 use Tm [1 0 .333 -1 ...], after horizontal scaling.
        if not native_ttf and shape.find('ITALIC') is not None and char not in ' \x1e\x1f':decoration['shear']=.333
        if family=='Arial Black':decoration['weight']=font['OS/2'].usWeightClass
        return dict(kind='text', char=char, font=('HYGothic' if family=='HY중고딕' else font['name'].getDebugName(16) if family=='Arial Black' else font['name'].getDebugName(1)) if native_ttf else 'Original HFT '+stem, height=height,
                    ratio=ratio, bold=bold and not (native_dot or native_composed_gulim), italic=native_ttf and shape.find('ITALIC') is not None,
                    kerning=shape.get('UseKerning')=='true',
                    stroke=stroke, offset=height*offset+script_offset, center_shift=center_shift, advance=advance,
                    trailing_spacing=trailing,draw_dx=0)|decoration

    def kerning(self,previous,current):
        if not previous or not previous.get('kerning') or not current.get('kerning'):
            return 0
        if current['font']!='Times New Roman' or any(previous.get(k)!=current[k] for k in ('font','height','ratio','bold','italic')):
            return 0
        if not all(t.get('char','').isascii() and len(t.get('char',''))==1 for t in (previous,current)):
            return 0
        face=('timesbi' if current['bold'] else 'timesi') if current['italic'] else ('timesbd' if current['bold'] else 'times')
        font=self.fonts[face];cmap=font.getBestCmap()
        pair=tuple(cmap[ord(t['char'])] for t in (previous,current))
        kern=font['kern'].kernTables[0].kernTable.get(pair,0)
        return int(kern/font['head'].unitsPerEm*current['height']*current['ratio']/4)*4

    def character_borders(self,spans):
        groups=[]
        for index,(token,x,baseline,width) in enumerate(spans):
            border=token.get('char_border')
            if border is None:groups.append(None);continue
            key=(border,baseline,token['height'])
            end=x+width-(token.get('trailing_spacing',0) if index==len(spans)-1 else 0)
            if groups and groups[-1] and groups[-1]['key']==key:groups[-1]['end']=end
            else:groups.append(dict(key=key,start=x,end=end))
            if token.get('char')!=' ':groups[-1]['last_tracking']=token.get('trailing_spacing',0)
            elif index==len(spans)-1:groups[-1]['end']-=groups[-1].get('last_tracking',0)
        saved=self.commands;self.commands=[]
        try:
            for group in filter(None,groups):
                border,baseline,height=group['key']
                definition=self.root.find(f'.//BORDERFILL[@Id="{border}"]')
                brush=definition.find('./FILLBRUSH/WINDOWBRUSH')
                assert brush is None or brush.get('FaceColor')=='4294967295', 'Filled character borders need background ordering'
                edges=[e for e in definition if e.tag in ('LEFTBORDER','RIGHTBORDER','TOPBORDER','BOTTOMBORDER') and e.get('Type')!='None']
                assert len(edges)==4 and len({(e.get('Type'),e.get('Width')) for e in edges})==1, 'Unequal character border edges need native verification'
                pen=round(float(edges[0].get('Width').removesuffix('mm'))*280)
                self.border(border,group['start']-pen/2,baseline-height*.85-pen/2,group['end']-group['start']+pen,height+pen)
                for command in self.commands[-4:]:
                    if command['width']==0:command['y']-=pen/2;command['height']+=pen
                    else:command['x']-=pen/2;command['width']+=pen
            return [command|dict(decoration='character-border') for command in self.commands]
        finally:self.commands=saved

    def border(self, border_id, x, y, w, h):
        b = self.root.find(f'.//BORDERFILL[@Id="{border_id}"]')
        def color(value):
            value=int(value)
            return '#'+''.join(f'{(value >> shift)&255:02x}' for shift in (0,8,16))
        brush=b.find('./FILLBRUSH/WINDOWBRUSH')
        if brush is not None and int(brush.get('FaceColor','4294967295'))!=4294967295:
            assert brush.get('HatchStyle') in (None,'None'), 'Unsupported original cell hatch'
            self.commands.append(dict(kind='fill',x=x,y=y,width=w,height=h,
                color=color(brush.get('FaceColor'))+f'{255-int(brush.get("Alpha","0")):02x}'))
        for name, coordinates in [('LEFT',(x,y,0,h)), ('RIGHT',(x+w,y,0,h)),
                                  ('TOP',(x,y,w,0)), ('BOTTOM',(x,y+h,w,0))]:
            edge = b.find(name+'BORDER')
            if edge is not None and edge.get('Type') != 'None':
                self.commands.append(dict(kind='line', x=coordinates[0],y=coordinates[1],width=coordinates[2],height=coordinates[3],
                    pen=float(edge.get('Width').removesuffix('mm'))*7200/25.4, dash=edge.get('Type')=='Dash',color=color(edge.get('Color','0'))))
        diagonal=b.find('DIAGONAL')
        slash,back,crooked=(int(b.get(k,'0')) for k in ('Slash','BackSlash','CrookedSlash'))
        assert all(b.get(k,'0')=='0' for k in ('CenterLine','CounterSlash','CounterBackSlash')), 'Unsupported original diagonal arrangement'
        assert (slash,back,crooked) in ((0,0,0),(2,0,0),(0,2,0),(0,2,2)), 'Unsupported original diagonal arrangement'
        if slash or back:
            assert diagonal is not None and diagonal.get('Type') in ('Solid','Dash')
            points=[(x,y+h),(x+w,y)] if slash else [(x,y),(x+w,y+h)]
            if crooked:
                # Original Korean articulation table uses eighth-width elbows at half height.
                points=[(x,y),(x+w/8,y+h/2),(x+w*7/8,y+h/2),(x+w,y+h)]
            for (sx,sy),(ex,ey) in zip(points,points[1:]):
                self.commands.append(dict(kind='line',x=sx,y=sy,width=ex-sx,height=ey-sy,
                    pen=float(diagonal.get('Width').removesuffix('mm'))*7200/25.4,
                    dash=diagonal.get('Type')=='Dash',color=color(diagonal.get('Color','0')),decoration='cell-diagonal'))

    def table(self, table, parent, fixed=None):
        x,y,w,h = fixed if fixed is not None else self.position(table,parent)
        rows = table.findall('ROW')
        assert len(rows) == 1
        for cell in rows[0].findall('CELL'):
            cw = int(cell.get('Width'))
            self.border(cell.get('BorderFill'),x,y,cw,h)
            margin = cell.find('CELLMARGIN') if cell.get('HasMargin') == 'true' else table.find('INSIDEMARGIN')
            ml,mt,mb = [int(margin.get(k)) for k in ('Left','Top','Bottom')]
            plist = cell.find('PARALIST')
            ps = plist.findall('P')
            content_height = max((self.records[p]['lines'][-1]['vertical_position']+self.records[p]['lines'][-1]['line_height'] for p in ps),default=0)
            if list(table.iterancestors('HEADER')):
                # The page-number text box occupies the full continuation header cell.
                for rect in plist.findall('./P/TEXT/RECTANGLE'):
                    position=rect.find('./SHAPEOBJECT/POSITION')
                    if position.get('VertRelTo')=='Para' and int(position.get('VertOffset'))==0:
                        content_height=max(content_height,int(rect.find('./SHAPEOBJECT/SIZE').get('Height')))
            cy = y+mt
            if plist.get('VertAlign') == 'Center':
                cy += (h-mt-mb-content_height)/2
            for p in ps:
                self.paragraph(p,x+ml,cy,cw-ml-int(margin.get('Right')))
            x += cw

    def rectangle(self, rectangle, parent, fixed=None):
        x,y,w,h = fixed if fixed is not None else self.position(rectangle,parent)
        line = rectangle.find('./DRAWINGOBJECT/LINESHAPE')
        if line is not None and line.get('Style') != 'None':
            self.commands.append(dict(kind='rect',x=x,y=y,width=w,height=h,pen=int(line.get('Width')),radius=int(rectangle.get('Ratio'))/100))
        draw = rectangle.find('./DRAWINGOBJECT/DRAWTEXT')
        if draw is not None:
            margin = draw.find('TEXTMARGIN')
            ps=draw.findall('./PARALIST/P')
            mt,mb=int(margin.get('Top')),int(margin.get('Bottom'))
            ch=max((self.records[p]['lines'][-1]['vertical_position']+self.records[p]['lines'][-1]['line_height'] for p in ps),default=0)
            dy=0
            if draw.find('PARALIST').get('VertAlign')=='Bottom':dy=h-mt-mb-ch
            elif draw.find('PARALIST').get('VertAlign')=='Center':dy=(h-mt-mb-ch)/2
            for p in ps:
                self.paragraph(p,x+int(margin.get('Left')),y+mt+dy,w-int(margin.get('Left'))-int(margin.get('Right')))

    def picture(self, picture, x,y,w,h):
        item = picture.find('IMAGE').get('BinItem')
        binitem = self.root.findall('.//BINITEM')[int(item)-1]
        data=picture_data(self.root,picture)
        target = ROOT / f'assets/original/{self.subject}-title.{binitem.get("Format").lower()}'
        assert target.is_file() and target.read_bytes()==data, 'Bundled heading image differs from the layout template'
        self.commands.append(picture_command(picture,x,y,w,h,str(target.relative_to(ROOT)).replace('\\','/')))

    def paragraph(self,p,x,y,w):
        record = self.records[p]
        assert len(record['lines']) == 1, 'Header must contain one-line paragraphs'
        line = record['lines'][0]
        shape = self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
        baseline = y+line['vertical_position']+line['baseline_distance']
        cursor, items, floats, trailing_spacing = 0, [], [], 0
        space_ends=[];previous=None
        units=record.get('text_utf16_units',[])
        tabs=[];i=0
        while i<len(units):
            if units[i]==9:tabs.append(units[i+1]+(units[i+2]<<16))
            i+=8 if units[i] in (1,2,3,9,11,12,14,15,16,17,18,21,22,23) else 1
        tabs=iter(tabs)
        for run in p.findall('TEXT'):
            cs = self.root.find(f'.//CHARSHAPE[@Id="{run.get("CharShape")}"]')
            for item in run:
                if item.tag in ('CHAR','AUTONUM'):
                    for char in chars(item):
                        if char=='\t':cursor+=next(tabs);trailing_spacing=0;previous=None;continue
                        glyph = self.glyph(char,cs)
                        cursor+=self.kerning(previous,glyph)
                        previous=glyph
                        trailing_spacing=glyph['trailing_spacing']
                        if item.tag=='AUTONUM':glyph['field']='total' if item.get('NumberType')=='TotalPage' else 'page-number'
                        glyph.update(x=cursor+glyph.pop('draw_dx'),y=baseline+glyph.pop('offset'))
                        if shape.get('VerAlign')=='Center': glyph['y'] += glyph['center_shift']
                        if char not in ' \x1e\x1f': items.append(glyph)
                        cursor += glyph['advance']
                        if char==' ':space_ends.append(cursor)
                elif item.tag in ('RECTANGLE','TABLE','PICTURE','LINE'):
                    so = item.find('SHAPEOBJECT')
                    if so.find('POSITION').get('TreatAsChar')=='true':
                        sz,mg = so.find('SIZE'),so.find('OUTSIDEMARGIN')
                        iw,ih=int(sz.get('Width')),int(sz.get('Height'))
                        mt,mb=int(mg.get('Top')),int(mg.get('Bottom'))
                        top = y+line['vertical_position']+line['line_height']-ih-mb
                        if item.tag=='TABLE':
                            top = y+line['vertical_position']+line['baseline_distance']-(ih+mt+mb)*.85+mt
                        # shortcut: native PDF places inline shapes differently from CreatePageImage;
                        # retain stored line-box placement until the two native paths are reconciled.
                        items.append(dict(kind='inline',element=item,x=cursor+int(mg.get('Left')),y=top,width=iw,height=ih))
                        cursor += iw+int(mg.get('Left'))+int(mg.get('Right'))
                        trailing_spacing=0
                        previous=None
                    else: floats.append(item)
                elif item.tag not in ('COLDEF','HEADER','FOOTER'): raise ValueError(item.tag)
        # Tracking separates glyphs; the final glyph has no following gap.
        cursor -= trailing_spacing
        available = line['segment_width']
        if p in getattr(self,'edited_headings',()):
            assert cursor<=available, 'Subject name exceeds the original heading width'
        if shape.get('Align')=='DistributeSpace' and items:
            gaps=[end for end in space_ends if items[0]['x']<end<=items[-1]['x']]
            if gaps:
                extra=(available-cursor)/len(gaps)
                for item in items:item['x']+=sum(end<=item['x'] for end in gaps)*extra
        start=x+line['column_start']
        if shape.get('Align')=='Center': start += (available-cursor)/2
        elif shape.get('Align')=='Right': start += available-cursor
        plain=''.join(i.get('char','') for i in items)
        for index,item in enumerate(items):
            item['x'] += start
            if item['kind']=='inline':
                element=item.pop('element')
                if element.tag=='TABLE':self.table(element,(0,0,0),fixed=tuple(item[k] for k in ('x','y','width','height')))
                elif element.tag=='PICTURE':self.picture(element,*(item[k] for k in ('x','y','width','height')))
                elif element.tag=='RECTANGLE':self.rectangle(element,(0,0,0),fixed=tuple(item[k] for k in ('x','y','width','height')))
                else:raise ValueError(element.tag)
            else:
                if plain.startswith('2025') and index<4:item['field']='year';item['field_index']=index
                if plain=='1':item['field']='page-number'
                self.commands.append(item)
        for item in floats:
            parent=(x,y+line['vertical_position'],w)
            pos=item.find('./SHAPEOBJECT/POSITION')
            if pos.get('VertRelTo')=='Para':
                # Paragraph-before spacing moves the text, not its anchored object.
                parent=(parent[0],parent[1]-int(shape.find('PARAMARGIN').get('Prev'))/2,parent[2])
            if pos.get('VertRelTo')=='Para' and int(pos.get('VertOffset'))<0:
                tables=p.findall('./TEXT/TABLE') or list(p.iterancestors('TABLE'))
                if tables:
                    table_height=int(tables[0].find('./SHAPEOBJECT/SIZE').get('Height'))
                    parent=(parent[0],parent[1]+table_height,parent[2])
            if item.tag=='RECTANGLE':self.rectangle(item,parent)
            elif item.tag=='LINE':
                lx,ly,lw,lh=self.position(item,parent)
                self.commands.append(dict(kind='line',x=lx,y=ly,width=lw,height=lh,pen=int(item.find('./DRAWINGOBJECT/LINESHAPE').get('Width')),dash=False))
            else:self.table(item,parent)

    def set_area_title(self,title,keep_subject=False):
        assert self.subject in ('social','science'), 'Area titles currently apply to inquiry templates'
        assert isinstance(title,str) and title.strip() and title==title.strip() and not any(ord(c)<32 for c in title), 'Enter a nonempty single-line area title'
        first=self.root.find('./BODY/SECTION/P/TEXT/TABLE')
        paragraphs=first.findall('.//P')+self.root.findall('.//HEADER//P')
        self.edited_headings=getattr(self,'edited_headings',set())
        for p in paragraphs:
            original=[(ch,run.get('CharShape')) for run in p.findall('TEXT') for c in run.findall('CHAR') for ch in chars(c)]
            literal=''.join(ch for ch,_ in original)
            if '영역' not in literal and '(' not in literal:continue
            if keep_subject and '영역' not in literal:continue
            replacement=[]
            if '영역' in literal:
                default=next(style for ch,style in original if '\uac00'<=ch<='\ud7a3')
                space=next(((ch,style) for ch,style in original if ch in ' \x1f'),(' ',default))
                replacement=[space if ch==' ' else (ch,default) for ch in title]
                if keep_subject and '(' in literal:
                    replacement+=original[literal.index('('):]
                self.edited_headings.add(p)
            # Keep page-number shapes and paragraph records; replace only their title text.
            for run in p.findall('TEXT'):
                for c in run.findall('CHAR'):run.remove(c)
            for text,style in replacement:
                run=E.SubElement(p,'TEXT',CharShape=style);c=E.SubElement(run,'CHAR')
                if text=='\x1f':E.SubElement(c,'FWSPACE')
                else:c.text=text

    def set_inquiry_name(self,name):
        assert self.subject in ('social','science'), 'Subject names apply to inquiry templates'
        assert isinstance(name,str) and name.strip() and name==name.strip() and not any(ord(c)<32 or c in '()' for c in name), 'Enter a nonempty subject name without parentheses or control characters'
        first=self.root.find('./BODY/SECTION/P/TEXT/TABLE')
        paragraphs=first.findall('.//P')+self.root.findall('.//HEADER//P')
        self.edited_headings=set()
        for p in paragraphs:
            runs=p.findall('TEXT')
            labels=[run for run in runs if '(' in ''.join(chars(c) for c in run.findall('CHAR'))]
            if not labels:continue
            start=runs.index(labels[0]);label_runs=runs[start:]
            original=[(ch,run.get('CharShape')) for run in label_runs for c in run.findall('CHAR') for ch in chars(c)]
            literal=''.join(ch for ch,_ in original)
            assert literal.startswith('(') and literal.endswith(')')
            canonical=lambda value:value.replace('\x1f','').replace('Ⅰ','I').replace('Ⅱ','II')
            if canonical(literal[1:-1])==canonical(name):continue
            default=next(style for ch,style in original if '\uac00'<=ch<='\ud7a3')
            styles={ch:style for ch,style in original if '\uac00'<=ch<='\ud7a3'}
            replacement=[('(',original[0][1])]
            match=re.fullmatch(r'(.+?)[ ]*([ⅠⅡ]|II|I)',name) if self.subject=='science' else None
            body=match[1] if match else name
            replacement.extend((ch,styles.get(ch,default)) for ch in body)
            if match:
                numeral,style=next((ch,style) for ch,style in original if ch in 'ⅠI')
                if any(ch=='\x1f' for ch,_ in original):replacement.append(('\x1f',default))
                level=2 if match[2] in ('Ⅱ','II') else 1
                replacement.append((('ⅠⅡ'[level-1] if numeral=='Ⅰ' else 'I'*level),style))
            replacement.append((')',original[-1][1]))
            position=list(p).index(label_runs[0])
            for run in label_runs:
                assert all(c.tag=='CHAR' for c in run), 'Unexpected object in subject-name runs'
                p.remove(run)
            for offset,(text,style) in enumerate(replacement):
                run=E.Element('TEXT',CharShape=style);c=E.SubElement(run,'CHAR')
                if text=='\x1f':E.SubElement(c,'FWSPACE')
                else:c.text=text
                p.insert(position+offset,run)
            self.edited_headings.add(p)

    def extract(self,write=True):
        table=self.root.find('./BODY/SECTION/P/TEXT/TABLE')
        self.bind(table,dict(korean=16,english=16,social=6,science=8)[self.subject])
        self.table(table,(0,0,self.width))
        if self.subject in ('korean','english'):
            rectangles=self.root.findall('./BODY/SECTION/P/TEXT/RECTANGLE')[:2]
            for rect,start in zip(rectangles,[19,20] if self.subject=='korean' else [20,21]):
                self.bind(rect,start);self.rectangle(rect,(0,0,self.width))
        divider=self.root.find('./BODY/SECTION/P/TEXT/POLYGON')
        if divider is None:divider=self.root.find('./BODY/SECTION/P/TEXT/LINE')
        if divider is not None:
            x,y,w,h=self.position(divider,(0,0,self.width))
            if divider.tag=='POLYGON':
                self.commands.append(dict(kind='fill',x=x,y=y,width=w,height=h))
            else:
                self.commands.append(dict(kind='line',x=x,y=y,width=w,height=h,pen=int(divider.find('./DRAWINGOBJECT/LINESHAPE').get('Width')),dash=False))
        if write:
            path=ROOT/f'source-layout/{self.subject}-header.json'
            path.write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')
            print(self.subject,len(self.commands),'source-derived header commands',flush=True)
        return self.commands

    def last_page_tables(self):
        masters=self.root.findall('.//EXT_MASTERPAGE[@Type="LastPage"]')
        optional=self.root.findall('.//EXT_MASTERPAGE[@Type="OptionalPage"]')
        if optional:masters.append(max(optional,key=lambda m:int(m.get('PageNumber'))))
        tables=[t for m in masters for t in m.findall('./PARALIST/P/TEXT/TABLE')]
        if self.subject=='social':tables+=self.root.findall('./BODY/SECTION/P/TEXT/TABLE')
        return [t for t in tables
            if t.find('./SHAPEOBJECT/POSITION').get('VertAlign')=='Bottom'
            and t.find('./SHAPEOBJECT/POSITION').get('VertRelTo')=='Page']

    def footer(self):
        self.commands=[]
        if self.subject in ('korean','english'):
            table=self.root.find('.//FOOTER//TABLE');self.bind(table,14)
            size=table.find('./SHAPEOBJECT/SIZE');w,h=int(size.get('Width')),int(size.get('Height'))
            y=int(self.page.get('Height'))-int(self.margin.get('Bottom'))-140-h
            self.table(table,(0,0,self.width),fixed=((self.width-w)/2,y,w,h))
        elif self.subject=='math':
            table=self.root.find('.//MASTERPAGE//TABLE');self.bind(table,2)
            x,y,w,h=self.position(table,(0,0,self.width))
            self.table(table,(0,0,self.width),fixed=(x,y+int(table.find('./SHAPEOBJECT/OUTSIDEMARGIN').get('Top')),w,h))
        else:
            table=next(t for t in self.root.findall('.//TABLE') if t.find('./SHAPEOBJECT/SIZE').get('Width')=='5102' and t.find('./SHAPEOBJECT/POSITION').get('VertAlign')=='Bottom')
            if self.subject=='social':self.bind(table,2)
            else:
                for p in table.findall('.//P'):
                    ps=int(p.get('ParaShape'))
                    plain=''.join(chars(c) for c in p.findall('./TEXT/CHAR'))+'\r'
                    found=[r for r in self.raw if struct.unpack_from('<H',bytes.fromhex(r['header_hex']),8)[0]==ps and ''.join(map(chr,r.get('text_utf16_units',[])))==plain]
                    assert found
                    self.records[p]=found[0]
            self.table(table,(0,0,self.width))
        texts=[c for c in self.commands if c['kind']=='text']
        total_index=0
        for c in texts:
            c['field']='page-number' if c['y']==texts[0]['y'] else 'total'
            if c['field']=='total':c['field_index']=total_index;total_index+=1
        (ROOT/f'source-layout/{self.subject}-footer.json').write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')

    def continuation(self,write=True):
        results={}
        if self.subject not in ('korean','english'):
            starts={'math':{'Even':53,'Odd':56},'social':{'Odd':25,'Even':28},'science':{'Odd':2,'Even':5}}[self.subject]
            for parity,start in starts.items():
                self.commands=[]
                header=self.root.find(f'.//HEADER[@ApplyPageType="{parity}"]')
                self.bind(header,start)
                for p in header.findall('./PARALIST/P'):
                    y=int(self.margin.get('Top'))
                    if self.subject=='science':y-=self.records[p]['lines'][0]['vertical_position']
                    self.paragraph(p,int(self.margin.get('Left')),y,self.width-int(self.margin.get('Left'))-int(self.margin.get('Right')))
                if self.subject in ('social','science'):
                    d=self.root.find('.//MASTERPAGE//LINE');x,y,w,h=self.position(d,(int(self.margin.get('Left')),0,self.width-2*int(self.margin.get('Left'))))
                    self.commands.append(dict(kind='line',x=x,y=y,width=w,height=h,pen=int(d.find('./DRAWINGOBJECT/LINESHAPE').get('Width')),dash=False))
                results[parity.lower()]=self.commands
                if write:(ROOT/f'source-layout/{self.subject}-{parity.lower()}-header.json').write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')
            return results
        for parity,start in [('Even',2),('Odd',8)]:
            self.commands=[]
            master=self.root.find(f'.//MASTERPAGE[@Type="{parity}"]')
            table=master.find('.//TABLE');self.bind(table,start)
            self.table(table,(0,0,self.width))
            d=master.find('.//POLYGON');x,y,w,h=self.position(d,(0,0,self.width))
            self.commands.append(dict(kind='fill',x=x,y=y,width=w,height=h))
            results[parity.lower()]=self.commands
            if write:(ROOT/f'source-layout/{self.subject}-{parity.lower()}-header.json').write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')
        return results


if __name__=='__main__':
    assert chars(E.fromstring('<CHAR>수험<FWSPACE/>번호</CHAR>'))=='수험\x1f번호'
    for subject in NAMES:
        header=Header(subject);header.extract();header.footer();header.continuation()
    header=Header('math');header.footer();header.continuation()
