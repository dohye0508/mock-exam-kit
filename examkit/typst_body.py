"""Build Markdown question data with the existing original-font Typst engine."""
import json
import os
import re
from pathlib import Path
import subprocess
import sys
import tempfile

from .typst_runtime import compile_pdf, engine_root

REVIEW_COLORS = {'keep': '#D62718', 'mod': '#12884A', 'new': '#1E5BD8'}


def build(meta, questions, destination, template='kice-sci', *, no_compile=False, review=False):
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not questions:
        raise ValueError('출력할 문항이 없습니다.')
    profile = meta.get('body_template', {'kice-sci': 'science', 'kice-social': 'social'}.get(template, template))
    if profile not in ('science', 'social'):
        raise ValueError('현재 MD 연결은 science(과탐), social(사탐) 본문 양식을 지원합니다.')
    engine = engine_root()
    root = Path(os.path.commonpath([engine, destination.parent]))
    source = destination.with_suffix('.typ')
    assets = destination.with_suffix('.assets')
    assets.mkdir(exist_ok=True)
    request = dict(meta=meta, questions=questions, profile=profile, review=review,
                   engine=str(engine), root=str(root), output=str(source), assets=str(assets))
    with tempfile.TemporaryDirectory(prefix='.body-', dir=destination.parent) as folder:
        path = Path(folder) / 'request.json'
        path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8')
        process = subprocess.run([sys.executable, '-X', 'utf8', str(Path(__file__).with_name('_typst_engine.py')), str(path)],
                                 capture_output=True, text=True, encoding='utf-8', timeout=240)
        if process.returncode:
            raise RuntimeError('Typst 본문 조판 실패 (기존 PDF 보존):\n' + process.stderr)
    manifest = json.loads((assets / 'manifest.json').read_text(encoding='utf-8'))
    expected = meta.get('pages', 'auto')
    if expected != 'auto' and manifest['pages'] != int(expected):
        raise ValueError(f'본문 {manifest["pages"]}쪽 (pages={expected}). 실제 쪽수를 설정하거나 pages: auto를 쓰세요.')
    if not no_compile:
        def validate(pdf):
            first=''.join(pdf[0].get_text().split())
            for value in (meta.get('body_title',f"{meta.get('year','2027학년도')} {meta.get('exam','모의고사')} 문제지"),
                          meta.get('area',''),meta.get('subject',''),meta.get('period','')):
                if value and ''.join(value.split()) not in first:
                    raise ValueError(f'본문 머리글 누락: {value}')
            text='\n'.join(p.get_text() for p in pdf)
            numbers={int(n) for n in re.findall(r'(?m)^\s*(\d+)\.\s',text)}
            missing={q['n'] for q in questions}-numbers
            if missing:raise ValueError(f'본문 문항 번호 누락: {sorted(missing)}')
        compile_pdf(source, destination, root=root, expected_pages=manifest['pages'], validate=validate)
    return manifest
