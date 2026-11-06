# -*- coding: utf-8 -*-
"""3교시 지리 교체 문항의 코드 그림(값이 정답을 좌우하는 그림). 흑백, 600dpi, 지면 실제 크기(mm).
python geo_replacement_figs.py <출력 폴더>
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, rcParams
from matplotlib.patches import Arc, Circle, FancyArrowPatch, FancyBboxPatch, Rectangle, Polygon
from PIL import Image, ImageDraw, ImageOps

for name in ("Malgun Gothic", "맑은 고딕"):
    if name in {f.name for f in font_manager.fontManager.ttflist}:
        rcParams["font.family"] = name
        break
rcParams["axes.unicode_minus"] = False
rcParams["mathtext.fontset"] = "stix"

FS = 8.5
LW = 1.1
AX = 0.7
OUT = sys.argv[1] if len(sys.argv) > 1 else "."


def canvas(w, h):
    fig = plt.figure(figsize=(w / 25.4, h / 25.4), dpi=600)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    ax.set_aspect("equal")
    fig.patch.set_facecolor("white")
    return fig, ax


def save(fig, name, w, h):
    path = os.path.join(OUT, name)
    fig.savefig(path, dpi=600, facecolor="white")
    plt.close(fig)
    print("%s w=%d h=%d" % (name, round(w * 283.46), round(h * 283.46)))
    return path


def arrow_axis(ax, x0, y0, x1, y1):
    hl, hw = 1.3, 0.55
    ax.plot([x0, x1 - hl if x1 > x0 else x1], [y0, y1 - hl if y1 > y0 else y1], color="black", lw=AX,
            solid_capstyle="butt", zorder=3)
    if x1 > x0:
        ax.fill([x1 - hl, x1, x1 - hl], [y1 - hw, y1, y1 + hw], color="black", lw=0, zorder=3)
    else:
        ax.fill([x1 - hw, x1, x1 + hw], [y1 - hl, y1, y1 - hl], color="black", lw=0, zorder=3)


# 1번: 벽시계. 실제 12:20을 그린 뒤 좌우로 뒤집어 거울 속 모습으로 만든다.
def clock():
    w = h = 34.0
    fig, ax = canvas(w, h)
    c = w / 2
    ax.add_patch(Circle((c, c), 16.2, fc="white", ec="black", lw=1.8))
    ax.add_patch(Circle((c, c), 15.0, fc="white", ec="black", lw=0.5))
    for i in range(60):
        a = np.pi / 2 - i * np.pi / 30
        r0 = 13.6 if i % 5 == 0 else 14.2
        ax.plot([c + r0 * np.cos(a), c + 14.8 * np.cos(a)], [c + r0 * np.sin(a), c + 14.8 * np.sin(a)],
                color="black", lw=0.8 if i % 5 == 0 else 0.35)
    for n in range(1, 13):
        a = np.pi / 2 - n * np.pi / 6
        ax.text(c + 10.9 * np.cos(a), c + 10.9 * np.sin(a), str(n), ha="center", va="center",
                fontsize=12.5, fontweight="bold")
    hour, minute = 12, 20
    ma = np.pi / 2 - minute * np.pi / 30
    ha = np.pi / 2 - (hour % 12 + minute / 60) * np.pi / 6
    ax.plot([c, c + 7.2 * np.cos(ha)], [c, c + 7.2 * np.sin(ha)], color="black", lw=2.4, solid_capstyle="round")
    ax.plot([c, c + 11.0 * np.cos(ma)], [c, c + 11.0 * np.sin(ma)], color="black", lw=1.5, solid_capstyle="round")
    ax.add_patch(Circle((c, c), 0.8, fc="black", ec="black"))
    p = save(fig, "geo_q1_clock.png", w, h)
    im = Image.open(p).convert("RGB")
    ImageOps.mirror(im).save(p, dpi=(600, 600))


GRAPH_H = 40.6     # 9번 기온 그래프와 교사 그림의 높이(mm)


# 9번: 높이에 따른 기온
def temp():
    w, h = 74.0, GRAPH_H
    fig, ax = canvas(w, h)
    x0, y0 = 11.0, 7.0
    px = lambda t: x0 + (t - 8) * 6.6
    py = lambda z: y0 + z * 0.19
    pts = [(14, 0), (10, 40), (14, 90), (13, 150)]
    arrow_axis(ax, x0, y0, px(16) + 6, y0)
    arrow_axis(ax, x0, y0, x0, py(150) + 5)
    ax.text(x0 - 0.8, y0 - 0.9, "0", ha="right", va="top", fontsize=FS)
    for t in (10, 12, 14):
        ax.plot([px(t)] * 2, [y0, y0 + 0.7], color="black", lw=0.45)
        ax.text(px(t), y0 - 1.3, str(t), ha="center", va="top", fontsize=FS)
    for z in (40, 90, 150):
        ax.text(x0 - 1.0, py(z), str(z), ha="right", va="center", fontsize=FS)
    dot = dict(color="0.35", lw=0.45, ls=(0, (1.2, 1.4)), zorder=1)
    for t, z in pts:
        ax.plot([x0, px(t)], [py(z), py(z)], **dot)
        ax.plot([px(t), px(t)], [y0, py(z)], **dot)
    ax.plot([px(t) for t, z in pts], [py(z) for t, z in pts], color="black", lw=LW, zorder=4)
    ax.text(px(16) + 6, y0 - 1.3, "기온(℃)", ha="right", va="top", fontsize=FS)
    ax.text(x0 + 1.2, py(150) + 5, "높이(m)", ha="left", va="top", fontsize=FS)
    save(fig, "geo_q9_temp.png", w, h)


# 9번: 연기 유형 5가지
def types():
    pw, ph, gap = 19.4, 16.0, 1.2
    w, h = 5 * pw + 4 * gap + 1.0, ph + 5.8
    fig, ax = canvas(w, h)
    names = ["훈증형", "지붕형", "부채형", "원추형", "환상형"]
    for i, nm in enumerate(names):
        ox, oy = 0.5 + i * (pw + gap), 5.0
        ax.add_patch(Rectangle((ox, oy), pw, ph, fc="white", ec="black", lw=0.5))
        g = oy + 1.8
        ax.plot([ox, ox + pw], [g, g], color="black", lw=0.8)
        xs, ys = ox + 2.8, oy + 7.6
        ax.add_patch(Rectangle((xs - 0.8, g), 1.6, ys - g, fc="0.45", ec="black", lw=0.5, zorder=5))
        x = np.linspace(xs, ox + pw - 0.6, 240)
        u = (x - xs) / (x[-1] - xs)
        b = 0.28 * np.abs(np.sin(u * 19)) + 0.12 * np.abs(np.sin(u * 37))
        if nm == "훈증형":
            top = ys + 2.2 - 2.2 * np.exp(-u * 26)
            bot = np.maximum(ys - (ys - g) * np.minimum(1, u * 2.2) - b, g + 0.05)
        elif nm == "지붕형":
            top = ys + 6.2 * u ** 0.62 + b
            bot = ys - 0.0 * u
        elif nm == "부채형":
            top = ys + 0.25 + 0.75 * u + 0.25 * b
            bot = ys - 0.25 - 0.75 * u - 0.25 * b
        elif nm == "원추형":
            top = ys + 4.5 * u + b * 0.8
            bot = ys - 4.5 * u - b * 0.8
        else:
            mid = ys + (0.7 + 3.0 * u ** 0.5) * np.sin(2 * np.pi * u * 1.65)
            hw = 0.45 + 1.0 * u + b * 0.4
            top, bot = mid + hw, mid - hw
        ax.fill_between(x, bot, top, facecolor="0.8", edgecolor="black", lw=0.55, zorder=4)
        ax.text(ox + pw / 2, 4.1, nm, ha="center", va="top", fontsize=FS)
    save(fig, "geo_q9_types.png", w, h)


# 10번: 단면과 위에서 본 등고선 지도
def mountain():
    w, h = 104.0, 46.0
    fig, ax = canvas(w, h)
    # 단면
    x0, y0, sx, sy = 7.0, 6.0, 10.5, 10.4
    k = 1.15
    xs = np.linspace(0, 3.3, 300)
    ys = np.exp(-(xs - k))
    arrow_axis(ax, x0, y0, x0 + 3.6 * sx, y0)
    arrow_axis(ax, x0, y0, x0, y0 + np.exp(k) * sy + 5.5)
    ax.plot(x0 + xs * sx, y0 + ys * sy, color="black", lw=LW)
    ax.text(x0 - 0.8, y0 - 0.8, "O", ha="right", va="top", fontsize=FS)
    ax.text(x0 + 3.6 * sx, y0 - 1.0, r"$x$", ha="right", va="top", fontsize=9.5)
    ax.text(x0 - 1.0, y0 + np.exp(k) * sy + 5.5, r"$y$", ha="right", va="top", fontsize=9.5)
    ax.text(x0 + 0.95 * sx, y0 + np.exp(k - 0.75) * sy + 1.2, r"$y=e^{-(x-k)}$", ha="left", va="bottom", fontsize=9.5)
    ax.text(x0 + 4.4, y0 + np.exp(k) * sy + 0.6, "정상", ha="left", va="center", fontsize=FS)
    ax.add_patch(Arc((x0, y0 + np.exp(k) * sy + 1.7), 6.5, 2.2, theta1=200, theta2=520, color="black", lw=0.6))
    ax.fill([x0 + 2.75, x0 + 3.45, x0 + 3.2], [y0 + np.exp(k) * sy + 1.0, y0 + np.exp(k) * sy + 1.25, y0 + np.exp(k) * sy + 1.9],
            color="black", lw=0)
    ax.text(x0 + 2.0 * sx, 0.8, "단면", ha="center", va="bottom", fontsize=FS)
    ax.text(w - 0.3, 0.8, "위에서 본 모습", ha="right", va="bottom", fontsize=FS)
    # 위에서 본 모습
    cx, cy, u = 76.0, 24.4, 6.2
    for r in (1, 2, 3):
        ax.add_patch(Circle((cx, cy), r * u, fc="none", ec="0.45", lw=0.6, zorder=1))

    def pol(r, deg):
        a = np.deg2rad(deg)
        return cx + r * u * np.cos(a), cy + r * u * np.sin(a)

    def arc(r, d0, d1):
        d = np.linspace(d0, d1, 120)
        return cx + r * u * np.cos(np.deg2rad(d)), cy + r * u * np.sin(np.deg2rad(d))

    # 등산로: 출발(남쪽) -> r=3에서 90도 -> r=2로 -> 180도 -> r=1로 -> 90도 -> 정상
    segs = [arc(3, -90, 0), ([pol(3, 0)[0], pol(2, 0)[0]], [pol(3, 0)[1], pol(2, 0)[1]]), arc(2, 0, 180),
            ([pol(2, 180)[0], pol(1, 180)[0]], [pol(2, 180)[1], pol(1, 180)[1]]), arc(1, 180, 90),
            ([pol(1, 90)[0], cx], [pol(1, 90)[1], cy])]
    for sx_, sy_ in segs:
        ax.plot(sx_, sy_, color="black", lw=1.5, solid_capstyle="round", zorder=3)
    # 최단 경로
    ax.plot([pol(3, -90)[0], cx], [pol(3, -90)[1], cy], color="black", lw=1.0, ls=(0, (2.6, 1.6)), zorder=3)
    ax.add_patch(Circle((cx, cy), 0.9, fc="black", ec="black", zorder=5))
    ax.text(cx + 1.3, cy + 0.4, "정상", ha="left", va="bottom", fontsize=FS, zorder=6,
            bbox=dict(fc="white", ec="none", pad=0.2))
    sxp, syp = pol(3, -90)
    ax.add_patch(Circle((sxp, syp), 0.9, fc="white", ec="black", lw=0.9, zorder=5))
    ax.text(sxp, syp - 1.4, "출발점", ha="center", va="top", fontsize=FS)
    white = dict(fc="white", ec="none", pad=0.25)
    for r, deg, lab in ((3, 150, r"$e^{k-3}$"), (2, 215, r"$e^{k-2}$"), (1, 318, r"$e^{k-1}$")):
        x, y = pol(r, deg)
        ax.text(x, y, lab, ha="center", va="center", fontsize=9, zorder=4, bbox=white)
    for r, deg, lab in ((3.42, -38, "90°"), (2.5, 62, "180°"), (1.5, 140, "90°")):
        x, y = pol(r, deg)
        ax.text(x, y, lab, ha="center", va="center", fontsize=FS, zorder=4, bbox=white)
    save(fig, "geo_q10_mountain.png", w, h)


# 13번: 기숙사에서 편의점까지의 길
def road_map():
    w, h = 104.0, 56.0
    fig, ax = canvas(w, h)
    pos = {"기숙사": (11, 9), "급식실": (11, 29), "정문": (33, 47), "후문": (39, 9),
           "연수원 길": (62, 28), "편의점": (92, 28)}
    edges = [("기숙사", "급식실", 2, 0, (-3.8, 0)), ("기숙사", "후문", 5, 0, (0, 2.4)), ("급식실", "정문", 3, 0, (-2.8, 2.4)),
             ("정문", "연수원 길", 4, 0, (2.8, 2.2)), ("후문", "연수원 길", 3, 0, (2.8, -2.2)), ("연수원 길", "편의점", 3, 0, (0, 2.4)),
             ("정문", "편의점", 8, -0.26, None), ("후문", "편의점", 9, 0.26, None)]
    for a, b, m, rad, off in edges:
        p, q = pos[a], pos[b]
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-", connectionstyle="arc3,rad=%g" % rad, color="black", lw=1.1,
                                     shrinkA=0, shrinkB=0, zorder=1))
        mx, my = (p[0] + q[0]) / 2, (p[1] + q[1]) / 2
        if off is None:                      # 곡선 길: 곡선의 중앙 바깥쪽에 시간 표시
            dx, dy = q[0] - p[0], q[1] - p[1]
            cx_, cy_ = mx + rad * dy * 0.5, my - rad * dx * 0.5
            sign = 1 if cy_ > my else -1
            ax.text(cx_, cy_ + sign * 2.3, "%d분" % m, ha="center", va="center", fontsize=FS)
        else:
            ax.text(mx + off[0], my + off[1], "%d분" % m, ha="center", va="center", fontsize=FS)
    for nm, (x, y) in pos.items():
        tw = 3.2 * len(nm.replace(" ", "")) + 3.0
        ax.add_patch(FancyBboxPatch((x - tw / 2, y - 3.0), tw, 6.0, boxstyle="round,pad=0,rounding_size=1.1", fc="white", ec="black",
                                    lw=0.9 if nm not in ("기숙사", "편의점") else 1.5, zorder=3))
        ax.text(x, y - 0.1, nm, ha="center", va="center", fontsize=FS, zorder=4)
    save(fig, "geo_q13_map.png", w, h)


# 20번: 칸별 한계 효용
def utility():
    w, h = 96.0, 55.0
    fig, ax = canvas(w, h)
    S = [30, 22, 14, 8, 4, 2]
    I = [40, 35, 30, 20, 10, 5]
    x0, y0, per, bw = 12.0, 8.0, 0.84, 5.2
    step = 13.2
    arrow_axis(ax, x0, y0, x0 + 6 * step + 3.8, y0)
    arrow_axis(ax, x0, y0, x0, y0 + 40 * per + 8.5)
    ax.text(x0 - 0.8, y0 - 0.6, "0", ha="right", va="top", fontsize=FS)
    for v in (10, 20, 30, 40):
        yy = y0 + v * per
        ax.plot([x0, x0 + 6 * step], [yy, yy], color="0.6", lw=0.4, ls=(0, (1.2, 1.4)), zorder=1)
        ax.text(x0 - 1.0, yy, str(v), ha="right", va="center", fontsize=FS)
    for i in range(6):
        c = x0 + step * (i + 0.5)
        ax.add_patch(Rectangle((c - bw - 0.15, y0), bw, S[i] * per, fc="0.45", ec="black", lw=0.6, zorder=2))
        ax.add_patch(Rectangle((c + 0.15, y0), bw, I[i] * per, fc="white", ec="black", lw=0.6, hatch="////", zorder=2))
        ax.text(c - bw / 2 - 0.15, y0 + S[i] * per + 0.5, str(S[i]), ha="center", va="bottom", fontsize=7.8, zorder=3)
        ax.text(c + bw / 2 + 0.15, y0 + I[i] * per + 0.5, str(I[i]), ha="center", va="bottom", fontsize=7.8, zorder=3)
        ax.text(c, y0 - 1.3, "%d번째" % (i + 1), ha="center", va="top", fontsize=FS)
    ax.text(x0 + 1.2, y0 + 40 * per + 8.5, "늘어나는 효용", ha="left", va="top", fontsize=FS)
    lx, ly = x0 + 3.6 * step, y0 + 37.0 * per
    ax.add_patch(Rectangle((lx, ly), 4.2, 2.8, fc="0.45", ec="black", lw=0.6))
    ax.text(lx + 5.2, ly + 1.3, "과학고 운동장", ha="left", va="center", fontsize=FS)
    ax.add_patch(Rectangle((lx, ly - 4.6), 4.2, 2.8, fc="white", ec="black", lw=0.6, hatch="////"))
    ax.text(lx + 5.2, ly - 3.3, "국제고 교육 시설", ha="left", va="center", fontsize=FS)
    save(fig, "geo_q20_utility.png", w, h)


# ChatGPT 장면 합성: 1번 거울 속 시계, 9번 교사+기온 그래프, 11·20번 위쪽 빈 곳 자르기


def scenes():
    src = lambda n: Image.open(os.path.join(OUT, n)).convert("RGB")
    # 1번: 빈 원을 덮도록 시계를 거울 위쪽에 합성
    scene = src("geo_clubroom_sleep_01.png")
    D, cx, cy = 280, 828, 205
    big = src("geo_q1_clock.png")
    k = big.width / 34.0
    r = int(16.6 * k)
    c = big.width // 2
    big = big.crop((c - r, c - r, c + r, c + r)).resize((D, D), Image.LANCZOS)
    mask = Image.new("L", (D * 4, D * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, D * 4 - 1, D * 4 - 1), fill=255)
    scene.paste(big, (cx - D // 2, cy - D // 2), mask.resize((D, D), Image.LANCZOS))
    scene.save(os.path.join(OUT, "geo_q1_scene.png"), dpi=(600, 600))
    print("geo_q1_scene.png w=25512 h=17008")
    # 9번: 교사 뒷모습(왼쪽) + 기온 그래프(오른쪽)
    t = src("geo_dorm_smoke_01.png").crop((540, 10, 950, 1014))
    g = src("geo_q9_temp.png")
    H = g.height
    t = t.resize((int(t.width * H / t.height), H), Image.LANCZOS)
    gap = int(2.0 * g.height / GRAPH_H)
    out = Image.new("RGB", (t.width + gap + g.width, H), "white")
    out.paste(t, (0, 0))
    out.paste(g, (t.width + gap, 0))
    out.save(os.path.join(OUT, "geo_q9_scene.png"), dpi=(600, 600))
    wm = out.width * GRAPH_H / g.height
    print("geo_q9_scene.png w=%d h=%d" % (round(wm * 283.46), round(GRAPH_H * 283.46)))
    # 11·20번: 위쪽 빈 곳 자르기
    for n, o, top in (("geo_balance_golf_01.png", "geo_q11_balance.png", 110), ("geo_field_school_01.png", "geo_q20_field.png", 130)):
        im = src(n)
        im.crop((0, top, im.width, im.height)).save(os.path.join(OUT, o), dpi=(600, 600))
        print(o, im.width, im.height - top)


for f in (clock, temp, types, mountain, road_map, utility, scenes):
    f()
