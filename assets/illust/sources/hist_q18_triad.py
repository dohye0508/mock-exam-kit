# -*- coding: utf-8 -*-
"""4교시 18번 3주체 관계도(삼권 분립 도식처럼). 흑백, 600dpi, 흰 배경.
지면 실제 크기(mm)로 그리므로 글자 크기(pt)가 그대로 지면 크기다(8pt 이상).
교원(위)·학생(왼쪽 아래)·학부모(오른쪽 아래), 화살표 (가)~(라).
  (가) 학생 -> 교원, (나) 교원 -> 학생, (다) 학부모 -> 교원, (라) 교원 -> 학부모
python hist_q18_triad.py <출력 png>"""
import sys
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.patches import FancyBboxPatch

FONT = None
for name in ("Malgun Gothic", "맑은 고딕"):
    if name in {f.name for f in font_manager.fontManager.ttflist}:
        FONT = name
        break
rcParams["font.family"] = FONT
rcParams["axes.unicode_minus"] = False

FS = 8.5
LW = 0.6          # 상자 선
AW = 0.75         # 화살표 선
M = 0.5
W, H = 66.0, 33.0
BW, BH = 24.0, 6.6    # 상자 크기(mm)

boxes = {
    "교원": (W / 2, H - M - BH / 2),
    "학생": (M + BW / 2, M + BH / 2),
    "학부모": (W - M - BW / 2, M + BH / 2),
}
labels = {"교원": "교원(학교장)", "학생": "학생(학생회)", "학부모": "학부모(학부모회)"}

fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=600)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")

for k, (cx, cy) in boxes.items():
    ax.add_patch(FancyBboxPatch((cx - BW / 2, cy - BH / 2), BW, BH,
                                boxstyle="round,pad=0,rounding_size=0.8", linewidth=LW,
                                edgecolor="black", facecolor="white", zorder=3))
    ax.text(cx, cy - 0.1, labels[k], ha="center", va="center", fontsize=FS, zorder=4)


def edge_point(box, p0, d):
    """상자 box 안의 점 p0에서 방향 d로 나가 상자 테두리와 만나는 점"""
    bx, by = box
    (x0, y0), (dx, dy) = p0, d
    ts = []
    if dx > 0: ts.append((bx + BW / 2 - x0) / dx)
    if dx < 0: ts.append((bx - BW / 2 - x0) / dx)
    if dy > 0: ts.append((by + BH / 2 - y0) / dy)
    if dy < 0: ts.append((by - BH / 2 - y0) / dy)
    t = min(t for t in ts if t > 0)
    return x0 + dx * t, y0 + dy * t


def arrow(p, q, label, off, lab_side):
    """p 상자에서 q 상자로 가는 화살표. off: 중심선에서 수직으로 비킨 거리(mm)"""
    (px, py), (qx, qy) = boxes[p], boxes[q]
    dx, dy = qx - px, qy - py
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux                      # 왼쪽 수직
    s = edge_point(boxes[p], (px + nx * off, py + ny * off), (ux, uy))
    e = edge_point(boxes[q], (qx + nx * off, qy + ny * off), (-ux, -uy))
    gap = 0.9
    sx, sy = s[0] + ux * gap, s[1] + uy * gap
    ex, ey = e[0] - ux * gap, e[1] - uy * gap
    hl, hw = 1.4, 0.65
    bx, by = ex - ux * hl, ey - uy * hl
    ax.plot([sx, bx], [sy, by], color="black", linewidth=AW, solid_capstyle="butt", zorder=2)
    ax.fill([bx + nx * hw, ex, bx - nx * hw], [by + ny * hw, ey, by - ny * hw], color="black",
            linewidth=0, zorder=2)
    mx, my = (sx + ex) / 2, (sy + ey) / 2
    ax.text(mx + nx * lab_side, my + ny * lab_side, label, ha="center", va="center",
            fontsize=FS, zorder=4)


# 학생-교원 쌍(왼쪽), 학부모-교원 쌍(오른쪽). 바깥쪽 화살표의 이름은 바깥에, 안쪽은 안쪽에 둔다.
arrow("학생", "교원", "(가)", +1.2, +3.4)     # 학생 -> 교원 (바깥쪽: 왼쪽 위)
arrow("교원", "학생", "(나)", +1.2, +3.4)     # 교원 -> 학생 (안쪽)
arrow("교원", "학부모", "(라)", +1.2, +3.4)   # 교원 -> 학부모 (바깥쪽: 오른쪽 위)
arrow("학부모", "교원", "(다)", +1.2, +3.4)   # 학부모 -> 교원 (안쪽)

out = sys.argv[1]
fig.savefig(out, dpi=600, facecolor="white")
plt.close(fig)
from PIL import Image
with Image.open(out) as im:
    g = im.convert("L")
    g.save(out, dpi=(600, 600))
    print(out, g.size, "삽입 %.2f×%.2fmm → w=%d h=%d HWPUNIT" % (W, H, round(W * 283.46), round(H * 283.46)))
