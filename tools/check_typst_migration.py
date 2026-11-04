"""Build inspectable compatibility examples without importing Hancom COM."""
from pathlib import Path
import json
import sys
import re

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from examkit.parse_md import parse, check
from examkit.typst_body import build
import pymupdf
from PIL import Image, ImageDraw


def main():
    out=ROOT/'output/migration-check'
    out.mkdir(parents=True,exist_ok=True)
    picture=out/'diagram.png'
    canvas=Image.new('RGB',(600,300),'white')
    draw=ImageDraw.Draw(canvas);draw.rectangle((1,1,598,298),outline='black',width=2)
    canvas.save(picture)
    source=(ROOT/'docs/examples/migration-compat.md').read_text(encoding='utf-8')
    source=source.replace('다음 자료를 읽으시오.',
        '다음 자료를 읽고 물체가 움직이는 방향과 그 위치가 어떻게 달라지는지 확인하시오. '*3+
        f'\n::: figure file path={picture.relative_to(ROOT).as_posix()} w=8000 h=4000 wrap=right\n'
        'text1: 0,0,27,13,left | 첫째 줄<br>둘째 줄\ntext1_font: 56\ntext1_wrap: 0\n:::')
    source=source.replace('표를 확인하시오.',
        f'표를 확인하시오.\n::: figure file path={picture.relative_to(ROOT).as_posix()} w=18000 h=9000\n'
        'text1: 0,0,60,30,left | 이 문장은 글상자 안에서 어절 단위로 줄바꿈하는 설정을 확인하기 위한 문장이다.\n'
        'text1_font: 56\ntext1_wrap: 1\n:::')
    meta,qs=parse(source)
    assert check(meta,qs)==[],check(meta,qs)
    result=[]
    profiles=[('science','과학탐구','제4교시'),('social','사회탐구','제4교시'),
              ('korean','국어','제1교시'),('english','영어','제3교시'),('math','수학','제2교시')]
    for profile,area,period in profiles:
        output=out/f'{profile}.pdf'
        settings=meta|dict(body_template=profile,area=area,period=period)
        manifest=build(settings,qs,output)
        with pymupdf.open(output) as pdf:
            text=''.join(p.get_text() for p in pdf)
            compact=re.sub(r'\s+','',text)
            assert '<br>' not in text
            for fragment in ('둘째줄','첫째문장이다.','둘째문장이다.','글상자안에서','[1∼2]'):
                assert fragment in compact,(profile,fragment)
            assert set(re.findall(r'(?m)^\s*(\d+)\.\s',text))=={'1','2','3'}
            assert sum(len(page.get_image_info()) for page in pdf)>=2
        result.append(dict(profile=profile,pages=manifest['pages'],passed=True))
        print(profile,'PASS',manifest['pages'],'pages',flush=True)
    for profile,area,period in profiles[-3:]:
        if profile=='english':continue
        for elective in (('화법과 작문','언어와 매체') if profile=='korean' else ('확률과 통계','미적분','기하')):
            settings=meta|dict(body_template=profile,area=area,period=period,elective=elective)
            output=out/f'{profile}-{elective}.pdf'
            manifest=build(settings,qs,output)
            with pymupdf.open(output) as pdf:
                assert elective.replace(' ','') in re.sub(r'\s+','',''.join(p.get_text() for p in pdf)),elective
            result.append(dict(profile=profile,elective=elective,pages=manifest['pages'],passed=True))
            print(profile,elective,'PASS',flush=True)
    (out/'checks.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':main()
