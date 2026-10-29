#!/usr/bin/env python3
"""Render a science-apparatus v1 JSON document as a deterministic SVG schematic."""
from __future__ import annotations
import argparse
import json
import math
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SVG = 'http://www.w3.org/2000/svg'
ET.register_namespace('', SVG)
FONT = "'Noto Sans CJK KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif"


def fail(message):
    raise ValueError(message)


def check_keys(obj, allowed, path):
    unknown = set(obj) - set(allowed)
    if unknown:
        fail(f"{path}: unknown fields: {', '.join(sorted(unknown))}")


def num(value, path):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        fail(f'{path}: expected a finite number')
    try:
        n = float(value)
    except (OverflowError, ValueError):
        fail(f'{path}: expected a finite number')
    if not math.isfinite(n) or abs(n) > 10000:
        fail(f'{path}: expected a finite number with magnitude at most 10000')
    return n


def string(value, path, allow_empty=True):
    if not isinstance(value, str):
        fail(f'{path}: expected text')
    if len(value) > 100 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
        fail(f'{path}: text contains invalid characters or exceeds 100 characters')
    if not allow_empty and not value.strip():
        fail(f'{path}: text must not be empty')
    return value


def q(x):
    return f'{x:.4f}'.rstrip('0').rstrip('.') or '0'


def el(parent, tag, **attrs):
    return ET.SubElement(parent, f'{{{SVG}}}{tag}', {k.replace('_', '-'): str(v) for k, v in attrs.items()})


def text(parent, s, x, y, **attrs):
    e = el(parent, 'text', x=q(x), y=q(y), **attrs)
    e.text = s
    return e


# Clip outlines are closed shapes; strokes are open where a vessel is open.
SHAPES = {
    'beaker': ('M 8 8 L 8 88 Q 8 96 17 96 L 83 96 Q 92 96 92 88 L 92 8 Z',
               'M 8 8 L 8 88 Q 8 96 17 96 L 83 96 Q 92 96 92 88 L 92 8 M 8 8 Q 50 0 92 8 Q 50 16 8 8 M 10 8 L 16 12 L 22 9'),
    'test_tube': ('M 22 5 L 22 72 Q 22 96 50 96 Q 78 96 78 72 L 78 5 Z',
                  'M 22 5 L 22 72 Q 22 96 50 96 Q 78 96 78 72 L 78 5 M 18 5 L 28 5 M 72 5 L 82 5'),
    'flask': ('M 37 5 L 37 38 L 8 82 Q 3 96 17 96 L 83 96 Q 97 96 92 82 L 63 38 L 63 5 Z',
              'M 37 5 L 37 38 L 8 82 Q 3 96 17 96 L 83 96 Q 97 96 92 82 L 63 38 L 63 5 M 32 5 L 42 5 M 58 5 L 68 5')
}


