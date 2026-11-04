# -*- coding: utf-8 -*-
"""python -m examkit build content/1교시.md [-o output] [--no-convert] [--only 1-10]
   python -m examkit check content/*.md
   python -m examkit answers content/*.md [-o content/answers]"""
import argparse, glob, os, sys
from .parse_md import parse, check
from .typst_body import build

MARKS = "①②③④⑤"


def write_answers(meta, qs, name, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    rows = ["| 문항 | 정답 | 배점 | 발문 |", "|---|---|---|---|"]
    for q in qs:
        ans = MARKS[q["answer"] - 1] if q["answer"] else "?"
        if "bogi" in q and q["answer"]:
            ans += " (%s)" % q["set"][q["answer"] - 1]
        rows.append("| %d | %s | %d | %s |" % (q["n"], ans, 3 if q["three"] else 2, q["head"][:40]))
    key = "".join(str(q["answer"]) for q in qs)
    title = meta.get("title", name)
    path = os.path.join(out_dir, title + " 정답.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write("# %s 정답표\n\n" % title)
        f.write("\n".join(rows))
        f.write("\n\n정답 나열: %s\n" % key)
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(prog="examkit")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="md → Typst/JSON/PDF (한글 실행 불필요)")
    b.add_argument("files", nargs="+")
    b.add_argument("-o", "--out", default="output")
    b.add_argument("-t", "--template", default="kice-sci")
    b.add_argument("--no-compile", "--no-convert", dest="no_convert", action="store_true", help="Typst 소스까지만 생성")
    b.add_argument("--only", help="문항 범위만 빌드(디버그용), 예: 1-10")
    c = sub.add_parser("check", help="문항 수·배점·정답 분포 점검")
    c.add_argument("files", nargs="+")
    k = sub.add_parser("answers", help="정답표 md 생성")
    k.add_argument("files", nargs="+")
    k.add_argument("-o", "--out", default="content/answers")
    r = sub.add_parser("review", help="정답을 @status 색으로 칠한 검토본을 만들고 한 PDF로 이어 붙임")
    r.add_argument("files", nargs="+")
    r.add_argument("-o", "--out", default="output/review")
    r.add_argument("-t", "--template", default="kice-sci")
    r.add_argument("--reuse", action="store_true", help="이미 만든 검토 PDF로 표지·병합만 다시")
    r.add_argument("--overlay", action="store_true", help="글자색 대신 PDF 위에 색 상자로 정답 표시")
    a = ap.parse_args(argv)

    files = [f for pat in a.files for f in (glob.glob(pat) or [pat])]
    if a.cmd == "review":
        from .review import review
        return review(files, a.out, a.template, reuse=a.reuse, overlay=a.overlay)
    rc = 0
    for f in files:
        with open(f, encoding="utf-8-sig") as source:
            meta, qs = parse(source.read())
        probs = check(meta, qs)
        name = os.path.splitext(os.path.basename(f))[0]
        if a.cmd == "check":
            print("%s: %s" % (name, "OK" if not probs else "; ".join(probs)))
            rc |= bool(probs)
            continue
        if probs:
            print("[오류] %s: %s" % (name, "; ".join(probs)))
            rc = 1
            continue
        if a.cmd == "answers":
            print("wrote", write_answers(meta, qs, name, a.out))
            continue
        os.makedirs(a.out, exist_ok=True)
        title = meta.get("title", name)
        if os.path.basename(title) != title or title in ('', '.', '..'):
            raise ValueError('title에는 폴더 경로가 아닌 출력 파일 이름을 적으세요.')
        if a.only:
            lo, hi = (int(x) for x in a.only.split("-"))
            selected = [dict(q) for q in qs if lo <= q['n'] <= hi]
            for q in qs:
                passage=q.get('passage')
                if passage and selected and passage['first']<selected[0]['n']<=passage['last']:
                    selected[0]['passage']=passage
            qs=selected
            title += "_%s" % a.only
            meta = meta | {'pages': 'auto'}
        pdf = os.path.join(a.out, title + ".pdf")
        result = build(meta, qs, pdf, template=a.template, no_compile=a.no_convert)
        print("built", pdf[:-4] + '.typ' if a.no_convert else pdf, "pages=", result['pages'])
    return rc


if __name__ == "__main__":
    sys.exit(main())
