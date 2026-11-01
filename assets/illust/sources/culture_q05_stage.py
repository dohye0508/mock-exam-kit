# -*- coding: utf-8 -*-
"""3교시 5번 곰솔제 공연 동안 무대 위 공연자 수(계단 그래프). 흑백, 600dpi, 흰 배경.
지면 실제 크기(mm)로 그리므로 글자 크기(pt)가 그대로 지면 크기다(8pt 이상).
공연과 공연 사이에는 무대가 비고(0명), 1부와 2부 사이에 쉬는 시간이 있다.
python culture_q05_stage.py <출력 png>"""
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

FS = 8.5          # 눈금 글자(pt, 지면 크기)
FS_AX = 9         # 축 이름·구간 이름(pt)
LW = 1.2          # 계단선 굵기(pt)
AX_LW = 0.7       # 축 굵기(pt)
GRID_LW = 0.4     # 보조선 굵기(pt)

W, H = 85.0, 43.0                       # 그림 전체(mm)
X0, MIN = 8.0, 0.60                     # 0분의 가로 위치, 1분 길이(mm)
Y0, PER = 6.5, 3.0                      # 0명의 세로 위치, 1명 높이(mm)
TMAX, NMAX = 100, 8

# (시작 분, 끝 분, 공연자 수): 순서대로 공연 6개
ACTS = [(0, 5, 2), (10, 25, 8), (30, 35, 1), (40, 45, 3),   # 1부
        (60, 70, 6), (75, 100, 7)]                           # 2부


def px(t):
    return X0 + MIN * t


def py(n):
    return Y0 + PER * n


fig = plt.figure(figsize=(W / 25.4, H / 25.4), dpi=600)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, W)
ax.set_ylim(0, H)
ax.axis("off")
fig.patch.set_facecolor("white")

# 가로 보조선(1명마다, 옅은 점선)
for n in range(1, NMAX + 1):
    ax.plot([px(0), px(TMAX)], [py(n), py(n)], color="0.6", lw=GRID_LW, ls=(0, (1, 1.6)), zorder=1)

# 축과 끝 화살표
hl, hw = 1.3, 0.55
xe, ye = px(TMAX) + 3.2, py(NMAX) + 7.5
ax.plot([X0, xe - hl], [Y0, Y0], color="black", lw=AX_LW, solid_capstyle="butt", zorder=2)
ax.fill([xe - hl, xe, xe - hl], [Y0 - hw, Y0, Y0 + hw], color="black", lw=0, zorder=2)
ax.plot([X0, X0], [Y0, ye - hl], color="black", lw=AX_LW, solid_capstyle="butt", zorder=2)
ax.fill([X0 - hw, X0, X0 + hw], [ye - hl, ye, ye - hl], color="black", lw=0, zorder=2)

# 가로축 눈금: 5분마다 짧게, 10분마다 길게 + 글자
for t in range(5, TMAX + 1, 5):
    L = 1.1 if t % 10 == 0 else 0.6
    ax.plot([px(t), px(t)], [Y0, Y0 + L], color="black", lw=AX_LW if t % 10 == 0 else 0.45, zorder=2)
for t in range(0, TMAX + 1, 10):
    ax.text(px(t), Y0 - 1.4, str(t), ha="center", va="top", fontsize=FS)

# 세로축 눈금: 1명마다 짧게, 2명마다 글자
for n in range(1, NMAX + 1):
    L = 0.9 if n % 2 == 0 else 0.5
    ax.plot([X0, X0 + L], [py(n), py(n)], color="black", lw=AX_LW if n % 2 == 0 else 0.45, zorder=2)
    if n % 2 == 0:
        ax.text(X0 - 0.8, py(n), str(n), ha="right", va="center", fontsize=FS)

# 계단선: 공연 사이는 0명
xs, ys = [px(0)], [py(0)]
for s, e, n in ACTS:
    xs += [px(s), px(s), px(e), px(e)]
    ys += [py(0), py(n), py(n), py(0)]
xs.append(px(TMAX)); ys.append(py(0))
ax.plot(xs, ys, color="black", lw=LW, solid_joinstyle="miter", solid_capstyle="butt", zorder=3)

# 1부·2부 구간 표시(위쪽 꺾쇠)
def bracket(t0, t1, label):
    yb = py(NMAX) + 1.6
    ax.plot([px(t0), px(t0), px(t1), px(t1)], [yb - 0.7, yb, yb, yb - 0.7], color="black", lw=0.5, zorder=3)
    ax.text((px(t0) + px(t1)) / 2, yb + 0.5, label, ha="center", va="bottom", fontsize=FS_AX)

bracket(0, 45, "1부")
bracket(60, 100, "2부")

# 축 이름: 세로축은 위 왼쪽, 가로축은 오른쪽 끝 아래
ax.text(X0 - 1.2, ye + 0.5, "공연자 수(명)", ha="left", va="bottom", fontsize=FS_AX)
ax.text(xe + 0.8, Y0, "시간(분)", ha="left", va="center", fontsize=FS_AX)

out = sys.argv[1] if len(sys.argv) > 1 else "culture_q05_stage.png"
fig.savefig(out, dpi=600, facecolor="white")
print(out)
