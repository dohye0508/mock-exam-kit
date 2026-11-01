"""최종본 한 벌을 한 번에 만든다: 원본 문제 합본, 정답표, 정답 및 해설.
  python tools/build_final.py ishs/pdf                      # content/1~4교시.md 전부
  python tools/build_final.py out content/3교시.md content/4교시.md   # 일부 교시만
필요: 한글(Hancom) 변환 환경(AGENTS.md 10장). 시험지 변환이 오래 걸리니 이미 빌드한 PDF를 쓰려면 --reuse.
출력: <out>/원본 문제.pdf, <out>/정답표.pdf, <out>/정답 및 해설.pdf (각 교시 시험지는 <out>/_build/에 남는다)
"""
import glob, os, subprocess, sys
import pymupdf as fitz

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))


def main():
    args = sys.argv[1:]
    reuse = "--reuse" in args
    args = [a for a in args if a != "--reuse"]
    out = args[0]
    mds = args[1:] or sorted(glob.glob(os.path.join(ROOT, "content", "[0-9]교시.md")))
    os.makedirs(out, exist_ok=True)
    pdfs = []
    for md in mds:
        n = os.path.basename(md)[0]
        d = os.path.join(out, "_build", n)
        found = glob.glob(os.path.join(d, "*.pdf"))
        if not (reuse and found):
            subprocess.run([sys.executable, "-m", "examkit", "build", md, "-o", d], cwd=ROOT, check=True)
            found = glob.glob(os.path.join(d, "*.pdf"))
        pdfs.append(found[0])
    book = fitz.open()
    for p in pdfs:
        book.insert_pdf(fitz.open(p))
    book.save(os.path.join(out, "원본 문제.pdf"))
    print("원본 문제.pdf", book.page_count, "쪽")
    import answer_key, build_key
    doc = fitz.open()
    for md in mds:
        answer_key.page(doc, *answer_key.meta_and_rows(md))
    doc.save(os.path.join(out, "정답표.pdf"))
    print("정답표.pdf", doc.page_count, "쪽")
    kdoc, problems = build_key.build(None, mds)
    kdoc.save(os.path.join(out, "정답 및 해설.pdf"))
    print("정답 및 해설.pdf", kdoc.page_count, "쪽")
    for p in problems:
        print("[경고]", p)


if __name__ == "__main__":
    main()
