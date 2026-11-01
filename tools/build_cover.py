"""Original HWP cover -> editable HWPX covers and PDF, one before each period.

python tools/build_cover.py output/covers content/1교시.md content/2교시.md
python tools/build_cover.py output/covers --no-convert content/1교시.md
"""
import argparse
import json
from pathlib import Path
import re
import sys
from zipfile import ZipFile

from lxml import etree as ET
import pymupdf as fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from examkit.parse_md import parse_front_matter
from examkit.convert import convert

SOURCE = ROOT / 'templates/covers/csat-2017-v2-source.hwpx'
HP = 'http://www.hancom.co.kr/hwpml/2011/paragraph'
NS = {'hp': HP}
DEFAULT_HANDWRITING = '지혜를 모아 지혜를 모아'


def metadata(md):
    meta, _ = parse_front_matter(Path(md).read_text(encoding='utf-8-sig'))
    for key in ('year', 'exam', 'period', 'area', 'subject'):
        if not meta.get(key):
            raise ValueError(f'{md}: missing {key}')
    return meta


def _text(node):
    return ''.join(node.itertext())


def _replace(section, old, new):
    matches = [t for t in section.findall('.//hp:t', NS) if _text(t) == old]
    if len(matches) != 1:
        raise ValueError(f'Cover source changed: {old!r}: {len(matches)} matches')
    t = matches[0]
    # Only the edited text content changes. Keep its run, charPr and paragraph.
    for child in list(t):
        t.remove(child)
    lines = new.split('\n')
    t.text = lines[0]
    for line in lines[1:]:
        ET.SubElement(t, f'{{{HP}}}lineBreak').tail = line
    return t


def make_hwpx(md, output):
    meta = metadata(md)
    with ZipFile(SOURCE) as source:
        section = ET.fromstring(source.read('Contents/section0.xml'))
        # Delete the odd/even badge including its rectangle, not a white overlay.
        odd = [r for r in section.findall('.//hp:rect', NS)
               if ''.join(r.xpath('.//hp:t//text()', namespaces=NS)) == '홀수형']
        if len(odd) != 1:
            raise ValueError('Cannot identify odd/even badge in original template')
        odd[0].getparent().remove(odd[0])
        period = _replace(section, '제2교시', meta['period'])
        m = re.fullmatch(r'제\s*(\d+)\s*교시', meta['period'])
        if m:
            period.text = '제'
            ET.SubElement(period, f'{{{HP}}}fwSpace').tail = m[1]
            ET.SubElement(period, f'{{{HP}}}fwSpace').tail = '교시'
        area = meta['area'] if meta['area'].endswith('영역') else meta['area'] + ' 영역'
        replacements = {
            '2017학년도 대학수학능력시험 문제지': f"{meta['year']} {meta['exam']} 문제지",
            '수학 영역': area,
            '(가 형)': f"({meta['subject']})",
            '자신이 선택한 유형(‘가’ 형/‘나’ 형)의 문제지인지 확인하시오.':
                '해당 교시와 과목의 문제지인지 확인하시오.',
            '싸우는 천사는 지금 악마가 된다': meta.get('handwriting', DEFAULT_HANDWRITING),
            '답안지의 해당란에 성명과 수험번호를 쓰고, 또 수험번호, 문형       (홀수/짝수), 답을 정확히 표시하시오.':
                '답안지의 해당란에 성명과 수험번호를 쓰고, 수험번호와\n   답을 정확히 표시하시오.',
            '단답형 답의 숫자에 ‘0’이 포함되면 그 ‘0’도 답란에 반드시 표시하시오.':
                '모든 문항은 5지선다형입니다. 각 문항의 답을 하나만 고르시오.',
            '   배점은 2점, 3점 또는 4점입니다.':
                '   배점은 2점 또는 3점입니다.',
            '한국교육과정평가원': meta.get('issuer', meta['exam']),
        }
        for old, new in replacements.items():
            _replace(section, old, new)
        # Cached line positions refer to old text. Hancom recomputes them on open.
        for cache in section.findall('.//hp:linesegarray', NS):
            cache.getparent().remove(cache)
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(output, 'w') as target:
            for info in source.infolist():
                data = source.read(info.filename)
                if info.filename == 'Contents/section0.xml':
                    data = ET.tostring(section, encoding='utf-8', xml_declaration=True, standalone=True)
                elif info.filename == 'Preview/PrvText.txt':
                    data = '\n'.join(section.xpath('.//hp:t//text()', namespaces=NS)).encode('utf-8')
                elif info.filename == 'Preview/PrvImage.png':
                    # Never show an old, unmodified preview as the generated cover.
                    continue
                target.writestr(info, data)
    return output


def build(mds, directory, no_convert=False):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    pdfs = []
    for md in mds:
        path = make_hwpx(md, directory / f'{Path(md).stem}_표지.hwpx')
        if no_convert:
            continue
        pdf = path.with_suffix('.pdf')
        result = convert(str(path), hwp_out=str(path.with_suffix('.hwp')), pdf_out=str(pdf))
        if result.get('pages') != 1 or not result.get('pdf') or not result.get('hwp'):
            raise RuntimeError(f'Cover conversion failed: {path}: {result}')
        with fitz.open(pdf) as doc:
            validate_cover(doc, metadata(md))
        pdfs.append(pdf)
        print(f'Cover: {pdf.name}', flush=True)
    if pdfs:
        with fitz.open() as combined:
            for pdf in pdfs:
                with fitz.open(pdf) as doc:
                    combined.insert_pdf(doc)
            combined.save(directory / '교시별_표지.pdf', garbage=4, deflate=True)
    return pdfs


def validate_cover(doc, meta):
    if len(doc) != 1:
        raise ValueError('Cover must be exactly one page')
    compact = re.sub(r'\s+', '', doc[0].get_text())
    for required in [meta['period'], meta['subject'], meta.get('handwriting', DEFAULT_HANDWRITING), '5지선다형']:
        if re.sub(r'\s+', '', required) not in compact:
            raise ValueError(f'Cover text missing: {required}')
    for forbidden in ['홀수', '짝수', '단답형', '주관식', '4점', '(가형)', '(나형)', '한국교육과정평가원']:
        if forbidden in compact:
            raise ValueError(f'Obsolete cover text remains: {forbidden}')


def assemble(pdfs, covers, mds):
    """Keep body pages untouched; uniformly fit each cover to its body paper size."""
    if not (len(pdfs) == len(covers) == len(mds)):
        raise ValueError('Body/cover/metadata counts differ')
    book = fitz.open()
    toc = []
    for pdf, cover, md in zip(pdfs, covers, mds):
        meta = metadata(md)
        with fitz.open(pdf) as body, fitz.open(cover) as front:
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
    parser.add_argument('--no-convert', action='store_true')
    args = parser.parse_intermixed_args()
    mds = args.mds or sorted((ROOT / 'content').glob('[1-4]교시.md'))
    build(mds, args.output, args.no_convert)


if __name__ == '__main__':
    main()
