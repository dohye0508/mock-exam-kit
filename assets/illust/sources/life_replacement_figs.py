# -*- coding: utf-8 -*-
"""4교시 생활 교체 문항의 코드 그림. 흑백, 지면 실제 크기(mm).
python life_replacement_figs.py <assets/illust 폴더>
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib import font_manager, rcParams
from matplotlib.font_manager import FontProperties
from matplotlib.patches import Circle, Ellipse, Polygon, Rectangle
from PIL import Image, ImageDraw

for name in ("Malgun Gothic", "맑은 고딕"):
    if name in {f.name for f in font_manager.fontManager.ttflist}:
        rcParams["font.family"] = name
        break
rcParams["axes.unicode_minus"] = False

FS = 8.5
OUT = sys.argv[1] if len(sys.argv) > 1 else "."
MUSIC = FontProperties(fname=r"C:\Windows\Fonts\seguisym.ttf")


def canvas(w, h, dpi=600):
    fig = plt.figure(figsize=(w / 25.4, h / 25.4), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(0, h)
    ax.axis("off")
    ax.set_aspect("equal")
    fig.patch.set_facecolor("white")
    return fig, ax


def save(fig, name, w, h):
    fig.savefig(os.path.join(OUT, name), dpi=fig.dpi, facecolor="white")
    plt.close(fig)
    print("%s w=%d h=%d" % (name, round(w * 283.46), round(h * 283.46)))


# 1번: 교사 C 전후 장면(ChatGPT) + 신분 단계 그림 합성
def caste():
    w, h = 48.0, 45.0
    fig, ax = canvas(w, h)
    cx, top, base = 16.8, 43.5, 1.5
    names = ["교장·교감", "교사", "학생", "그냥 아저씨"]
    n = len(names)
    tone = ["0.72", "0.82", "0.9", "1.0"]
    half = lambda t: 9.2 + (16.3 - 9.2) * t
    for i, nm in enumerate(names):
        y1 = top - (top - base) * i / n
        y0 = top - (top - base) * (i + 1) / n
        ax.add_patch(Polygon([(cx - half(i / n), y1), (cx + half(i / n), y1), (cx + half((i + 1) / n), y0), (cx - half((i + 1) / n), y0)],
                             closed=True, fc=tone[i], ec="black", lw=0.9))
        ax.text(cx, (y0 + y1) / 2, nm, ha="center", va="center", fontsize=FS)
    y_from = top - (top - base) * 1.5 / n
    y_to = top - (top - base) * 3.5 / n
    x = 37.0
    ax.plot([cx + half(1.5 / n), x], [y_from, y_from], color="black", lw=0.9)
    ax.plot([x, x], [y_from, y_to + 1.3], color="black", lw=0.9)
    ax.plot([x, cx + half(3.5 / n)], [y_to, y_to], color="black", lw=0.9)
    ax.fill([cx + half(3.5 / n) + 1.4, cx + half(3.5 / n) + 1.4, cx + half(3.5 / n)], [y_to - 0.7, y_to + 0.7, y_to], color="black", lw=0)
    ax.text(x + 0.9, (y_from + y_to) / 2, "교사 C", ha="left", va="center", fontsize=FS)
    tmp = os.path.join(OUT, "_life_ladder_tmp.png")
    fig.savefig(tmp, dpi=600, facecolor="white")
    plt.close(fig)
    lad = Image.open(tmp).convert("RGB")
    os.remove(tmp)
    k = lad.height / 45.0                     # px/mm
    scene = Image.open(os.path.join(OUT, "life_caste_ajeossi_01.png")).convert("RGB")
    sw, sh = int(54 * k), int(36 * k)
    scene = scene.resize((sw, sh), Image.LANCZOS)
    out = Image.new("RGB", (sw + int(2 * k) + lad.width, lad.height), "white")
    out.paste(scene, (0, int(4.5 * k)))
    out.paste(lad, (sw + int(2 * k), 0))
    out.save(os.path.join(OUT, "life_q1_scene.png"), dpi=(600, 600))
    print("life_q1_scene.png w=%d h=%d" % (round(out.width / k * 283.46), round(45 * 283.46)))


# 3번: 갑의 답안지(OMR). 1번 답을 2번 칸에 쓰는 식으로 밀려 씀
KEY = [3, 3, 1, 4, 4, 4, 2, 5, 5, 1]
MARK = [None] + KEY[:-1]


def omr():
    w, h = 91.0, 38.0
    fig, ax = canvas(w, h)
    x0, y_top, dx, dy = 13.0, 29.6, 8.0, 6.0
    ax.add_patch(Rectangle((0.4, 0.4), w - 0.8, h - 0.8, fc="white", ec="black", lw=0.9))
    ax.add_patch(Rectangle((0.4, 33.0), w - 0.8, h - 33.4, fc="0.85", ec="black", lw=0.6))
    ax.text(4.8, 35.4, "문항", ha="center", va="center", fontsize=FS)
    for c in range(10):
        x = x0 + c * dx
        ax.text(x, 35.4, str(c + 1), ha="center", va="center", fontsize=FS)
        if c % 2 == 1:
            ax.add_patch(Rectangle((x - dx / 2, 0.4), dx, 32.6, fc="0.95", ec="none", zorder=0))
        for r in range(5):
            y = y_top - r * dy
            on = MARK[c] == r + 1
            ax.add_patch(Ellipse((x, y), 5.2, 4.3, fc="black" if on else "white", ec="black", lw=0.6, zorder=2))
            if not on:
                ax.text(x, y - 0.05, str(r + 1), ha="center", va="center", fontsize=7.5, color="0.35", zorder=3)
    save(fig, "life_q3_omr.png", w, h)


# 7번: 게시물 틀(ishs_bob 틀 재사용)에 악보·기타 프로필을 합성
def score_png(path):
    W, H = 1400, 440
    dpi = 200
    fig = plt.figure(figsize=(W / dpi, H / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    ax.set_aspect("equal")
    fig.patch.set_facecolor("white")
    S, y0 = 38.0, 130.0                    # 줄 간격, 맨 아래 줄 높이
    x0, x1 = 30.0, W - 20.0
    for i in range(5):
        ax.plot([x0, x1], [y0 + i * S] * 2, color="black", lw=1.1)
    ax.text(x0 + 4, y0 + 1.0 * S, "\U0001D11E", fontproperties=MUSIC, fontsize=48, ha="left", va="center")
    for t, yy in (("4", y0 + 3 * S), ("4", y0 + S)):
        ax.text(x0 + 125, yy, t, ha="center", va="center", fontsize=19, fontweight="bold", family="DejaVu Serif")
    bars = [x0 + 150, x0 + 590, x0 + 1050, x1]
    ax.plot([x0, x0], [y0, y0 + 4 * S], color="black", lw=1.1)
    for b in bars[1:]:
        ax.plot([b, b], [y0, y0 + 4 * S], color="black", lw=1.3)

    def note(x, step, kind):
        y = y0 + step * S / 2
        hollow = kind in ("half", "whole")
        ax.add_patch(Ellipse((x, y), 46, 31, angle=20, fc="white" if hollow else "black", ec="black", lw=1.6, zorder=4))
        if kind == "whole":
            return
        up = step < 4
        sx = x + 21 if up else x - 21
        sy = y + 118 if up else y - 118
        ax.plot([sx, sx], [y, sy], color="black", lw=1.6, zorder=4)
        if kind == "eighth":
            d = -1 if up else 1
            ax.fill([sx, sx + 34, sx + 30, sx], [sy, sy + d * 44, sy + d * 58, sy + d * 26], color="black", lw=0, zorder=4)

    # 1마디: 4분음표 4개 / 2마디: 2분음표, 8분음표, ㉠ / 3마디: 온음표
    for x, st in zip((x0 + 215, x0 + 320, x0 + 425, x0 + 530), (0, 2, 5, 2)):
        note(x, st, "quarter")
    note(x0 + 665, 6, "half")
    note(x0 + 830, 4, "eighth")
    ax.add_patch(Rectangle((x0 + 900, y0 - 16), 112, 4 * S + 32, fc="white", ec="black", lw=1.4, zorder=5))
    ax.text(x0 + 956, y0 + 2 * S, "㉠", ha="center", va="center", fontsize=20, zorder=6)
    note(x0 + 1180, 5, "whole")
    for x, ch in ((x0 + 215, "C"), (x0 + 665, "G"), (x0 + 1180, "C")):
        ax.text(x, y0 + 4 * S + 62, ch, ha="center", va="center", fontsize=17, fontweight="bold", family="DejaVu Sans")
    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)


def guitar_icon(size):
    dpi = 200
    fig = plt.figure(figsize=(size / dpi, size / dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-1, 1)
    ax.set_ylim(-1, 1)
    ax.axis("off")
    ax.set_aspect("equal")
    fig.patch.set_facecolor("white")
    rot = matplotlib.transforms.Affine2D().rotate_deg(-40) + ax.transData
    for (cx, cy, r) in ((0, -0.32, 0.42), (0, 0.08, 0.29)):
        c = Circle((cx, cy), r, fc="0.72", ec="black", lw=2.0, zorder=2, transform=rot)
        ax.add_patch(c)
    ax.add_patch(Circle((0, -0.32), 0.40, fc="0.72", ec="none", zorder=3, transform=rot))
    ax.add_patch(Circle((0, 0.08), 0.27, fc="0.72", ec="none", zorder=3, transform=rot))
    ax.add_patch(Circle((0, -0.12), 0.12, fc="black", ec="none", zorder=4, transform=rot))
    ax.add_patch(Rectangle((-0.045, 0.12), 0.09, 0.62, fc="0.2", ec="black", lw=1, zorder=4, transform=rot))
    ax.add_patch(Rectangle((-0.08, 0.72), 0.16, 0.2, fc="0.2", ec="black", lw=1, zorder=4, transform=rot))
    ax.add_patch(Rectangle((-0.12, -0.56), 0.24, 0.05, fc="black", ec="none", zorder=4, transform=rot))
    fig.canvas.draw()
    im = Image.frombuffer("RGBA", fig.canvas.get_width_height(), fig.canvas.buffer_rgba()).convert("RGB")
    plt.close(fig)
    return im


def post():
    frame = Image.open(os.path.join(OUT, "life_post_bot_02p.png")).convert("RGB")
    tmp = os.path.join(OUT, "_life_score_tmp.png")
    score_png(tmp)
    s = Image.open(tmp).convert("RGB")
    frame.paste(s, (68, 400))
    os.remove(tmp)
    # 프로필 원 안을 기타 그림으로 바꾼다
    cx, cy, D = 148, 150, 134
    icon = guitar_icon(D).resize((D, D), Image.LANCZOS)
    mask = Image.new("L", (D * 4, D * 4), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, D * 4 - 1, D * 4 - 1), fill=255)
    frame.paste(icon, (cx - D // 2, cy - D // 2), mask.resize((D, D), Image.LANCZOS))
    frame.save(os.path.join(OUT, "life_q7_post.png"), dpi=(600, 600))
    print("life_q7_post.png w=24094 h=16063")


for f in (caste, omr, post):
    f()
