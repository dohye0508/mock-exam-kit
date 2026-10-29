---
name: science-apparatus
description: 통합과학 실험 도구를 SVG로 스케치하고 이미지 생성과 마커 인식으로 흑백 그림과 편집 가능한 글자 레이어를 만든다. 실험 장치 그림, 시험 문항용 실험 기구 모식도, 눈금과 한글 라벨이 있는 과학 삽화를 만들거나 수정할 때 사용한다.
---

# 통합과학 실험 도구

실험 장치의 **SVG 스케치 → 이미지 생성 → 마커 인식·제거와 글자 합성 → 검토·반복** 순서로 작업한다. SVG 스케치를 최종 그림으로 전달하지 않는다. 이 파일 하나에 제작 절차와 실행 코드를 모두 담았다. 이미지 생성·편집 도구, Python 3, Node.js와 Node용 `sharp`가 필요하다. 이미지 생성 도구가 없으면 완성했다고 주장하지 말고 스케치 및 미완성 사유를 전달한다.

## 1. 조건 확인과 스케치

정답이나 해석에 영향을 주는 장치 상태가 모호하면 추측하지 말고 사용자에게 확인한다. 기구 개수·상대 위치·액면·침지 깊이·마개·피스톤·전기 연결, 필요한 문구와 숫자·단위를 정리한다. 가상 수치는 실제 측정값과 구분한다. 액면 높이의 비율은 부피 비율이 아니며, 그림의 치수·눈금·주사기 부피나 압력은 자동 보정·계산되지 않는다. 정답과 해설 등 인쇄하지 않을 내용은 이미지 원본 JSON에 넣지 않는다.

기구 배열을 SVG로 스케치한다. 아래 렌더러와 JSON 형식을 사용하거나 직접 SVG를 작성할 수 있다. 배치 스케치는 최종 결과가 아니다. 숫자·단위·한글을 포함한 **모든 최종 글자**는 글자 위치마다 넣는 선명한 마젠타(`#ff00ff`) 사각 마커로 표시하고 그 외 글자는 비운다. 마커에 숫자나 문자를 쓰지 않는다. 가까운 눈금 숫자에는 약 8px 크기의 마커를 쓰고 검색 영역이 서로 겹치지 않게 한다. 렌더러는 마커를 자동으로 넣지 않으므로 스케치 SVG에 직접 추가한다.

### 스케치 JSON 형식

좌표와 치수는 mm, `objects`는 그리기 순서다. 패널 내부까지 최대 200개다. 기본 캔버스 크기는 160 × 85mm, 각 변의 허용 범위는 30–300mm다.

```json
{
  "version": 1,
  "width_mm": 100,
  "height_mm": 70,
  "objects": [
    {"type": "beaker", "x": 20, "y": 10, "width": 25, "height": 35, "liquid": 0.5},
    {"type": "beaker", "x": 55, "y": 10, "width": 25, "height": 35, "liquid": 0.7}
  ]
}
```

지원하는 기구의 공통 필드는 `type`, 왼쪽 위 `x`, `y`, `width`, `height`, 선택적 `label`이다. 텍스트 없는 스케치를 만들려면 `label`을 생략한다.

| type | 상태 |
|---|---|
| `beaker`, `test_tube`, `flask` | `liquid`: 0–1의 그림 높이 비율, 기본 0 |
| `syringe` | `plunger`: 0–1, 기본 0.5; 값이 커지면 피스톤이 끝쪽으로 이동. `orientation`: `horizontal`(기본, 노즐 오른쪽) 또는 `vertical`(노즐 아래). `cap`: boolean, 기본 false |
| `thermometer` | 수치 없는 개략 온도계 |
| `power_supply` | 전원 장치 개략도, 극성 자동 지정 없음 |

