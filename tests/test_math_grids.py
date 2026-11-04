import os
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from examkit.native_math import equation, latex
from examkit.math_grids import expand, rows


class GridSyntaxTests(unittest.TestCase):
    def test_array_and_alignment(self):
        for source,expected in [(r'\begin{array}{lr}1&2\\3&4\end{array}','lr'),
                                (r'\begin{aligned}x&=1\\y&=2\end{aligned}','rl')]:
            grids={};atom=expand(source,grids,set(source))
            self.assertEqual(grids[atom][2],expected)
        for source in [r'\begin{array}{l}1&2\end{array}',r'\begin{align}x\end{align}',
                       r'\begin{array}{|c|}1\end{array}']:
            with self.assertRaises(ValueError):expand(source,{},set(source))

    def test_groups_empty_cells_and_trailing_separator(self):
        self.assertEqual(rows(r'a&&\frac{b}{c}\\d&e&f\\'),[['a','',r'\frac{b}{c}'],['d','e','f']])
        self.assertEqual(rows(r'\text{a\&b}&c'),[[r'\text{a\&b}','c']])
        converted=latex('cases {sqrt{x}&x geq 0#{1} over {x}&x<0}')
        self.assertEqual(converted,r'\begin{cases}\sqrt{x}&x \geq 0\\\frac{{1}}{{x}}&x<0\end{cases}')
        with self.assertRaises(ValueError):latex('matrix a&b')

    def test_reject_invalid_environments(self):
        for source in [r'\begin{matrix}a&b\\c\end{matrix}',r'\begin{cases}a&b&c\end{cases}',
                       r'\begin{matrix}\end{matrix}',r'\begin{matrix}a\end{cases}',
                       r'\begin{matrix}a',r'\end{matrix}',r'\begin{array}a\end{array}']:
            with self.subTest(source=source),self.assertRaises(ValueError):expand(source,{},set(source))

    def test_nested_environments_and_literal_private_character(self):
        source='\ue000'+r'\begin{pmatrix}\begin{matrix}1&2\\3&4\end{matrix}&0\\0&1\end{pmatrix}'
        grids={};result=expand(source,grids,set(source))
        self.assertEqual(result[0],'\ue000')
        self.assertNotIn('\ue000',grids)
        self.assertEqual(len(grids),2)
        self.assertEqual(grids[result[-1]][0],'pmatrix')


