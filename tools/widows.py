"""빌드한 PDF에서 문단 마지막 줄이 1~3글자만 남은 곳(외톨이 줄)을 찾는다.
  python tools/widows.py "output/fit/2교시 인곽 생활.pdf"
"""
import re
import sys

import pymupdf

d = pymupdf.open(sys.argv[1])
for i, p in enumerate(d):
    for b in p.get_text("dict")["blocks"]:
        lines = [("".join(s["text"] for s in l["spans"]).strip(), l["bbox"]) for l in b.get("lines", [])]
        for (prev, pb), (t, bb) in zip(lines, lines[1:]):
            core = re.sub(r"\s", "", t)
            if core == "[3점]" or (0 < len(core) <= 3 and core != "◦" and pb[2] - pb[0] > 150):
                print("%d쪽 y=%d  …%s / %s" % (i + 1, bb[1], prev[-12:], t))
