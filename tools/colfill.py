"""빌드한 PDF의 쪽·단별로 글·그림이 끝나는 위치와 남은 여백(실제 크기 mm)을 출력한다. 여백 고르게 맞추기용.
  python tools/colfill.py "output/fit/2교시 인곽 생활.pdf"
"""
import sys
import numpy as np
import pymupdf

SCALE = 0.754                                     # PDF(A4)는 8절의 약 0.754배
d = pymupdf.open(sys.argv[1])
for i, p in enumerate(d):
    pix = p.get_pixmap(dpi=72)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].min(axis=2) < 200
    W, H = pix.w, pix.h
    top, foot = 60, H - 60                         # 머리글·쪽 번호 영역 제외
    res = []
    for name, x0, x1 in (("L", 30, W // 2 - 8), ("R", W // 2 + 8, W - 30)):
        rows = np.where(a[top:foot, x0:x1].sum(axis=1) > 0)[0]
        end = top + (rows.max() if len(rows) else 0)
        res.append("%s 끝 %d / 여백 %.0fmm" % (name, end, (foot - end) * 25.4 / 72 / SCALE))
    print(i + 1, " | ".join(res))
