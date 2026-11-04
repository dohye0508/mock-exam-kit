"""Same-content HWP body fixtures: source text, line records, tables and embedded pictures."""
from io import BytesIO
from copy import deepcopy
from pathlib import Path
import json
import struct
import sys
from PIL import Image
from extract_headers import Header,ROOT,picture_command,picture_data,chars,underline_commands,justification_gaps,condense_line,character_border_padding

CONTROL_TAGS={'secd':'SECDEF','cold':'COLDEF','head':'HEADER','foot':'FOOTER',
              'tbl ':'TABLE','gso ':'SHAPE','eqed':'EQUATION','pghd':'PAGEHIDING',
              'nwno':'NEWNUM','atno':'AUTONUM','pgct':'PAGEBORDERFILL'}


def record_text(record):
    units=record.get('text_utf16_units',[]);result=[];pos=0
    while pos<len(units):
        value=units[pos]
        if value in (1,2,3,9,11,12,14,15,16,17,18,21,22,23):
            if value==9:result.append('\t')
            pos+=8;continue
        if value not in (0,13):result.append(chr(value))
        pos+=1
    return ''.join(result).encode('utf-16-le','surrogatepass').decode('utf-16-le')


class Body(Header):
    def __init__(self,subject):
        super().__init__(subject)
        data=json.loads((ROOT/f'source-layout/{subject}.json').read_text(encoding='utf-8'))
        paragraphs=list(self.root.iter('P'))
        self.records={paragraphs[int(i)]:record for i,record in data['paragraph_records'].items()}
        self.skip=set()
        for section in self.root.findall('./BODY/SECTION'):
            self.skip.add(section.find('./P[1]/TEXT/TABLE'))
            for tag in ('RECTANGLE','POLYGON','LINE'):
                self.skip.update(section.findall(f'./P[1]/TEXT/{tag}'))
        self.images={}
        self.numbers={}
        self.fragments={}
        self.fragment_of={}
        self.paragraph_count=0
        self.equations=json.loads((ROOT/'equations.json').read_text(encoding='utf-8'))
        self.equation_cache=json.loads((ROOT/'assets/equations/manifest.json').read_text(encoding='utf-8'))
        self.skip.update(self.last_page_tables())
        if subject=='math':
            for section in self.root.findall('./BODY/SECTION'):
                for p in section.findall('P'):
                    objects=[e for t in p.findall('TEXT') for e in t if e.tag in ('TABLE','RECTANGLE','LINE')]
                    if any(e.tag=='TABLE' and e.find('./SHAPEOBJECT/SIZE').get('Height')=='10629' for e in objects):self.skip.update(objects)
                    if section.get('Id')=='1':
                        self.skip.update(e for e in objects if e.tag=='RECTANGLE' and e.find('./SHAPEOBJECT/SIZE').get('Height')=='4252')
                        self.skip.update(e for e in objects if e.tag=='TABLE' and (e.find('./SHAPEOBJECT/SIZE').get('Width')=='7892' or e.find('./SHAPEOBJECT/POSITION').get('VertAlign')=='Bottom'))

    def equation(self,element,x,y,w,h):
        script=element.findtext('SCRIPT')
        key=next((k for k,v in self.equations.items() if v==script and k in self.equation_cache
            and self.equation_cache[k]['base_unit']*100==int(element.get('BaseUnit'))),None)
        assert key is not None and key in self.equation_cache, 'Import and render the original equation first'
        cached=self.equation_cache[key]
        assert cached['script']==script and cached['base_unit']*100==int(element.get('BaseUnit')), 'Equation cache differs from the original script or size'
        assert element.get('TextColor')=='0' and element.get('LineMode')=='false', 'Unsupported original equation style'
        assert (ROOT/f'assets/equations/{key}.svg').is_file()
        self.commands.append(dict(kind='equation',key=key,x=x,y=y,width=w,height=h))

    def picture(self,element,x,y,w,h):
        item=element.find('IMAGE').get('BinItem')
        if item not in self.images:
            data=picture_data(self.root,element)
            dest=ROOT/f'assets/original/{self.subject}-body-{item}.png'
            dest.parent.mkdir(parents=True,exist_ok=True)
            with Image.open(BytesIO(data)) as image:
                image.save(dest)
                with Image.open(dest) as saved:assert image.convert('RGBA').tobytes()==saved.convert('RGBA').tobytes()
            self.images[item]=str(dest.relative_to(ROOT)).replace('\\','/')
        self.commands.append(picture_command(element,x,y,w,h,self.images[item]))

    def table(self,table,parent,fixed=None,nested_cells=None):
        from compose import Composer
        rectangle=fixed if fixed is not None else self.position(table,parent)
        composer=Composer(self.subject)
        tables=self.root.findall('./BODY/SECTION//TABLE');index=tables.index(table)
        nested_cells=nested_cells or {}
        descendants={str(tables.index(t)) for t in table.findall('.//TABLE')}
        end=composer.source_table(dict(table_template=index,cells=nested_cells.get(str(index),{}),
            nested_cells={k:v for k,v in nested_cells.items() if k in descendants}),
            *parent,source=self,fixed=rectangle)
        self.commands.extend(composer.commands)
        return end

    def paragraph(self,p,x,y,w,nested_cells=None):
        record=self.records[p];units=record.get('text_utf16_units',[])
        assert int(p.get('ParaShape'))==struct.unpack_from('<H',bytes.fromhex(record['header_hex']),8)[0], 'Paragraph record association differs'
        ps=self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
        margin=ps.find('PARAMARGIN');indent=int(margin.get('Indent'))/2
        objects=iter(child for run in p.findall('TEXT') for child in run if child.tag!='CHAR')
        source_lines=record.get('source_lines',record['lines'])
        lines=[[] for _ in source_lines];li=0;pos=0
        while pos<len(units):
            if li+1<len(lines) and pos>=source_lines[li+1]['text_position']:li+=1
            unit=units[pos]
            if unit==9:
                lines[li].append(dict(kind='space',advance=units[pos+1]+(units[pos+2]<<16)));pos+=8;continue
            if unit in (1,2,3,11,12,14,15,16,17,18,21,22,23):
                cid=struct.pack('<HH',*units[pos+1:pos+3])[::-1].decode('ascii')
                element=next(objects)
                expected=CONTROL_TAGS[cid]
                assert element.tag==expected or expected=='SHAPE' and element.tag in ('PICTURE','RECTANGLE','LINE','POLYGON','ELLIPSE','CONTAINER'),(cid,element.tag)
                if element not in self.skip and element.tag in ('TABLE','PICTURE','RECTANGLE','EQUATION'):
                    shape=element.find('SHAPEOBJECT');size,outer,position=shape.find('SIZE'),shape.find('OUTSIDEMARGIN'),shape.find('POSITION')
                    iw,ih=int(size.get('Width')),int(size.get('Height'))
                    advance=iw+int(outer.get('Left'))+int(outer.get('Right')) if position.get('TreatAsChar')=='true' else 0
                    lines[li].append(dict(kind='object',element=element,advance=advance,width=iw,height=ih))
                pos+=8;continue
            if unit in (0,10,13):pos+=1;continue
            consumed=1
            if 0xd800<=unit<=0xdbff:
                assert pos+1<len(units) and 0xdc00<=units[pos+1]<=0xdfff, 'Invalid source UTF-16 surrogate pair'
                char=chr(0x10000+((unit-0xd800)<<10)+units[pos+1]-0xdc00);consumed=2
            else:char=chr(unit)
            shape_id=next(s['shape_id'] for s in reversed(record['character_shapes']) if s['position']<=pos)
            cs=self.root.find(f'.//CHARSHAPE[@Id="{shape_id}"]')
            glyph=self.glyph(char,cs)
            if lines[li]:
                previous=lines[li][-1];kern=self.kerning(previous,glyph)
                if kern:
                    previous['advance']+=kern
                    previous['trailing_spacing']+=kern
            lines[li].append(glyph);pos+=consumed
        assert next(objects,None) is None,'Unmatched HWP object'
        auto_indent=0
        if ps.get('HeadingType')=='Number':
            definition=self.root.find(f'.//NUMBERING[@Id="{ps.get("Heading")}"]')
            level=int(ps.get('Level'))+1
            head=definition.find(f'PARAHEAD[@Level="{level}"]')
            assert level==1 and head.get('NumFormat') in ('Digit','HangulJamo') and head.get('Alignment')=='Left'
            assert head.get('UseInstWidth')=='true', 'Unsupported fixed-width paragraph numbering'
            key=(ps.get('Heading'),level)
            number=self.numbers.get(key,int(definition.get('Start')))
            self.numbers[key]=number+1
            cs=self.root.find(f'.//CHARSHAPE[@Id="{head.get("CharShape",p.find("TEXT").get("CharShape"))}"]')
            label=str(number) if head.get('NumFormat')=='Digit' else 'ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎ'[number-1]
            prefix=[self.glyph(char,cs)|dict(heading=True) for char in head.text.replace('^1',label)]
            prefix[-1]['advance']-=prefix[-1]['trailing_spacing']
            prefix[-1]['trailing_spacing']=0
            offset=int(head.get('TextOffset'))
            if offset:
                assert head.get('TextOffsetType')=='percent', 'Absolute numbering text offset needs native verification'
                offset=int(cs.get('Height'))*offset/100
            gap=int(head.get('WidthAdjust'))+offset
            if head.get('AutoIndent')=='true':auto_indent=sum(t['advance'] for t in prefix)+gap
            lines[0]=prefix+[dict(kind='space',advance=gap)]+lines[0]
        growth=0
        edited_tables={self.root.findall('./BODY/SECTION//TABLE')[int(k)] for k in (nested_cells or {})}
        for li,tokens in enumerate(lines):
            if not record.get('line_offset',0)<=li<record.get('line_offset',0)+len(record['lines']):continue
            while tokens and tokens[-1].get('char')==' ' and not tokens[-1].get('char_border'):tokens.pop()
            above=below=0
            for token in tokens:
                if token['kind']!='object' or token['element'].tag!='TABLE':continue
                table=token['element']
                if not edited_tables.intersection(table.iter('TABLE')):continue
                start=len(self.commands)
                end=self.table(table,(0,0,w),fixed=(0,0,token['width'],token['height']),nested_cells=nested_cells)
                token['commands']=self.commands[start:];del self.commands[start:]
                delta=max(0,end-token['height']);token['height']+=delta
                inline=table.find('SHAPEOBJECT/POSITION').get('TreatAsChar')=='true'
                assert inline or delta==0, 'Growing a floating nested table needs text-wrap reflow'
                fraction=.5 if ps.get('VerAlign')=='Center' else .85
                above=max(above,delta*fraction);below=max(below,delta*(1-fraction))
            line=source_lines[li];baseline=y+growth+above+line['vertical_position']+line['baseline_distance']
            inset=max(0,indent) if li==0 else max(0,-indent)+auto_indent
            available=line['segment_width']-inset
            compressed=condense_line(tokens,available,int(ps.get('Condense','0')))
            if compressed is not None:tokens=compressed
            padding=character_border_padding(tokens)
            occupied=sum(t['advance'] for t in tokens)+sum(sum(p) for p in padding)-(tokens[-1].get('trailing_spacing',0) if tokens else 0)
            cursor=x+line['column_start']+inset
            if ps.get('Align')=='Center':cursor+=max(0,available-occupied)/2
            elif ps.get('Align')=='Right':cursor+=available-occupied
            gaps=justification_gaps(tokens)
            extra=(available-occupied)/len(gaps) if ps.get('Align')=='Justify' and li<len(lines)-1 and gaps else 0
            if ps.get('Align') in ('Distribute','DistributeSpace'):
                gaps=[i for i,t in enumerate(tokens[:-1]) if ps.get('Align')=='Distribute' or t.get('char')==' ']
                extra=(available-occupied)/len(gaps) if gaps else 0
            underlines=[];borders=[]
            for ti,token in enumerate(tokens):
                cursor+=padding[ti][0]
                if token.get('underline'):underlines.append((token,cursor,token['advance']+(extra if ti in gaps else 0)))
                if token['kind']=='text':
                    dy=token['center_shift'] if ps.get('VerAlign')=='Center' else 0
                    borders.append((token,cursor,baseline+token['offset']+dy,token['advance']+(extra if ti in gaps else 0)))
                    if token['char'] not in ' \x1e\x1f':
                        self.commands.append({k:v for k,v in token.items() if k not in ('offset','draw_dx')} |
                            dict(x=cursor,y=baseline+token['offset']+dy))
                elif token['kind']=='object':
                    command_start=len(self.commands)
                    element=token['element'];shape=element.find('SHAPEOBJECT');outer=shape.find('OUTSIDEMARGIN');position=shape.find('POSITION')
                    if position.get('TreatAsChar')=='true':
                        ml,mt,mb=[int(outer.get(k)) for k in ('Left','Top','Bottom')]
                        fraction=.5 if ps.get('VerAlign')=='Center' else .85
                        ox=cursor+ml;oy=baseline-(token['height']+mt+mb)*fraction+mt
                        fixed=(ox,oy,token['width'],token['height'])
                        # Centered lines align the equation box, not its internal math baseline.
                        if element.tag=='EQUATION' and ps.get('VerAlign')!='Center':
                            fixed=(ox,baseline-round(token['height']*int(element.get('BaseLine'))/100),token['width'],token['height'])
                    else:
                        # Wrapped line segments exclude the floating object; anchors use the full paragraph area.
                        left,right=int(margin.get('Left'))/2,int(margin.get('Right'))/2
                        parent_x,parent_width=(x+left,w-left-right) if position.get('HorzRelTo')=='Para' else (x,w)
                        fixed=self.position(element,(parent_x,y+growth+line['vertical_position'],parent_width))
                    if element.tag=='PICTURE':self.picture(element,*fixed)
                    elif element.tag=='TABLE':
                        if 'commands' in token:
                            self.commands.extend(c|dict(x=c['x']+fixed[0],y=c['y']+fixed[1]) for c in token['commands'])
                        else:self.table(element,(x,y,w),fixed=fixed)
                    elif element.tag=='RECTANGLE':self.rectangle(element,(x,y,w),fixed=fixed)
                    else:self.equation(element,*fixed)
                    for command in self.commands[command_start:]:command['z_order']=int(shape.get('ZOrder'))
                cursor+=token['advance']+(extra if ti in gaps else 0)+padding[ti][1]
            self.commands.extend(underline_commands(underlines,y+growth+above+below+line['vertical_position']+line['line_height']))
            self.commands.extend(self.character_borders(borders))
            growth+=above+below
        self.paragraph_count+=1
        return growth

    def paragraph_borders(self, placements):
        rendered_styles={}
        def signature(border):
            border_id=border.get('BorderFill')
            if border_id not in rendered_styles:
                saved=self.commands;self.commands=[]
                try:
                    self.border(border_id,0,0,1,1)
                    rendered_styles[border_id]=json.dumps(self.commands,sort_keys=True)
                finally:self.commands=saved
            # Distinct HWP IDs can have identical visible borders (e.g. transparent footnote fills).
            return (tuple(sorted((k,v) for k,v in border.attrib.items() if k not in ('BorderFill','OffsetTop','OffsetBottom'))),rendered_styles[border_id])
        column_widths={}
        for p,x,y,w in placements:
            ps=self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
            ends=[line['column_start']+line['segment_width']+int(ps.find('PARAMARGIN').get('Right'))/2 for line in self.records[p]['lines']]
            if ends:column_widths[x,y,w]=max(column_widths.get((x,y,w),0),max(ends))
        def style(p):
            if p is None or p.tag!='P':return None
            ps=self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]');border=ps.find('PARABORDER')
            if border is None or border.get('Connect')!='true':return None
            margins=ps.find('PARAMARGIN')
            return (signature(border),
                tuple(margins.get(k) for k in ('Left','Right')) if border.get('IgnoreMargin')=='true' else ())
        def neighbor(p,direction):
            original=self.fragment_of.get(p,p);parts=self.fragments.get(original,[original]);index=parts.index(p)+direction
            if 0<=index<len(parts):return parts[index]
            return original.getprevious() if direction<0 else original.getnext()
        groups=[]
        for p,x,y,w in placements:
            ps=self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
            border=ps.find('PARABORDER')
            lines=self.records[p]['lines']
            if border is None or not lines:
                groups.append(None);continue
            fill=self.root.find(f'.//BORDERFILL[@Id="{border.get("BorderFill")}"]')
            if not any(e.get('Type')!='None' for e in fill if e.tag in ('LEFTBORDER','RIGHTBORDER','TOPBORDER','BOTTOMBORDER')):
                groups.append(None);continue
            first,last=lines[0],lines[-1]
            # Floating labels narrow text runs, not the enclosing connected frame.
            w=column_widths[x,y,w]
            if border.get('IgnoreMargin')=='true':
                margins=ps.find('PARAMARGIN')
                x+=int(margins.get('Left'))/2
                w-=(int(margins.get('Left'))+int(margins.get('Right')))/2
            top=y+first['vertical_position']-int(border.get('OffsetTop','0'))
            bottom=y+last['vertical_position']+last['line_height']+int(border.get('OffsetBottom','0'))
            if border.get('IgnoreMargin')!='true':
                bottom+=last['line_spacing']+int(ps.find('PARAMARGIN').get('Next'))/2
            # A connected frame takes its top from the first paragraph and bottom from the last.
            key=(signature(border),x,y,w)
            previous=groups[-1] if groups else None
            if border.get('Connect')=='true' and previous and previous['key']==key:
                previous['bottom']=bottom
                previous['last']=p
            else:
                groups.append(dict(key=key,border=border,x=x,w=w,top=top,bottom=bottom,first=p,last=p))
        for group in filter(None,groups):
            border=group['border'];left=int(border.get('OffsetLeft','0'));right=int(border.get('OffsetRight','0'))
            open_top=style(group['first']) is not None and style(group['first'])==style(neighbor(group['first'],-1))
            open_bottom=style(group['last']) is not None and style(group['last'])==style(neighbor(group['last'],1))
            start=len(self.commands)
            self.border(border.get('BorderFill'),group['x']-left,group['top'],
                group['w']+left+right,group['bottom']-group['top'])
            self.commands[start:]=[c for c in self.commands[start:] if not (c['kind']=='line' and c['height']==0 and
                (open_top and c['y']==group['top'] or open_bottom and c['y']==group['bottom']))]

    def paragraph_parts(self,p):
        if p in self.fragments:return self.fragments[p]
        record=self.records[p];lines=record['lines']
        cuts=[0]+[i for i in range(1,len(lines)) if lines[i]['vertical_position']<lines[i-1]['vertical_position']]+[len(lines)]
        if len(cuts)==2:return [p]
        ps=self.root.find(f'.//PARASHAPE[@Id="{p.get("ParaShape")}"]')
        assert ps.get('HeadingType')!='Number', 'Numbered paragraphs crossing columns need continuation numbering'
        parts=[]
        for start,end in zip(cuts,cuts[1:]):
            part=deepcopy(p)
            for original,copy in zip(p.iter(),part.iter()):
                if original in self.records:self.records[copy]=self.records[original]
                if original in self.skip:self.skip.add(copy)
            self.records[part]=record|dict(lines=lines[start:end],source_lines=lines,line_offset=start)
            self.fragment_of[part]=p;parts.append(part)
        self.fragments[p]=parts
        return parts

    def page_placements(self,max_pages=None,section=None):
        if section is None:section=self.root.find('./BODY/SECTION')
        page=section.find('.//PAGEDEF');margin=page.find('PAGEMARGIN')
        col=next(c for c in section.findall('./P/TEXT/COLDEF') if c.get('Count')=='2')
        left=int(margin.get('Left'));gap=int(col.get('SameGap'))
        width=(int(page.get('Width'))-left-int(margin.get('Right'))-gap)/2
        top=int(margin.get('Top'))+int(margin.get('Header'))
        column=0;previous=-1;placements=[]
        for p in section.findall('P'):
            for index,part in enumerate(self.paragraph_parts(p)):
                lines=self.records[part]['lines']
                if not lines:continue
                current=lines[0]['vertical_position']
                if index==0 and placements and p.get('PageBreak')=='true':column=(column//2+1)*2
                elif current<previous or index==0 and p.get('ColumnBreak')=='true':column+=1
                if max_pages is not None and column//2>=max_pages:return placements
                if column//2>=len(placements):placements.append([])
                placements[column//2].append((part,left+(column%2)*(width+gap),top,width))
                previous=lines[-1]['vertical_position']
        return placements

    def first_page_placements(self):
        return self.page_placements(max_pages=1)[0]

    def order_objects(self):
        self.commands.sort(key=lambda command:command.get('z_order',-1))
        for command in self.commands:command.pop('z_order',None)

    def last_page_note(self,tables=None):
        for table in self.last_page_tables() if tables is None else tables:
            for p in table.findall('.//P'):
                if p in self.records:continue
                plain=''.join(chars(c) for c in p.findall('./TEXT/CHAR'))
                matches=[r for r in self.raw if int(p.get('ParaShape'))==struct.unpack_from('<H',bytes.fromhex(r['header_hex']),8)[0] and record_text(r)==plain]
                assert len(matches)==1, 'Last-page note paragraph must have one source record'
                self.records[p]=matches[0]
            self.table(table,(0,0,self.width))

    def footer_override(self,page_no):
        labels=[]
        for table in self.root.findall(f'.//EXT_MASTERPAGE[@Type="OptionalPage"][@PageNumber="{page_no}"]/PARALIST/P/TEXT/TABLE'):
            pos=table.find('./SHAPEOBJECT/POSITION')
            if pos.get('VertRelTo')=='Paper' and pos.get('VertAlign')=='Bottom':
                label=''.join(chars(c) for c in table.find('.//P').findall('./TEXT/CHAR'))
                assert label.isdigit(), 'Source footer must be a numeric page label'
                labels.append(int(label))
        assert len(labels)<=1, 'Multiple original footer overrides'
        return labels[0] if labels else None

    def extract_document(self):
        sections=self.root.findall('./BODY/SECTION')
        assert len(sections)==1 or self.subject in ('social','math'), 'Elective section headers need their own page profiles'
        self.commands=[];self.last_page_note();self.order_objects()
        (ROOT/f'source-layout/{self.subject}-last-note.json').write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')
        pages=[(section,placements) for section in sections for placements in self.page_placements(section=section)]
        source=['#import "../exam.typ": exam-page\n#import "../original-header.typ": source-commands\n']
        counts=[]
        for page_no,(section,placements) in enumerate(pages,1):
            self.page=section.find('.//PAGEDEF');self.margin=self.page.find('PAGEMARGIN');self.width=int(self.page.get('Width'))
            self.commands=[]
            self.paragraph_borders(placements)
            for p,x,y,w in placements:self.paragraph(p,x,y,w)
            self.order_objects()
            name=f'{self.subject}-original-page{page_no}'
            (ROOT/f'generated/{name}.json').write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')
            footer=''
            display_page=page_no
            if self.subject=='math' and section.get('Id')=='1':
                profiles=json.loads((ROOT/'source-layout/math-electives.json').read_text(encoding='utf-8'))
                name_profile=next((key,value) for key,value in profiles.items() if value['page_offset']<page_no<=value['page_offset']+4)
                display_page=page_no-name_profile[1]['page_offset']
                footer=f'elective: {json.dumps(name_profile[0],ensure_ascii=False)}, '
            override=self.footer_override(page_no)
            if override is not None:footer=f'footer-no: {override}, '
            source.append(f'#exam-page("{self.subject}", [], [], page-no: {display_page}, {footer}overlay: source-commands(json("../generated/{name}.json")))\n')
            counts.append(dict(page=page_no,paragraphs=len(placements),commands=len(self.commands)))
        (ROOT/f'fixtures/{self.subject}-original-all.typ').write_text(''.join(source),encoding='utf-8')
        return counts

    def extract_first_page(self):
        placements=self.first_page_placements()
        self.paragraph_borders(placements)
        for p,x,y,w in placements:self.paragraph(p,x,y,w)
        self.order_objects()
        (ROOT/f'source-layout/{self.subject}-body-fixture.json').write_text(json.dumps(self.commands,ensure_ascii=False,indent=2),encoding='utf-8')
        (ROOT/f'fixtures/{self.subject}-original.typ').write_text(
            '#import "../exam.typ": exam-page\n#import "../original-header.typ": source-commands\n'
            f'#exam-page("{self.subject}", [], [], overlay: source-commands(json("../source-layout/{self.subject}-body-fixture.json")))\n',encoding='utf-8')
        print(self.subject,self.paragraph_count,'paragraphs;',len(self.commands),'commands;',len(self.images),'source pictures')


if __name__=='__main__':
    for subject in sys.argv[1:] or ['korean','english']:
        Body(subject).extract_first_page()
