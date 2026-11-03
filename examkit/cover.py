"""Connect Markdown cover settings to the original-HWP Typst engine."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from .typst_runtime import compile_pdf, engine_root

DEFAULT_HANDWRITING = '필적 확인란 문구'


def cover_settings(meta):
    variant = meta.get('cover_template', 'math' if meta['area'].strip() in ('수학', '수학 영역') else 'korean')
    if variant not in ('korean', 'math'):
        raise ValueError('cover_template은 korean 또는 math여야 합니다.')
    pages = int(meta['pages'])
    if pages < 1:
        raise ValueError('pages는 1 이상이어야 합니다.')
    area = meta['area'] if meta['area'].endswith('영역') else meta['area'] + ' 영역'
    period = meta['period']
    match = re.fullmatch(r'제\s*(\d+)\s*교시', period)
    if match:
        period = '제\x1f' + match[1] + '\x1f교시'
    paragraphs = {
        '1': period, '2': meta.get('cover_title', f"{meta['year']} {meta['exam']} 문제지"),
        '5': meta.get('cover_area', area), '6': meta.get('cover_badge', ''),
        '18': meta.get('handwriting', DEFAULT_HANDWRITING),
        '20': '답안지의 해당란에 성명과 수험번호를 쓰고, 답을 정확히 표시하시오.',
    }
    score = '문항에 따라 배점이 다르니, 각 물음의 끝에 표시된 배점을 참고하시오.'
    if variant == 'korean':
        paragraphs.update({'22': score, '25': '※ 교시와 과목을 확인하고, 답을 정확히 표시하시오.',
                           '27': '○  ' + meta['subject'], '29': f'1~{pages} 쪽',
                           '47': meta.get('issuer', meta['exam'])})
        unused = ('31', '35', '36', '37', '39', '40', '41')
    else:
        paragraphs.update({'22': '각 문항에서 요구하는 방식에 따라 답을 표시하시오.', '24': score,
                           '29': '※ 교시와 과목을 확인하고, 답을 정확히 표시하시오.',
                           '31': '○  ' + meta['subject'], '33': f'1~{pages} 쪽',
                           '53': meta.get('issuer', meta['exam'])})
        unused = ('35', '39', '40', '41', '43', '44', '45', '47', '48', '49')
    paragraphs.update(dict.fromkeys(unused, ''))
    for key, value in meta.items():
        if key.startswith('cover_p'):
            if not re.fullmatch(r'cover_p\d+', key):
                raise ValueError(f'잘못된 표지 문단 설정: {key}')
            paragraphs[key[7:]] = value.replace('\\n', '\n')
    return dict(variant=variant, paragraphs=paragraphs)


def validate_cover(doc, meta):
    if len(doc) != 1:
        raise ValueError('Cover must be exactly one page')
    compact = re.sub(r'\s+', '', doc[0].get_text())
    for value in cover_settings(meta)['paragraphs'].values():
        if value and re.sub(r'\s+', '', value) not in compact:
            raise ValueError(f'Cover text missing: {value}')


def build_cover(meta, destination, *, no_compile=False):
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    engine = engine_root()
    # Typst imports must share a root; no font or engine copies enter this repository.
    root = Path(os.path.commonpath([engine, destination.parent]))
    source = destination.with_suffix('.typ')
    commands = destination.with_suffix('.json')
    with tempfile.TemporaryDirectory(prefix='.cover-', dir=destination.parent) as folder:
        request = Path(folder) / 'settings.json'
        exported = Path(folder) / 'commands.json'
        request.write_text(json.dumps(cover_settings(meta), ensure_ascii=False), encoding='utf-8')
        result = subprocess.run([sys.executable, '-X', 'utf8', str(engine / 'scripts/cover.py'),
                                 str(request), '--export-json', str(exported)],
                                capture_output=True, text=True, encoding='utf-8', timeout=120)
        if result.returncode:
            raise RuntimeError(f'표지 조판 실패 (기존 PDF 보존):\n{result.stderr}')
        data = json.loads(exported.read_text(encoding='utf-8'))
        header = Path(os.path.relpath(engine / 'original-header.typ', source.parent)).as_posix()
        text = (f'#import {json.dumps(header)}: source-commands\n'
                f'#let cover = json({json.dumps(commands.name, ensure_ascii=False)})\n'
                '#set page(width: cover.width / 100 * 1pt, height: cover.height / 100 * 1pt, margin: 0pt)\n'
                '#source-commands(cover.commands)\n')
        assert data['commands'] and data['width'] > 0 and data['height'] > 0
        os.replace(exported, commands)
        source.write_text(text, encoding='utf-8')
    if not no_compile:
        compile_pdf(source, destination, root=root, expected_pages=1, validate=lambda pdf: validate_cover(pdf, meta))
    return source if no_compile else destination
