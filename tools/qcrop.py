"""PDF에서 문항별 영역을 실제 8절 크기 기준 dpi로 잘라 낸다. python qcrop.py <pdf> <outdir> <dpi> n1 n2 ..."""
import pymupdf, re, os, sys
pdf, outdir, dpi = sys.argv[1], sys.argv[2], float(sys.argv[3])
want = set(int(x) for x in sys.argv[4:])
os.makedirs(outdir, exist_ok=True)
zoom = dpi / 72 / 0.754
d = pymupdf.open(pdf)
starts = []
for pi, p in enumerate(d):
    W, H = p.rect.width, p.rect.height
    for b in p.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = ''.join(s['text'] for s in l['spans']).strip(); x0, y0, x1, y1 = l['bbox']
            if y0 < 60 or y1 > H - 45: continue
            col = 0 if x0 < W / 2 else 1
            m = re.match(r'^(\d{1,2})\.\s', t + ' ')
            if m and x0 - col * W / 2 < 60: starts.append((int(m.group(1)), pi, col, y0))
order = sorted(starts, key=lambda s: (s[1], s[2], s[3]))
for k, (n, pi, col, y) in enumerate(order):
    if want and n not in want: continue
    p = d[pi]; W, H = p.rect.width, p.rect.height
    nxt = order[k + 1] if k + 1 < len(order) else None
    yend = nxt[3] - 4 if nxt and nxt[1] == pi and nxt[2] == col else H - 45
    clip = pymupdf.Rect(col * W / 2 + 4, y - 4, (col + 1) * W / 2 - 4, yend)
    p.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), clip=clip).save(os.path.join(outdir, 'q%02d.png' % n))
print('ok', len(order))
