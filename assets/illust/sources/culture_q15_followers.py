# -*- coding: utf-8 -*-
"""3교시 15번 팔로워 수 꺾은선. 흑백, 600dpi, 흰 배경, 제목·격자 없음.
지면 실제 크기(mm)로 그리므로 글자 크기(pt)가 그대로 지면 크기다(8pt 이상).
가로축은 날짜 간격을 실제 비율(하루 = 5 mm)로 두고, 하루마다 짧은 눈금을 긋는다.
python culture_q15_followers.py <출력 png>"""
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

FS = 8.5          # 눈금·값 글자(pt, 지면 크기)
FS_AX = 9         # 축 이름(pt)
LW = 1.1          # 꺾은선 굵기(pt)
AX_LW = 0.7       # 축 굵기(pt)

W, H = 82.0, 35.0                       # 그림 전체(mm)
X0, DAY = 9.0, 5.0                      # 3/23의 가로 위치, 하루 길이(mm)
Y0, YH = 5.6, 21.0                      # 0명의 세로 위치, 100명까지 높이(mm)
LAB_TOP = Y0 - 1.6                      # 날짜 글자 윗선

DATA = [(0, 3, "3/23"), (1, 4, "3/24"), (3, 50, "3/26"), (5, 67, "3/28"), (12, 84, "4/4")]


def px(d):
    return X0 + DAY * d


def py(v):
    return Y0 + YH * v / 100.0


fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=600)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")

# 축과 끝 화살표
hl, hw = 1.3, 0.55
xe, ye = px(13) + 1.0, py(100) + 2.6
ax.plot([X0, xe - hl], [Y0, Y0], color="black", lw=AX_LW, solid_capstyle="butt")
ax.fill([xe - hl, xe, xe - hl], [Y0 - hw, Y0, Y0 + hw], color="black", lw=0)
ax.plot([X0, X0], [Y0, ye - hl], color="black", lw=AX_LW, solid_capstyle="butt")
ax.fill([X0 - hw, X0, X0 + hw], [ye - hl, ye, ye - hl], color="black", lw=0)

# 하루마다 짧은 눈금, 기록한 날은 조금 긴 눈금과 날짜
for d in range(1, 13):
    ax.plot([px(d), px(d)], [Y0, Y0 + 0.6], color="black", lw=0.45)
for d, v, lab in DATA:
    if d:
        ax.plot([px(d), px(d)], [Y0, Y0 + 1.1], color="black", lw=AX_LW)
    ha, dx = "center", 0.0
    if lab == "3/24":
        ha, dx = "left", -0.3            # 하루 뒤인 3/23 글자와 겹치지 않게 오른쪽으로 민다
    ax.text(px(d) + dx, LAB_TOP, lab, ha=ha, va="top", fontsize=FS)

# 세로축 눈금
for v in (50, 100):
    ax.plot([X0, X0 + 0.9], [py(v), py(v)], color="black", lw=AX_LW)
    ax.text(X0 - 0.8, py(v), str(v), ha="right", va="center", fontsize=FS)
ax.text(X0 - 0.8, Y0 + 0.2, "0", ha="right", va="center", fontsize=FS)

# 꺾은선과 점, 값
xs = [px(d) for d, v, _ in DATA]
ys = [py(v) for d, v, _ in DATA]
ax.plot(xs, ys, color="black", lw=LW, solid_joinstyle="miter", zorder=3)
ax.plot(xs, ys, "o", color="black", ms=2.6, zorder=4)
OFF = {3: (0.5, 0.9, "left"), 4: (0.3, 1.0, "center"), 50: (-0.9, 0.8, "right"), 67: (-0.6, 1.1, "right"),
       84: (0.0, 1.2, "center")}
for (d, v, _), x, y in zip(DATA, xs, ys):
    dx, dy, ha = OFF[v]
    ax.text(x + dx, y + dy, str(v), ha=ha, va="bottom", fontsize=FS, zorder=5)

# 축 이름: 세로축은 위 왼쪽, 가로축은 오른쪽 끝 아래
ax.text(X0 - 1.5, ye + 0.6, "팔로워 수(명)", ha="left", va="bottom", fontsize=FS_AX)
ax.text(W - 0.4, LAB_TOP, "날짜", ha="right", va="top", fontsize=FS_AX)

out = sys.argv[1] if len(sys.argv) > 1 else "culture_q15_followers.png"
fig.savefig(out, dpi=600, facecolor="white")
print(out)
