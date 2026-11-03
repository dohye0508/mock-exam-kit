"""원본 HWP에서 가져온 양식으로 Typst 표지를 만들고 본문 앞에 붙인다.

python tools/build_cover.py output/covers content/example.md
python tools/build_cover.py output/covers --no-compile content/example.md
"""
import argparse
from pathlib import Path
import sys

import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from examkit.parse_md import parse_front_matter
from examkit.cover import build_cover, validate_cover


def metadata(md):
    meta, _ = parse_front_matter(Path(md).read_text(encoding='utf-8-sig'))
    for key in ('year', 'exam', 'period', 'area', 'subject', 'pages'):
        if not meta.get(key):
            raise ValueError(f'{md}: missing {key}')
    return meta


def build(mds, directory, no_convert=False, page_counts=None):
    directory = Path(directory).resolve()
    mds = list(mds)
    if not mds or len({Path(md).stem.casefold() for md in mds}) != len(mds):
        raise ValueError('표지 입력 MD가 없거나 파일 이름이 중복됩니다.')
    directory.mkdir(parents=True, exist_ok=True)
    pdfs = []
    if page_counts is not None and len(page_counts) != len(mds):
        raise ValueError('본문 쪽수와 표지 입력 수가 다릅니다.')
    for index, md in enumerate(mds):
        meta = metadata(md)
        if meta['pages'] == 'auto' and page_counts is not None:
            meta['pages'] = str(page_counts[index])
        path = build_cover(meta, directory / f'{Path(md).stem}_표지.pdf', no_compile=no_convert)
        print(f'Cover: {path.name}', flush=True)
        if not no_convert:
            pdfs.append(path)
    if pdfs:
        with fitz.open() as combined:
            for pdf in pdfs:
                with fitz.open(pdf) as doc:
                    combined.insert_pdf(doc)
            combined.save(directory / '교시별_표지.pdf', garbage=4, deflate=True)
    return pdfs


def assemble(pdfs, covers, mds):
    """Keep body pages untouched; uniformly fit each cover to its body paper size."""
    if not (len(pdfs) == len(covers) == len(mds)):
        raise ValueError('Body/cover/metadata counts differ')
    book = fitz.open()
    toc = []
    for pdf, cover, md in zip(pdfs, covers, mds):
        meta = metadata(md)
        with fitz.open(pdf) as body, fitz.open(cover) as front:
            if meta['pages'] == 'auto': meta['pages'] = str(len(body))
            if len(body) != int(meta['pages']):
                raise ValueError(f'{pdf}: 본문이 {len(body)}쪽인데 MD의 pages는 {meta["pages"]}입니다. 실제 쪽수에 맞게 pages를 고치거나 배치를 줄이세요(이미 표지가 붙은 PDF를 넣었는지도 확인)')
            validate_cover(front, meta)
            toc.append([1, f"{meta['period']} {meta['subject']}", len(book) + 1])
            rect = body[0].rect
            page = book.new_page(width=rect.width, height=rect.height)
            page.show_pdf_page(page.rect, front, 0, keep_proportion=True)
            book.insert_pdf(body)
    book.set_toc(toc)
    book.set_metadata({'title': '교시별 표지가 포함된 문제지', 'creator': 'mock-exam-kit/build_cover.py'})
    return book


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output')
    parser.add_argument('mds', nargs='*')
    parser.add_argument('--no-compile', '--no-convert', dest='no_compile', action='store_true',
                        help='Typst/JSON만 생성하고 PDF 컴파일 생략 (--no-convert는 호환 별칭)')
    args = parser.parse_intermixed_args()
    mds = args.mds or sorted((ROOT / 'content').glob('[1-4]교시.md'))
    build(mds, args.output, args.no_compile)


if __name__ == '__main__':
    main()
