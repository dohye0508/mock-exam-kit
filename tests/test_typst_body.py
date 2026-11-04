import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import pymupdf

from examkit.native_math import latex, equation

ROOT = Path(__file__).resolve().parents[1]


class EquationTests(unittest.TestCase):
    def test_hwp_fraction_groups_and_latex(self):
        self.assertEqual(latex('{a} over {b}'), r'\frac{{a}}{{b}}')
        self.assertIn(r'\frac', latex('{{a} over {b}} over {c}'))
        self.assertEqual(latex(r'\frac{x^2}{\sqrt{y}}'), r'\frac{x^2}{\sqrt{y}}')
        with self.assertRaises(ValueError): latex('{a')
        self.assertEqual(latex('matrix {a&b#c&d}'),r'\begin{matrix}a&b\\c&d\end{matrix}')

    @unittest.skipUnless(os.environ.get('EXAMKIT_TYPST_ROOT'), 'Original fonts required')
    def test_new_equations_use_only_original_face(self):
        font = str(Path(os.environ['EXAMKIT_TYPST_ROOT']) / 'fonts/HancomEQN.ttf')
        for source in (r'\frac{x^2+1}{\sqrt{a}}', r'\sum_{i=1}^{n} x_i', r'\int_0^1 x\,dx', '{a} over {b}'):
            result = equation(source, 11.5, font)
            self.assertGreater(result['width'], 0)
            self.assertGreater(result['height'], 0)
            self.assertEqual({c['font'] for c in result['commands'] if c['kind']=='text'}, {'HancomEQN'})
        with self.assertRaises(ValueError): equation(r'\not_a_command{x}', 11.5, font)


