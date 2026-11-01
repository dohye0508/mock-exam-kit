"""빌드한 PDF에서 문항 번호의 위치(쪽, 단, y)와 단별 글 끝 위치를 출력한다. 4쪽 맞추기용.
  python tools/qpos.py "output/fit/1교시 인곽 지리.pdf"
"""
import pymupdf, re, sys
d = pymupdf.open(sys.argv[1])
for i, p in enumerate(d):
    W, H = p.rect.width, p.rect.height
    cols = {'L': [], 'R': []}
    bottoms = {'L': 0, 'R': 0}
    for b in p.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            t = ''.join(s['text'] for s in l['spans']).strip()
            x0, y0, x1, y1 = l['bbox']
            if y0 < 60 or y1 > H - 45: continue
            side = 'L' if x0 < W / 2 else 'R'
            bottoms[side] = max(bottoms[side], y1)
            m = re.match(r'^(\d{1,2})\.\s', t + ' ')
            colx = 0 if side == 'L' else W / 2
            if m and x0 - colx < 60:
                cols[side].append((m.group(1), round(y0)))
    print(i + 1, 'H=%d' % H, {k: v for k, v in cols.items()}, {k: round(v) for k, v in bottoms.items()})
