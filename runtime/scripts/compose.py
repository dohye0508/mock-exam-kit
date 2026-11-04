"""Compose editable question text using the original HWP character/paragraph styles.

The output is text and vector equations, never a screenshot background.
shortcut: arbitrary paragraph reflow has not yet passed full Hancom parity;
keep the original-line fixtures for independent comparisons.
"""
import json
import re
from math import isfinite
from copy import deepcopy
from functools import lru_cache
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from typst_source import authoring_documents
from pathlib import Path
from extract_headers import Header, ROOT,underline_commands,justification_gaps,condense_line,character_border_padding

STYLE_IDS = {
    'korean': dict(question=6,number=5,choices=7,passage=3,range=2),
    'english': dict(question=4,number=3,choices=7,passage=10),
    'math': dict(question=1,number=3,choices=4,passage=2),
    'social': dict(question=1,number=None,choices=10,passage=2),
    'science': dict(question=1,number=8,choices=4,passage=2),
}


def line_gap(height,percent):
    # Hancom rounds the percentage of an integer quarter-height back to four HWP units.
    numerator=(int(height)//4)*(percent-100)
    return 4*((abs(numerator)+50)//100)*(1 if numerator>=0 else -1)


@lru_cache(maxsize=None)
def glyph_descent(family,bold,italic,char):
    if family.startswith('Original HFT '):
        stem=family.removeprefix('Original HFT ')
        filename=stem+'-horizontal-bold.otf' if bold else 'TEJMJHG-verified.otf' if stem=='TEJMJHG' else stem+'.otf'
    elif family=='Times New Roman':filename=('timesbi' if bold and italic else 'timesbd' if bold else 'timesi' if italic else 'times')+'.ttf'
    else:filename={'HCR Batang':'HANBatangB.ttf' if bold else 'HANBatang.ttf','Haansoft Batang':'HBATANG-native-fallback.ttf',
        'Gulim':'Gulim-native-fallback.ttf','Batang':'Batang-native.ttf','Arial':'ariblk.ttf','HYGothic':'H2GTRM.ttf','HancomEQN':'HancomEQN.ttf'}[family]
    with TTFont(ROOT/'fonts'/filename) as font:
        glyphs=font.getGlyphSet();pen=BoundsPen(glyphs);glyphs[font.getBestCmap()[ord(char)]].draw(pen)
        return -pen.bounds[1]/font['head'].unitsPerEm if pen.bounds else 0


def command_bottom(item):
    if item['kind']!='text':return item['y']+max(0,item['height'])
    return item['y']+item['height']*glyph_descent(item['font'],item.get('bold',False),item.get('italic',False),item['char'])+item.get('stroke',0)/2


class Composer:
    def __init__(self,subject):
        self.header=Header(subject)
        self.subject=subject
        self.root=self.header.root
        self.commands=[]
        self.float_regions=[]
        margins={tuple(int(e.find('./SHAPEOBJECT/OUTSIDEMARGIN').get(side)) for side in ('Left','Right','Top','Bottom')) for e in self.root.findall('.//EQUATION')}
        assert len(margins)<=1, 'Mixed original equation margins require per-equation profiles'
        self.equation_margins=next(iter(margins),(56,56,0,0))
        assert self.equation_margins[2:]==(0,0), 'Nonzero vertical equation margins need native verification'
        self.equations=json.loads((ROOT/'assets/equations/manifest.json').read_text(encoding='utf-8'))
        self.equation_scripts=json.loads((ROOT/'equations.json').read_text(encoding='utf-8'))
        style_path=ROOT/'source-layout/equation-styles.json'
        self.equation_styles=json.loads(style_path.read_text(encoding='utf-8')) if style_path.exists() else {}
        self.styles={}
        for role,index in STYLE_IDS[subject].items():
            if index is None:continue
            style=self.root.find(f'.//STYLE[@Id="{index}"]')
            cs=self.root.find(f'.//CHARSHAPE[@Id="{style.get("CharShape")}"]')
            ps=self.root.find(f'.//PARASHAPE[@Id="{style.get("ParaShape")}"]') if style.get('ParaShape') else None
            self.styles[role]=(cs,ps)
        for style in self.root.findall('.//STYLE'):
            if style.get('Type')!='Para':continue
            cs=self.root.find(f'.//CHARSHAPE[@Id="{style.get("CharShape")}"]')
            ps=self.root.find(f'.//PARASHAPE[@Id="{style.get("ParaShape")}"]')
            self.styles[style.get('Name')]=(cs,ps)
        if subject=='social':
            ps=self.styles['question'][1]
            head=self.root.find(f'.//NUMBERING[@Id="{ps.get("Heading")}"]/PARAHEAD[@Level="1"]')
            number_shape=self.root.find(f'.//CHARSHAPE[@Id="{head.get("CharShape")}"]')
            self.styles['number']=(number_shape,None)

    def paragraph_shape(self,role,shape_id=None):
        if shape_id is None:return self.styles[role][1]
        assert type(shape_id) is int, 'para_shape must be an original paragraph-shape integer'
        shape=self.root.find(f'.//PARASHAPE[@Id="{shape_id}"]')
        assert shape is not None, 'Unknown original para_shape'
        return shape

    def tokens(self,runs,role,para_shape=None):
        if isinstance(runs,str):runs=[runs]
        assert isinstance(runs,list), 'Paragraph runs must be text or a list'
        paragraph_shape=self.paragraph_shape(role,para_shape)
        break_non_latin=paragraph_shape is None or paragraph_shape.get('BreakNonLatinWord')!='false'
        result=[]
        for run in runs:
            if isinstance(run,str) or isinstance(run,dict) and 'text' in run:
                content=run if isinstance(run,str) else run['text'];override=None
                if isinstance(run,dict):
                    assert set(run)=={'text','char_shape'}, 'Styled text accepts only text and char_shape'
                    assert isinstance(content,str) and type(run.get('char_shape')) is int, 'Styled text requires text and an original char_shape integer'
                    override=self.root.find(f'.//CHARSHAPE[@Id="{run["char_shape"]}"]')
                    assert override is not None, 'Unknown original char_shape'
                    if not content:
                        height=int(override.get('Height'))
                        result.append(dict(kind='space',advance=0,above=height*.85,below=height*.15,strut_height=height,can_break=False))
                for char in content:
                    if char=='\n':result.append({'kind':'break'});continue
                    cs=override if override is not None else self.styles[role][0]
                    if char=='\t':
                        assert paragraph_shape is not None, 'A tab requires an original paragraph style'
                        tab=self.root.find(f'.//TABDEF[@Id="{paragraph_shape.get("TabDef")}"]')
                        assert tab is not None and all(t.get('Type')=='Left' and t.get('Leader')=='None' for t in tab), 'Only original left tabs without leaders are supported'
                        origin=int(paragraph_shape.find('PARAMARGIN').get('Left'))/2
                        intervals={int(s.get('TabStop'))/2 for s in self.root.findall('.//SECDEF')}
                        assert len(intervals)==1 and next(iter(intervals))>0, 'Section-specific default tabs need an explicit section style'
                        height=int(cs.get('Height'))
                        result.append(dict(kind='space',char=char,advance=0,above=height*.85,below=height*.15,strut_height=height,can_break=True,
                            tab_stops=sorted({int(t.get('Pos'))/2-origin for t in tab}),tab_origin=origin,tab_interval=next(iter(intervals)),
                            tab_auto_right=tab.get('AutoTabRight')=='true'))
                        continue
                    if override is None and self.subject=='korean' and role=='range' and char in '[]':
                        # The original range heading has separate bracket runs.
                        cs=self.root.find('.//CHARSHAPE[@Id="31"]')
                    token=self.header.glyph(char,cs)
                    if result:
                        kern=self.header.kerning(result[-1],token)
                        if kern:
                            result[-1]['advance']+=kern
                            result[-1]['trailing_spacing']+=kern
                    token['strut_height']=int(cs.get('Height'))
                    token['above']=token['height']*.85
                    token['below']=token['height']*.15
                    non_latin=0xac00<=ord(char)<=0xd7a3 or char in '\u200b\U000f0855' or 0xe000<=ord(char)<=0xf8ff and token['font'].startswith('Original HFT korean-native-')
                    closing_punctuation=char in '’”)․' and result and result[-1].get('can_break',False)
                    token['can_break']=bool(char.isspace() and char!='\x1e' or break_non_latin and (non_latin or closing_punctuation))
                    result.append(token)
            elif isinstance(run,dict) and 'picture_template' in run:
                from extract_body_fixture import Body
                assert set(run)=={'picture_template'}, 'Inline picture accepts only picture_template'
                source=Body(self.subject);pictures=source.root.findall('./BODY/SECTION//PICTURE');index=run['picture_template']
                assert type(index) is int and 0<=index<len(pictures), 'Choose an original picture_template index'
                picture=pictures[index];shape=picture.find('SHAPEOBJECT')
                assert shape.find('POSITION').get('TreatAsChar')=='true', 'Inline runs require a source picture treated as a character'
                size,outer=shape.find('SIZE'),shape.find('OUTSIDEMARGIN')
                w,h=int(size.get('Width')),int(size.get('Height'))
                ml,mr,mt,mb=[int(outer.get(side)) for side in ('Left','Right','Top','Bottom')]
                source.picture(picture,0,0,w,h);total=h+mt+mb
                result.append(dict(kind='inline-picture',commands=source.commands,width=w,height=h,left_margin=ml,top_margin=mt,
                    advance=w+ml+mr,above=total*.85,below=total*.15,can_break=break_non_latin))
            elif isinstance(run,dict) and 'rectangle_template' in run:
                from extract_body_fixture import Body
                assert set(run)<={'rectangle_template','label'}, 'Inline rectangle accepts rectangle_template and label'
                source=Body(self.subject);rectangles=source.root.findall('./BODY/SECTION//RECTANGLE');index=run['rectangle_template']
                assert type(index) is int and 0<=index<len(rectangles), 'Choose an original rectangle_template index'
                rectangle=rectangles[index];shape=rectangle.find('SHAPEOBJECT')
                assert rectangle not in source.skip and shape.find('POSITION').get('TreatAsChar')=='true', 'Inline runs require a body rectangle treated as a character'
                size,outer=shape.find('SIZE'),shape.find('OUTSIDEMARGIN')
                w,h=int(size.get('Width')),int(size.get('Height'))
                ml,mr,mt,mb=[int(outer.get(side)) for side in ('Left','Right','Top','Bottom')]
                source.rectangle(rectangle,(0,0,w),fixed=(0,0,w,h))
                commands=source.commands
                if 'label' in run:
                    assert isinstance(run['label'],str), 'Rectangle label must be text'
                    draw=rectangle.find('DRAWINGOBJECT/DRAWTEXT');paragraphs=draw.findall('PARALIST/P') if draw is not None else []
                    assert len(paragraphs)==1 and len(paragraphs[0].findall('TEXT'))==1 and all(c.tag=='CHAR' for c in paragraphs[0].find('TEXT')), 'Label editing requires a single plain-text source paragraph'
                    p=paragraphs[0];label=Composer(self.subject)
                    label.styles['@rectangle']=(source.root.find(f'.//CHARSHAPE[@Id="{p.find("TEXT").get("CharShape")}"]'),source.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]'))
                    margin=draw.find('TEXTMARGIN');lm,rm,tm,bm=[int(margin.get(side)) for side in ('Left','Right','Top','Bottom')]
                    end=label.paragraph(run['label'],'@rectangle',0,0,w-lm-rm,trim_end=True)
                    assert end<=h-tm-bm, 'Edited label exceeds the original rectangle height'
                    align=draw.find('PARALIST').get('VertAlign');dy=(h-tm-bm-end)/(2 if align=='Center' else 1) if align in ('Center','Bottom') else 0
                    commands=[c for c in commands if c['kind']=='rect']+[c|dict(x=c['x']+lm,y=c['y']+tm+dy) for c in label.commands]
                total=h+mt+mb
                result.append(dict(kind='inline-rectangle',commands=commands,width=w,height=h,left_margin=ml,top_margin=mt,
                    advance=w+ml+mr,above=total*.85,below=total*.15,can_break=break_non_latin))
            elif isinstance(run,dict) and 'table_template' in run:
                from extract_body_fixture import Body
                assert set(run)<={'table_template','cells','nested_cells'}, 'Inline table accepts table_template, cells and nested_cells'
                source=Body(self.subject);tables=source.root.findall('./BODY/SECTION//TABLE');index=run['table_template']
                assert type(index) is int and 0<=index<len(tables), 'Choose an original table_template index'
                table=tables[index];shape=table.find('SHAPEOBJECT')
                assert shape.find('POSITION').get('TreatAsChar')=='true', 'Inline runs require a source table treated as a character'
                size=shape.find('SIZE');outer=shape.find('OUTSIDEMARGIN');w=int(size.get('Width'))
                ml,mr,mt,mb=[int(outer.get(side)) for side in ('Left','Right','Top','Bottom')]
                saved=self.commands;cell_style=self.styles.get('@source-cell');self.commands=[]
                try:
                    h=self.source_table(run,0,0,w,source=source,fixed=(0,0,w,int(size.get('Height'))))
                    commands=self.commands
                finally:
                    self.commands=saved
                    if cell_style is None:self.styles.pop('@source-cell',None)
                    else:self.styles['@source-cell']=cell_style
                total=h+mt+mb
                result.append(dict(kind='inline-table',commands=commands,width=w,height=h,left_margin=ml,top_margin=mt,
                    advance=w+ml+mr,above=total*.85,below=total*.15,can_break=break_non_latin))
            elif isinstance(run,dict) and 'equation' in run:
                key=run['equation'];eq=self.equations[key]
                assert eq['script']==self.equation_scripts[key], f'{key}: run scripts/render_equations.py after editing the equation'
                assert eq['base_unit']*100==self.equation_styles.get(key,1100), f'{key}: render again after changing the equation size'
                assert (ROOT/f'assets/equations/{key}.svg').is_file(), f'Missing rendered equation: {key}'
                result.append(dict(kind='equation',key=key,width=eq['width']*100,height=eq['height']*100,left_margin=self.equation_margins[0],
                    advance=eq['width']*100+sum(self.equation_margins[:2]),above=eq['baseline']*100,below=(eq['height']-eq['baseline'])*100,
                    can_break=break_non_latin))
            else:raise ValueError(f'Unsupported run {run!r}')
        return result

    @staticmethod
    def wrap(tokens,width,hanging=0,first_indent=0,condense=0,next_width=None):
        tokens=[dict(t) for t in tokens]
        tail=0
        for token in reversed(tokens):
            if 'tab_stops' in token:token['tab_tail_width']=tail;tail=0
            elif token['kind']=='break':tail=0
            else:tail+=token['advance']
        def positioned(token,cursor):
            if 'tab_stops' not in token:return token
            default=((cursor+token['tab_origin'])//token['tab_interval']+1)*token['tab_interval']-token['tab_origin']
            explicit=next((s for s in token['tab_stops'] if s>cursor),None)
            right=explicit is None and token['tab_auto_right']
            stop=explicit if explicit is not None else max(cursor,width-token['tab_tail_width']) if right else default
            return token|dict(advance=stop-cursor,tab_right_aligned=right)
        lines=[];line=[];used=0
        def commit(finished):
            nonlocal width
            lines.append(finished)
            if next_width is not None:width=next_width(finished)
        for token in tokens:
            if token['kind']=='break':
                if line:line[-1]['hard_break']=True
                commit(line);line=[];used=0;continue
            if 'tab_stops' in token and line and (hanging if lines else first_indent)+used>=width:
                commit(line);line=[];used=0
            available=width-(hanging if lines else first_indent)
            token=positioned(token,(hanging if lines else first_indent)+used)
            # Ordinary trailing spaces are trimmed when painting, so they cannot force a line break.
            trailing=0 if token.get('char_border') or any(t.get('tab_right_aligned') for t in line) else token.get('trailing_spacing',0)
            padding=sum(sum(p) for p in character_border_padding(line+[token]))
            if token.get('char')!=' ' and used+token['advance']+padding-trailing>available and line and condense_line(line+[token],available,condense) is None:
                forbidden=set('.,!?;:)]}〉》」』】、。，？！：；’”․\U000f0855\x1e')
                opportunities=[i+1 for i,t in enumerate(line) if t['can_break']
                    and ((line[i+1].get('char','') if i+1<len(line) else token.get('char','')) not in forbidden
                         or t.get('char')==' ' and (line[i+1].get('char','') if i+1<len(line) else token.get('char',''))=='\x1e')]
                split=opportunities[-1] if opportunities else len(line)
                commit(line[:split]);line=line[split:]
                while line and line[0].get('char')==' ':line.pop(0)
                used=0
                for index,moved in enumerate(line):
                    line[index]=positioned(moved,hanging+used);used+=line[index]['advance']
                token=positioned(token,hanging+used)
            assert token['advance']-token.get('trailing_spacing',0)<=width, 'An inline object or glyph is wider than the paragraph'
            line.append(token);used+=token['advance']
        if line:lines.append(line)
        for line in lines:
            for index,tab in enumerate(line):
                if not tab.get('tab_right_aligned'):continue
                end=next((i for i in range(index+1,len(line)) if 'tab_stops' in line[i]),len(line))
                group=line[index+1:end]
                if not group:continue
                # Hancom locates the tab using full advances, then fits the run's final tracking inside that width.
                gaps=justification_gaps(group)
                if gaps:
                    extra=group[-1].get('trailing_spacing',0)/len(gaps)
                    for i in gaps:group[i]['advance']+=extra
                else:group[-1]['trailing_spacing']=0
        return lines

    def paragraph_width(self,x,y,width):
        return self.paragraph_region(x,y,width)[1]

    def paragraph_region(self,x,y,width):
        right=x+width
        for region in self.float_regions:
            if region.get('wrap_top',region['top'])<=y<region['bottom'] and x<region['right'] and right>region['left']:
                if region.get('side')=='Left':x=max(x,region['right'])
                else:right=min(right,region['left'])
        width=right-x
        assert width>0, 'Floating picture leaves no space for the paragraph'
        return x,width

    def paragraph(self,runs,role,x,y,width,number=None,align=None,trim_end=False,para_shape=None,number_suffix=None,fragment=None,continued=False,continues=False):
        column_right=x+width
        cs=self.styles[role][0];ps=self.paragraph_shape(role,para_shape)
        margin=ps.find('PARAMARGIN') if ps is not None else None
        if margin is not None:
            left=int(margin.get('Left'))/2;right=int(margin.get('Right'))/2
            x+=left;width-=left+right
            assert margin.get('LineSpacingType')=='Percent', 'Unsupported original line-spacing mode'
            if not continued and (not fragment or not fragment.get('continued')):y+=int(margin.get('Prev'))/2
        indent=int(margin.get('Indent'))/2 if margin is not None else 0
        hanging=max(0,-indent)
        first_indent=max(0,indent)
        if continued:first_indent=hanging
        tokens=self.tokens(runs,role,para_shape)
        assert number is not None or number_suffix is None, 'number_suffix requires a question number'
        if number is not None:
            assert type(number) is int and number>0, 'Question number must be a positive integer'
            head=None
            if ps is not None and ps.get('HeadingType')=='Number':
                head=self.root.find(f'.//NUMBERING[@Id="{ps.get("Heading")}"]/PARAHEAD[@Level="{int(ps.get("Level"))+1}"]')
                assert int(ps.get('Level'))==0 and head is not None and head.get('NumFormat')=='Digit' and head.get('UseInstWidth')=='true', 'Unsupported original automatic number format'
                prefix=self.tokens([dict(text=head.text.replace('^1',str(number)),char_shape=int(head.get('CharShape')))],role,para_shape)
                for token in prefix:token['heading']=True
                prefix[-1]['advance']-=prefix[-1].get('trailing_spacing',0)
                prefix[-1]['trailing_spacing']=0
            elif 'number' in self.styles:
                prefix=self.tokens(str(number)+'.','number')
            else:
                prefix=self.tokens(str(number)+'.',role,para_shape)
                for token in prefix:
                    token.update(font='Original HFT ENGMJ',height=1350,strut_height=1350,above=1147.5,below=202.5)
            if head is not None and number_suffix is None:
                assert head.get('TextOffsetType')=='percent', 'Unsupported original number text offset'
                gap=int(head.get('WidthAdjust'))+prefix[0]['strut_height']*int(head.get('TextOffset'))/100
                prefix.append(dict(kind='space',advance=gap,above=0,below=0,can_break=False))
            else:
                suffix=number_suffix if number_suffix is not None else dict(korean='\x1e\x1f',english='\x1e\x1f',math='\t',science='\x1e').get(self.subject,' ')
                assert isinstance(suffix,(str,list)), 'number_suffix must be spacing text or styled spacing runs'
                for run in ([suffix] if isinstance(suffix,str) else suffix):
                    value=run if isinstance(run,str) else run.get('text') if isinstance(run,dict) else None
                    assert isinstance(value,str) and all(char in ' \t\x1e\x1f' for char in value), 'number_suffix accepts only spaces and tabs'
                suffix_role='number' if self.subject=='science' and number_suffix is None else role
                prefix+=self.tokens(suffix,suffix_role,para_shape)
            if head is not None and head.get('AutoIndent')=='true':
                assert not any('tab_stops' in t for t in prefix), 'Tabbed automatic-number indentation needs native verification'
                hanging+=sum(t['advance'] for t in prefix)
            tokens=prefix+tokens
        fixed_line_height=ps is not None and ps.get('FontLineHeight')=='false'
        if fixed_line_height:
            for token in tokens:
                if 'strut_height' in token:
                    token['above']=(token['strut_height']*85+50)//100
                    token['below']=token['strut_height']-token['above']
        if fragment is not None:
            fragment['progress']=False
            fragment['last_gap']=0
            if 'tokens' in fragment:
                tokens=fragment['tokens'];hanging=fragment['hanging']
                if fragment.get('continued'):first_indent=hanging
            tokens=[t|dict(_index=i) for i,t in enumerate(tokens)]
            fragment['hanging']=hanging
        condense=int(ps.get('Condense','0')) if ps is not None else 0
        line_percent=int(margin.get('LineSpacing')) if margin is not None else 160
        def line_step(line,trim_gap=False):
            end=len(line)
            while end and line[end-1].get('char')==' ' and not line[end-1].get('char_border'):end-=1
            blank_height=max((t.get('strut_height',0) for t in line),default=0) or int(cs.get('Height'))
            line=line[:end]
            if not line:return blank_height+(0 if trim_gap else line_gap(blank_height,line_percent))
            spacing_height=max((t.get('strut_height',0) for t in line),default=0) or int(cs.get('Height'))
            border_height=max(0,max((t.get('strut_height',0)+2*t.get('char_border_pen',0) for t in line),default=0)-spacing_height)
            gap=line_gap(spacing_height+border_height,line_percent) if fixed_line_height else int(cs.get('Height'))*(line_percent/100-1)
            return max(t['above']+t['below'] for t in line)+border_height+(0 if trim_gap else gap)
        line_y=y
        def next_width(line):
            nonlocal line_y
            line_y+=line_step(line)
            return self.paragraph_width(x,line_y,width)
        visible=[t for t in tokens if t.get('advance')]
        single_object=len(visible)==1 and visible[0]['kind'] in ('inline-table','inline-picture','inline-rectangle') and x+first_indent+visible[0]['advance']<=column_right
        wrap_width=self.paragraph_width(x,y,width)
        if single_object and wrap_width==width:wrap_width=max(wrap_width,visible[0]['advance']+first_indent)
        lines=self.wrap(tokens,wrap_width,hanging,first_indent,condense,
            next_width if self.float_regions else None) or [[]]
        alignment=align or (ps.get('Align') if ps is not None else 'Left')
        consumed=0
        for li,line in enumerate(lines):
            command_start=len(self.commands)
            if fragment is not None:
                start_index=min((t['_index'] for t in line),default=consumed)
                required=line_step(line,trim_end and li==len(lines)-1) if fragment.get('include_spacing') else line_step(line,True)
                if fragment.get('include_spacing') and li==len(lines)-1 and margin is not None and not trim_end:required+=int(margin.get('Next'))/2
                clearance=fragment.get('fit_clearance',0)
                fits=y+required<fragment['bottom']-clearance if clearance else y+required<=fragment['bottom']
                if tokens and not fits:
                    fragment.update(tokens=tokens[start_index:],continued=fragment.get('continued',False) or li>0)
                    return y
                consumed=max((t['_index']+1 for t in line),default=consumed)
                if consumed<len(tokens) and tokens[consumed]['kind']=='break':consumed+=1
            hard_break=any(t.get('hard_break',False) for t in line)
            empty_step=line_step(line,trim_end and li==len(lines)-1)
            trailing_gap=line_step(line)-line_step(line,True) if fragment is not None else 0
            while line and line[-1].get('char')==' ' and not line[-1].get('char_border'):line.pop()
            if not line:
                if fragment is not None:
                    fragment['progress']=True
                    fragment['last_gap']=trailing_gap
                y+=empty_step
                continue
            above=max(t['above'] for t in line);below=max(t['below'] for t in line)
            centered=ps is not None and ps.get('VerAlign')=='Center'
            if centered:above=below=max(t['above']+t['below'] for t in line)/2
            inset=hanging if li else first_indent
            available=self.paragraph_width(x,y,width)-inset
            compressed=condense_line(line,available,condense)
            if compressed is not None:line=compressed
            padding=character_border_padding(line)
            occupied=sum(t['advance'] for t in line)+sum(sum(p) for p in padding)-line[-1].get('trailing_spacing',0)
            visible=[t for t in line if t['advance']]
            # Hancom lets an object alone on a line protrude by the hanging indent.
            if li>0 and hanging and len(visible)==1 and visible[0]['kind'] in ('inline-table','inline-picture','inline-rectangle') and occupied<=self.paragraph_width(x,y,width):
                available=max(available,occupied)
            if single_object and self.paragraph_width(x,y,width)==width:available=max(available,occupied)
            assert occupied<=available+1, 'Paragraph line overflow'
            cursor=self.paragraph_region(x,y,width)[0]+inset
            if alignment=='Center':cursor+=(available-occupied)/2
            elif alignment=='Right':cursor+=available-occupied
            gaps=justification_gaps(line)
            extra=(available-occupied)/len(gaps) if alignment=='Justify' and (li<len(lines)-1 or continues) and not hard_break and gaps else 0
            if alignment in ('Distribute','DistributeSpace'):
                gaps=[i for i,t in enumerate(line[:-1]) if alignment=='Distribute' or t.get('char')==' ']
                extra=(available-occupied)/len(gaps) if gaps else 0
            underlines=[];borders=[]
            for ti,token in enumerate(line):
                cursor+=padding[ti][0]
                paint_y=y+above+(token['center_shift'] if centered and token['kind']=='text' else 0)+token.get('offset',0)
                if token.get('underline'):underlines.append((token,cursor,token['advance']+(extra if ti in gaps else 0)))
                if token['kind']=='text':borders.append((token,cursor,paint_y,token['advance']+(extra if ti in gaps else 0)))
                if token['kind']=='text' and not token['char'].isspace():
                    self.commands.append({k:v for k,v in token.items() if k not in ('above','below','strut_height','can_break','offset','draw_dx','_index')} |
                        dict(x=cursor+token.get('draw_dx',0),y=paint_y))
                elif token['kind']=='equation':
                    self.commands.append(dict(kind='equation',key=token['key'],x=cursor+token['left_margin'],y=y+above-(token['height']/2 if centered else token['above']),width=token['width'],height=token['height']))
                elif token['kind'] in ('inline-table','inline-picture','inline-rectangle'):
                    top=y+above-((token['above']+token['below'])/2 if centered else token['above'])+token['top_margin']
                    self.commands.extend(c|dict(x=c['x']+cursor+token['left_margin'],y=c['y']+top) for c in token['commands'])
                cursor+=token['advance']+(extra if ti in gaps else 0)+padding[ti][1]
            self.commands.extend(underline_commands(underlines,y+above+below))
            self.commands.extend(self.header.character_borders(borders))
            if fragment is not None and max((command_bottom(c) for c in self.commands[command_start:]),default=y)>fragment['bottom']:
                del self.commands[command_start:]
                fragment.update(tokens=tokens[start_index:],continued=fragment.get('continued',False) or li>0)
                return y
            if fragment is not None:
                fragment['progress']=True
                fragment['last_gap']=trailing_gap
            y+=line_step(line,trim_end and li==len(lines)-1)
        if fragment is not None:fragment['tokens']=[]
        return y+(int(margin.get('Next'))/2 if margin is not None and not trim_end and not continues else 0)

    def passage_signature(self,border):
        if border is None:return None
        saved=self.header.commands;self.header.commands=[]
        try:
            self.header.border(border.get('BorderFill'),0,0,1,1)
            return ({k:v for k,v in border.attrib.items() if k not in ('BorderFill','OffsetTop','OffsetBottom')},self.header.commands)
        finally:self.header.commands=saved

    def source_passage(self,block,x,y,width,fragment=None):
        items=block.get('items')
        assert isinstance(items,list) and items, 'A passage requires nonempty paragraph items'
        role=block.get('style','passage');ps=self.paragraph_shape(role,block.get('para_shape'))
        border=ps.find('PARABORDER');pm=ps.find('PARAMARGIN')
        assert border is not None and border.get('Connect')=='true', 'Choose an original style with connected paragraph borders'
        inset=border.get('IgnoreMargin')=='true'
        ml,mr,mt,mb=[int(border.get('Offset'+side,'0')) for side in ('Left','Right','Top','Bottom')]
        continued=fragment is not None and fragment.get('continued',False)
        if fragment is not None:fragment['progress']=False
        if continued:mt=0
        start=len(self.commands);end=y+mt
        first_item=fragment.get('item',0) if fragment is not None else 0
        remaining=False
        for i in range(first_item,len(items)):
            item=items[i]
            runs=item['runs'] if isinstance(item,dict) else item
            shape=item.get('para_shape',block.get('para_shape')) if isinstance(item,dict) else block.get('para_shape')
            item_ps=self.paragraph_shape(role,shape);item_pm=item_ps.find('PARAMARGIN')
            item_border=item_ps.find('PARABORDER')
            assert item_border is not None and self.passage_signature(item_border)==self.passage_signature(border) and (not inset or all(item_pm.get(k)==pm.get(k) for k in ('Left','Right'))), 'Connected paragraphs must share border and enclosed side margins'
            mb=int(item_border.get('OffsetBottom','0'))
            paragraph_fragment=None
            if fragment is not None:
                paragraph_fragment=fragment.setdefault('paragraph',{})
                paragraph_fragment['bottom']=fragment['bottom']-mb
                paragraph_fragment['include_spacing']=True
            if isinstance(item,dict) and 'wrap_table' in item:
                assert fragment is None, 'A floating-label passage needs explicit pages until automatic continuation is verified'
                self.wrapped_table(item['wrap_table'],x,end+int(item_pm.get('Prev'))/2,width,para_shape=shape)
            end=self.paragraph(runs,role,x,end,width,para_shape=shape,trim_end=inset and i==len(items)-1,fragment=paragraph_fragment,
                continued=item.get('continued',False) if isinstance(item,dict) else False,continues=item.get('continues',False) if isinstance(item,dict) else False)
            if paragraph_fragment is not None:
                fragment['progress'] |= paragraph_fragment['progress']
                if paragraph_fragment.get('tokens'):
                    fragment['item']=i;remaining=True;break
                fragment['paragraph']={};fragment['item']=i+1
        if fragment is not None:
            fragment['remaining']=remaining
            fragment['continued']=continued or end>y+mt
            if remaining and end==y+mt and len(self.commands)==start:return y
        bottom=end+mb
        # Background and border precede the editable paragraph text.
        text=self.commands[start:];del self.commands[start:]
        saved=self.header.commands;self.header.commands=[]
        try:
            left=int(pm.get('Left'))/2 if inset else 0
            right=int(pm.get('Right'))/2 if inset else 0
            self.header.border(border.get('BorderFill'),x+left-ml,y+int(pm.get('Prev'))/2,width-left-right+ml+mr,bottom-y-int(pm.get('Prev'))/2)
            self.commands.extend(c|({'continuation_frame':True} if block.get('open_bottom') and c['kind']=='line' and c['width']==0 else {}) for c in self.header.commands if not (c['kind']=='line' and c['height']==0 and
                ((continued or block.get('open_top')) and c['y']==y+int(pm.get('Prev'))/2 or (remaining or block.get('open_bottom')) and c['y']==bottom)))
        finally:self.header.commands=saved
        self.commands.extend(text)
        return end+mb

    def source_object_left(self,table,x,width):
        parent=next(table.iterancestors('P'))
        ps=self.root.find(f'.//PARASHAPE[@Id="{parent.get("ParaShape")}"]')
        pm=ps.find('PARAMARGIN');outer=table.find('SHAPEOBJECT/OUTSIDEMARGIN')
        object_width=int(table.find('SHAPEOBJECT/SIZE').get('Width'))
        inset=int(pm.get('Left'))/2+max(0,int(pm.get('Indent'))/2)+int(outer.get('Left'))
        available=width-int(pm.get('Left'))/2-int(pm.get('Right'))/2
        if ps.get('Align')=='Center':inset+=max(0,available-object_width)/2
        elif ps.get('Align')=='Right':inset+=available-object_width
        return x+inset

    def source_object_spacing(self,table):
        parent=next(table.iterancestors('P'))
        ps=self.root.find(f'.//PARASHAPE[@Id="{parent.get("ParaShape")}"]')
        pm=ps.find('PARAMARGIN');outer=table.find('SHAPEOBJECT/OUTSIDEMARGIN')
        assert pm.get('LineSpacingType')=='Percent', 'Source box requires percentage paragraph spacing'
        height=max(int(self.root.find(f'.//CHARSHAPE[@Id="{t.get("CharShape")}"]').get('Height')) for t in parent.findall('TEXT'))
        # Inline tables retain their parent paragraph's line gap after the outer margin.
        return (int(pm.get('Prev'))/2+int(outer.get('Top')),
                int(pm.get('Next'))/2+int(outer.get('Bottom'))+line_gap(height,int(pm.get('LineSpacing'))))

    def box_frame(self,block,x,width):
        subject=block.get('box_subject',self.subject)
        assert subject in ('korean','english','social','science'), 'Choose a subject with a source table box'
        owner=self if subject==self.subject else Composer(subject)
        table=owner.root.findall('./BODY/SECTION//TABLE')[dict(korean=27,english=14,social=10,science=14)[subject]]
        return owner.source_object_left(table,x,width),int(table.find('SHAPEOBJECT/SIZE').get('Width'))

    def source_box(self,block,x,y,width):
        if self.subject=='math':
            cs,original_ps=self.styles['21 박스(테두리)']
            ps=deepcopy(original_ps);pm=ps.find('PARAMARGIN');border=ps.find('PARABORDER')
            ml,mr,mt,mb=[int(border.get('Offset'+side)) for side in ('Left','Right','Top','Bottom')]
            inset=int(pm.get('Left'))/2-ml
            box_width=width-inset-int(pm.get('Right'))/2+mr
            after=int(pm.get('Next'))/2;before=int(pm.get('Prev'))/2
            pm.set('Left','0');pm.set('Right','0');pm.set('Prev','0');pm.set('Next','0')
            minimum=0;border_id=border.get('BorderFill');x+=inset;y+=before
        else:
            index=block.get('box_template',dict(korean=27,english=14,social=10,science=14)[self.subject])
            tables=self.root.findall('./BODY/SECTION//TABLE')
            assert isinstance(index,int) and 0<=index<len(tables), 'Invalid source box table index'
            table=tables[index];cells=table.findall('./ROW/CELL')
            assert len(cells)==1, 'This box requires a single-cell source table'
            cell=cells[0];p=cell.find('./PARALIST/P')
            cs=self.root.find(f'.//CHARSHAPE[@Id="{p.find("TEXT").get("CharShape")}"]')
            ps=self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
            mg=cell.find('CELLMARGIN') if cell.get('HasMargin')=='true' else table.find('INSIDEMARGIN')
            ml,mr,mt,mb=[int(mg.get(side)) for side in ('Left','Right','Top','Bottom')]
            size=table.find('./SHAPEOBJECT/SIZE');box_width=int(size.get('Width'));minimum=int(size.get('Height'))
            before,after=self.source_object_spacing(table)
            x=self.source_object_left(table,x,width);y+=before
            border_id=cell.get('BorderFill')
        self.styles['@source-box']=(cs,ps)
        role=block.get('style','@source-box')
        paragraphs=block['items'] if 'items' in block else [block['runs']]
        assert isinstance(paragraphs,list) and paragraphs, 'Box items must contain paragraphs'
        end=y+mt
        for i,item in enumerate(paragraphs):
            runs=item['runs'] if isinstance(item,dict) else item
            align=item.get('align',block.get('align')) if isinstance(item,dict) else block.get('align')
            end=self.paragraph(runs,role,x+ml,end,box_width-ml-mr,align=align,trim_end=i==len(paragraphs)-1)
        height=max(0 if block.get('fit_content') else minimum,end+mb-y)
        start=len(self.header.commands)
        self.header.border(border_id,x,y,box_width,height)
        self.commands[0:0]=self.header.commands[start:]
        return y+height+after

    def source_example(self,block,x,y,width):
        from extract_body_fixture import Body
        from extract_headers import Header
        templates=dict(korean=6,social=11,science=12)
        assert self.subject in templates, 'This original HWP has no labelled example table prototype'
        source=Body(self.subject)
        table=source.root.findall('./BODY/SECTION//TABLE')[templates[self.subject]]
        cells=table.findall('./ROW/CELL')
        assert table.get('RowCount')=='3' and table.get('ColCount')=='3' and len(cells)==6
        size=table.find('./SHAPEOBJECT/SIZE');tw=int(size.get('Width'))
        before,after=self.source_object_spacing(table)
        x=self.source_object_left(table,x,width);y+=before
        column_widths=[max(int(c.get('Width')) for c in cells if int(c.get('ColAddr'))==col and c.get('ColSpan')=='1') for col in range(3)]
        row_heights=[max(int(c.get('Height')) for c in cells if int(c.get('RowAddr'))==row and c.get('RowSpan')=='1') for row in range(2)]
        assert sum(column_widths)==tw
        label=next(c for c in cells if c.get('RowSpan')=='2')
        assert sum(row_heights)>=int(label.get('Height'))
        body=next(c for c in cells if c.get('ColSpan')=='3');p=body.find('./PARALIST/P')
        cs=source.root.find(f'.//CHARSHAPE[@Id="{p.find("TEXT").get("CharShape")}"]')
        ps=source.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
        self.styles['@source-example']=(cs,ps)
        mg=body.find('CELLMARGIN') if body.get('HasMargin')=='true' else table.find('INSIDEMARGIN')
        ml,mr,mt,mb=[int(mg.get(side)) for side in ('Left','Right','Top','Bottom')]
        body_y=y+sum(row_heights);cursor=body_y+mt
        paragraphs=block.get('items',[block.get('runs','')])
        assert isinstance(paragraphs,list) and paragraphs and all(isinstance(item,(str,list)) for item in paragraphs), 'Example content must contain a list of paragraphs'
        for index,runs in enumerate(paragraphs):
            cursor=self.paragraph(runs,'@source-example',x+ml,cursor,tw-ml-mr,trim_end=index==len(paragraphs)-1)
        body_height=max(0 if block.get('fit_content') else int(size.get('Height'))-sum(row_heights),cursor+mb-body_y)
        row_heights.append(body_height)
        for cell in cells:
            col,row=int(cell.get('ColAddr')),int(cell.get('RowAddr'))
            cw=sum(column_widths[col:col+int(cell.get('ColSpan'))]);ch=sum(row_heights[row:row+int(cell.get('RowSpan'))])
            cx=x+sum(column_widths[:col]);cy=y+sum(row_heights[:row])
            source.border(cell.get('BorderFill'),cx,cy,cw,ch)
            if cell is label:
                mg=cell.find('CELLMARGIN') if cell.get('HasMargin')=='true' else table.find('INSIDEMARGIN')
                lm,rm,tm,bm=[int(mg.get(side)) for side in ('Left','Right','Top','Bottom')]
                plist=cell.find('PARALIST');paragraphs=plist.findall('P')
                content=max(line['vertical_position']+line['line_height'] for lp in paragraphs for line in source.records[lp]['lines'])
                dy=(ch-tm-bm-content)/2 if plist.get('VertAlign')=='Center' else 0
                for lp in paragraphs:Header.paragraph(source,lp,cx+lm,cy+tm+dy,cw-lm-rm)
        self.commands[0:0]=source.commands
        return y+sum(row_heights)+after

    def can_split_table(self,block,table=None):
        if table is None:
            tables=self.root.findall('./BODY/SECTION//TABLE');index=block.get('table_template')
            if type(index) is not int or not 0<=index<len(tables):return False
            table=tables[index]
        cells=table.findall('./ROW/CELL')
        # shortcut: add vertical spans and repeated headings after native pagination checks.
        position=table.find('./SHAPEOBJECT/POSITION')
        return (table.get('PageBreak')=='Cell' and all(c.get('RowSpan')=='1' for c in cells)
            and table.find('./SHAPEOBJECT/POSITION').get('TreatAsChar')=='false'
            and position.get('HorzRelTo') in ('Para','Column') and position.get('VertRelTo')=='Para' and position.get('VertAlign')=='Top'
            and not (table.get('RepeatHeader')=='true' and any(c.get('Header')=='true' for c in cells))
            and isinstance(block.get('cells'),dict)
            and all(c.get('RowAddr')+','+c.get('ColAddr') in block['cells'] for c in cells))

    def source_table(self,block,x,y,width,source=None,fixed=None,fragment=None,layout=None,anchor=None):
        from extract_body_fixture import Body
        source=source if source is not None else Body(self.subject)
        tables=source.root.findall('./BODY/SECTION//TABLE')
        index=block.get('table_template')
        assert type(index) is int and 0<=index<len(tables), 'Choose an original table_template index'
        table=tables[index];cells=table.findall('./ROW/CELL')
        if fragment is not None and fixed is None:anchor=fragment
        if fragment is not None:
            assert self.can_split_table(block,table), 'This original table cannot split into editable cell fragments yet'
            if int(table.get('RowCount'))>1:
                return self.source_table_rows(block,x,y,width,source,table,fragment)
            before_fragment=deepcopy(fragment);stalled=False
            fragment['progress']=False
            fragment['remaining']=False
        assert table.get('CellSpacing')=='0', 'Nonzero source cell spacing is not implemented'
        edits=block.get('cells',{})
        assert isinstance(edits,dict), 'Table cells must be an object keyed by zero-based row,column'
        anchors={f'{c.get("RowAddr")},{c.get("ColAddr")}' for c in cells}
        assert edits.keys()<=anchors, 'Edited cell is outside the table or covered by a merged cell'
        nested=block.get('nested_cells',{})
        assert isinstance(nested,dict), 'nested_cells must map source table indices to cell edits'
        descendants={str(tables.index(t)):t for t in table.findall('.//TABLE')}
        assert nested.keys()<=descendants.keys(), 'Edited nested table must belong to this source table'
        for key in nested:
            target=descendants[key]
            assert isinstance(nested[key],dict), 'Nested cell edits must be an object'
            assert all(t not in source.skip for t in (target,*target.iterancestors('TABLE'))), 'Nested table is excluded from body rendering'
            for ancestor in target.iterancestors('CELL'):
                owner=ancestor.getparent().getparent()
                owner_edits=edits if owner is table else nested.get(str(tables.index(owner)),{})
                assert f'{ancestor.get("RowAddr")},{ancestor.get("ColAddr")}' not in owner_edits, 'Cannot edit a nested table inside a replaced cell'
                if owner is table:break
        for border_id in {c.get('BorderFill') for c in cells}:
            border=source.root.find(f'.//BORDERFILL[@Id="{border_id}"]')
            assert all(edge.get('Type') in ('None','Solid','Dash') for edge in border if edge.tag.endswith('BORDER')), 'Unsupported original table line style'
            brush=border.find('FILLBRUSH')
            assert brush is None or all(child.tag=='WINDOWBRUSH' for child in brush), 'Original image or gradient cell fill needs a renderer'
        rows,cols=int(table.get('RowCount')),int(table.get('ColCount'))
        parent=next(table.iterancestors('P'))
        ps=source.root.find(f'.//PARASHAPE[@Id="{parent.get("ParaShape")}"]')
        pm=ps.find('PARAMARGIN');outer=table.find('./SHAPEOBJECT/OUTSIDEMARGIN')
        position=table.find('./SHAPEOBJECT/POSITION')
        anchor_position=None
        if anchor is not None:
            ax,aw=x,width
            if position.get('HorzRelTo')=='Para':
                ax+=int(pm.get('Left'))/2+max(0,int(pm.get('Indent'))/2)
                aw-=(int(pm.get('Left'))+int(pm.get('Right')))/2
            ay=y+(int(pm.get('Prev'))/2+int(outer.get('Top')) if not anchor.get('started') else 0)
            anchor_position=list(source.position(table,(ax,ay,aw)))
            if anchor.get('started'):anchor_position[1]-=int(position.get('VertOffset'))
        size=table.find('./SHAPEOBJECT/SIZE');tw=int(size.get('Width'))
        xs=dict(fragment.get('columns',{0:0})) if fragment is not None else {0:0}
        # Prefer unmerged widths; HWP may round a merged width by one unit.
        pending=sorted(cells,key=lambda c:int(c.get('ColSpan')))
        while pending:
            before=len(pending)
            for cell in pending[:]:
                col=int(cell.get('ColAddr'));end=col+int(cell.get('ColSpan'))
                if col in xs:xs.setdefault(end,xs[col]+int(cell.get('Width')))
                elif end in xs:xs[col]=xs[end]-int(cell.get('Width'))
                else:continue
                pending.remove(cell)
            assert len(pending)<before, 'Cannot resolve original merged column widths'
        assert all(i in xs for i in range(cols+1)), 'Missing original column boundary'
        assert abs(xs[cols]-tw)<=cols, 'Source table width conflicts with its cells'
        xs[cols]=tw
        heights=[0]*rows;prepared=[];occupied=set()
        for cell in cells:
            row,col=int(cell.get('RowAddr')),int(cell.get('ColAddr'))
            rs,cs=int(cell.get('RowSpan')),int(cell.get('ColSpan'))
            assert 0<=row<row+rs<=rows and 0<=col<col+cs<=cols
            area={(r,c) for r in range(row,row+rs) for c in range(col,col+cs)}
            assert not occupied.intersection(area), 'Overlapping original merged cells'
            occupied.update(area)
            plist=cell.find('PARALIST');paragraphs=plist.findall('P')
            assert plist.get('TextDirection')=='0' and plist.get('LineWrap')=='Break', 'Unsupported source cell writing direction or wrapping'
            mg=cell.find('CELLMARGIN') if cell.get('HasMargin')=='true' else table.find('INSIDEMARGIN')
            ml,mr,mt,mb=[int(mg.get(side)) for side in ('Left','Right','Top','Bottom')]
            cw=xs[col+cs]-xs[col];key=f'{row},{col}'
            if key in edits:
                assert isinstance(edits[key],(str,list)), 'Replacement cell content must be text or a list of text/equation runs'
                p=paragraphs[0]
                charshape=source.root.find(f'.//CHARSHAPE[@Id="{p.find("TEXT").get("CharShape")}"]')
                parashape=source.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
                self.styles['@source-cell']=(charshape,parashape)
                saved=self.commands;regions=self.float_regions;self.commands=[];self.float_regions=[]
                try:
                    paragraph_fragment=None
                    if fragment is not None:
                        paragraph_fragment=fragment.setdefault('cells',{}).setdefault(key,{})
                        table_top=fixed[1] if fixed is not None else anchor_position[1] if anchor_position is not None else y+int(pm.get('Prev'))/2+int(outer.get('Top'))
                        # Native table cells require strictly more than 1pt below the next line.
                        paragraph_fragment.update(bottom=fragment['bottom']-table_top-mt-mb,include_spacing=False,fit_clearance=100)
                    if paragraph_fragment is not None and paragraph_fragment.get('done'):
                        end=0;paragraph_fragment.update(progress=False,last_gap=0)
                    # Native cell line records keep a 1440-unit text width even inside narrower cells.
                    else:end=self.paragraph(edits[key],'@source-cell',0,0,max(1440,cw-ml-mr),trim_end=True,fragment=paragraph_fragment)
                    commands=self.commands
                finally:self.commands=saved;self.float_regions=regions
                content=max(0,end-(paragraph_fragment['last_gap'] if paragraph_fragment and paragraph_fragment.get('tokens') else 0))
            else:
                assert all(child.tag in ('CHAR','PICTURE','TABLE','RECTANGLE','COLDEF','EQUATION') for p in paragraphs for run in p.findall('TEXT') for child in run), 'This source cell contains an unsupported object'
                start=len(source.commands)
                growth=0
                for p in paragraphs:growth+=source.paragraph(p,0,growth,cw-ml-mr,nested_cells=nested)
                commands=source.commands[start:];del source.commands[start:]
                content=max((line['vertical_position']+line['line_height'] for p in paragraphs for line in source.records[p]['lines']),default=0)+growth
                content=max(content,max((c['y']+c['height'] for c in commands if c['kind'] in ('image','equation')),default=0))
            minimum=int(cell.get('Height'))
            if fragment is not None:
                remaining=bool(paragraph_fragment.get('tokens'))
                stalled |= remaining and not paragraph_fragment['progress']
                fragment['progress'] |= paragraph_fragment['progress']
                fragment['remaining'] |= remaining
                paragraph_fragment['done']=not remaining
                minimum=0 if remaining else max(0,minimum-fragment.get('consumed_height',0))
            required=max(minimum,mt+content+mb)
            if rs==1:heights[row]=max(heights[row],required)
            prepared.append((cell,commands,content,(ml,mr,mt,mb),required))
        assert len(occupied)==rows*cols, 'Source table has uncovered grid slots'
        if fragment is not None and stalled:
            fragment.clear();fragment.update(before_fragment,progress=False,remaining=True)
            return y
        for cell,_,_,_,required in sorted(prepared,key=lambda item:int(item[0].get('RowSpan'))):
            row=int(cell.get('RowAddr'));rs=int(cell.get('RowSpan'))
            heights[row+rs-1]+=max(0,required-sum(heights[row:row+rs]))
        minimum=int(size.get('Height'))
        if fragment is not None:minimum=0 if fragment['remaining'] else max(0,minimum-fragment.get('consumed_height',0))
        heights[-1]+=max(0,minimum-sum(heights))
        inset=int(pm.get('Left'))/2+max(0,int(pm.get('Indent'))/2)+int(outer.get('Left'))
        available=width-int(pm.get('Left'))/2-int(pm.get('Right'))/2
        alignment=ps.get('Align')
        if alignment=='Center':inset+=max(0,available-tw)/2
        elif alignment=='Right':inset+=available-tw
        if fixed is None:
            if anchor_position is not None:x,y=anchor_position[:2]
            else:x+=inset;y+=int(pm.get('Prev'))/2+int(outer.get('Top'))
        else:
            x,y,fw,fh=fixed
            assert fw==tw, 'Scaled source table width needs a renderer'
            heights[-1]+=max(0,fh-sum(heights))
        if layout is not None:layout.update(x=x,y=y,columns=xs,heights=heights,width=tw)
        text=[];rules=[]
        for cell,commands,content,(ml,mr,mt,mb),_ in prepared:
            row,col=int(cell.get('RowAddr')),int(cell.get('ColAddr'))
            rs,cs=int(cell.get('RowSpan')),int(cell.get('ColSpan'))
            cx,cy=x+xs[col],y+sum(heights[:row]);cw=xs[col+cs]-xs[col];ch=sum(heights[row:row+rs])
            start=len(source.commands)
            source.border(cell.get('BorderFill'),cx,cy,cw,ch)
            rules.extend(source.commands[start:]);del source.commands[start:]
            align=cell.find('PARALIST').get('VertAlign');assert align in ('Top','Center','Bottom')
            dy=(ch-mt-mb-content)*({'Top':0,'Center':.5,'Bottom':1}[align])
            for command in commands:
                placed=command|dict(x=command['x']+cx+ml,y=command['y']+cy+mt+dy)
                if f'{row},{col}' in edits and cw-ml-mr<1440:
                    # Native clips the expanded line canvas to the physical narrow cell.
                    placed['clip']=dict(x=cx-placed['x'],y=cy-placed['y'],width=cw,height=ch)
                text.append(placed)
        # Paint all backgrounds before any cell rules, including shared edges.
        self.commands.extend(c for c in rules if c['kind']=='fill')
        self.commands.extend(c for c in rules if c['kind']!='fill')
        self.commands.extend(text)
        if fragment is not None:
            fragment['consumed_height']=fragment.get('consumed_height',0)+sum(heights)
            fragment['started']=True
        after=int(pm.get('Next'))/2+int(outer.get('Bottom')) if fixed is None and not (fragment and fragment['remaining']) else 0
        return y+sum(heights)+after

    def source_table_rows(self,block,x,y,width,source,table,fragment):
        model={};start=len(self.commands)
        end=self.source_table(block,x,y,width,source=source,layout=model,anchor=fragment)
        trial=self.commands[start:];del self.commands[start:]
        if not fragment.get('row') and not fragment.get('row_fragment') and model['y']+sum(model['heights'])+100<fragment['bottom']:
            self.commands.extend(trial);fragment.update(progress=True,remaining=False,started=True)
            return end
        row=fragment.get('row',0);rows=table.findall('ROW');parent=table.getparent()
        top=model['y'];progress=False
        while row<len(rows):
            piece=deepcopy(table)
            for child in piece.findall('ROW'):piece.remove(child)
            current=deepcopy(rows[row]);piece.append(current);piece.set('RowCount','1')
            piece.find('./SHAPEOBJECT/SIZE').set('Height','0')
            edits={}
            for cell in current.findall('CELL'):
                old=cell.get('RowAddr')+','+cell.get('ColAddr')
                cell.set('RowAddr','0');edits['0,'+cell.get('ColAddr')]=block['cells'][old]
            state=fragment.setdefault('row_fragment',{})
            state.update(bottom=fragment['bottom'],columns=model['columns'])
            parent.replace(table,piece)
            try:
                finish=self.source_table(block|dict(cells=edits),x,top,width,source=source,
                    fixed=(model['x'],top,model['width'],0),fragment=state)
            finally:parent.replace(piece,table)
            progress |= state['progress']
            if state['remaining']:
                fragment.update(row=row,progress=progress,remaining=True,started=fragment.get('started',False) or progress)
                return finish
            top=finish;row+=1;fragment['row']=row;fragment.pop('row_fragment',None)
        fragment.update(progress=progress,remaining=False,started=True)
        return top+(end-model['y']-sum(model['heights']))

    def wrapped_picture(self,index,x,y,width):
        from extract_body_fixture import Body
        source=Body(self.subject);pictures=source.root.findall('./BODY/SECTION//PICTURE')
        assert type(index) is int and 0<=index<len(pictures), 'Choose an original wrap_picture index'
        picture=pictures[index];shape=picture.find('SHAPEOBJECT');position=shape.find('POSITION')
        # shortcut: only original top/right column anchors; extend after native checks for other wrap modes.
        assert shape.get('TextWrap')=='Square' and shape.get('TextFlow')=='BothSides' and all(position.get(k)==v for k,v in
            dict(TreatAsChar='false',HorzAlign='Right',HorzRelTo='Column',HorzOffset='0',VertAlign='Top',VertRelTo='Para',VertOffset='0').items()), 'wrap_picture requires an original top/right column-anchored square wrap'
        px,py,w,h=source.position(picture,(x,y,width));outer=shape.find('OUTSIDEMARGIN')
        region=dict(left=px-int(outer.get('Left')),right=px+w+int(outer.get('Right')),
            top=py-int(outer.get('Top')),bottom=py+h+int(outer.get('Bottom')))
        assert region['left']>x and region['right']<=x+width, 'Floating picture must leave text space inside its column'
        assert not any(region['left']<r['right'] and r['left']<region['right'] and region['top']<r['bottom'] and r['top']<region['bottom'] for r in self.float_regions), 'Floating pictures overlap'
        source.picture(picture,px,py,w,h);self.commands.extend(source.commands)
        self.float_regions.append(region)
        return region

    def wrapped_table(self,block,x,y,width,para_shape=None):
        from extract_body_fixture import Body
        source=Body(self.subject);tables=source.root.findall('./BODY/SECTION//TABLE')
        index=block.get('table_template')
        assert type(index) is int and 0<=index<len(tables), 'Choose an original wrap_table index'
        table=tables[index];shape=table.find('SHAPEOBJECT');position=shape.find('POSITION')
        assert shape.get('TextWrap')=='Square' and shape.get('TextFlow')=='BothSides' and all(position.get(k)==v for k,v in
            dict(TreatAsChar='false',VertAlign='Top',VertRelTo='Para').items()), 'Unsupported floating table anchor'
        column=position.get('HorzRelTo')=='Column'
        if column:
            assert self.subject=='korean' and position.get('HorzAlign') in ('Left','Right') and position.get('HorzOffset')=='708' and position.get('VertOffset') in ('141','396'), 'Unsupported column label anchor'
        else:
            assert position.get('HorzRelTo')=='Para' and position.get('HorzAlign')=='Right' and position.get('HorzOffset')=='0', 'Unsupported floating paragraph anchor'
            if para_shape is not None:
                pm=self.paragraph_shape('question',para_shape).find('PARAMARGIN');ml,mr=int(pm.get('Left'))/2,int(pm.get('Right'))/2
                x+=ml;width-=ml+mr
        px,py,w,h=source.position(table,(x,y,width));outer=shape.find('OUTSIDEMARGIN')
        bottom=self.source_table(block,x,y,width,source=source,fixed=(px,py,w,h))
        region=dict(left=px-int(outer.get('Left')),right=px+w+int(outer.get('Right')),
            top=py-int(outer.get('Top')),bottom=bottom+int(outer.get('Bottom')))
        if column:region.update(side=position.get('HorzAlign'),wrap_top=y)
        assert (region['left']>x if position.get('HorzAlign')=='Right' else region['right']<x+width) and region['right']<=x+width, 'Floating table must leave text space inside its paragraph'
        assert not any(region['left']<r['right'] and r['left']<region['right'] and region['top']<r['bottom'] and r['top']<region['bottom'] for r in self.float_regions), 'Floating objects overlap'
        self.float_regions.append(region)
        return region

    def data_table(self,block,x,y,width):
        assert self.subject=='social', 'Editable data tables currently use original social table styles'
        rows=block['rows']
        assert isinstance(rows,list) and rows and all(isinstance(row,list) and row for row in rows), 'Table rows must be nonempty lists'
        weights=block.get('widths',[1]*len(rows[0]))
        assert weights and all(len(row)==len(weights) for row in rows), 'Table rows must have the same number of cells'
        assert all(type(v) in (int,float) and isfinite(v) and v>0 for v in weights), 'Table column weights must be positive'
        prototype=self.root.findall('./BODY/SECTION//TABLE')[9 if block.get('rules') is False else 50]
        table_width=min(width,int(prototype.find('SHAPEOBJECT/SIZE').get('Width')))
        x,width=self.box_frame(block,x,width)
        table_width=min(width,table_width)
        x+=(width-table_width)/2;width=table_width
        cell=prototype.find('./ROW/CELL');p=cell.find('./PARALIST/P')
        cs=self.root.find(f'.//CHARSHAPE[@Id="{p.find("TEXT").get("CharShape")}"]')
        ps=deepcopy(self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]'))
        if block.get('rules') is False:cs,original_ps=self.styles['choices'];ps=deepcopy(original_ps)
        ps.find('PARAMARGIN').attrib.update(dict(Left='0',Right='0',Indent='0',Prev='0',Next='0'))
        self.styles['@data-table']=(cs,ps)
        role='@data-table'
        mg=cell.find('CELLMARGIN') if cell.get('HasMargin')=='true' else prototype.find('INSIDEMARGIN')
        ml,mr,mt,mb=[int(mg.get(side)) for side in ('Left','Right','Top','Bottom')]
        widths=[width*v/sum(weights) for v in weights]
        assert all(w>ml+mr for w in widths), 'Table cells must leave room for text after original padding'
        for row in rows:
            prepared=[];cx=x;height=0
            for runs,w in zip(row,widths):
                saved=self.commands;regions=self.float_regions;self.commands=[];self.float_regions=[]
                try:
                    end=self.paragraph(runs,role,0,0,w-ml-mr,align='Center',trim_end=True)
                    prepared.append((cx,w,end,self.commands))
                finally:self.commands=saved;self.float_regions=regions
                height=max(height,mt+end+mb);cx+=w
            for cx,w,end,commands in prepared:
                if block.get('rules') is not False:
                    start=len(self.header.commands);self.header.border(cell.get('BorderFill'),cx,y,w,height)
                    self.commands.extend(self.header.commands[start:])
                self.commands.extend(c|dict(x=c['x']+cx+ml,y=c['y']+y+mt+(height-mt-mb-end)/2) for c in commands)
            y+=height
        return y

    def figure(self,block,x,y,width):
        path=(ROOT/block['file']).resolve()
        assert path.is_relative_to((ROOT/'assets').resolve()) and path.is_file(), 'Figure must be an existing file inside assets'
        assert path.suffix.lower() in ('.svg','.png','.jpg','.jpeg'), 'Use an SVG, PNG or JPEG figure'
        sizes=[block[k] for k in ('width_mm','height_mm')]
        assert all(type(v) in (int,float) and isfinite(v) and v>0 for v in sizes), 'Figure dimensions must be positive finite millimetres'
        w,h=[v*7200/25.4 for v in sizes]
        assert w<=width, 'Figure is wider than the original column'
        if self.subject=='social' or 'box_subject' in block:
            x,width=self.box_frame(block,x,width)
            assert w<=width, 'Figure is wider than the original source box'
        self.commands.append(dict(kind='image',path=path.relative_to(ROOT).as_posix(),
            x=x+(width-w)/2,y=y,width=w,height=h,full_width=w,full_height=h))
        return y+h

    def source_picture(self,block,x,y,width):
        from extract_body_fixture import Body
        source=Body(self.subject)
        pictures=source.root.findall('./BODY/SECTION//PICTURE');index=block.get('picture_template')
        assert type(index) is int and 0<=index<len(pictures), 'Choose an original picture_template index'
        picture=pictures[index];shape=picture.find('SHAPEOBJECT')
        inline=shape.find('POSITION').get('TreatAsChar')=='true'
        size,outer=shape.find('SIZE'),shape.find('OUTSIDEMARGIN')
        w,h=int(size.get('Width')),int(size.get('Height'))
        ml,mr,mt,mb=[int(outer.get(k)) for k in ('Left','Right','Top','Bottom')]
        parent=next(picture.iterancestors('P'))
        ps=source.root.find(f'.//PARASHAPE[@Id="{parent.get("ParaShape")}"]')
        pm=ps.find('PARAMARGIN')
        left=int(pm.get('Left'))/2+max(0,int(pm.get('Indent'))/2)
        available=width-left-int(pm.get('Right'))/2
        x+=left;y+=int(pm.get('Prev'))/2
        if inline:
            x+=ml;y+=mt
            if ps.get('Align')=='Center':x+=max(0,available-w-ml-mr)/2
            elif ps.get('Align')=='Right':x+=available-w-ml-mr
        else:x,y,w,h=source.position(picture,(x,y,available))
        assert 0<=x and x+w<=int(source.page.get('Width')), 'Original picture extends outside the paper'
        source.picture(picture,x,y,w,h)
        self.commands.extend(source.commands)
        return y+h+mb+int(pm.get('Next'))/2

    def source_artwork(self,block,x,y,width):
        from extract_body_fixture import Body,chars
        source=Body(self.subject);paragraphs=[p for s in source.root.findall('./BODY/SECTION') for p in s.findall('P')]
        index=block.get('artwork_paragraph')
        assert type(index) is int and 0<=index<len(paragraphs), 'Choose an original artwork paragraph'
        p=paragraphs[index];lines=source.records[p]['lines']
        assert len(lines)==1 and not any(chars(c).strip() for c in p.findall('./TEXT/CHAR')), 'Artwork requires a single object-only source paragraph'
        ps=source.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]');pm=ps.find('PARAMARGIN');line=lines[0]
        top=y+int(pm.get('Prev'))/2
        source.paragraph(p,x,top-line['vertical_position'],width)
        tables=source.root.findall('./BODY/SECTION//TABLE');direct=p.findall('./TEXT/TABLE')
        edits=block.get('tables',{})
        assert isinstance(edits,dict) and edits.keys()<={str(tables.index(t)) for t in direct}, 'Artwork table edits must name a direct source table'
        growth=0
        for key,cells in edits.items():
            table=tables[int(key)];shape=table.find('SHAPEOBJECT');position=shape.find('POSITION')
            assert position.get('TreatAsChar')=='false', 'Artwork table edits currently require an anchored table'
            ml,mr=int(pm.get('Left'))/2,int(pm.get('Right'))/2
            parent=(x+ml,top,width-ml-mr) if position.get('HorzRelTo')=='Para' else (x,top,width)
            fixed=source.position(table,parent);z=int(shape.get('ZOrder'))
            source.commands=[c for c in source.commands if c.get('z_order')!=z]
            saved=self.commands;self.commands=[]
            try:
                end=self.source_table(dict(table_template=int(key),cells=cells),*parent,source=source,fixed=fixed)
                source.commands.extend(c|dict(z_order=z) for c in self.commands)
            finally:self.commands=saved
            growth=max(growth,end-fixed[1]-fixed[3])
        source.order_objects();self.commands.extend(source.commands)
        return top+line['line_height']+line['line_spacing']+int(pm.get('Next'))/2+growth

    def page_geometry(self,document):
        page=self.header.page;margin=self.header.margin
        col=next(c for c in self.root.findall('.//COLDEF') if c.get('Count')=='2')
        if self.subject=='social' and document.get('page_no',1)>1:
            section=self.root.findall('./BODY/SECTION')[1]
            page=section.find('.//PAGEDEF');margin=page.find('PAGEMARGIN');col=section.find('./P/TEXT/COLDEF')
        elective=None
        if document.get('elective') is not None:
            assert self.subject in ('math','korean'), 'Elective layouts apply to mathematics and Korean'
            profiles=json.loads((ROOT/f'source-layout/{self.subject}-electives.json').read_text(encoding='utf-8'))
            assert document['elective'] in profiles, 'Choose an original elective for this subject'
            elective=profiles[document['elective']]
            assert document.get('page_no',1)>0 and (document.get('auto_flow') or document.get('page_no',1) in range(1,5)), 'Original elective sections contain four pages'
            assert document.get('page_no',1)!=4 or 'last_note' in elective, 'Original Korean final-note glyphs are not yet imported; page 4 cannot be rendered completely'
            page=elective['settings']['page'];margin=elective['settings']['margins'];col=elective['settings']['columns'][0]
        gap=int(col.get('SameGap'));left=int(margin.get('Left'))
        width=(int(page.get('Width'))-left-int(margin.get('Right'))-gap)/2
        top=dict(korean=22959,english=23075,math=19049,social=20125,science=20127)[self.subject]
        if document.get('page_no',1)>1:top=int(margin.get('Top'))+int(margin.get('Header'))
        positions=[22583,18177] if self.subject=='math' and document.get('page_no',1)==1 else [top,top]
        if elective is not None and document.get('page_no',1)==1:positions=list(elective['body_top'])
        if elective is not None and not document.get('auto_flow') and document.get('page_no',1)==4:positions=list(elective['last_body_top'])
        bottom=dict(korean=106682,english=106720,math=101881,social=102321,science=102321)[self.subject]
        limits=[bottom,bottom]
        if elective is not None and (document.get('last_page',False) if document.get('auto_flow') else document.get('page_no',1)==4):limits[1]=min(bottom,elective['note_top'])
        if self.subject=='korean' and elective is None and document.get('last_page',document.get('page_no',1)==12):
            note=next(t for t in self.root.find('./BODY/SECTION').findall('.//EXT_MASTERPAGE/PARALIST/P/TEXT/TABLE')
                if t.find('./SHAPEOBJECT/POSITION').get('VertAlign')=='Bottom')
            limits[1]=min(bottom,self.header.position(note,(0,0,int(page.get('Width'))))[1])
        if self.subject in ('english','social','science') and document.get('last_page',document.get('page_no',1)==(document.get('total',8) if self.subject=='english' else 4)):
            [note]=self.header.last_page_tables()
            limits[1]=min(bottom,self.header.position(note,(0,0,int(page.get('Width'))))[1])
        return dict(left=left,width=width,gap=gap,top=positions,bottom=limits)

    def compose(self,document,output_name=None,write=True):
        geometry=self.page_geometry(document)
        left,width,gap=(geometry[k] for k in ('left','width','gap'))
        positions=list(geometry['top']);limits=geometry['bottom']
        ink_bottom=[0,0]
        for block in document['blocks']:
            assert 'wrap_picture' not in block or block.get('kind') in (None,'paragraph'), 'wrap_picture belongs to a paragraph'
            assert 'wrap_table' not in block or block.get('kind') in (None,'paragraph'), 'wrap_table belongs to a paragraph'
            assert 'para_shape' not in block or block.get('kind') in (None,'paragraph','choices','passage'), 'para_shape applies to paragraphs, choices and passages'
            assert 'number_suffix' not in block or block.get('kind') in (None,'paragraph') and block.get('number') is not None, 'number_suffix requires a numbered paragraph'
            existing={id(item) for item in self.commands}
            column=block.get('column',0);assert column in (0,1)
            x=left+column*(width+gap);y=positions[column]
            inset_left=block.get('left_mm',0)*7200/25.4
            x+=inset_left
            if 'top_mm' in block:y=block['top_mm']*7200/25.4
            y+=block.get('gap_mm',0)*7200/25.4
            if block.get('kind')=='passage' and 'top_mm' not in block:
                # Flow cursors locate the paragraph; explicit top_mm locates the border.
                border=self.paragraph_shape(block.get('style','passage'),block.get('para_shape')).find('PARABORDER')
                assert border is not None, 'Choose an original style with connected paragraph borders'
                y-=int(border.get('OffsetTop','0'))
            assert y>=ink_bottom[column]-1, f'{self.subject}: explicit top_mm overlaps the preceding block in column {column+1}'
            if 'wrap_picture' in block:
                pm=self.paragraph_shape(block.get('style','question'),block.get('para_shape')).find('PARAMARGIN')
                region=self.wrapped_picture(block['wrap_picture'],x,y+int(pm.get('Prev'))/2,width-inset_left)
                assert region['bottom']<limits[column], 'Floating picture exceeds the original body area'
                existing.update(id(item) for item in self.commands)
            if 'wrap_table' in block:
                pm=self.paragraph_shape(block.get('style','question'),block.get('para_shape')).find('PARAMARGIN')
                region=self.wrapped_table(block['wrap_table'],x,y+int(pm.get('Prev'))/2,width-inset_left,para_shape=int(pm.getparent().get('Id')))
                assert region['bottom']<limits[column], 'Floating table exceeds the original body area'
                existing.update(id(item) for item in self.commands)
            if block.get('kind') in ('passage','box','example','table','data_table','picture','figure','artwork'):
                assert self.paragraph_width(x,y,width-inset_left)==width-inset_left, 'This block overlaps a floating picture; place it below the picture'
            if block.get('kind')=='choices':
                items=block['items'];assert len(items)==5
                count=block.get('columns',1);assert count in (1,2,3,5)
                defaults={
                    'korean':{2:'①-3행답안',3:'①-2행답안',5:'①-1행답안'},
                    'english':{2:'①-3행답안',3:'①-2행답안',5:'①-5행답안'},
                    'math':{2:'3행',3:'2행',5:'21 1행'},
                    'social':{2:'①-2',3:'2행답항',5:'①-⑤'},
                    'science':{2:'3행답항',3:'①－2행',5:'①－1행'},
                }
                role=block.get('style',defaults[self.subject].get(count,'choices'))
                ps=self.paragraph_shape(role,block.get('para_shape'));pm=ps.find('PARAMARGIN')
                offset=int(pm.get('Left'))/2
                stops=sorted({int(t.get('Pos'))/2 for t in self.root.findall(f'.//TABDEF[@Id="{ps.get("TabDef")}"]/TABITEM') if t.get('Type')=='Left' and int(t.get('Pos'))>0})
                assert count==1 or len(stops)==count-1, f'{self.subject}: choose an original style with {count-1} tab stops'
                anchors=[offset]+stops if count>1 else [offset]
                rows=[]
                for i,item in enumerate(items):
                    row=i//count
                    while len(rows)<=row:rows.append([])
                    separator='\x1e' if self.subject in ('korean','english') else ' '
                    runs=[chr(0x2460+i)+separator]+([item] if isinstance(item,str) else item)
                    rows[row].append((i%count,runs))
                for row in rows:
                    y=max(self.paragraph(runs,role,x+anchors[c]-offset,y,
                        (anchors[c+1] if c+1<count else width-inset_left)-anchors[c]+offset,align=None if count==1 else 'Left',para_shape=block.get('para_shape')) for c,runs in row)
            elif block.get('kind')=='passage':
                y=self.source_passage(block,x,y,width-inset_left)
            elif block.get('kind')=='box':
                subject=block.get('box_subject',self.subject)
                assert subject in STYLE_IDS, 'Choose an original box subject'
                owner=self if subject==self.subject else Composer(subject)
                y=getattr(owner,'source_'+block['kind'])(block,x,y,width-inset_left)
                if owner is not self:self.commands.extend(owner.commands)
            elif block.get('kind')=='example':
                y=self.source_example(block,x,y,width-inset_left)
            elif block.get('kind')=='table':
                y=self.source_table(block,x,y,width-inset_left)
            elif block.get('kind')=='picture':
                y=self.source_picture(block,x,y,width-inset_left)
            elif block.get('kind')=='figure':
                y=self.figure(block,x,y,width-inset_left)
            elif block.get('kind')=='data_table':
                y=self.data_table(block,x,y,width-inset_left)
            elif block.get('kind')=='artwork':
                y=self.source_artwork(block,x,y,width-inset_left)
            else:
                role=block.get('style','question')
                y=self.paragraph(block['runs'],role,x,y,width-inset_left,number=block.get('number'),align=block.get('align'),para_shape=block.get('para_shape'),number_suffix=block.get('number_suffix'),continued=block.get('continued',False),continues=block.get('continues',False))
            added=[item for item in self.commands if id(item) not in existing]
            # An open source frame includes trailing line spacing beyond the text boundary.
            content_end=max((command_bottom(item) for item in added if not item.get('continuation_frame')),default=ink_bottom[column])
            assert content_end<=limits[column]+1e-6, f'{self.subject}: column {column+1} exceeds the original divider or last-page note; add a page'
            if added:ink_bottom[column]=content_end
            positions[column]=y+block.get('after_mm',0)*7200/25.4
        if not write:return positions
        destination=ROOT/'generated';destination.mkdir(exist_ok=True)
        output_name=output_name or self.subject
        (destination/f'{output_name}-body.json').write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')
        settings=', '.join(f'{k.replace("_","-")}: {json.dumps(document[k],ensure_ascii=False)}' for k in ('year','title','elective','page_no','footer_no','total','last_page','auto_flow') if k in document and document[k] is not None)
        if 'subject_name' in document or 'area_title' in document:
            heading=Header(self.subject)
            if 'area_title' in document:heading.set_area_title(document['area_title'])
            else:heading.set_inquiry_name(document['subject_name'])
            page_no=document.get('page_no',1)
            commands=heading.extract(write=False) if page_no==1 else heading.continuation(write=False)['even' if page_no%2==0 else 'odd']
            (destination/f'{output_name}-header.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')
            settings+=(', ' if settings else '')+f'heading-commands: json("{output_name}-header.json")'
        settings=settings+', ' if settings else ''
        print(self.subject,len(self.commands),'editable text/equation commands',flush=True)
        return f'#exam-page("{self.subject}", [], [], {settings}overlay: source-commands(json("{output_name}-body.json")))\n'


def compose_document(document, name=None):
    name=name or document["subject"]
    assert document['subject'] in STYLE_IDS
    if document.get('flow'):
        from flow import compose_flow
        return compose_flow(document,name)
    pages=document.get('pages',[document])
    source='#import "../exam.typ": *\n#import "../original-header.typ": source-commands\n'
    for index,page in enumerate(pages):
        data={k:v for k,v in document.items() if k!='pages'}|dict(page_no=index+1)|page
        source+=Composer(document['subject']).compose(data,f'{name}-{index+1}')
    (ROOT/f'generated/{name}.typ').write_text(source,encoding='utf-8')
    return ROOT/f"generated/{name}.typ",len(pages)


def main():
    tokens=[dict(kind='text',advance=4,can_break=True),dict(kind='text',advance=4,can_break=True),dict(kind='text',advance=4,can_break=True)]
    assert [len(l) for l in Composer.wrap(tokens,8)]==[2,1]
    geometry={}
    for subject in STYLE_IDS:
        composer=Composer(subject)
        last=dict(korean=12,english=8,math=8,social=4,science=4)[subject]
        geometry[subject]={key:composer.page_geometry(document) for key,document in (
            ('first',dict(page_no=1)),('continuation',dict(page_no=2)),
            ('last',dict(page_no=last)),('first_last',dict(page_no=1,total=1)))}
        if subject in ('math','korean'):
            profiles=json.loads((ROOT/f'source-layout/{subject}-electives.json').read_text(encoding='utf-8'))
            geometry[subject]['electives']={name:[composer.page_geometry(dict(elective=name,page_no=n))
                for n in range(1,5)] for name in profiles}
    (ROOT/'source-layout/body-geometry.json').write_text(json.dumps(geometry,ensure_ascii=False,indent=2),encoding='utf-8')
    for document in authoring_documents().values():
        compose_document(document)


if __name__=='__main__':main()