@unittest.skipUnless(os.environ.get('EXAMKIT_TYPST_ROOT') and os.environ.get('TYPST_EXE'), 'Configured Typst engine required')
class BodyIntegrationTests(unittest.TestCase):
    def test_choice_layouts_use_original_rows_and_tab_positions(self):
        from examkit.parse_md import parse
        from examkit.typst_body import build
        meta, _ = parse((ROOT/'docs/examples/format-demo.md').read_text(encoding='utf-8'))
        meta.update(pages='auto',question_spacing='compact')
        samples=[(['1','2','3','4','5'],None,5),
                 (['RAIBIT','RBAIBT','RBIABT','RABBIT','RIBBAT'],None,3),
                 (['ABCDEFGHIJKLMNO']*5,None,2),
                 (['선택지의 내용을 끝까지 읽고 서로 비교하여 판단한다.']*5,None,1),
                 (['1','2','3','4','5'],3,3),(['1','2','3','4','5'],2,2)]
        questions=[]
        for n,(items,override,_) in enumerate(samples,1):
            _,parsed=parse(f'## {n}.\n배열을 확인하시오.\n? 알맞은 것을 고르시오.\n'+
                           '\n'.join(mark+' '+item for mark,item in zip('①②③④⑤',items))+
                           (f'\n@choices {override}' if override else ''))
            questions.extend(parsed)
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            for profile in ('science','social'):
                target=Path(folder)/f'{profile}.pdf'
                build(meta|{'body_template':profile},questions,target)
                commands=[c for file in sorted(target.with_suffix('.assets').glob('body-*.json'))
                          for c in json.loads(file.read_text(encoding='utf-8'))]
                groups=[]
                for c in commands:
                    if 'question_start' in c:groups.append([])
                    if c.get('char') in tuple('①②③④⑤'):groups[-1].append(c)
                self.assertEqual(len(groups),len(samples))
                for marks,(_,_,columns) in zip(groups,samples):
                    self.assertEqual([c['char'] for c in marks],list('①②③④⑤'))
                    self.assertEqual(len({round(c['y'],3) for c in marks}),(5+columns-1)//columns)
                    for i in range(columns,len(marks)):
                        self.assertAlmostEqual(marks[i]['x'],marks[i%columns]['x'],places=3)

    def test_question_and_example_styles_match_native_reference(self):
        from examkit.parse_md import parse
        from examkit.typst_body import build
        source='''---
title: 서식 대조
year: 2026학년도
exam: 원본 대조
period: 제1교시
area: 과학탐구
subject: 배치 확인
pages: auto
question_spacing: compact
count: 2
three: 0
---
## 1.
다음은 어느 학교의 하루 일과 중 일부를 나타낸 자료이다.
::: box
◦ 오전에는 도서관에서 자료를 조사한다.
◦ 오후에는 모둠별로 조사한 내용을 정리한다.
◦ 정리한 자료는 발표 시간에 함께 확인한다.
:::
? 이에 대한 설명으로 옳은 것만을 <보기>에서 있는 대로 고른 것은?
::: bogi
ㄱ. 오전에는 A 자료를 조사하고 조사한 내용을 모둠원에게 설명한다. 자료에서 확인한 내용을 바탕으로 의견을 정리한다.
ㄴ. 오후에는 내용을 정리한다.
ㄷ. 발표 시간에 자료를 확인한다.
:::
@set A
@answer 3
## 2.
다음은 간격과 줄바꿈을 확인하기 위한 두 번째 문항이다.
? 자료에서 확인할 수 있는 내용에 대한 설명으로 옳은 것을 고른 것은? (단, 주어진 자료만을 이용하여 판단한다.)
① 첫째
② 둘째
③ 셋째
④ 넷째
⑤ 다섯째
@answer 2
'''
        meta,questions=parse(source)
        # Measured from Hancom PDFs using the same text in the original source styles.
        native={
            'science': [('이에대한',74.64,305.051),('것은?',64.32,321.119),
                        ('ㄱ.',72.84,361.409),('설명한다.',91.8,377.956),
                        ('ㄴ.',72.84,414.049),('자료에서확인할',74.64,508.298)],
            'social': [('이에대한',75.6,296.058),('것은?',64.32,312.126),
                       ('ㄱ.',72.72,353.375),('설명한다.',72.72,369.563),
                       ('ㄴ.',72.72,385.631),('자료에서확인할',75.6,468.488)],
        }
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            for profile,anchors in native.items():
                with self.subTest(profile=profile):
                    target=Path(folder)/f'{profile}.pdf'
                    build(meta|{'body_template':profile},questions,target)
                    with pymupdf.open(target) as doc:
                        lines=[line for b in doc[0].get_text('dict')['blocks'] for line in b.get('lines',[])]
                    for prefix,x,y in anchors:
                        line=next(l for l in lines if ''.join(s['text'] for s in l['spans']).replace(' ','').startswith(prefix))
                        actual=line['spans'][0]['origin']
                        self.assertAlmostEqual(actual[0],x,delta=.12)
                        self.assertAlmostEqual(actual[1],y,delta=.5)
                    body=json.loads(target.with_suffix('.assets').joinpath('body-1.json').read_text(encoding='utf-8'))
                    first=next(c for c in body if c.get('char')=='오' and abs(c['y']/100-anchors[2][2])<.5)
                    second=next(c for c in body if c.get('char')=='오' and abs(c['y']/100-anchors[4][2])<.5)
                    self.assertAlmostEqual(second['advance']-first['advance'],24 if profile=='science' else 0,places=4)
                    # A source-shaped run must still parse subscripts, equations, and underlines.
                    _,inline_questions=parse(source)
                    inline_questions[0]['bogi'][1]='H₂O와 $x^2$를 __확인__한다.'
                    special=Path(folder)/f'{profile}-inline.pdf'
                    build(meta|{'body_template':profile},inline_questions,special)
                    commands=json.loads(special.with_suffix('.assets').joinpath('body-1.json').read_text(encoding='utf-8'))
                    text=[c for c in commands if c['kind']=='text'];i=next(i for i,c in enumerate(text) if c['char']=='H')
                    self.assertEqual([c['char'] for c in text[i:i+3]],['H','2','O'])
                    self.assertAlmostEqual(text[i+1]['height'],text[i]['height']*.64)
                    self.assertTrue(any(c.get('font')=='HancomEQN' for c in text))
                    self.assertTrue(any(c.get('decoration')=='underline' for c in commands))

    def test_prompt_only_question_keeps_number_on_same_line(self):
        from examkit.parse_md import parse
        from examkit.typst_body import build
        meta, questions = parse((ROOT/'docs/examples/format-demo.md').read_text(encoding='utf-8'))
        meta['question_spacing']='compact'
        self.assertTrue(all(q['gap']==0 for q in questions))
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            target = Path(folder)/'prompt.pdf'
            build(meta, questions, target)
            with pymupdf.open(target) as doc:
                lines = [line for block in doc[0].get_text('dict')['blocks'] for line in block.get('lines',[])]
                numbered = [''.join(span['text'] for span in line['spans']) for line in lines]
                self.assertTrue(any(re.match(r'1\.\s*빨간', line) for line in numbered))
            commands=json.loads(target.with_suffix('.assets').joinpath('body-1.json').read_text(encoding='utf-8'))
            text=[c for c in commands if c['kind']=='text']
            numbers=[i for i,c in enumerate(text) if c['char'] in ('1','2','3') and c['x']==text[0]['x']]
            for n,start in enumerate(numbers):
                end=numbers[n+1] if n+1<len(numbers) else len(text)
                marks=[c for c in text[start:end] if c['char'] in '①②③④⑤']
                self.assertEqual(len(marks),5)
                gaps=[b['x']-a['x'] for a,b in zip(marks,marks[1:])]
                self.assertLess(max(gaps)-min(gaps),.01)
                # Original HWP choice table: 1391-unit marker + 4787-unit content cells.
                self.assertAlmostEqual(gaps[0],6178,delta=1)
                self.assertAlmostEqual(marks[0]['x']/100,64.32,delta=.05)
                if n+1<len(numbers):
                    # Native source: first choice at 450.502pt, next question at 470.287pt.
                    self.assertAlmostEqual((text[end]['y']-marks[0]['y'])/100,19.785,delta=.05)
            h=next(i for i,c in enumerate(text) if c['char']=='H')
            letter,sub,oxygen=text[h:h+3]
            self.assertEqual([letter['char'],sub['char'],oxygen['char']],['H','2','O'])
            self.assertEqual(sub['font'],letter['font'])
            self.assertAlmostEqual(sub['height'],letter['height']*.64)
            self.assertGreater(sub['y'],letter['y'])
            self.assertLess(sub['advance'],letter['advance'])
            auto=Path(folder)/'auto.pdf'
            build(meta|{'question_spacing':'auto'},questions,auto)
            spaced=json.loads(auto.with_suffix('.assets').joinpath('body-1.json').read_text(encoding='utf-8'))
            self.assertEqual(len(commands),len(spaced))
            starts=sorted((c['question_top'],c['question_start']) for c in commands if 'question_start' in c)
            offsets={n:set() for _,n in starts}
            for before,after in zip(commands,spaced):
                self.assertEqual({k:v for k,v in before.items() if k not in ('y','question_top')},
                                 {k:v for k,v in after.items() if k not in ('y','question_top')})
                n=max((top,n) for top,n in starts if before['y']>=top)[1]
                offsets[n].add(round(after['y']-before['y'],5))
            self.assertTrue(all(len(values)==1 for values in offsets.values()),'Each question must move as a whole')
            shifts=[next(iter(offsets[n])) for _,n in starts]
            self.assertEqual(shifts[0],0)
            self.assertGreater(shifts[1],0)
            self.assertLessEqual(shifts[1],2*1150*1.4)
            self.assertAlmostEqual(shifts[2],2*shifts[1],places=4)
            questions[0]['gap']=2
            questions[0]['opts']=['iiiiiii']*5  # Seven narrow glyphs fit the original cell.
            build(meta,questions,target)
            commands=json.loads(target.with_suffix('.assets').joinpath('body-1.json').read_text(encoding='utf-8'))
            marks=[c for c in commands if c.get('char') in '①②③④⑤'][:5]
            self.assertEqual(len({c['y'] for c in marks}),1)
            second=next(c for c in commands if c.get('char')=='2' and c['x']==5300)
            self.assertAlmostEqual((second['y']-marks[0]['y'])/100,19.785+14,delta=.05)

    def test_default_cli_and_review_without_hancom(self):
        with tempfile.TemporaryDirectory(prefix='.body-test-', dir=ROOT) as folder:
            folder = Path(folder)
            (folder / 'sitecustomize.py').write_text('''import sys
class NoCOM:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('win32com','pythoncom','pywintypes'):
            raise RuntimeError('Hancom is disabled for this test')
sys.meta_path.insert(0, NoCOM())
''', encoding='utf-8')
            env = os.environ | {'PYTHONPATH': str(folder), 'PYTHONUTF8': '1'}
            text = (ROOT / 'content/example.md').read_text(encoding='utf-8')
            text = text.replace('pages: 2', 'pages: auto').replace('period: 제1교시', 'period: 제3교시')
            text = text.replace('area: 예시탐구', 'area: 자유 영역').replace('subject: 예시 생활', 'subject: 선택 과목')
            from PIL import Image
            picture = folder / 'blank.png'
            Image.new('RGB', (400, 400), 'white').save(picture)
            text = text.replace('## 2.', f'''::: figure file path={picture.relative_to(ROOT).as_posix()} w=15000 h=14000
text1: 0,0,40,15,center@170 | 글상자 검사
text1_font: 56
text1_valign: BOTTOM
table1: 0,16,40,20
table1_rows: 이름|수 ; 가|2
table1_font: 39
table1_rowh: 6
:::

## 2.''', 1)
            text = re.sub(r'(## (\d+)\.[^\n]*)', lambda m: m[1]+'\n@status '+('keep','mod','new')[(int(m[2])-1)%3], text)
            source = folder / 'paper.md'; source.write_text(text, encoding='utf-8')
            def run(*args):
                result = subprocess.run([sys.executable, '-X', 'utf8', '-m', 'examkit', *map(str,args)],
                                        cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8', timeout=180)
                self.assertEqual(result.returncode, 0, result.stdout+'\n'+result.stderr)
            run('build', source, '-o', folder / 'out')
            output = folder / 'out/example.pdf'
            with pymupdf.open(output) as doc:
                text = ''.join(''.join(p.get_text().split()) for p in doc)
                for expected in ('자유영역','선택과목','제3교시','0.4','A기의입학학생수'):
                    self.assertIn(expected, text)
                self.assertNotIn('화학Ⅰ', text)
                self.assertIn('글상자검사', text)
                commands = json.loads((folder/'out/example.assets/body-1.json').read_text(encoding='utf-8'))
                self.assertTrue(any(c.get('height')==900 and c.get('char')=='글' for c in commands))
                self.assertTrue(any(c.get('char')=='A' and c.get('height')==950 for c in commands))
                self.assertTrue(any(c.get('char')=='입' and c.get('height')==1000 and c.get('font')=='Original HFT TEJGTHG' for c in commands))
                for n in range(1,7): self.assertIn(f'{n}.',text)
                self.assertGreaterEqual(len(doc),2)  # source has an explicit page break
            run('review', source, '-o', folder / 'review')
            with pymupdf.open(folder / 'review/example_검토.pdf') as doc:
                colors={s['color'] for p in doc for b in p.get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']}
                self.assertTrue({0xD62718,0x12884A,0x1E5BD8}.issubset(colors))
            previous = output.read_bytes()
            source.write_text(source.read_text(encoding='utf-8').replace('$0.4$', r'$\not_a_command{x}$'), encoding='utf-8')
            failed = subprocess.run([sys.executable,'-X','utf8','-m','examkit','build',str(source),'-o',str(folder/'out')],
                                    cwd=ROOT,env=env,capture_output=True,timeout=180)
            self.assertNotEqual(failed.returncode,0)
            self.assertEqual(output.read_bytes(),previous)


if __name__ == '__main__': unittest.main()
