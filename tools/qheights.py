"""빌드한 PDF에서 문항별 높이(실제 크기 mm)와 4쪽에 들어가는지를 출력한다. 쪽수 맞추기용.
  python tools/qheights.py "output/fit/3교시 인곽 문화.pdf"
문항 높이 = 다음 문항 시작까지(같은 단) 또는 단의 글·그림 끝까지. 단 높이는 1쪽 약 295mm, 2쪽부터 약 327mm.
"""
import re, sys
import numpy as np
import pymupdf

SCALE = 0.754
MM = 25.4 / 72 / SCALE                           # PDF pt → 실제 크기 mm
d = pymupdf.open(sys.argv[1])
items = []                                       # (번호, 높이mm)
for i, p in enumerate(d):
    W, H = p.rect.width, p.rect.height
    pix = p.get_pixmap(dpi=72)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w, pix.n)[:, :, :3].min(axis=2) < 200
    starts = {'L': [], 'R': []}
    for b in p.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = ''.join(s['text'] for s in l['spans']).strip()
            x0, y0, x1, y1 = l['bbox']
            if y0 < 60 or y1 > H - 45: continue
            side = 'L' if x0 < W / 2 else 'R'
            m = re.match(r'^(\d{1,2})\.\s', t + ' ')
            if m and x0 - (0 if side == 'L' else W / 2) < 60:
                starts[side].append((int(m.group(1)), y0))
    for side, x0, x1 in (('L', 30, pix.w // 2 - 8), ('R', pix.w // 2 + 8, pix.w - 30)):
        rows = np.where(a[60:pix.h - 60, x0:x1].sum(axis=1) > 0)[0]
        end = 60 + (rows.max() if len(rows) else 0)
        st = sorted(starts[side], key=lambda s: s[1])
        for k, (n, y) in enumerate(st):
            nxt = st[k + 1][1] if k + 1 < len(st) else end + 6
            items.append((n, (nxt - y) * MM))
items.sort()
cap = [295, 295] + [327] * 6
print(' '.join('%d:%.0f' % (n, h) for n, h in items))
print('합계 %.0fmm / 4쪽 용량 %dmm' % (sum(h for _, h in items), sum(cap)))
# 앞에서부터 단에 채워 넣으면 몇 단이 필요한지
col, used, out = 0, 0, [[]]
for n, h in items:
    c = cap[col] if col < len(cap) else 327
    if used + h > c and used > 0:
        col += 1; used = 0; out.append([])
    used += h; out[-1].append(n)
print('필요한 단 %d개(8단이면 4쪽):' % len(out), ' | '.join(','.join(map(str, c)) for c in out))
