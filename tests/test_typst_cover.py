import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'tools'))
import build_cover
from examkit.cover import cover_settings
from examkit.typst_runtime import compile_pdf


META = dict(year='2027학년도', exam='표지 연결 시험', period='제3교시', area='자유 영역',
            subject='자료 해석', pages='2', handwriting='함께 배우며 자란다', issuer='편집 확인')


class CoverSettingsTests(unittest.TestCase):
    def test_custom_titles_and_instructions_are_not_fixed(self):
        for variant in ('korean', 'math'):
            settings = cover_settings(META | dict(cover_template=variant, cover_title='원하는 제목',
                                                  cover_area='임의 영역', cover_p22='4점 문항 안내'))
            p = settings['paragraphs']
            self.assertEqual(p['2'], '원하는 제목')
            self.assertEqual(p['5'], '임의 영역')
            self.assertEqual(p['22'], '4점 문항 안내')
            self.assertEqual(p['6'], '')
            self.assertEqual(p['29' if variant == 'korean' else '33'], '1~2 쪽')
            self.assertNotIn('5지선다형', ''.join(p.values()))
            self.assertNotIn('한국교육과정평가원', ''.join(p.values()))

    def test_invalid_settings_fail(self):
        for change in (dict(cover_template='unknown'), dict(pages='0'), dict(cover_pbad='text')):
            with self.subTest(change=change), self.assertRaises(ValueError):
                cover_settings(META | change)

    def test_validation_failure_preserves_last_pdf(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            target = folder / 'cover.pdf'
            target.write_bytes(b'previous output')
            def compile(command, **kwargs):
                with pymupdf.open() as pdf:
                    pdf.new_page()
                    pdf.save(command[3])
                return type('Result', (), dict(returncode=0, stderr=''))()
            def reject(pdf):
                raise ValueError('missing configured text')
            with patch('examkit.typst_runtime.engine_root', return_value=folder), \
                 patch('examkit.typst_runtime.executable', return_value='typst'), \
                 patch('examkit.typst_runtime.subprocess.run', side_effect=compile), \
                 self.assertRaisesRegex(ValueError, 'missing configured text'):
                compile_pdf(folder / 'source.typ', target, expected_pages=1, validate=reject)
            self.assertEqual(target.read_bytes(), b'previous output')


@unittest.skipUnless(os.environ.get('EXAMKIT_TYPST_ROOT') and os.environ.get('TYPST_EXE'),
                     'Set EXAMKIT_TYPST_ROOT and TYPST_EXE for actual Typst integration')
class TypstCoverIntegrationTests(unittest.TestCase):
    def test_both_templates_and_assembly_preserve_body(self):
        # Keep inputs beside the repository so engine and output share a Windows drive.
        with tempfile.TemporaryDirectory(prefix='.cover-test-', dir=ROOT) as folder:
            folder = Path(folder)
            for variant in ('korean', 'math'):
                meta = META | dict(cover_template=variant, cover_title='직접 지정한 시험 제목', cover_p22='배점은 4점입니다.')
                md = folder / f'{variant}.md'
                md.write_text('---\n' + '\n'.join(f'{k}: {v}' for k, v in meta.items()) + '\n---\n', encoding='utf-8')
                front = build_cover.build([md], folder / variant)[0]
                with pymupdf.open(front) as pdf:
                    self.assertEqual(len(pdf), 1)
                    text = ''.join(pdf[0].get_text().split())
                    self.assertIn('직접지정한시험제목', text)
                    self.assertIn('자유영역', text)
                    self.assertNotIn('홀수형', text)
                    self.assertNotIn('한국교육과정평가원', text)
                body_path = folder / f'{variant}-body.pdf'
                with pymupdf.open() as body:
                    for n in range(2):
                        p = body.new_page(width=595, height=842)
                        p.insert_text((72, 72), f'Original body {n + 1}')
                        p.draw_rect((80, 100, 200, 220))
                    body.save(body_path)
                merged = build_cover.assemble([body_path], [front], [md])
                try:
                    self.assertEqual(len(merged), 3)
                    self.assertEqual(merged.get_toc()[0][2], 1)
                    with pymupdf.open(body_path) as original:
                        for n in range(2):
                            self.assertEqual(original[n].get_text(), merged[n+1].get_text())
                            self.assertEqual(original[n].get_pixmap().samples, merged[n+1].get_pixmap().samples)
                finally:
                    merged.close()
                previous = front.read_bytes()
                md.write_text(md.read_text(encoding='utf-8').replace('직접 지정한 시험 제목', '너무 긴 제목 ' * 300), encoding='utf-8')
                with self.assertRaises(RuntimeError):
                    build_cover.build([md], folder / variant)
                self.assertEqual(front.read_bytes(), previous)


if __name__ == '__main__':
    unittest.main()
