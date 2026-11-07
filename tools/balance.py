"""단마다 남는 아래 여백을 그 단의 문항 사이에 고르게 나눠 준다(평가원 시험지처럼 문항 아래 풀이 공간을 고르게).
빌드한 PDF에서 단별 문항과 남은 여백을 재고, 단의 마지막 문항을 뺀 문항에 {gap=N}(빈 줄 1개 = 약 2.47mm)을 더한다.
  python tools/balance.py "output/fit/2교시 인곽 생활.pdf" content/2교시.md          # 제안만 출력
  python tools/balance.py "output/fit/2교시 인곽 생활.pdf" content/2교시.md --apply  # md에 반영
  python tools/balance.py ... --bottom --apply   # 남는 자리를 문항 사이에 모두 써서 단 아래 모서리까지 채운다(--keep N: 아래에 남길 mm)
반영한 뒤에는 다시 빌드해 쪽수와 단 배치가 그대로인지 확인한다.
"""
import re
import sys

import numpy as np
import pymupdf

SCALE = 0.754          # PDF(A4)는 8절의 약 0.754배
LINE_MM = 2.47         # 빈 문단 1개(5pt, 줄 간격 140%)의 실제 높이
SAFETY_MM = 12         # 다음 문항이 넘어가지 않도록 남겨 둘 여백(작으면 단이 밀린다)
BOTTOM_MM = 21         # --bottom: 쪽 번호 위까지의 여백 재기에서 실제로 비는 자리가 거의 없을 때의 값


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
        # 단 구분선·쪽 번호 상자 같은 선을 잉크로 세지 않도록 글과 그림의 실제 범위로 잰다
        scale = W * 25.4 / 72 / 272.0            # 8절(가로 272mm) 그대로면 1, A4로 줄였으면 약 0.77
        foot = H - 52
        items = [(b[0], b[1], b[2], b[3]) for b in p.get_text("blocks")]
        items += [tuple(im["bbox"]) for im in p.get_image_info()]
        for side, x0, x1 in (("L", 0, W / 2), ("R", W / 2, W)):
            ys = [y1 for (a, y0, c, y1) in items if a >= x0 - 2 and c <= x1 + 2 and 60 < y0 and y1 < foot + 8]
            # 마지막 쪽 '확인 사항' 상자가 있으면 그 위까지만 문항 자리로 본다(상자 위 8mm쯤 남긴다)
            box = [b[1] for b in p.get_text("blocks") if b[0] >= x0 - 2 and b[2] <= x1 + 2 and "확인사항" in re.sub(r"\s", "", b[4])]
            limit = foot
            if box:
                ys = [v for v in ys if v < box[0] - 1]
                limit = box[0] + 12 * scale * 72 / 25.4
            end = max(ys) if ys else limit
            blank = max(0.0, limit - end) * 25.4 / 72 / scale
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
        if "--bottom" in sys.argv:                     # 마지막 문항이 단 아래 모서리까지 오도록 남는 자리를 문항 사이에 다 쓴다
            keep = float(sys.argv[sys.argv.index("--keep") + 1]) if "--keep" in sys.argv else BOTTOM_MM
            extra = int(max(0.0, blank - keep) / (len(qs) - 1) / LINE_MM)
            new[qs[-1]] = 0
        else:
            extra = int(usable / len(qs) / LINE_MM)    # 마지막 문항 아래에도 같은 만큼 남도록 n등분
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