선은 `{"type":"line","x1":10,"y1":20,"x2":30,"y2":20}`이고 `stroke`는 `solid` 또는 `dashed`다. `arrow`는 끝점에 화살촉이 붙는다. 두 끝점은 서로 달라야 한다. 전원 장치의 단자 중심은 `(x + 0.25 × width, y + 0.72 × height)`와 `(x + 0.75 × width, y + 0.72 × height)`다. 도구와 연결선은 자동 결합되지 않으므로 위치를 바꾸면 선도 확인한다. 텍스트 객체와 패널 라벨은 렌더러가 지원하지만 최종 글자는 반드시 이미지 생성물의 마커로 배치한다. 패널은 `{"type":"panel","x":5,"y":5,"width":40,"height":50,"objects":[...]}` 형식이며 내부 좌표는 패널 기준, 패널 중첩은 지원하지 않는다. 개략적인 앞모습만 지원하며 임의 회전, 복잡한 부품 및 물리량 계산은 지원하지 않는다. 겹침·잘림·침지·연결 상태를 직접 확인한다.

## 2. 마커 명세와 이미지 생성

마커마다 고유 ID와 최종 문구를 아래와 같이 `labels.json`에 저장한다. `x`, `y`는 0–1의 정규화된 **예상 검색 위치**이며 최종 위치는 생성 이미지에서 탐지한 마커로 결정한다. `width`, `height`는 기준 이미지 해상도다.

```json
{
  "version": 1,
  "width": 1536,
  "height": 1024,
  "labels": [
    {"id": "beaker-a", "x": 0.25, "y": 0.75, "text": "비커 A", "font_size": 36, "search_radius": 0.025},
    {"id": "panel-a", "x": 0.25, "y": 0.875, "text": "(가)", "font_size": 36, "search_radius": 0.025}
  ]
}
```

1–50개의 마커를 사용하며, `id`는 고유 ASCII 영문·숫자·밑줄·하이픈, `font_size`는 기준 픽셀, `search_radius`는 정규화 검색 반경이다. 선택 필드는 `anchor` (`start`, `middle`, `end`, 기본 `middle`), `cleanup` (`white`, `local_gray`, 기본 `white`), `halo` (흰 테두리 0–4 기준 px)다. `local_gray`는 밝고 매끄러운 회색 영역에서만 사용하며 선이나 급격한 경계에 닿으면 중단한다. 흰 여백의 마커를 우선한다.

스케치를 PNG로 렌더링해 실제로 확인한 다음, 이미지 생성 도구에 참조 이미지로 제공한다. 프롬프트에 기구의 핵심 관계, 보완할 모양, 흑백 시험지 그림, 텍스트 생성 금지, 마커의 개수·색·각 위치를 명시한다. 마커는 인식 가능하게 보존하고 주변 선과 닿지 않게 요청한다. 원통형 유리의 눈금은 곡면 투영에 맞는 완만한 곡선으로 요청한다. 유리·액체 안에 마커를 놓아야 한다면 그 주변에 선 없는 밝고 매끄러운 영역을 요청한다. 프롬프트와 마커가 남은 원본 생성 이미지를 저장한다.

새 글자가 필요한 자리에 마커가 없으면 현재 그림을 이미지 생성 도구로 다시 편집해 먼저 그 위치의 마커를 받는다. 생성 모델에 숫자 자체를 쓰게 하거나 예상 좌표에 직접 글자를 얹어 마커 단계를 우회하지 않는다.

## 3. 내장 스크립트 추출 및 합성

이 SKILL.md를 공유한 뒤, 작업할 디렉터리에서 다음 명령을 실행한다. `/path/to/SKILL.md`를 이 파일의 실제 경로로 바꾼다. 스크립트 두 개가 현재 디렉터리에 생성된다. 기존 파일은 덮어쓰지 않는다.

```bash
python3 - /path/to/SKILL.md <<'PY_EXTRACT'
import re, sys
from pathlib import Path
source = Path(sys.argv[1]).read_text(encoding='utf-8')
for name in ('render_apparatus.py', 'compose_labels.js'):
    match = re.search(r'^```(?:python|javascript) filename=' + re.escape(name) + r'\n(.*?)^```$', source, re.M | re.S)
    if not match:
        raise SystemExit(f'내장 코드를 찾지 못했습니다: {name}')
    target = Path(name)
    with target.open('x', encoding='utf-8') as f:
        f.write(match.group(1))
    print(target)
PY_EXTRACT
```

