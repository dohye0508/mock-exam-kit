"""기출 참고 이미지에서 삽화(인물·장면 그림)가 들어 있을 법한 문항을 골라 썸네일 시트로 만든다.

보조 수단일 뿐이다. 점수가 높아도 지도·사진일 수 있으니 시트를 눈으로 보고 고른다.
  python tools/find_illust.py assets/reference/tongsarang/생활과윤리 -n 96 -o output/illust_sheets
"""
import argparse, glob, os
from PIL import Image, ImageDraw, ImageFilter
import numpy as np


def score(path):
    """큰 비텍스트 영역 안의 '그림 같은' 정도. 글줄은 가로로 촘촘하고, 선화는 곡선·사선이 많다."""
    im = Image.open(path).convert("L")
    w = 600
    im = im.resize((w, max(1, int(im.height * w / im.width))))
    a = np.asarray(im, dtype=np.float32)
    ink = a < 200
    # 회색 톤(명암) 비율: 선화 삽화는 회색 칠이 조금 있다
    mid = ((a > 90) & (a < 225)).mean()
    # 세로·가로 기울기 비율: 글자는 가로·세로 획, 그림은 사선·곡선이 많다
    gx = np.abs(np.diff(a, axis=1))[:-1, :]
    gy = np.abs(np.diff(a, axis=0))[:, :-1]
    edges = (gx + gy) > 60
    diag = (np.minimum(gx, gy) > 25) & edges
    diag_ratio = diag.sum() / max(1, edges.sum())
    # 큰 덩어리: 60×60 칸 중 잉크가 있으면서 글줄 패턴(행별 잉크 띠)이 약한 칸
    blocks = 0
    for y in range(0, a.shape[0] - 60, 30):
        for x in range(0, a.shape[1] - 60, 30):
            b = ink[y:y + 60, x:x + 60]
            if 0.04 < b.mean() < 0.5:
                rows = b.mean(axis=1)
                if (rows > 0.02).mean() > 0.8:  # 거의 모든 행에 잉크 → 글줄 사이 여백이 없음 → 그림
                    blocks += 1
    return diag_ratio * 2 + mid * 3 + blocks / 60


def sheet(paths, out, cols=8, tw=300):
    tiles = []
    for p in paths:
        im = Image.open(p).convert("RGB")
        im.thumbnail((tw, tw))
        t = Image.new("RGB", (tw, tw + 18), "white")
        t.paste(im, ((tw - im.width) // 2, 0))
        ImageDraw.Draw(t).text((4, tw + 2), os.path.basename(p)[:-4], fill="black")
        tiles.append(t)
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new("RGB", (cols * tw, rows * (tw + 18)), "white")
    for i, t in enumerate(tiles):
        s.paste(t, ((i % cols) * tw, (i // cols) * (tw + 18)))
    s.save(out, quality=80)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("-n", type=int, default=96)
    ap.add_argument("-o", "--out", default="output/illust_sheets")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    files = [f for d in a.dirs for f in glob.glob(os.path.join(d, "**", "*.jpg"), recursive=True) if os.path.getsize(f) > 1000]
    scored = sorted(((score(f), f) for f in files), reverse=True)[:a.n]
    with open(os.path.join(a.out, "ranking.txt"), "w", encoding="utf-8") as fh:
        for s, f in scored:
            fh.write("%.3f\t%s\n" % (s, f))
    for i in range(0, len(scored), 32):
        sheet([f for _, f in scored[i:i + 32]], os.path.join(a.out, "sheet_%02d.jpg" % (i // 32)))
    print(len(files), "files scored;", len(scored), "in sheets ->", a.out)


if __name__ == "__main__":
    main()
