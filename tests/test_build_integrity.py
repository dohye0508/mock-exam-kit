"""Run with python -m unittest discover -s tests -v; no Hancom process is opened."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import runpy
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch
from zipfile import ZipFile

from lxml import etree
import pymupdf as fitz

from examkit import build, cli, convert, hwpx, parse_md, review

ROOT = Path(__file__).resolve().parents[1]


def tool(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


answer_key = tool('answer_key')
build_final = tool('build_final')
build_cover = tool('build_cover')


def question(answer=1, extra='', choices=None):
    choices = choices or '\n'.join(f'{mark} {i}' for i, mark in enumerate('①②③④⑤', 1))
    return (f'---\ntitle: current\nyear: 2026학년도\nexam: 모의평가\nperiod: 제1교시\n'
            f'area: 과학탐구\nsubject: 과학\ncount: 1\nthree: 0\npages: 4\n---\n'
            f'## 1.\n자료를 읽으시오.\n{extra}\n? 옳은 것은?\n{choices}\n@answer {answer}\n')


def pdf(path=None, text='fixture'):
    doc = fitz.open()
    doc.new_page().insert_text((72, 72), text)
    if path is not None:
        doc.save(path)
        doc.close()
    else:
        return doc


class InputTests(unittest.TestCase):
    def test_valid_example(self):
        source = (ROOT / 'content/example.md').read_text(encoding='utf-8')
        self.assertEqual(parse_md.check(*parse_md.parse(source)), [])

    def test_reject_invalid_answer_and_numbering(self):
        for answer in (0, 6, -1):
            with self.subTest(answer=answer):
                self.assertTrue(parse_md.check(*parse_md.parse(question(answer))))
        body = question()[question().index('## 1.'):]
        source = question().replace('count: 1', 'count: 2') + body
        self.assertTrue(parse_md.check(*parse_md.parse(source)))
        self.assertTrue(parse_md.check(*parse_md.parse(question().replace('## 1.', '## 2.'))))

    def test_reject_invalid_grid(self):
        for rows in ('1 | 2\n' * 4, '1 | 2\n' * 6, '1 | 2\n' * 4 + '3\n'):
            with self.subTest(rows=rows):
                source = question(choices='::: grid headers=A,B\n' + rows + ':::')
                self.assertTrue(parse_md.check(*parse_md.parse(source)))
        valid = question(choices='::: grid headers=A,B\n' + '1 | 2\n' * 5 + ':::')
        self.assertEqual(parse_md.check(*parse_md.parse(valid)), [])

    def test_invalid_input_does_not_reach_outputs(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'invalid.md'
            source.write_text(question(0), encoding='utf-8')
            with patch.object(cli, 'build') as builder, patch.object(cli, 'write_answers') as answers:
                for command in ('build', 'answers'):
                    with contextlib.redirect_stdout(io.StringIO()):
                        self.assertNotEqual(cli.main([command, str(source), '-o', folder]), 0)
                builder.assert_not_called()
                answers.assert_not_called()
            with self.assertRaises(ValueError):
                answer_key.meta_and_rows(source)
            with patch.object(review, 'build') as builder, self.assertRaises(ValueError):
                review.review([str(source)], folder)
            builder.assert_not_called()


class HwpxTests(unittest.TestCase):
    def test_score_stays_with_prompt_ending(self):
        _, questions = parse_md.parse(question())
        q = questions[0]
        q['ask'] = '옳은 것은?  '
        for three in (False, True):
            q['three'] = three
            xml = build.build_question(q, None)
            wrapped = etree.fromstring(('<root xmlns:hp="urn:hp">' + xml + '</root>').encode())
            text = ''.join(wrapped.itertext())
            self.assertEqual('[3점]' in text, three)
            if three:
                self.assertIn('것은?\u00a0[3점]', text)
                self.assertNotIn('것은? \u00a0', text)

    def test_cover_centers_box_without_leading_padding(self):
        ns = dict(build_cover.NS, hh='http://www.hancom.co.kr/hwpml/2011/head')
        with tempfile.TemporaryDirectory() as folder:
            for phrase in (None, '함께 배우며 자란다'):
                source = Path(folder) / 'cover.md'
                text = question()
                if phrase:
                    text = text.replace('title: current', 'title: current\nhandwriting: ' + phrase)
                source.write_text(text, encoding='utf-8')
                output = build_cover.make_hwpx(source, Path(folder) / 'cover.hwpx')
                with ZipFile(output) as archive:
                    section = etree.fromstring(archive.read('Contents/section0.xml'))
                    header = etree.fromstring(archive.read('Contents/header.xml'))
                    target = phrase or build_cover.DEFAULT_HANDWRITING
                    t = next(t for t in section.findall('.//hp:t', ns) if ''.join(t.itertext()) == target)
                    box = next(t.iterancestors(f'{{{build_cover.HP}}}rect'))
                    paragraph = box.getparent().getparent()
                    style = next(p for p in header.findall('.//hh:paraPr', ns)
                                 if p.get('id') == paragraph.get('paraPrIDRef'))
                    self.assertEqual(style.find('hh:align', ns).get('horizontal'), 'CENTER')
                    self.assertEqual(''.join(paragraph.xpath('./hp:run/hp:t/text()', namespaces=ns)), '')
                    self.assertEqual(box.find('hp:sz', ns).get('width'), '28826')
                    self.assertEqual(box.find('hp:pos', ns).get('treatAsChar'), '1')

    def test_widows_reports_isolated_score(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'score.pdf'
            with fitz.open() as doc:
                doc.new_page().insert_text((72, 72), 'A long question ending here?\n[3점]', fontname='korea')
                doc.save(path)
            output = io.StringIO()
            with patch.object(sys, 'argv', ['widows.py', str(path)]), contextlib.redirect_stdout(output):
                runpy.run_path(str(ROOT / 'tools/widows.py'), run_name='__main__')
            self.assertIn('[3점]', output.getvalue())

    def test_dialog_keeps_unattributed_lines(self):
        _, questions = parse_md.parse(question(extra='::: dialog\n갑: 앞\n(중략)\n을: 뒤\n:::'))
        pairs = questions[0]['blocks'][0][1]
        self.assertEqual(pairs, [('갑', '앞'), ('', '(중략)'), ('을', '뒤')])
        xml = hwpx.dialog(pairs)
        self.assertIn('(중략)', xml)
        self.assertNotIn('@c ', xml)

    def test_fraction_choices_have_room(self):
        xml = hwpx.choices10([r'$\frac{1}{2}$', '2', '3', '4', '5'])
        wrapped = etree.fromstring(('<root xmlns:hp="urn:hp">' + xml + '</root>').encode())
        cells = wrapped.findall('.//{urn:hp}cellSz')
        self.assertTrue(all(int(cell.get('height')) >= 2580 for cell in cells))

    def test_real_package_escapes_metadata(self):
        meta, questions = parse_md.parse(question())
        meta.update(exam='R&E <탐구>', subject=r'&연구\1', area='수학 & 과학')
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / 'metadata.hwpx'
            build.build(meta, questions, str(output))
            with ZipFile(output) as archive:
                for name in archive.namelist():
                    if name.endswith(('.xml', '.hpf')):
                        etree.fromstring(archive.read(name))
                section = etree.fromstring(archive.read('Contents/section0.xml'))
                text = ''.join(section.itertext())
                self.assertIn(meta['exam'], text)
                self.assertIn(meta['subject'], text)
                self.assertIn(meta['area'], text)


class ConversionTests(unittest.TestCase):
    def run_conversion(self, folder, save):
        hwp = Mock()
        hwp.RegisterModule.return_value = True
        hwp.Open.return_value = True
        hwp.PageCount = 4
        hwp.SaveAs.side_effect = save
        client = types.ModuleType('win32com.client')
        client.gencache = types.SimpleNamespace(EnsureDispatch=lambda *args: hwp)
        package = types.ModuleType('win32com')
        package.client = client
        modules = {'win32com': package, 'win32com.client': client}
        with patch.dict(sys.modules, modules):
            try:
                return convert._convert_inproc(str(folder / 'input.hwpx'),
                    str(folder / 'paper.hwp'), str(folder / 'paper.pdf'))
            finally:
                hwp.Quit.assert_called_once()

    def test_failed_second_save_preserves_both_outputs(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            for suffix in ('hwp', 'pdf'):
                (folder / ('paper.' + suffix)).write_bytes(b'old')
            def save(path, fmt, options):
                if fmt == 'PDF':
                    return False
                Path(path).write_bytes(b'new')
                return True
            with self.assertRaises(RuntimeError):
                self.run_conversion(folder, save)
            self.assertEqual((folder / 'paper.hwp').read_bytes(), b'old')
            self.assertEqual((folder / 'paper.pdf').read_bytes(), b'old')
            self.assertEqual(list(folder.glob('.examkit-*')), [])

    def test_success_requires_nonempty_output(self):
        for mode in ('missing', 'empty', 'valid'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                def save(path, fmt, options):
                    if mode != 'missing':
                        Path(path).write_bytes(b'new' if mode == 'valid' else b'')
                    return True
                if mode == 'valid':
                    self.assertEqual(self.run_conversion(folder, save), {'pages':4, 'hwp':True, 'pdf':True})
                    self.assertEqual((folder / 'paper.pdf').read_bytes(), b'new')
                else:
                    with self.assertRaises(RuntimeError):
                        self.run_conversion(folder, save)


class FinalAssemblyTests(unittest.TestCase):
    def test_selects_current_title_with_or_without_reuse(self):
        for reuse in (False, True):
            with self.subTest(reuse=reuse), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                md = base / '1교시.md'
                md.write_text(question(), encoding='utf-8')
                out = base / 'out'
                folder = out / '_build/1'
                folder.mkdir(parents=True)
                pdf(folder / 'AAA_old.pdf', 'OLD')
                current = folder / 'current.pdf'
                if reuse:
                    pdf(current, 'CURRENT')
                calls = []
                def run(args, **kwargs):
                    calls.append(args)
                    if 'build' in args:
                        pdf(current, 'CURRENT')
                    return types.SimpleNamespace(returncode=0)
                fake_answers = types.SimpleNamespace(meta_and_rows=lambda p: ({'title':'current'}, []),
                    page=lambda doc, *args: doc.new_page().insert_text((72,72), 'ANSWER'))
                fake_key = types.SimpleNamespace(build=lambda *args: (pdf(text='EXPLANATION'), []))
                args = ['build_final.py', str(out), str(md), '--no-cover'] + (['--reuse'] if reuse else [])
                with patch.object(build_final.subprocess, 'run', side_effect=run), \
                     patch.dict(sys.modules, {'answer_key':fake_answers, 'build_key':fake_key}), \
                     patch.object(sys, 'argv', args), contextlib.redirect_stdout(io.StringIO()):
                    build_final.main()
                self.assertEqual(any('build' in call for call in calls), not reuse)
                with fitz.open(out / '원본 문제.pdf') as merged:
                    self.assertEqual(merged[0].get_text().strip(), 'CURRENT')

    def test_missing_current_pdf_is_not_replaced_by_old_one(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            md = base / '1교시.md'; md.write_text(question(), encoding='utf-8')
            out = base / 'out'; folder = out / '_build/1'; folder.mkdir(parents=True)
            pdf(folder / 'old.pdf', 'OLD')
            with patch.object(build_final.subprocess, 'run'), \
                 patch.object(sys, 'argv', ['build_final.py', str(out), str(md), '--no-cover']), \
                 self.assertRaises(FileNotFoundError):
                build_final.main()
            self.assertFalse((out / '원본 문제.pdf').exists())


if __name__ == '__main__':
    unittest.main()
