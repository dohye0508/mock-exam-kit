# -*- coding: utf-8 -*-
"""4교시 12번 녹물 시료 X에 Y 또는 Z를 섞을 때(부피 합 40 mL) X의 부피에 따른 전체 이온 수.
흑백, 600dpi, 흰 배경. 지면 실제 크기(mm)로 그리므로 글자 크기(pt)가 그대로 지면 크기다.
(가) 실선: X + Z(AgNO3)  (0, 1.6N) -> (10, N) -> (40, 4N)
(나) 점선: X + Y(NaOH)   (0, 4N)   -> (25, 3N) -> (40, 4N)
(문항에서는 (가), (나)가 어느 쪽인지 알려 주지 않는다. 검산: new_chem/b_verify.py)
python hist_q12_ions.py <출력 png>"""
import sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager, rcParams

for name in ("Malgun Gothic", "맑은 고딕"):
    if name in {f.name for f in font_manager.fontManager.ttflist}:
        rcParams["font.family"] = name
        break
rcParams["axes.unicode_minus"] = False
rcParams["mathtext.fontset"] = "stix"

FS = 8.5          # 눈금·이름 글자(pt)
LW = 1.2          # 곡선 굵기(pt)
AX_LW = 0.7       # 축 굵기(pt)
GRID_LW = 0.45    # 보조선 굵기(pt)

W, H = 86.0, 51.5                       # 그림 전체(mm)
X0, PERV = 9.0, 1.45                     # V=0 가로 위치, 1 mL 길이(mm)
Y0, PERN = 6.0, 8.6                     # 0 세로 위치, N 하나 높이(mm)
VMAX, NMAX = 40, 4

GA = [(0, 1.6), (10, 1), (40, 4)]       # (가)
NA = [(0, 4), (25, 3), (40, 4)]         # (나)


def px(v):
    return X0 + PERV * v


def py(n):
    return Y0 + PERN * n


fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=600)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")

DOT = dict(color="0.35", lw=GRID_LW, ls=(0, (1.2, 1.4)), zorder=1)

# 축과 끝 화살표
hl, hw = 1.3, 0.55
xe, ye = px(VMAX) + 6.0, py(NMAX) + 5.5
ax.plot([X0, xe - hl], [Y0, Y0], color="black", lw=AX_LW, solid_capstyle="butt", zorder=2)
ax.fill([xe - hl, xe, xe - hl], [Y0 - hw, Y0, Y0 + hw], color="black", lw=0, zorder=2)
ax.plot([X0, X0], [Y0, ye - hl], color="black", lw=AX_LW, solid_capstyle="butt", zorder=2)
ax.fill([X0 - hw, X0, X0 + hw], [ye - hl, ye, ye - hl], color="black", lw=0, zorder=2)

# 가로축: 5 mL마다 짧은 눈금, 0·10·25·40에 글자
for v in range(5, VMAX + 1, 5):
    ax.plot([px(v), px(v)], [Y0, Y0 + 0.7], color="black", lw=0.45, zorder=2)
ax.text(X0 - 0.8, Y0 - 0.9, "0", ha="right", va="top", fontsize=FS)
for v in (10, 25, 40):
    ax.text(px(v), Y0 - 1.3, str(v), ha="center", va="top", fontsize=FS)

# 꺾인 점·끝점에서 축으로 점선
for v, n in ((10, 1), (25, 3), (40, 4)):
    ax.plot([px(v), px(v)], [Y0, py(n)], **DOT)
for v, n, lab in ((10, 1, r"$N$"), (25, 3, r"$3N$"), (40, 4, r"$4N$")):
    ax.plot([X0, px(v)], [py(n), py(n)], **DOT)
    ax.text(X0 - 0.9, py(n), lab, ha="right", va="center", fontsize=FS)

# 곡선
ax.plot([px(v) for v, _ in GA], [py(n) for _, n in GA], color="black", lw=LW,
        solid_joinstyle="miter", solid_capstyle="butt", zorder=4)
ax.plot([px(v) for v, _ in NA], [py(n) for _, n in NA], color="black", lw=LW,
        ls=(0, (3.2, 1.8)), dash_joinstyle="miter", dash_capstyle="butt", zorder=4)

# 곡선 이름
ax.text(px(3.2), py(1.38) + 1.6, "(가)", ha="left", va="bottom", fontsize=FS, zorder=5)
ax.text(px(9.0), py(3.29), "(나)", ha="center", va="center", fontsize=FS, zorder=5)

# 축 이름: 세로축은 위 왼쪽, 가로축은 오른쪽 끝 아래
ax.text(X0 - 1.2, ye + 0.5, "전체 이온 수", ha="left", va="bottom", fontsize=FS)
ax.text(xe + 0.8, Y0 + 0.4, "X의 부피", ha="left", va="bottom", fontsize=FS)
ax.text(xe + 0.8, Y0 - 0.4, "(mL)", ha="left", va="top", fontsize=FS)

out = sys.argv[1] if len(sys.argv) > 1 else "hist_q12_ions.png"
fig.savefig(out, dpi=600, facecolor="white")
plt.close(fig)
from PIL import Image
with Image.open(out) as im:
    g = im.convert("L")
    g.save(out, dpi=(600, 600))
    print(out, g.size, "삽입 %.2f×%.2fmm → w=%d h=%d HWPUNIT" % (W, H, round(W * 283.46), round(H * 283.46)))
