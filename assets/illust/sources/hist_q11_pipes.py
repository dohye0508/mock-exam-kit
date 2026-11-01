# -*- coding: utf-8 -*-
"""4교시 11번 기숙사 단면 배관도(단순화한 자료). 흑백, 600dpi, 흰 배경.
지면 실제 크기(mm)로 그리므로 글자 크기(pt)가 그대로 지면 크기다(8pt 이상).
옥상 물탱크 -> 갈림점 -> 왼쪽·오른쪽 세로관 -> 층마다 샤워실(왼쪽 A~C, 오른쪽 D~F).
python hist_q11_pipes.py <출력 png>"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle

FONT = None
for name in ("Malgun Gothic", "맑은 고딕"):
    if name in {f.name for f in font_manager.fontManager.ttflist}:
        FONT = name
        break
rcParams["font.family"] = FONT
rcParams["axes.unicode_minus"] = False

FS = 8.5          # 글자 크기 pt(지면 크기)
LW = 0.6          # 선 굵기 pt
PIPE = 1.4        # 배관 굵기 pt
W = 100.0         # 그림 폭(mm)
FH = 10.0         # 층 높이(mm)
BX0, BX1 = 2.0, 98.0            # 건물 바깥벽
BY0 = 1.0                       # 2층 바닥
ROOF = BY0 + 3 * FH             # 옥상
RW, RH = 22.0, 6.4              # 샤워실 상자
XL, XR = 37.0, 63.0             # 세로관
TW, TH = 16.0, 5.6              # 물탱크
TY = ROOF + 2.6                 # 물탱크 아랫변
H = TY + TH + 0.8

fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=600)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")


def pipe(xs, ys):
    ax.plot(xs, ys, color="black", linewidth=PIPE, solid_capstyle="butt",
            solid_joinstyle="miter", zorder=3)


def node(x, y):
    ax.add_patch(Circle((x, y), 0.6, facecolor="black", edgecolor="none", zorder=4))


def arrow(x, y, dx=0, dy=-1):
    """흐름 방향 작은 화살촉"""
    hl, hw = 1.3, 0.75
    if dy:
        ax.fill([x - hw, x + hw, x], [y + hl / 2, y + hl / 2, y - hl / 2], color="black", lw=0, zorder=4)
    else:
        ax.fill([x - dx * hl / 2, x - dx * hl / 2, x + dx * hl / 2], [y - hw, y + hw, y], color="black", lw=0, zorder=4)


def box(x, y, w, h, label, fill="white"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.6", linewidth=LW,
                                edgecolor="black", facecolor=fill, zorder=5))
    ax.text(x + w / 2, y + h / 2 - 0.1, label, ha="center", va="center", fontsize=FS, zorder=6)


# 건물 단면: 바깥벽과 층 바닥(옅은 회색)
ax.add_patch(Rectangle((BX0, BY0), BX1 - BX0, ROOF - BY0, fill=False, linewidth=LW * 1.6, edgecolor="black", zorder=2))
for k in (1, 2):
    ax.plot([BX0, BX1], [BY0 + k * FH] * 2, color="0.55", linewidth=LW, zorder=1)
# 물탱크와 갈림점
box(W / 2 - TW / 2, TY, TW, TH, "물탱크", fill="0.92")
yS = ROOF - 2.2
pipe([W / 2, W / 2], [TY, yS])
pipe([XL, XR], [yS, yS])
node(W / 2, yS)
# 층마다 샤워실과 가지관
floors = [(BY0 + 2.5 * FH, "4층", "A", "D"), (BY0 + 1.5 * FH, "3층", "B", "E"), (BY0 + 0.5 * FH, "2층", "C", "F")]
for x, side in ((XL, -1), (XR, +1)):
    pipe([x, x], [yS, floors[-1][0]])
    arrow(x, (yS + floors[0][0]) / 2)
    arrow(x, (floors[0][0] + floors[1][0]) / 2)
    arrow(x, (floors[1][0] + floors[2][0]) / 2)
for y, fl, lw_, re_ in floors:
    lx = XL - 5.0 - RW                    # 왼쪽 샤워실 왼쪽 끝
    rx = XR + 5.0                         # 오른쪽 샤워실 왼쪽 끝
    pipe([XL, XL - 5.0], [y, y])
    pipe([XR, XR + 5.0], [y, y])
    if fl != "2층":
        node(XL, y)
        node(XR, y)
    box(lx, y - RH / 2, RW, RH, "샤워실 " + lw_)
    box(rx, y - RH / 2, RW, RH, "샤워실 " + re_)
    ax.text(W / 2, y - 0.1, fl, ha="center", va="center", fontsize=FS, zorder=6)

out = sys.argv[1]
fig.savefig(out, dpi=600, facecolor="white")
plt.close(fig)
from PIL import Image
with Image.open(out) as im:
    g = im.convert("L")
    g.save(out, dpi=(600, 600))
    print(out, g.size, "삽입 %.2f×%.2fmm → w=%d h=%d HWPUNIT" % (W, H, round(W * 283.46), round(H * 283.46)))
