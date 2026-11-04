"""Invoke Typst with the original-font engine supplied by EXAMKIT_TYPST_ROOT."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pymupdf


def engine_root():
    root = Path(os.environ.get('EXAMKIT_TYPST_ROOT') or Path(__file__).resolve().parents[1] / 'runtime').expanduser().resolve()
    if not (root / 'scripts/compose.py').is_file() or not (root / 'fonts').is_dir():
        raise RuntimeError('EXAMKIT_TYPST_ROOT를 우리가 만든 조판 시스템 폴더로 지정하세요 (scripts/compose.py, fonts/ 필요).')
    return root


def executable():
    bundled=engine_root() / 'bin' / ('typst.exe' if os.name=='nt' else 'typst')
    path = os.environ.get('TYPST_EXE') or shutil.which('typst') or str(bundled)
    if not path or not Path(path).is_file():
        raise RuntimeError('Typst를 PATH에 추가하거나 TYPST_EXE를 실행 파일로 지정하세요.')
    return path


def compile_pdf(source, destination, *, root=None, expected_pages=None, validate=None):
    """Validate a temporary PDF before replacing the last successful output."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.typst-', dir=destination.parent) as work:
        temporary = Path(work) / 'result.pdf'
        command = [executable(), 'compile', str(source), str(temporary),
                   '--root', str(root or source.parent), '--font-path', str(engine_root() / 'fonts'),
                   '--ignore-system-fonts', '--ignore-embedded-fonts', '--diagnostic-format', 'short']
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', timeout=180)
        if result.returncode or result.stderr.strip():
            raise RuntimeError(f'Typst 출력 실패 (기존 PDF 보존):\n{result.stderr}')
        with pymupdf.open(temporary) as pdf:
            count = len(pdf)
            if expected_pages is not None and count != expected_pages:
                raise ValueError(f'PDF 쪽수: {count}, 기대: {expected_pages}')
            if validate is not None:
                validate(pdf)
        os.replace(temporary, destination)
    return count