`sharp`를 Node가 찾을 수 있어야 한다. 이미 설치된 패키지를 쓰거나 `SCIENCE_SHARP_PATH`에 `sharp` 패키지 디렉터리의 절대경로를 지정한다. Codex에서는 사용 가능한 경우 `load_workspace_dependencies`로 번들 경로를 찾을 수 있다. 스케치와 합성 실행 예:

```bash
python3 render_apparatus.py apparatus.json sketch.svg
node compose_labels.js generated.png labels.json output/prefix
```

합성기는 각 검색 반경에서 마커를 정확히 하나씩 찾고 재사용·예상 밖 마커·잔여 마커·안전하지 않은 제거 영역을 검사한다. 누락·복수·오류가 나면 멈추고 이미지 생성이나 마커 배치부터 수정한다. 출력 경로가 이미 존재하면 덮어쓰지 않는다. 출력은 `prefix.clean.png`, `prefix.final.png`, `prefix.final.svg`, `prefix.detected.json`이다. 최종 SVG는 정리된 래스터 배경과 별도 편집 가능한 `<text>`를 포함하며 장치 그림 자체가 벡터로 변환되지는 않는다. 문구나 글자 크기만 바꿀 때는 보관한 마커 원본과 수정된 JSON으로 새 prefix에 다시 합성한다.

## 4. 검토와 전달

원본 스케치와 생성 그림을 대조해 기구 개수와 상대 위치, 액면 순서, 침지, 밀폐·피스톤·전기 접속을 확인한다. 눈금의 곡률·개수·간격과 숫자 순서, 문구·단위, 한글 가독성, 마커 잔여, 겹침·잘림을 실제 인쇄 크기에서 확인한다. 검출 성공은 물리적 관계나 눈금의 정량적 정확성을 보장하지 않는다. 그림·눈금이 틀리면 이미지 생성부터, 마커가 잘못되면 마커 추가부터 반복한다. 최종 PNG와 SVG, 스케치 SVG와 해당 JSON, 마커가 있는 생성 이미지, 글자 JSON, 검출 보고서 및 프롬프트를 함께 제공한다. 실제 자료 그림을 그대로 재사용할 때는 출처와 재사용 조건을 확인한다.

## 내장 코드: 스케치 렌더러

```python filename=render_apparatus.py
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
```

## 내장 코드: 마커 검출과 글자 합성