def render(doc):
    if not isinstance(doc, dict) or doc.get('version') != 1 or isinstance(doc.get('version'), bool):
        fail('version: expected 1')
    check_keys(doc, {'version', 'width_mm', 'height_mm', 'objects'}, 'document')
    w = num(doc.get('width_mm', 160), 'width_mm')
    h = num(doc.get('height_mm', 85), 'height_mm')
    if not (30 <= w <= 300 and 30 <= h <= 300):
        fail('width_mm and height_mm must be between 30 and 300')
    objects = doc.get('objects')
    if not isinstance(objects, list) or not 1 <= len(objects) <= 200:
        fail('objects: expected 1–200 objects')
    root = ET.Element(f'{{{SVG}}}svg', {'width':q(w)+'mm', 'height':q(h)+'mm', 'viewBox':f'0 0 {q(w)} {q(h)}', 'role':'img'})
    el(root, 'title').text = '과학 실험 장치 모식도'
    el(root, 'desc').text = '입력 원본에 따라 생성한 모식도이며, 눈금이나 양을 자동 계산하지 않습니다.'
    defs = el(root, 'defs')
    marker = el(defs, 'marker', id='arrowhead', viewBox='0 0 10 10', refX='9', refY='5', markerWidth='2.4', markerHeight='2.4', orient='auto', markerUnits='userSpaceOnUse')
    el(marker, 'path', d='M 0 0 L 10 5 L 0 10 z', fill='black')
    el(root, 'rect', x='0', y='0', width=q(w), height=q(h), fill='white')
    main = el(root, 'g', font_family=FONT, fill='black')
    counter = [0]
    count = [0]

    def point(x, y, bw, bh, p):
        if not 0 <= x <= bw or not 0 <= y <= bh:
            fail(f'{p}: coordinate outside parent bounds')

    def draw(parent, items, bw, bh, path, level=0):
        if not isinstance(items, list) or not 1 <= len(items) <= 200:
            fail(f'{path}: expected 1–200 objects')
        for i, obj in enumerate(items):
            p = f'{path}[{i}]'
            count[0] += 1
            if count[0] > 200:
                fail('document: at most 200 objects including panel contents')
            if not isinstance(obj, dict):
                fail(f'{p}: expected object')
            typ = obj.get('type')
            if typ in ('line','arrow'):
                check_keys(obj, {'type','x1','y1','x2','y2','stroke'}, p)
                a,b,c,d = (num(obj.get(k), p+'.'+k) for k in ('x1','y1','x2','y2'))
                point(a,b,bw,bh,p); point(c,d,bw,bh,p)
                if a == c and b == d:
                    fail(f'{p}: line endpoints must be distinct')
                style = obj.get('stroke', 'solid')
                if style not in ('solid', 'dashed'):
                    fail(f'{p}.stroke: expected solid or dashed')
                attrs = {'x1':q(a),'y1':q(b),'x2':q(c),'y2':q(d),'stroke':'black','stroke_width':'0.35','fill':'none'}
                if style == 'dashed': attrs['stroke_dasharray'] = '1.5 0.8'
                if typ == 'arrow': attrs['marker_end'] = 'url(#arrowhead)'
                el(parent,'line',**attrs)
            elif typ == 'text':
                check_keys(obj, {'type','x','y','text','size','anchor'}, p)
                x,y = num(obj.get('x'),p+'.x'),num(obj.get('y'),p+'.y')
                point(x,y,bw,bh,p)
                value = string(obj.get('text'),p+'.text',False)
                size = num(obj.get('size',2.8),p+'.size')
                if not 1.5 <= size <= 8: fail(f'{p}.size: expected 1.5–8 mm')
                anchor = obj.get('anchor','middle')
                if anchor not in ('start','middle','end'): fail(f'{p}.anchor: expected start, middle or end')
                text(parent,value,x,y,font_size=q(size),text_anchor=anchor)
            elif typ in ('beaker','test_tube','flask','syringe','thermometer','power_supply','panel'):
                allowed = {'type','x','y','width','height','label'}
                if typ in SHAPES: allowed.add('liquid')
                if typ == 'syringe': allowed.update({'plunger', 'orientation', 'cap'})
                if typ == 'panel': allowed.add('objects')
                check_keys(obj, allowed, p)
                x,y,ow,oh = (num(obj.get(k),p+'.'+k) for k in ('x','y','width','height'))
                if ow <= 0 or oh <= 0 or x < 0 or y < 0 or x+ow > bw or y+oh > bh:
                    fail(f'{p}: object rectangle must be positive and inside parent bounds')
                label = string(obj.get('label',''),p+'.label')
                if typ == 'panel':
                    if level >= 1: fail(f'{p}: nested panels are not supported')
                    if label and oh < 8: fail(f'{p}: panel height too small for label')
                    g=el(parent,'g',transform=f'translate({q(x)} {q(y)})')
                    el(g,'rect',x='0',y='0',width=q(ow),height=q(oh),fill='none',stroke='black',stroke_width='0.25')
                    draw(g,obj.get('objects'),ow,oh,p+'.objects',level+1)
                    if label: text(g,label,ow/2,oh-1.5,font_size='2.8',text_anchor='middle')
                    continue
                if label and y+oh+3.2 > bh:
                    fail(f'{p}.label: insufficient room below object')
                orientation = obj.get('orientation', 'horizontal') if typ == 'syringe' else 'horizontal'
                if orientation not in ('horizontal', 'vertical'):
                    fail(f'{p}.orientation: expected horizontal or vertical')
                cap = obj.get('cap', False) if typ == 'syringe' else False
                if not isinstance(cap, bool):
                    fail(f'{p}.cap: expected true or false')
                transform = (f'translate({q(x+ow)} {q(y)}) rotate(90)' if orientation == 'vertical'
                             else f'translate({q(x)} {q(y)})')
                g=el(parent,'g',transform=transform,aria_label=typ)
                # Write geometry in page units, so 0.35 mm strokes stay visible in
                # renderers that do not support SVG vector-effect.
                sx, sy = ((oh/100, ow/100) if orientation == 'vertical' else (ow/100, oh/100))
                line={'stroke':'black','stroke_width':'0.35','fill':'none'}
                def path_data(path):
                    tokens = re.findall(r'[A-Za-z]|-?\d+(?:\.\d+)?',path)
                    result=[]
                    axis=0
                    for token in tokens:
                        if token.isalpha():
                            result.append(token); axis=0
                        else:
                            result.append(q(float(token)*(sx if axis % 2 == 0 else sy)))
                            axis += 1
                    return ' '.join(result)
                def seg(parent,x1,y1,x2,y2):
                    return el(parent,'line',x1=q(x1*sx),y1=q(y1*sy),x2=q(x2*sx),y2=q(y2*sy),**line)
                def rect(parent,x,y,width,height,**attrs):
                    return el(parent,'rect',x=q(x*sx),y=q(y*sy),width=q(width*sx),height=q(height*sy),**attrs)
                def ellipse(parent,cx,cy,r,**attrs):
                    return el(parent,'ellipse',cx=q(cx*sx),cy=q(cy*sy),rx=q(r*sx),ry=q(r*sy),**attrs)
                if typ in SHAPES:
                    liquid = num(obj.get('liquid',0),p+'.liquid')
                    if not 0 <= liquid <= 1: fail(f'{p}.liquid: expected 0–1')
                    closed, outline = SHAPES[typ]
                    counter[0] += 1
                    clip_id = f'vessel-{counter[0]}'
                    clip=el(defs,'clipPath',id=clip_id,clipPathUnits='userSpaceOnUse')
                    el(clip,'path',d=path_data(closed))
                    if liquid > 0:
                        top=96 - (88 if typ == 'beaker' else 91)*liquid
                        lg=el(g,'g',clip_path=f'url(#{clip_id})')
                        rect(lg,0,top,100,100-top,fill='#dedede')
                        if typ == 'beaker':
                            el(lg, 'ellipse', cx=q(50*sx), cy=q(top*sy), rx=q(42*sx), ry=q(3*sy),
                               fill='#d4d4d4', stroke='black', stroke_width='0.2')
                        else:
                            seg(lg,0,top,100,top)
                    el(g,'path',d=path_data(outline),**line)
                    if typ == 'beaker':
                        el(g,'path',d=path_data('M 9 88 Q 50 98 91 88'),
                           stroke='black',stroke_width='0.16',fill='none')
                elif typ == 'syringe':
                    plunger=num(obj.get('plunger',0.5),p+'.plunger')
                    if not 0 <= plunger <= 1: fail(f'{p}.plunger: expected 0–1')
                    # Side-on schematic; plunger is normalized along the barrel.
                    el(g,'path',d=path_data('M 20 27 L 76 27 L 76 73 L 20 73 M 76 42 L 86 42 L 86 58 L 76 58 M 86 50 L 97 50'),**line)
                    # The piston, rigid rod, and thumb plate translate together.
                    # The travel keeps the thumb plate outside the barrel flange
                    # and the complete assembly inside its declared rectangle.
                    piston=25+17*plunger
                    handle=piston-23
                    rect(g,piston-1.5,28,3,44,fill='#888',stroke='black',stroke_width='0.2')
                    seg(g,handle,50,piston-1.5,50)
                    seg(g,handle,35,handle,65)
                    seg(g,20,18,20,82)
                    if cap:
                        rect(g,93,40,7,20,rx=q(1*sx),fill='#555',stroke='black',stroke_width='0.2')
                elif typ == 'thermometer':
                    el(g,'path',d=path_data('M 42 74 L 42 15 Q 42 5 50 5 Q 58 5 58 15 L 58 74 Q 72 80 67 91 Q 62 99 50 98 Q 38 99 33 91 Q 28 80 42 74 Z'),**dict(line, fill='white'))
                    seg(g,50,25,50,85)
                    ellipse(g,50,86,5,fill='#777',stroke='none')
                else:
                    rect(g,4,10,92,80,rx=q(4*sx),**line)
                    rect(g,5,11,90,6,fill='#d0d0d0',stroke='none')
                    rect(g,14,22,40,22,fill='white',stroke='black',stroke_width='0.25')
                    ellipse(g,68,33,7,fill='#dedede',stroke='black',stroke_width='0.25')
                    ellipse(g,84,33,5,fill='#dedede',stroke='black',stroke_width='0.25')
                    ellipse(g,25,72,5,**line)
                    ellipse(g,75,72,5,**line)
                if label: text(parent,label,x+ow/2,y+oh+2.8,font_size='2.8',text_anchor='middle')
            else:
                fail(f'{p}.type: unsupported object type')
    draw(main,objects,w,h,'objects')
    return ET.tostring(root,encoding='unicode',xml_declaration=True)+'\n'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',type=Path)
    parser.add_argument('output',type=Path)
    args=parser.parse_args()
    try:
        if args.input.resolve()==args.output.resolve(): fail('input and output must be different files')
        data=json.loads(args.input.read_text(encoding='utf-8'))
        svg=render(data)
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(svg,encoding='utf-8')
    except (ValueError,OSError) as e:
        print(f'Error: {e}',file=sys.stderr)
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())