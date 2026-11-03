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
        with self.assertRaises(ValueError): latex('matrix {a}')

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
    def test_prompt_only_question_keeps_number_on_same_line(self):
        from examkit.parse_md import parse
        from examkit.typst_body import build
        meta, questions = parse((ROOT/'docs/examples/format-demo.md').read_text(encoding='utf-8'))
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
            gaps=[];between=[]
            for n,start in enumerate(numbers):
                end=numbers[n+1] if n+1<len(numbers) else len(text)
                group=text[start:end];choice=next(i for i,c in enumerate(group) if c['char']=='①')
                baseline=max(c['y'] for c in group[:choice] if c['height']==1150)
                gaps.append(group[choice]['y']-baseline)
                if n+1<len(numbers):between.append(text[end]['y']-group[choice]['y'])
            self.assertLess(max(gaps)-min(gaps),.01)
            self.assertLess(max(between)-min(between),.01)
            h=next(i for i,c in enumerate(text) if c['char']=='H')
            letter,sub,oxygen=text[h:h+3]
            self.assertEqual([letter['char'],sub['char'],oxygen['char']],['H','2','O'])
            self.assertEqual(sub['font'],letter['font'])
            self.assertAlmostEqual(sub['height'],letter['height']*.64)
            self.assertGreater(sub['y'],letter['y'])
            self.assertLess(sub['advance'],letter['advance'])

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
