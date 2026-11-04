"""md의 @answer와 [3점]으로 평가원 양식 정답표 PDF를 만든다(교시마다 한 쪽, 문항번호·정답·배점 5행×4묶음).
  python tools/answer_key.py out.pdf content/1교시.md content/2교시.md ...
제목의 연도·시험 이름·영역은 md 머리(year, exam, area, subject)에서 읽는다.
"""
import os, sys
import pymupdf as fitz

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from examkit.parse_md import parse, check

CIRC = "①②③④⑤"


def meta_and_rows(path):
    s = open(path, encoding="utf8").read()
    meta, questions = parse(s)
    problems = check(meta, questions)
    if problems:
        raise ValueError("%s: %s" % (path, "; ".join(problems)))
    rows = [(q["n"], CIRC[q["answer"] - 1], 3 if q["three"] else 2) for q in questions]
    return meta, sorted(rows)


def page(doc, meta, rows):
    from examkit.typst_runtime import engine_root
    font_path=str(engine_root()/'fonts/Batang-native.ttf')
    pg = doc.new_page(width=595, height=842)
    pg.insert_font(fontname="bt", fontfile=font_path)
    font = fitz.Font(fontfile=font_path)

    def ct(x, y, t, size):
        pg.insert_text((x - font.text_length(t, fontsize=size) / 2, y), t, fontname="bt", fontsize=size)

    ct(297.5, 115, "%s %s" % (meta.get("year", ""), meta.get("exam", "")), 12)
    area = meta.get("area", "탐구")
    ct(297.5, 150, "%s 정답표" % (area if area.endswith("영역") else area + " 영역"), 17)
    ct(297.5, 178, "(  %s )과목" % meta.get("subject", ""), 17)
    x0, y0, cw, hh, rh = 90, 215, [35, 33, 33], 34, 40
    gw = sum(cw); W = gw * 4; H = hh + 5 * rh
    for g in range(4):
        cx = x0 + g * gw
        for j, h in enumerate((("문항", "번호"), ("정 답",), ("배 점",))):
            mid = cx + cw[j] / 2
            if len(h) == 2:
                ct(mid, y0 + 15, h[0], 8.5); ct(mid, y0 + 26, h[1], 8.5)
            else:
                ct(mid, y0 + 21, h[0], 8.5)
            cx += cw[j]
        for r in range(5):
            if g * 5 + r >= len(rows):
                break
            n, a, pt = rows[g * 5 + r]
            cx = x0 + g * gw
            for j, t in enumerate((str(n), a, str(pt))):
                ct(cx + cw[j] / 2, y0 + hh + r * rh + rh / 2 + 3.5, t, 10); cx += cw[j]
    pg.draw_rect(fitz.Rect(x0, y0, x0 + W, y0 + H), width=1.2)
    for r in range(5):
        pg.draw_line((x0, y0 + hh + r * rh), (x0 + W, y0 + hh + r * rh), width=0.6)
    cx = x0
    for g in range(4):
        for j in range(3):
            cx += cw[j]
            if cx < x0 + W - 0.1:
                pg.draw_line((cx, y0), (cx, y0 + H), width=1.2 if j == 2 else 0.6)


if __name__ == "__main__":
    doc = fitz.open()
    for md in sys.argv[2:]:
        page(doc, *meta_and_rows(md))
    doc.subset_fonts()
    doc.save(sys.argv[1], garbage=4, deflate=True)
    print(sys.argv[1], doc.page_count, "쪽")
