"""단마다 남는 아래 여백을 그 단의 문항 사이에 고르게 나눠 준다(평가원 시험지처럼 문항 아래 풀이 공간을 고르게).
빌드한 PDF에서 단별 문항과 남은 여백을 재고, 단의 마지막 문항을 뺀 문항에 {gap=N}(빈 줄 1개 = 약 2.47mm)을 더한다.
  python tools/balance.py "output/fit/2교시 인곽 생활.pdf" content/2교시.md          # 제안만 출력
  python tools/balance.py "output/fit/2교시 인곽 생활.pdf" content/2교시.md --apply  # md에 반영
반영한 뒤에는 다시 빌드해 쪽수와 단 배치가 그대로인지 확인한다.
"""
import re
import sys

import numpy as np
import pymupdf

SCALE = 0.754          # PDF(A4)는 8절의 약 0.754배
LINE_MM = 2.47         # 빈 문단 1개(5pt, 줄 간격 140%)의 실제 높이
SAFETY_MM = 5          # 다음 문항이 넘어가지 않도록 남겨 둘 여백


def columns(pdf):
    """[(쪽, 단, [문항 번호...], 남은 여백 mm)]"""
    out = []
    d = pymupdf.open(pdf)
    for i, p in enumerate(d):
        W, H = p.rect.width, p.rect.height
        qs = {"L": [], "R": []}
        for b in p.get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                t = "".join(s["text"] for s in l["spans"]).strip()
                x0, y0 = l["bbox"][:2]
                side = "L" if x0 < W / 2 else "R"
                m = re.match(r"^(\d{1,2})\.\s", t + " ")
                if m and 60 < y0 < H - 45 and x0 - (0 if side == "L" else W / 2) < 60:
                    qs[side].append((y0, int(m.group(1))))
        pix = p.get_pixmap(dpi=72)
        ink = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].min(axis=2) < 200
        top, foot = 60, pix.h - 60
        for side, x0, x1 in (("L", 30, pix.w // 2 - 8), ("R", pix.w // 2 + 8, pix.w - 30)):
            rows = np.where(ink[top:foot, x0:x1].sum(axis=1) > 0)[0]
            end = top + (rows.max() if len(rows) else 0)
            blank = (foot - end) * 25.4 / 72 / SCALE
            out.append((i + 1, side, [n for _, n in sorted(qs[side])], blank))
    return out


def main():
    pdf, md = sys.argv[1], sys.argv[2]
    src = open(md, encoding="utf-8", newline="").read()
    cur = {}
    for m in re.finditer(r"^## (\d+)\.[^\r\n]*", src, re.M):
        g = re.search(r"\{gap=(\d+)\}", m.group(0))
        cur[int(m.group(1))] = int(g.group(1)) if g else 1
    new = dict(cur)
    for page, side, qs, blank in columns(pdf):
        usable = blank - SAFETY_MM
        if len(qs) < 2 or usable < LINE_MM * len(qs):
            print("%d%s %s 여백 %.0fmm — 그대로" % (page, side, qs, blank))
            continue
        extra = int(usable / len(qs) / LINE_MM)        # 마지막 문항 아래에도 같은 만큼 남도록 n등분
        for n in qs[:-1]:
            new[n] = cur[n] + extra
        print("%d%s %s 여백 %.0fmm → 문항 %s 뒤에 빈 줄 %d개(약 %.0fmm) 추가"
              % (page, side, qs, blank, qs[:-1], extra, extra * LINE_MM))
    if "--apply" in sys.argv:
        def fix(m):
            n = int(m.group(1))
            line = re.sub(r"\s*\{gap=\d+\}", "", m.group(0)).rstrip()
            return line if new[n] == 1 else "%s {gap=%d}" % (line, new[n])
        src = re.sub(r"^## (\d+)\.[^\r\n]*", fix, src, flags=re.M)
        open(md, "w", encoding="utf-8", newline="").write(src)
        print("반영:", {n: g for n, g in new.items() if g != cur[n]})


if __name__ == "__main__":
    main()