@unittest.skipUnless(os.environ.get('EXAMKIT_TYPST_ROOT'),'Original equation font required')
class GridRenderingTests(unittest.TestCase):
    def setUp(self):
        self.font=str(Path(os.environ['EXAMKIT_TYPST_ROOT'])/'fonts/HancomEQN.ttf')

    def test_aligned_equals_and_array(self):
        result=equation(r'\begin{aligned}x&=1\\yyy&=2\end{aligned}',11.5,self.font)
        equals=[c for c in result['commands'] if c.get('char')=='=']
        self.assertEqual(len(equals),2)
        self.assertAlmostEqual(equals[0]['x'],equals[1]['x'])
        self.assertLess(equals[0]['y'],equals[1]['y'])
        result=equation(r'\begin{array}{lr}1&22\\333&4\end{array}',11.5,self.font)
        chars=[c for c in result['commands'] if c['kind']=='text']
        self.assertAlmostEqual(next(c['x'] for c in chars if c['char']=='1'),next(c['x'] for c in chars if c['char']=='3'))

    def test_rows_columns_delimiters_and_baseline(self):
        for name in ('matrix','pmatrix','bmatrix','Bmatrix','vmatrix','Vmatrix','cases'):
            with self.subTest(name=name):
                source=r'A=\begin{'+name+r'}1&2\\3&4\end{'+name+'}'
                result=equation(source,11.5,self.font)
                text=[c for c in result['commands'] if c['kind']=='text']
                self.assertEqual({c['font'] for c in text},{'HancomEQN'})
                digit={c['char']:c for c in text if c['char'] in '1234'}
                self.assertEqual(set(digit),set('1234'))
                self.assertEqual(digit['1']['y'],digit['2']['y'])
                self.assertEqual(digit['3']['y'],digit['4']['y'])
                self.assertAlmostEqual(digit['1']['x'],digit['3']['x'])
                self.assertAlmostEqual(digit['2']['x'],digit['4']['x'])
                self.assertGreater(digit['2']['x'],digit['1']['x'])
                self.assertGreater(digit['3']['y']-digit['1']['y'],1150)
                equals=next(c for c in text if c['char']=='=')
                self.assertLess(digit['1']['y'],equals['y'])
                self.assertGreater(digit['3']['y'],equals['y'])

    def test_nested_fraction_scripts_empty_cell_and_hwp(self):
        for source in [r'\frac{\begin{bmatrix}a&b\\c&d\end{bmatrix}}{2}',
                       r'\begin{pmatrix}1&\\&4\end{pmatrix}^{2}',
                       r'\begin{pmatrix}\begin{matrix}1&2\\3&4\end{matrix}&0\\0&1\end{pmatrix}',
                       r'LEFT ( matrix {a&b#c&d} RIGHT )',
                       r'cases {sqrt{x}&x geq 0#{1} over {x}&x<0}']:
            with self.subTest(source=source):
                result=equation(source,11.5,self.font)
                self.assertGreater(result['width'],0)
                self.assertGreater(result['height'],0)
                self.assertTrue(0<result['baseline']<=result['height'])
                self.assertEqual({c['font'] for c in result['commands'] if c['kind']=='text'},{'HancomEQN'})
        with self.assertRaises(ValueError):equation(r'\begin{matrix}\unknown{x}\end{matrix}',11.5,self.font)

    def test_explanation_raster_uses_same_grid_parser(self):
        from tools.key_math import render_math
        from PIL import Image
        with tempfile.TemporaryDirectory() as folder:
            for source in [r'\begin{bmatrix}1&2\\3&4\end{bmatrix}',r'cases {x&x>0#-x&x<0}']:
                width,height,depth,name=render_math(source,True,folder)
                self.assertTrue(width>0 and height>depth>0)
                with Image.open(Path(folder)/name) as image:
                    self.assertLess(image.getextrema()[0],255)

    @unittest.skipUnless(os.environ.get('TYPST_EXE'),'Typst executable required')
    def test_body_and_explanation_cli_without_hancom(self):
        import pymupdf
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(dir=root) as folder:
            folder=Path(folder)
            (folder/'sitecustomize.py').write_text('''import sys
class NoCOM:
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in ('win32com','pythoncom','pywintypes'):
            raise RuntimeError('Hancom is disabled')
sys.meta_path.insert(0,NoCOM())
''',encoding='utf8')
            env=os.environ|{'PYTHONPATH':str(folder)}
            source=root/'docs/examples/math-grids.md'
            for args in [('-m','examkit','build',str(source),'-o',str(folder)),
                         ('tools/build_key.py',str(folder/'key.pdf'),str(source))]:
                process=subprocess.run([sys.executable,'-X','utf8',*args],cwd=root,env=env,capture_output=True,text=True,encoding='utf8',timeout=180)
                self.assertEqual(process.returncode,0,process.stdout+process.stderr)
            for pdf in (folder/'행렬과 경우 나눔.pdf',folder/'key.pdf'):
                with pymupdf.open(pdf) as doc:
                    self.assertEqual(len(doc),1)
                    text=''.join(p.get_text() for p in doc)
                    self.assertNotIn(r'\begin',text)
                    for n in range(1,7):self.assertIn(f'{n}.',text)
            commands=json.loads((folder/'행렬과 경우 나눔.assets/body-1.json').read_text(encoding='utf8'))
            self.assertGreater(sum(c.get('font')=='HancomEQN' for c in commands),100)
            self.assertFalse(any(0xE000<=ord(c['char'])<0xF900 for c in commands if c.get('font')=='HancomEQN'))


if __name__=='__main__':unittest.main()