```javascript filename=compose_labels.js
#!/usr/bin/env node
'use strict';
/* Detect disposable magenta markers, replace their white label zones, and add
   editable SVG text over a self-contained generated raster illustration. */
const fs = require('node:fs');
const path = require('node:path');
function getSharp() {
  const candidates = [process.env.SCIENCE_SHARP_PATH, 'sharp',
    path.join(process.env.HOME || '', '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp')].filter(Boolean);
  for (const candidate of candidates) { try { return require(candidate); } catch (e) { if (e.code !== 'MODULE_NOT_FOUND') throw e; } }
  throw new Error('sharp is required. Set SCIENCE_SHARP_PATH to its absolute package directory or install sharp in the Node environment.');
}
const sharp = getSharp();
function fail(message) { throw new Error(message); }
function finite(value, label, min, max) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) fail(`${label}: expected a number between ${min} and ${max}`);
  return value;
}
function escapeXML(value) { return value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&apos;'); }
function core(r,g,b,a) { return a > 200 && r >= 160 && b >= 160 && g <= 160 && r-g >= 65 && b-g >= 65; }
function loose(r,g,b,a) {
  // Image-generation antialiasing may leave a very pale magenta fringe, e.g.
  // [252,234,255]. Admit only bright magenta-tinted fringe, never gray/black.
  const brightFringe = r >= 235 && b >= 235 && g >= 210 && r-g >= 8 && b-g >= 8;
  return a > 0 && ((r >= 130 && b >= 130 && r-g >= 20 && b-g >= 20) || brightFringe);
}
function white(r,g,b,a) { return a === 0 || (r >= 235 && g >= 235 && b >= 235); }
function gray(r,g,b,a) {
  // Generated grayscale art can contain faint chromatic ringing around markers.
  // Keep the tolerance small; brightness and smooth-background checks also apply.
  return a >= 240 && Math.min(r,g,b) >= 160 && Math.max(r,g,b)-Math.min(r,g,b) <= 20;
}
function grayMarker(r,g,b,a) {
  // A magenta edge blended against gray may be less saturated than its core.
  return a > 0 && r >= 130 && b >= 130 && Math.abs(r-b) <= 35 && r-g >= 8 && b-g >= 8;
}
function parseLabels(doc) {
  if (!doc || doc.version !== 1 || !Array.isArray(doc.labels) || !doc.labels.length || doc.labels.length > 50) fail('labels JSON requires version:1 and 1–50 labels');
  if (Object.hasOwn(doc, 'overlays')) fail('overlays are not allowed: request an image-generation marker for every text label first');
  finite(doc.width, 'width', 100, 20000);
  finite(doc.height, 'height', 100, 20000);
  const ids = new Set();
  return doc.labels.map((item, i) => {
    if (!item || typeof item !== 'object') fail(`labels[${i}]: expected an object`);
    const id = item.id;
    if (typeof id !== 'string' || !/^[A-Za-z0-9_-]{1,64}$/.test(id) || ids.has(id)) fail(`labels[${i}].id: expected a unique ASCII identifier`);
    ids.add(id);
    if (typeof item.text !== 'string' || !item.text.trim() || item.text.length > 120 || /[\u0000-\u001f\ud800-\udfff\ufffe\uffff]/.test(item.text)) fail(`${id}.text: expected nonempty single-line text without control characters (max 120 chars)`);
    const anchor=item.anchor ?? 'middle', cleanup=item.cleanup ?? 'white';
    if (!['start','middle','end'].includes(anchor)) fail(`${id}.anchor: expected start, middle or end`);
    if (!['white','local_gray'].includes(cleanup)) fail(`${id}.cleanup: expected white or local_gray`);
    return {id, x: finite(item.x, `${id}.x`, 0, 1), y: finite(item.y, `${id}.y`, 0, 1), text:item.text,
      font_size: finite(item.font_size, `${id}.font_size`, 4, 512), search_radius: finite(item.search_radius ?? 0.08, `${id}.search_radius`, 0.001, 0.3),
      anchor, cleanup, halo:finite(item.halo ?? 0,`${id}.halo`,0,4)};
  });
}
function localGrayBackground(data,w,box,id) {
  const at=(x,y)=>{const k=(y*w+x)*4;return [data[k],data[k+1],data[k+2],data[k+3]];};
  const corner=(x,y,dx,dy)=>{
    let total=0,n=0;
    for(const [xx,yy] of [[x,y],[x+dx,y],[x,y+dy]]) {
      const pixel=at(xx,yy);
      if(!gray(...pixel)) fail(`${id}: local_gray border is not bright neutral background; review marker placement`);
      total+=(pixel[0]+pixel[1]+pixel[2])/3;n++;
    }
    return total/n;
  };
  const corners=[corner(box.x,box.y,1,1),corner(box.right,box.y,-1,1),corner(box.x,box.bottom,1,-1),corner(box.right,box.bottom,-1,-1)];
  if(Math.max(...corners)-Math.min(...corners)>45) fail(`${id}: local_gray background changes too much; review marker placement`);
  const predict=(x,y)=>{
    const tx=(x-box.x)/(box.right-box.x),ty=(y-box.y)/(box.bottom-box.y);
    return Math.round((corners[0]*(1-tx)+corners[1]*tx)*(1-ty)+(corners[2]*(1-tx)+corners[3]*tx)*ty);
  };
  for(let y=box.y;y<=box.bottom;y++)for(let x=box.x;x<=box.right;x++) {
    const pixel=at(x,y), edge=x===box.x||x===box.right||y===box.y||y===box.bottom;
    if(!edge && grayMarker(...pixel)) continue;
    const mean=(pixel[0]+pixel[1]+pixel[2])/3;
    if(!gray(...pixel)||Math.abs(mean-predict(x,y))>16) fail(`${id}: local_gray cleanup touches a drawing line or non-smooth background at (${x},${y}); request a safer marker position`);
  }
  return {predict,corners:corners.map(x=>+x.toFixed(2))};
}
function checkTextBounds(item, center, size, w, h, anchor='middle') {
  // Font-independent conservative estimate; final font/layout still needs visual review.
  const estimatedWidth = [...item.text].reduce((sum, c) => sum + (c.codePointAt(0) > 0x2ff ? 1.1 : 0.75), 0) * size;
  const left = center[0] - (anchor === 'end' ? estimatedWidth : anchor === 'middle' ? estimatedWidth/2 : 0);
  if (left < 0 || left + estimatedWidth > w) fail(`${item.id}: text may clip at left/right edge; reduce font size or move its anchor`);
  if (center[1] < size*0.65 || center[1] + size*0.65 > h) fail(`${item.id}: text is too close to top/bottom edge`);
}
function detect(data, w, h) {
  const n = w*h, seen = new Uint8Array(n), candidates = [];
  // 8-connectivity preserves antialiased diagonal marker edges.
  for (let p=0; p<n; p++) {
    if (seen[p]) continue;
    const k=p*4;
    if (!core(data[k],data[k+1],data[k+2],data[k+3])) continue;
    const queue=[p]; seen[p]=1;
    let area=0, minX=w, minY=h, maxX=0, maxY=0;
    for(let head=0;head<queue.length;head++) {
      const q=queue[head], x=q%w, y=Math.floor(q/w); area++;
      minX=Math.min(minX,x);maxX=Math.max(maxX,x);minY=Math.min(minY,y);maxY=Math.max(maxY,y);
      for(let dy=-1;dy<=1;dy++) for(let dx=-1;dx<=1;dx++) {
        const xx=x+dx, yy=y+dy;
        if(xx<0||xx>=w||yy<0||yy>=h) continue;
        const t=yy*w+xx,j=t*4;
        if(!seen[t]&&core(data[j],data[j+1],data[j+2],data[j+3])) {seen[t]=1;queue.push(t);}
      }
    }
    if(area>=4) candidates.push({area,minX,minY,maxX,maxY,x:(minX+maxX)/2,y:(minY+maxY)/2});
  }
  return candidates;
}
async function compose(input, labelPath, prefix) {
  const doc=JSON.parse(fs.readFileSync(labelPath,'utf8')), labels=parseLabels(doc);
  const outputs={clean:prefix+'.clean.png',svg:prefix+'.final.svg',png:prefix+'.final.png',report:prefix+'.detected.json'};
  for(const file of Object.values(outputs)) if(fs.existsSync(file)) fail(`Refusing to overwrite ${file}; use a new output prefix`);
  const result=await sharp(input,{limitInputPixels:80e6}).ensureAlpha().raw().toBuffer({resolveWithObject:true});
  const {width:w,height:h}=result.info;
  if(w<100||h<100) fail('Input image is too small');
  if(Math.abs(w/h-doc.width/doc.height)/(doc.width/doc.height)>0.03) fail('Generated image aspect ratio differs from sketch by more than 3%; review before composing');
  const data=result.data, candidates=detect(data,w,h), matches=[], used=new Set();
  for(const label of labels) {
    const nearby=candidates.map((c,i)=>({c,i,d:Math.hypot(c.x/w-label.x,c.y/h-label.y)})).filter(x=>x.d<=label.search_radius);
    if(nearby.length!==1) fail(`${label.id}: expected exactly one marker within search_radius, found ${nearby.length}`);
    const {c,i}=nearby[0];
    if(used.has(i)) fail(`${label.id}: marker already assigned to another label`);
    const cw=c.maxX-c.minX+1,ch=c.maxY-c.minY+1;
    if(cw/ch<0.4||cw/ch>2.5||cw>0.07*w||ch>0.07*h) fail(`${label.id}: candidate is not a small compact marker`);
    used.add(i);
    const pad=Math.max(3,Math.ceil(w/doc.width*3));
    const box={x:Math.max(0,c.minX-pad),y:Math.max(0,c.minY-pad),right:Math.min(w-1,c.maxX+pad),bottom:Math.min(h-1,c.maxY+pad)};
    let background;
    if(label.cleanup==='local_gray') background=localGrayBackground(data,w,box,label.id);
    else for(let y=box.y;y<=box.bottom;y++) for(let x=box.x;x<=box.right;x++) {
        const k=(y*w+x)*4;
        if(!white(data[k],data[k+1],data[k+2],data[k+3])&&!loose(data[k],data[k+1],data[k+2],data[k+3])) fail(`${label.id}: marker cleanup region touches nonwhite drawing pixels at (${x},${y}); review the generated image`);
      }
    matches.push({...label,center_px:[c.x,c.y],marker_bbox_px:[c.minX,c.minY,c.maxX+1,c.maxY+1],cleanup_bbox_px:[box.x,box.y,box.right+1,box.bottom+1],area:c.area,background});
  }
  if(used.size!==candidates.length) fail(`Found ${candidates.length-used.size} unexpected magenta marker(s); review the generated image`);
  // Only verified marker neighborhoods may change; other illustration pixels stay intact.
  const cleaned=Buffer.from(data);
  for(const m of matches) {
    const [x0,y0,x1,y1]=m.cleanup_bbox_px;
    for(let y=y0;y<y1;y++) for(let x=x0;x<x1;x++) {
      const k=(y*w+x)*4;
      if(m.cleanup==='white') cleaned.fill(255,k,k+4);
      else {
        const value=m.background.predict(x,y);cleaned[k]=cleaned[k+1]=cleaned[k+2]=value;cleaned[k+3]=255;
      }
    }
  }
  for(let k=0;k<cleaned.length;k+=4) if(core(cleaned[k],cleaned[k+1],cleaned[k+2],cleaned[k+3])) fail('Residual magenta found outside verified marker regions; review before exporting');
  const cleanPNG=await sharp(cleaned,{raw:{width:w,height:h,channels:4}}).png().toBuffer();
  const font="'Noto Sans CJK KR', 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif";
  const texts=matches.map(m=>`  <text data-label-id="${escapeXML(m.id)}" x="${m.center_px[0]}" y="${m.center_px[1]}" font-size="${+(m.font_size*w/doc.width).toFixed(3)}" text-anchor="${m.anchor}" dominant-baseline="central"${m.halo > 0 ? ` stroke="white" stroke-width="${+(m.halo*w/doc.width).toFixed(3)}" stroke-linejoin="round" paint-order="stroke fill"` : ''}>${escapeXML(m.text)}</text>`).join('\n');
  for(const m of matches) checkTextBounds(m,m.center_px,m.font_size*w/doc.width,w,h,m.anchor);
  const svg=`<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img">\n  <title>실험 장치 모식도</title>\n  <image x="0" y="0" width="${w}" height="${h}" href="data:image/png;base64,${cleanPNG.toString('base64')}"/>\n  <g id="labels" font-family="${escapeXML(font)}" fill="black">\n${texts}\n  </g>\n</svg>\n`;
  const finalPNG=await sharp(Buffer.from(svg),{limitInputPixels:80e6}).png().toBuffer();
  fs.mkdirSync(path.dirname(prefix),{recursive:true});
  fs.writeFileSync(outputs.clean,cleanPNG);fs.writeFileSync(outputs.svg,svg);fs.writeFileSync(outputs.png,finalPNG);
  fs.writeFileSync(outputs.report,JSON.stringify({version:1,input_image:path.basename(input),width:w,height:h,labels:matches.map(({search_radius,background,...m})=>({...m,...(background ? {background_corners_gray:background.corners}: {})}))},null,2)+'\n');
  return outputs;
}
if(require.main===module) {
  const args=process.argv.slice(2);
  if(args.length!==3) {console.error('Usage: node compose_labels.js generated.png labels.json output/prefix');process.exitCode=2;}
  else compose(...args).then(outputs=>console.log(JSON.stringify(outputs,null,2))).catch(e=>{console.error('Error: '+e.message);process.exitCode=1;});
}
module.exports={compose,detect,parseLabels};
```
