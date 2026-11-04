"""Export layout-only templates from the original, local extraction workspace."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import re
import sys


def without_text(record):
    result=deepcopy(record)
    units=result.get('text_utf16_units',[]);i=0
    while i<len(units):
        if units[i] in (1,2,3,9,11,12,14,15,16,17,18,21,22,23):i+=8
        else:units[i]=0;i+=1
    return result


def export(source,destination):
    sys.path.insert(0,str(source/'scripts'))
    from extract_headers import Header, chars
    from extract_body_fixture import Body
    from cover import Cover
    from lxml import etree as E
    for subject in ('korean','english','math','science','social','cover-korean','cover-math'):
        cover=subject.startswith('cover-')
        model=Cover(subject[6:]) if cover else Body(subject)
        root=model.root;paragraphs=list(root.iter('P'))
        keep=set(paragraphs) if cover else set()
        if not cover:
            for element in root.iter():
                if element.tag in ('HEADER','FOOTER','MASTERPAGE','EXT_MASTERPAGE'):
                    keep.update(element.iter('P'))
            first=root.find('./BODY/SECTION/P/TEXT/TABLE')
            keep.update(first.iter('P'))
            for element in root.findall('./BODY/SECTION/P/TEXT/RECTANGLE')[:2 if subject in ('korean','english') else 1]:
                keep.update(element.iter('P'))
            if subject in ('korean','science','social'):
                table=root.findall('./BODY/SECTION//TABLE')[dict(korean=6,science=12,social=11)[subject]]
                label=next(c for c in table.findall('ROW/CELL') if c.get('RowSpan')=='2')
                keep.update(label.iter('P'))
                if subject in ('science','social'):
                    for p in next(c for c in table.findall('ROW/CELL') if c.get('ColSpan')=='3').findall('PARALIST/P'):
                        # Keep label/body char-shape boundaries without retaining question content.
                        runs=p.findall('TEXT');literal=''.join(chars(c) for t in runs for c in t.findall('CHAR'))
                        prefix=re.match(r'^[ㄱ-ㅎ]\.\s*',literal)
                        assert prefix is not None
                        position=0
                        for t in runs:
                            for c in t.findall('CHAR'):
                                value=chars(c);c.clear()
                                c.text=''.join(ch if position+j<len(prefix[0]) else '가' for j,ch in enumerate(value))
                                position+=len(value)
                        keep.add(p)
            for p in paragraphs:
                if p not in keep:
                    for t in p.findall('TEXT'):
                        for c in t.findall('CHAR'):c.clear()
            for script in root.findall('.//SCRIPT'):script.text=''
        # Retain only images belonging to fixed headings, never question illustrations.
        image_ids={image.get('BinItem') for p in keep for image in p.findall('.//IMAGE')}
        for data in root.findall('.//BINDATA'):
            if data.get('Id') not in image_ids:data.getparent().remove(data)
        for summary in root.findall('.//DOCSUMMARY'):summary.getparent().remove(summary)
        for tag in ('SCRIPTCODE','SHAPECOMMENT'):
            for element in root.findall('.//'+tag):element.getparent().remove(element)
        target=destination/'templates'/f'{subject}.xml'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(E.tostring(root,encoding='utf-8',xml_declaration=True))
        original=json.loads((source/f'source-layout/{subject}.json').read_text(encoding='utf8'))
        transform=(lambda x:deepcopy(x)) if cover else without_text
        data={'line_segments':{section:[transform(r) for r in records] for section,records in original['line_segments'].items()},
              'paragraph_records':{str(i):transform(model.records[p]) for i,p in enumerate(paragraphs) if p in model.records}}
        (destination/'source-layout'/f'{subject}.json').write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')),encoding='utf8')
        print(subject,'layout exported',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('destination',type=Path)
    args=parser.parse_args()
    export(args.source.resolve(),args.destination.resolve())
