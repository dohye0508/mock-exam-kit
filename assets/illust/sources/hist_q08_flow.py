# -*- coding: utf-8 -*-
"""4교시 8번 조기졸업·조기진학 흐름도. 흑백, 600dpi, 흰 배경.
지면 실제 크기(mm)로 그리므로 글자 크기(pt)가 그대로 지면 크기다(8pt 이상).
python draw_q08_flow.py <출력 png>"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.patches import FancyBboxPatch
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties

FONT = None
for name in ("Malgun Gothic", "맑은 고딕"):
    if name in {f.name for f in font_manager.fontManager.ttflist}:
        FONT = name
        break
rcParams["font.family"] = FONT
rcParams["axes.unicode_minus"] = False

FS = 8.5                   # pt (지면 크기)
LW = 0.6                   # 선 굵기 pt
MM_PER_PT = 25.4 / 72
PAD = 1.6                  # 상자 안 좌우 여백(mm, 한쪽)
BH = 4.6                   # 상자 높이(mm)
GAP = 6.0                  # 열 사이(mm)
M = 0.4                    # 그림 가장자리 여백(mm)


def text_w(s):
    """글자 폭(mm). TextPath 단위는 pt(글자 크기 FS 기준)."""
    tp = TextPath((0, 0), s, size=FS, prop=FontProperties(family=FONT))
    return tp.get_extents().width * MM_PER_PT


COL_A = ["2학년 72명"]
COL_B = ["조기졸업 대상 10명", "조기진학 대상 11명", "그 밖의 학생"]
COL_C = ["합격 ㉠명", "불합격 2명", "합격 ㉡명", "불합격 ㉢명"]
wA = max(map(text_w, COL_A)) + 2 * PAD
wB = max(map(text_w, COL_B)) + 2 * PAD
wC = max(map(text_w, COL_C)) + 2 * PAD
W = M + wA + GAP + wB + GAP + wC + M
ROW = 6.2                                              # 줄 간격(mm)
H = 2 * M + BH + 4 * ROW
ROWS = [H - M - BH / 2 - k * ROW for k in range(5)]    # 위에서부터 다섯 줄

fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=600)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")


def box(x0, w, yc, text):
    ax.add_patch(FancyBboxPatch((x0, yc - BH / 2), w, BH, boxstyle="round,pad=0,rounding_size=0.7",
                                linewidth=LW, edgecolor="black", facecolor="white", zorder=3))
    ax.text(x0 + w / 2, yc - 0.15, text, ha="center", va="center", fontsize=FS, zorder=4)


def elbow(x0, y0, xm, x1, y1):
    """(x0,y0)에서 가로로 xm까지, 세로로 y1까지, 다시 가로로 x1까지 가는 화살표(끝에 작은 화살촉)"""
    hl, hw = 1.1, 0.55                                  # 화살촉 길이·반폭(mm)
    ax.plot([x0, xm, xm, x1 - hl], [y0, y0, y1, y1], color="black", linewidth=LW,
            solid_capstyle="butt", solid_joinstyle="miter", zorder=2)
    ax.fill([x1 - hl, x1, x1 - hl], [y1 - hw, y1, y1 + hw], color="black", linewidth=0, zorder=2)


xA = M
xB = xA + wA + GAP
xC = xB + wB + GAP
yA = ROWS[2]
yB1 = (ROWS[0] + ROWS[1]) / 2
yB2 = (ROWS[2] + ROWS[3]) / 2
yB3 = ROWS[4]

box(xA, wA, yA, COL_A[0])
for y, t in zip((yB1, yB2, yB3), COL_B):
    box(xB, wB, y, t)
for y, t in zip(ROWS[:4], COL_C):
    box(xC, wC, y, t)

xm1 = xA + wA + GAP / 2
for y in (yB1, yB2, yB3):
    elbow(xA + wA, yA, xm1, xB, y)
xm2 = xB + wB + GAP / 2
for yb, ys in ((yB1, ROWS[:2]), (yB2, ROWS[2:4])):
    for y in ys:
        elbow(xB + wB, yb, xm2, xC, y)

out = sys.argv[1]
fig.savefig(out, dpi=600, facecolor="white")
plt.close(fig)
from PIL import Image
with Image.open(out) as im:
    g = im.convert("L")                                 # 회색조로 저장
    g.save(out, dpi=(600, 600))
    print(out, g.size, "삽입 %.2f×%.2fmm → w=%d h=%d HWPUNIT" % (W, H, round(W * 283.46), round(H * 283.46)))
