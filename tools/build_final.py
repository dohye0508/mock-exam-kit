"""최종본 한 벌을 한 번에 만든다: 원본 문제 합본, 정답표, 정답 및 해설.
  python tools/build_final.py ishs/pdf                      # content/1~4교시.md 전부
  python tools/build_final.py out content/3교시.md content/4교시.md   # 일부 교시만
필요: Typst 및 원본 조판 엔진/글꼴(docs/typst-migration.md). 기존 PDF를 명시적으로 재사용하려면 --reuse.
출력: <out>/원본 문제.pdf(교시별 표지 포함), <out>/정답표.pdf, <out>/정답 및 해설.pdf, <out>/교시별/<교시>{, 정답표, 정답 및 해설}.pdf
본문은 <out>/_build/, 편집 가능한 표지는 <out>/_covers/에 남는다. --no-cover로 표지만 생략할 수 있다.
"""
import glob, os, subprocess, sys
import pymupdf as fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from examkit.parse_md import parse_front_matter


def main():
    args = sys.argv[1:]
    reuse = "--reuse" in args
    no_cover = "--no-cover" in args
    args = [a for a in args if a not in ("--reuse", "--no-cover")]
    out = os.path.abspath(args[0])
    mds = [os.path.abspath(md) for md in (args[1:] or sorted(glob.glob(os.path.join(ROOT, "content", "[0-9]교시.md"))))]
    os.makedirs(out, exist_ok=True)
    # 한 번에 끝나도록 문항 검사부터 같은 명령 안에서 한다(실패하면 여기서 멈춤)
    subprocess.run([sys.executable, "-X", "utf8", "-m", "examkit", "check", *mds], cwd=ROOT, check=True)
    pdfs = []
    for md in mds:
        n = os.path.basename(md)[0]
        d = os.path.join(out, "_build", n)
        with open(md, encoding="utf-8") as source:
            meta, _ = parse_front_matter(source.read())
        title = meta.get("title", os.path.splitext(os.path.basename(md))[0])
        pdf = os.path.join(d, title + ".pdf")
        if not (reuse and os.path.isfile(pdf)):
            subprocess.run([sys.executable, "-X", "utf8", "-m", "examkit", "build", md, "-o", d], cwd=ROOT, check=True)
        if not os.path.isfile(pdf):
            raise FileNotFoundError("본문 PDF가 생성되지 않았습니다: %s" % pdf)
        pdfs.append(pdf)
    covers = None
    if no_cover:
        book = fitz.open()
        for p in pdfs:
            with fitz.open(p) as body:
                book.insert_pdf(body)
    else:
        import build_cover
        counts = []
        for pdf in pdfs:
            with fitz.open(pdf) as document:
                counts.append(len(document))
        covers = build_cover.build(mds, os.path.join(out, "_covers"), page_counts=counts)
        book = build_cover.assemble(pdfs, covers, mds)
    book.save(os.path.join(out, "원본 문제.pdf"), garbage=4, deflate=True)
    print("원본 문제.pdf", book.page_count, "쪽")
    import answer_key, build_key
    doc = fitz.open()
    for md in mds:
        answer_key.page(doc, *answer_key.meta_and_rows(md))
    doc.subset_fonts()
    doc.save(os.path.join(out, "정답표.pdf"), garbage=4, deflate=True)
    print("정답표.pdf", doc.page_count, "쪽")
    kdoc, problems = build_key.build(None, mds)
    kdoc.subset_fonts()
    kdoc.save(os.path.join(out, "정답 및 해설.pdf"), garbage=4, deflate=True)   # 쪽마다 넣은 글꼴을 하나로 합치고 부분 집합으로 줄인다
    print("정답 및 해설.pdf", kdoc.page_count, "쪽")
    for p in problems:
        print("[경고]", p)
    # 교시별 파일: 문제지(표지 포함)·정답표·정답 및 해설을 교시마다 따로 둔다
    sub = os.path.join(out, "교시별")
    os.makedirs(sub, exist_ok=True)
    for md, pdf in zip(mds, pdfs):
        meta, rows = answer_key.meta_and_rows(md)
        name = meta.get("title") or os.path.splitext(os.path.basename(md))[0]
        if covers is None:
            one = fitz.open(pdf)
        else:
            one = build_cover.assemble([pdf], [covers[mds.index(md)]], [md])
        one.save(os.path.join(sub, name + ".pdf"), garbage=4, deflate=True)
        k = fitz.open(); answer_key.page(k, meta, rows); k.subset_fonts()
        k.save(os.path.join(sub, name + " 정답표.pdf"), garbage=4, deflate=True)
        e, _ = build_key.build(None, [md]); e.subset_fonts()
        e.save(os.path.join(sub, name + " 정답 및 해설.pdf"), garbage=4, deflate=True)
    print("교시별/", len(mds), "교시 × 3개")


if __name__ == "__main__":
    main()
